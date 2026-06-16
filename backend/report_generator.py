"""
AI Financial Report Generator
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Transforms structured Excel/CSV data into professional, client-ready
financial reports and investment commentary.

Workflow:
  1. Ingest Excel/CSV â†’ parse sheets â†’ extract metrics
  2. Detect report type (portfolio, performance, market commentary, etc.)
  3. Run QC checks (missing data, outliers, inconsistencies)
  4. Build structured context payload
  5. Generate narrative sections via LLM
  6. Assemble final report with consistent tone/format

Supported report types:
  - portfolio_summary    : Holdings, allocation, P&L, risk metrics
  - performance_review   : Period returns, benchmark comparison, attribution
  - market_commentary    : Market overview, sector rotation, macro themes
  - client_letter        : Personalised narrative for wealth management clients
  - risk_report          : VaR, drawdown, concentration, stress scenarios
  - custom               : Free-form with user-defined sections
"""

import io
import json
import re
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from llm_factory import generate_response, PROMPTS, format_prompt
from langfuse import observe as traceable

# â”€â”€ Constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

REPORT_TYPES = {
    "portfolio_summary": "Portfolio Summary Report",
    "performance_review": "Performance Review Report",
    "market_commentary": "Market Commentary",
    "client_letter": "Client Investment Letter",
    "risk_report": "Risk & Compliance Report",
    "custom": "Custom Financial Report",
}

# Expected column keyword sets per report type.
# At least one keyword from the set must appear in the data columns for the
# data to be considered a reasonable match.  Multiple keyword groups are
# checked independently so partial matches still score points.
_REPORT_TYPE_EXPECTED_COLUMNS: Dict[str, List[set]] = {
    "portfolio_summary": [
        {"market_value", "value", "nav", "aum", "portfolio_value"},
        {"weight", "allocation", "weight_pct"},
        {"ticker", "symbol", "asset", "security", "holding", "stock"},
        {"return", "pnl", "gain", "gain_loss", "profit"},
    ],
    "performance_review": [
        {"return", "total_return", "pnl", "gain", "gain_loss", "performance"},
        {"benchmark", "index", "alpha", "beta"},
        {"period", "date", "month", "quarter", "year"},
    ],
    "market_commentary": [
        {"price", "close", "open", "high", "low"},
        {"return", "change", "pct_change"},
        {"index", "sector", "market", "asset_class"},
    ],
    "client_letter": [
        {"value", "market_value", "nav", "portfolio_value", "aum"},
        {"return", "pnl", "gain", "performance"},
        {"ticker", "symbol", "asset", "holding"},
    ],
    "risk_report": [
        {"volatility", "vol", "std_dev", "standard_deviation"},
        {"drawdown", "max_drawdown", "var", "value_at_risk"},
        {"beta", "correlation", "sharpe", "risk"},
    ],
    "custom": [],  # no validation for custom â€” accept anything
}

# Columns that are almost certainly monetary â€” used for currency detection
_MONEY_KEYWORDS = {
    "value", "amount", "price", "cost", "gain", "loss", "pnl", "p&l",
    "revenue", "income", "expense", "fee", "nav", "aum", "market_value",
    "book_value", "unrealized", "realized", "dividend", "interest",
}

# Columns that are almost certainly percentages
_PCT_KEYWORDS = {
    "return", "yield", "rate", "pct", "percent", "weight", "allocation",
    "change", "growth", "drawdown", "volatility", "beta", "alpha",
}

# â”€â”€ Excel / CSV Ingestion â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def ingest_excel(file_bytes: bytes, filename: str) -> Dict[str, pd.DataFrame]:
    """
    Parse an Excel (.xlsx/.xls) or CSV file into a dict of DataFrames.
    Keys are sheet names (or 'Sheet1' for CSV).
    """
    ext = filename.lower().rsplit(".", 1)[-1]
    sheets: Dict[str, pd.DataFrame] = {}

    try:
        if ext in ("xlsx", "xls", "xlsm"):
            xl = pd.ExcelFile(io.BytesIO(file_bytes))
            for sheet in xl.sheet_names:
                df = xl.parse(sheet, header=0)
                df = _clean_dataframe(df)
                if not df.empty:
                    sheets[sheet] = df
        elif ext == "csv":
            df = pd.read_csv(io.BytesIO(file_bytes))
            df = _clean_dataframe(df)
            sheets["Sheet1"] = df
        else:
            raise ValueError(f"Unsupported file type: .{ext}. Use .xlsx, .xls, or .csv")
    except Exception as e:
        raise ValueError(f"Failed to parse file '{filename}': {e}")

    if not sheets:
        raise ValueError("No usable data found in the uploaded file.")

    return sheets


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise column names, drop fully-empty rows/cols, coerce numeric types."""
    # Drop completely empty rows and columns
    df = df.dropna(how="all").dropna(axis=1, how="all")
    if df.empty:
        return df

    # Normalise column names: lowercase, strip, replace spaces with underscores
    df.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_").replace("/", "_")
        for c in df.columns
    ]

    # Coerce numeric columns
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col], errors="ignore")
        except Exception:
            pass

    # Parse date columns
    for col in df.columns:
        if any(kw in col for kw in ("date", "period", "month", "year", "as_of")):
            try:
                df[col] = pd.to_datetime(df[col], errors="ignore")
            except Exception:
                pass

    return df.reset_index(drop=True)


# â”€â”€ QC & Validation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def run_qc_checks(sheets: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """
    Inspect all sheets for data quality issues.
    Returns a structured QC report with warnings and errors.
    """
    qc: Dict[str, Any] = {
        "passed": True,
        "warnings": [],
        "errors": [],
        "sheet_summaries": {},
    }

    for sheet_name, df in sheets.items():
        summary: Dict[str, Any] = {
            "rows": len(df),
            "columns": list(df.columns),
            "missing_pct": {},
            "numeric_columns": [],
            "date_columns": [],
            "outliers": {},
        }

        # Missing data
        for col in df.columns:
            missing_pct = df[col].isna().mean() * 100
            if missing_pct > 0:
                summary["missing_pct"][col] = round(missing_pct, 1)
                if missing_pct > 50:
                    qc["warnings"].append(
                        f"Sheet '{sheet_name}', column '{col}': {missing_pct:.0f}% missing values"
                    )

        # Numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        summary["numeric_columns"] = numeric_cols

        # Date columns
        date_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()
        summary["date_columns"] = date_cols

        # Outlier detection (IQR method) for numeric columns
        for col in numeric_cols:
            series = df[col].dropna()
            if len(series) < 4:
                continue
            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            outlier_mask = (series < q1 - 3 * iqr) | (series > q3 + 3 * iqr)
            n_outliers = outlier_mask.sum()
            if n_outliers > 0:
                summary["outliers"][col] = int(n_outliers)
                qc["warnings"].append(
                    f"Sheet '{sheet_name}', column '{col}': {n_outliers} statistical outlier(s) detected"
                )

        # Check for duplicate rows
        n_dupes = df.duplicated().sum()
        if n_dupes > 0:
            qc["warnings"].append(
                f"Sheet '{sheet_name}': {n_dupes} duplicate row(s) found"
            )

        # Check for negative values in columns that should be positive
        for col in numeric_cols:
            col_lower = col.lower()
            if any(kw in col_lower for kw in ("price", "nav", "aum", "market_value")):
                n_neg = (df[col] < 0).sum()
                if n_neg > 0:
                    qc["errors"].append(
                        f"Sheet '{sheet_name}', column '{col}': {n_neg} unexpected negative value(s)"
                    )
                    qc["passed"] = False

        qc["sheet_summaries"][sheet_name] = summary

    return qc


# â”€â”€ Metric Extraction â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def extract_metrics(sheets: Dict[str, pd.DataFrame], report_type: str) -> Dict[str, Any]:
    """
    Extract key financial metrics from parsed sheets.
    Returns a structured dict ready to be injected into LLM prompts.
    """
    metrics: Dict[str, Any] = {
        "report_type": report_type,
        "sheets": {},
        "summary_stats": {},
        "detected_currency": "USD",
        "as_of_date": None,
    }

    # Detect currency from column names or values
    metrics["detected_currency"] = _detect_currency(sheets)

    # Detect as-of date
    metrics["as_of_date"] = _detect_as_of_date(sheets)

    for sheet_name, df in sheets.items():
        sheet_metrics: Dict[str, Any] = {
            "row_count": len(df),
            "columns": list(df.columns),
            "data_preview": _safe_preview(df, n=10),
            "numeric_summary": {},
            "totals": {},
        }

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

        # Summary statistics for numeric columns
        for col in numeric_cols:
            series = df[col].dropna()
            if len(series) == 0:
                continue
            sheet_metrics["numeric_summary"][col] = {
                "count": int(len(series)),
                "sum": _safe_float(series.sum()),
                "mean": _safe_float(series.mean()),
                "median": _safe_float(series.median()),
                "min": _safe_float(series.min()),
                "max": _safe_float(series.max()),
                "std": _safe_float(series.std()),
            }

        # Detect and compute totals for money/value columns
        for col in numeric_cols:
            col_lower = col.lower()
            if any(kw in col_lower for kw in _MONEY_KEYWORDS):
                total = df[col].sum()
                sheet_metrics["totals"][col] = _safe_float(total)

        metrics["sheets"][sheet_name] = sheet_metrics

    # Cross-sheet summary stats
    metrics["summary_stats"] = _compute_summary_stats(sheets, report_type)

    return metrics


def _detect_currency(sheets: Dict[str, pd.DataFrame]) -> str:
    """Heuristic: look for currency symbols or column name hints."""
    currency_hints = {
        "â‚¹": "INR", "inr": "INR", "rupee": "INR",
        "Â£": "GBP", "gbp": "GBP", "sterling": "GBP",
        "â‚¬": "EUR", "eur": "EUR", "euro": "EUR",
        "Â¥": "JPY", "jpy": "JPY", "yen": "JPY",
        "$": "USD", "usd": "USD", "dollar": "USD",
    }
    for df in sheets.values():
        for col in df.columns:
            col_lower = col.lower()
            for hint, currency in currency_hints.items():
                if hint in col_lower:
                    return currency
        # Check string values in first few rows
        for col in df.select_dtypes(include="object").columns:
            sample = df[col].dropna().head(5).astype(str)
            for val in sample:
                for hint, currency in currency_hints.items():
                    if hint in val.lower():
                        return currency
    return "USD"


def _detect_as_of_date(sheets: Dict[str, pd.DataFrame]) -> Optional[str]:
    """Try to find the most recent date in the data."""
    latest: Optional[datetime] = None
    for df in sheets.values():
        for col in df.select_dtypes(include=["datetime64"]).columns:
            col_max = df[col].max()
            if pd.notna(col_max):
                if latest is None or col_max > latest:
                    latest = col_max
    return latest.strftime("%Y-%m-%d") if latest else None


def _compute_summary_stats(
    sheets: Dict[str, pd.DataFrame], report_type: str
) -> Dict[str, Any]:
    """Compute high-level summary statistics relevant to the report type."""
    stats: Dict[str, Any] = {}

    # Combine all numeric data for aggregate stats
    all_numeric: Dict[str, List[float]] = {}
    for df in sheets.values():
        for col in df.select_dtypes(include=[np.number]).columns:
            key = col.lower()
            if key not in all_numeric:
                all_numeric[key] = []
            all_numeric[key].extend(df[col].dropna().tolist())

    # Portfolio-specific aggregations
    if report_type in ("portfolio_summary", "performance_review", "client_letter"):
        for key in ("market_value", "value", "amount", "nav"):
            if key in all_numeric:
                stats["total_aum"] = _safe_float(sum(all_numeric[key]))
                break

        for key in ("return", "total_return", "pnl", "gain_loss"):
            if key in all_numeric:
                vals = all_numeric[key]
                stats["avg_return"] = _safe_float(sum(vals) / len(vals))
                stats["best_return"] = _safe_float(max(vals))
                stats["worst_return"] = _safe_float(min(vals))
                break

        for key in ("weight", "allocation", "weight_pct"):
            if key in all_numeric:
                stats["total_weight"] = _safe_float(sum(all_numeric[key]))
                break

    # Risk-specific aggregations
    if report_type == "risk_report":
        for key in ("volatility", "std_dev", "vol"):
            if key in all_numeric:
                stats["avg_volatility"] = _safe_float(
                    sum(all_numeric[key]) / len(all_numeric[key])
                )
                break
        for key in ("drawdown", "max_drawdown"):
            if key in all_numeric:
                stats["max_drawdown"] = _safe_float(min(all_numeric[key]))
                break

    return stats


def _safe_preview(df: pd.DataFrame, n: int = 10) -> List[Dict]:
    """Return first n rows as a list of dicts, with NaN replaced by None."""
    preview = df.head(n).copy()
    # Convert datetime columns to strings
    for col in preview.select_dtypes(include=["datetime64"]).columns:
        preview[col] = preview[col].dt.strftime("%Y-%m-%d")
    return json.loads(preview.to_json(orient="records", default_handler=str))


def _safe_float(val: Any) -> Optional[float]:
    """Convert to float, return None if not possible."""
    try:
        f = float(val)
        return None if (np.isnan(f) or np.isinf(f)) else round(f, 4)
    except (TypeError, ValueError):
        return None


# â”€â”€ Report Generation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def generate_report(
    metrics: Dict[str, Any],
    qc_result: Dict[str, Any],
    report_type: str,
    firm_name: str = "Our Firm",
    client_name: str = "Valued Client",
    report_period: str = "",
    custom_instructions: str = "",
    tone: str = "professional",
) -> Dict[str, Any]:
    """
    Generate a structured narrative report from extracted metrics.

    Returns:
        {
            "report_type": str,
            "title": str,
            "generated_at": str,
            "sections": [{"heading": str, "content": str}, ...],
            "executive_summary": str,
            "qc_warnings": list,
            "metadata": dict
        }
    """
    report_title = REPORT_TYPES.get(report_type, "Financial Report")
    if report_period:
        report_title = f"{report_title} â€” {report_period}"

    # Build the context payload for the LLM
    context = _build_llm_context(
        metrics=metrics,
        qc_result=qc_result,
        report_type=report_type,
        firm_name=firm_name,
        client_name=client_name,
        report_period=report_period,
        custom_instructions=custom_instructions,
        tone=tone,
    )

    # Generate each section
    sections = _generate_sections(context, report_type)

    # Generate executive summary
    exec_summary = _generate_executive_summary(sections, context)

    return {
        "report_type": report_type,
        "title": report_title,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "firm_name": firm_name,
        "client_name": client_name,
        "report_period": report_period,
        "currency": metrics.get("detected_currency", "USD"),
        "as_of_date": metrics.get("as_of_date"),
        "executive_summary": exec_summary,
        "sections": sections,
        "qc_warnings": qc_result.get("warnings", []),
        "qc_errors": qc_result.get("errors", []),
        "qc_passed": qc_result.get("passed", True),
        "metadata": {
            "sheets_processed": list(metrics.get("sheets", {}).keys()),
            "summary_stats": metrics.get("summary_stats", {}),
            "tone": tone,
        },
    }


def _build_llm_context(
    metrics: Dict[str, Any],
    qc_result: Dict[str, Any],
    report_type: str,
    firm_name: str,
    client_name: str,
    report_period: str,
    custom_instructions: str,
    tone: str,
) -> Dict[str, Any]:
    """Assemble the full context dict passed to every LLM prompt."""
    # Compact the metrics to avoid token overflow â€” keep summaries, not raw rows
    compact_metrics: Dict[str, Any] = {
        "report_type": report_type,
        "detected_currency": metrics.get("detected_currency", "USD"),
        "as_of_date": metrics.get("as_of_date"),
        "summary_stats": metrics.get("summary_stats", {}),
        "sheets": {},
    }
    for sheet_name, sheet_data in metrics.get("sheets", {}).items():
        compact_metrics["sheets"][sheet_name] = {
            "row_count": sheet_data.get("row_count", 0),
            "columns": sheet_data.get("columns", []),
            "numeric_summary": sheet_data.get("numeric_summary", {}),
            "totals": sheet_data.get("totals", {}),
            "data_preview": sheet_data.get("data_preview", [])[:5],  # first 5 rows only
        }

    return {
        "firm_name": firm_name,
        "client_name": client_name,
        "report_period": report_period or "Current Period",
        "report_type": report_type,
        "tone": tone,
        "custom_instructions": custom_instructions,
        "metrics": compact_metrics,
        "qc_warnings": qc_result.get("warnings", []),
        "qc_errors": qc_result.get("errors", []),
    }


def _generate_sections(
    context: Dict[str, Any], report_type: str
) -> List[Dict[str, str]]:
    """Generate each narrative section using the appropriate LLM prompt."""
    section_configs = _get_section_configs(report_type)
    sections: List[Dict[str, str]] = []

    for section in section_configs:
        prompt_key = section["prompt_key"]
        heading = section["heading"]

        # Build the section-specific prompt
        prompt_template = PROMPTS.get(prompt_key, PROMPTS.get("report_generic_section_prompt", ""))
        if not prompt_template:
            continue

        prompt = format_prompt(
            prompt_template,
            section_heading=heading,
            context_json=json.dumps(context, indent=2, default=str),
            firm_name=context["firm_name"],
            client_name=context["client_name"],
            report_period=context["report_period"],
            tone=context["tone"],
            custom_instructions=context.get("custom_instructions", ""),
        )

        try:
            content = generate_response(prompt)
            # Strip any accidental markdown fences
            content = _strip_markdown_fences(content)
            sections.append({"heading": heading, "content": content.strip()})
        except Exception as e:
            sections.append({
                "heading": heading,
                "content": f"[Section generation failed: {e}]",
            })

    return sections


def _generate_executive_summary(
    sections: List[Dict[str, str]], context: Dict[str, Any]
) -> str:
    """Generate a concise executive summary from all sections."""
    sections_text = "\n\n".join(
        f"## {s['heading']}\n{s['content']}" for s in sections
    )

    prompt_template = PROMPTS.get("report_executive_summary_prompt", "")
    if not prompt_template:
        return "Executive summary not available."

    prompt = format_prompt(
        prompt_template,
        sections_text=sections_text,
        firm_name=context["firm_name"],
        client_name=context["client_name"],
        report_period=context["report_period"],
        tone=context["tone"],
        context_json=json.dumps(context.get("metrics", {}), indent=2, default=str),
    )

    try:
        summary = generate_response(prompt)
        return _strip_markdown_fences(summary).strip()
    except Exception as e:
        return f"[Executive summary generation failed: {e}]"


def _get_section_configs(report_type: str) -> List[Dict[str, str]]:
    """Return the ordered list of sections for each report type."""
    configs = {
        "portfolio_summary": [
            {"heading": "Portfolio Overview", "prompt_key": "report_portfolio_overview_prompt"},
            {"heading": "Asset Allocation", "prompt_key": "report_asset_allocation_prompt"},
            {"heading": "Top Holdings", "prompt_key": "report_top_holdings_prompt"},
            {"heading": "Performance Summary", "prompt_key": "report_performance_summary_prompt"},
            {"heading": "Risk Metrics", "prompt_key": "report_risk_metrics_prompt"},
            {"heading": "Outlook & Recommendations", "prompt_key": "report_outlook_prompt"},
        ],
        "performance_review": [
            {"heading": "Period Performance", "prompt_key": "report_period_performance_prompt"},
            {"heading": "Benchmark Comparison", "prompt_key": "report_benchmark_prompt"},
            {"heading": "Attribution Analysis", "prompt_key": "report_attribution_prompt"},
            {"heading": "Top Contributors & Detractors", "prompt_key": "report_contributors_prompt"},
            {"heading": "Forward Outlook", "prompt_key": "report_outlook_prompt"},
        ],
        "market_commentary": [
            {"heading": "Market Overview", "prompt_key": "report_market_overview_prompt"},
            {"heading": "Sector & Asset Class Review", "prompt_key": "report_sector_review_prompt"},
            {"heading": "Macro & Economic Themes", "prompt_key": "report_macro_themes_prompt"},
            {"heading": "Investment Implications", "prompt_key": "report_investment_implications_prompt"},
        ],
        "client_letter": [
            {"heading": "Dear Client", "prompt_key": "report_client_greeting_prompt"},
            {"heading": "Portfolio Update", "prompt_key": "report_portfolio_overview_prompt"},
            {"heading": "Market Context", "prompt_key": "report_market_overview_prompt"},
            {"heading": "What We Are Doing", "prompt_key": "report_outlook_prompt"},
            {"heading": "Closing Remarks", "prompt_key": "report_client_closing_prompt"},
        ],
        "risk_report": [
            {"heading": "Risk Summary", "prompt_key": "report_risk_summary_prompt"},
            {"heading": "Concentration Risk", "prompt_key": "report_concentration_risk_prompt"},
            {"heading": "Drawdown & Volatility Analysis", "prompt_key": "report_drawdown_prompt"},
            {"heading": "Stress Scenarios", "prompt_key": "report_stress_scenarios_prompt"},
            {"heading": "Risk Mitigation Recommendations", "prompt_key": "report_risk_mitigation_prompt"},
        ],
        "custom": [
            {"heading": "Analysis", "prompt_key": "report_generic_section_prompt"},
            {"heading": "Key Findings", "prompt_key": "report_generic_section_prompt"},
            {"heading": "Recommendations", "prompt_key": "report_generic_section_prompt"},
        ],
    }
    return configs.get(report_type, configs["custom"])


def _strip_markdown_fences(text: str) -> str:
    """Remove ```markdown``` or ``` fences that LLMs sometimes add."""
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text.strip())
    text = re.sub(r"\n?```$", "", text.strip())
    return text


def _check_data_report_type_fit(
    sheets: Dict[str, pd.DataFrame], report_type: str
) -> List[str]:
    """
    Check whether the uploaded data columns are a reasonable match for the
    selected report type.

    Strategy:
      - For each keyword group defined in _REPORT_TYPE_EXPECTED_COLUMNS,
        check whether at least one keyword appears anywhere in the combined
        set of column names across all sheets.
      - A "match" for a group means at least one keyword hit.
      - Score = matched_groups / total_groups.
      - Score < 0.25  â†’ strong mismatch warning (no groups matched at all)
      - Score < 0.50  â†’ partial mismatch warning (fewer than half matched)
      - Score >= 0.50 â†’ data looks reasonable, no warning

    Returns a list of warning strings (empty if data looks fine).
    """
    keyword_groups = _REPORT_TYPE_EXPECTED_COLUMNS.get(report_type, [])

    # custom report type â€” skip validation entirely
    if not keyword_groups:
        return []

    # Collect all column names across every sheet (lowercased)
    all_cols: set = set()
    for df in sheets.values():
        all_cols.update(col.lower() for col in df.columns)

    matched_groups: List[set] = []
    unmatched_groups: List[set] = []

    for group in keyword_groups:
        if group & all_cols:          # at least one keyword from the group found
            matched_groups.append(group)
        else:
            unmatched_groups.append(group)

    total = len(keyword_groups)
    score = len(matched_groups) / total

    warnings: List[str] = []

    if score == 0.0:
        # No expected columns found at all â€” very likely a wrong file
        expected_sample = ", ".join(
            sorted(kw for g in keyword_groups for kw in list(g)[:2])[:10]
        )
        warnings.append(
            f"Data mismatch: none of the expected columns for "
            f"'{REPORT_TYPES[report_type]}' were found in the uploaded file. "
            f"Expected columns such as: {expected_sample}. "
            f"The generated report may contain estimated or placeholder content."
        )
    elif score < 0.5:
        # Partial match â€” some relevant columns present but key ones missing
        missing_sample = ", ".join(
            sorted(kw for g in unmatched_groups for kw in list(g)[:1])
        )
        warnings.append(
            f"Partial data match for '{REPORT_TYPES[report_type]}': "
            f"{len(matched_groups)}/{total} expected column groups found. "
            f"Missing data for: {missing_sample}. "
            f"Some report sections may have limited detail."
        )

    return warnings


# â”€â”€ Public Entry Point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@traceable(name="run-report-generator", as_type="chain")
def run_report_generator(
    file_bytes: bytes,
    filename: str,
    report_type: str = "portfolio_summary",
    firm_name: str = "Our Firm",
    client_name: str = "Valued Client",
    report_period: str = "",
    custom_instructions: str = "",
    tone: str = "professional",
) -> Dict[str, Any]:
    """
    Main entry point called by the FastAPI endpoint.

    Args:
        file_bytes:           Raw bytes of the uploaded Excel/CSV file
        filename:             Original filename (used for extension detection)
        report_type:          One of REPORT_TYPES keys
        firm_name:            Wealth management firm name
        client_name:          Client name for personalised reports
        report_period:        e.g. "Q1 2026", "January 2026"
        custom_instructions:  Additional instructions to guide the LLM
        tone:                 "professional" | "conversational" | "formal"

    Returns:
        Full report dict (see generate_report docstring)
    """
    if report_type not in REPORT_TYPES:
        raise ValueError(
            f"Invalid report_type '{report_type}'. "
            f"Choose from: {', '.join(REPORT_TYPES.keys())}"
        )

    # Step 1: Ingest
    sheets = ingest_excel(file_bytes, filename)

    # Step 2: QC
    qc_result = run_qc_checks(sheets)

    # Step 2.5: Validate data relevance for the selected report type
    mismatch_warnings = _check_data_report_type_fit(sheets, report_type)
    if mismatch_warnings:
        # Prepend so the mismatch notice is the first thing the user sees
        qc_result["warnings"] = mismatch_warnings + qc_result["warnings"]
        # A complete mismatch (score == 0) is treated as a QC failure so the
        # UI badge turns red and the user is clearly alerted.
        if any("Data mismatch:" in w for w in mismatch_warnings):
            qc_result["passed"] = False
            qc_result["errors"] = [mismatch_warnings[0]] + qc_result.get("errors", [])

    # Step 3: Extract metrics
    metrics = extract_metrics(sheets, report_type)

    # Step 4: Generate report
    report = generate_report(
        metrics=metrics,
        qc_result=qc_result,
        report_type=report_type,
        firm_name=firm_name,
        client_name=client_name,
        report_period=report_period,
        custom_instructions=custom_instructions,
        tone=tone,
    )

    return report
