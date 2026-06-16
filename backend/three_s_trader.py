"""
3S-Trader: Multi-LLM Framework for Adaptive Stock Scoring, Strategy, and Selection
Based on the paper: "3S-Trader: A Multi-LLM Framework for Adaptive Stock Scoring,
Strategy, and Selection in Portfolio Optimization"

Architecture:
1. Data Analysis Stage: News Agent, Fundamental Agent, Technical Agent
2. Stock Scoring: Score Agent evaluates stocks across 6 dimensions
3. Stock Selection: Selector Agent constructs portfolio based on strategy
4. Strategy Iteration: Strategy Agent refines selection strategy
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import numpy as np
from llm_factory import generate_response
import json
import re


# ═══════════════════════════════════════════════════════════════════════════
# AGENT PROMPTS
# ═══════════════════════════════════════════════════════════════════════════

NEWS_AGENT_PROMPT = """You are a financial news analysis agent. Your task is to filter and summarize news related to the stock {stock_code}.

The news content below includes summaries or full articles from the past week:
{news_content}

Please provide a concise and insightful weekly summary of the stock's recent news. Your output will be used to help a downstream stock selection agent make informed weekly investment decisions.

Focus on:
- Key events and announcements
- Market sentiment and investor perception
- Any significant developments affecting the company

Keep your summary concise (2-3 short sentences max)."""

TECHNICAL_AGENT_PROMPT = """You are a stock price analysis agent. Your task is to analyze the recent technical indicators and price data of the stock {stock_code}.

Below is the stock's recent price and technical indicator data from the past 4 weeks:
{technical_text}

Please provide a summary of the stock's recent performance. Your output will be used to help a downstream stock selection agent make informed weekly investment decisions.

Focus on:
- Recent price trends, strength, and consistency
- Key technical indicator signals (SMA, RSI, MACD, Bollinger Bands, ATR)
- Notable improvements or warning signs

Keep your summary concise (2-3 short sentences max)."""

FUNDAMENTAL_AGENT_PROMPT = """You are a stock fundamentals analysis agent. Your task is to analyze the recent financial performance of the stock {stock_code} based on its past 4 quarterly reports.

Below is the stock's recent financial data, including 4 quarters of: Income statements, Balance sheets, Cash flow statements:
{fundamental_text}

Please provide a summary of the stock's recent fundamental trends. You may consider trends in revenue, profit, expenses, margins, cash flow, and balance sheet strength, as well as any notable improvements or warning signs.

Your output will be used to help a downstream stock selection agent make informed weekly investment decisions.

Keep your summary concise (2-3 short sentences max)."""

SCORE_AGENT_PROMPT = """You are an expert stock evaluation assistant. Tasked with assessing each stock using three input types: News summary, Fundamental analysis, and Recent price behavior.

From these inputs, evaluate the stock along six scoring dimensions. For each dimension: provide a score from 1 to 10, and give a brief justification (1–2 short sentences max).

Use all information provided below. If anything is missing, score conservatively and state that in the reason.

**Stock**: {stock_code}

**News Summary**: {news_summary}
**Fundamental Analysis**: {fundamental_analysis}
**Price and Technical Analysis**: {technical_analysis}

---

From these inputs, evaluate the stock along the following six scoring dimensions:

1. **Financial Health**: Evaluates a company's current financial stability. A higher score reflects stronger fundamentals and lower short-term risk.

2. **Growth Potential**: Assesses the company's future expansion capacity based on investment plans, and industry growth outlook. A higher score suggests stronger long-term earnings potential.

3. **News Sentiment**: Reflects overall sentiment polarity extracted from recent news articles. A higher score implies more positive news coverage and investor perception.

4. **News Impact**: Assesses the breadth and duration of news influence. Higher scores reflect more sustained impacts, e.g., from political events or industry-level shifts.

5. **Price Momentum**: Captures recent upward or downward trends in stock price movement. A higher score reflects a stronger and more consistent upward price trend.

6. **Volatility Risk**: Quantifies the level of recent price fluctuations, indicating risk exposure. A higher score represents higher volatility and less stable price behavior.

---

Return ONLY a valid JSON object (no markdown, no explanation) with this structure:

{{
  "stock": "{stock_code}",
  "financial_health": {{"score": 1-10, "reason": "..."}},
  "growth_potential": {{"score": 1-10, "reason": "..."}},
  "news_sentiment": {{"score": 1-10, "reason": "..."}},
  "news_impact": {{"score": 1-10, "reason": "..."}},
  "price_momentum": {{"score": 1-10, "reason": "..."}},
  "volatility_risk": {{"score": 1-10, "reason": "..."}}
}}"""

SELECTOR_AGENT_PROMPT = """As an experienced stock-picking expert, your task is to construct a prudent and strategically aligned portfolio for **next week's holding period**.

You are provided with two sources of information:

1. **Score reports for various stocks**. Each report includes metrics from technical indicators, fundamentals, and market news.

2. **A recommended strategy** for the upcoming period. This strategy reflects performance trends and current market conditions.

---

**Score Reports**:
{score_reports}

---

**Recommended Strategy**:
{strategy}

---

Using these inputs, select the most suitable stocks that align with the recommended strategy. Allocate a total portfolio weight of less than 100% if you believe partial investment is more appropriate.

**Output Guidelines**:
- A step-by-step reasoning process showing how you evaluated and compared the candidates.
- Explain how you interpreted the strategy, which score dimensions you emphasized, and why each stock was chosen.
- "Explanation" should show how you evaluated and compared the candidates, and why each stock was chosen.

Return ONLY a valid JSON object (no markdown, no explanation) with this structure:

{{
  "selected_stocks": [
    {{"stock_code": "TICKER", "weight": 0.25}},
    {{"stock_code": "TICKER", "weight": 0.20}}
  ],
  "reasoning": "Explanation of how you evaluated and compared the candidates."
}}

**Output Guidelines**:
- Select up to 5 stocks
- Allocate a total portfolio weight ≤ 100% (≤ 1.0)
- At most 5 elements should have non-zero weight
- Provide clear reasoning for your selections"""

STRATEGY_AGENT_PROMPT = """You are a strategic investment advisor tasked with refining portfolio strategies based on historical performance and current market signals. Your inputs include:

1. **Recent Strategy History**
A list of the past {history_length} weeks' portfolio strategies, their observed returns, and the average return of the candidate stock universe. This provides insight into how past strategies and returns relate to the broader market.

{strategy_history}

---

2. **Last Week's Selection Result**
Information on last week's candidate stock pool, including each stock's price change and multi-dimensional scoring report. Also includes the selected stocks, their weights, and the portfolio return.

{last_week_result}

---

**Your task is to analyze the past performance of different strategies and provide a refined, data-driven strategy recommendation** for the upcoming week.

- You may consider the following:
  - Examine whether high- or low-return stocks from last week share common characteristics in the score report.
  - Analyze whether past strategies consistently yielded high or low returns.
  - If the current strategy has shown stable outperformance over time, it is reasonable to maintain it.
  - If recent strategies have generally underperformed, consider generating a focused strategy that emphasizes only one specific aspect, such as news sentiment, fundamentals, or technical indicators.

**Market Outlook**: {market_outlook}

---

Return ONLY a valid JSON object (no markdown, no explanation) with this structure:

{{
  "strategy": "Detailed strategy description for next week",
  "reasoning": "Brief explanation of why this strategy was chosen based on historical performance"
}}

The strategy should be a clear, actionable description that specifies which types of stocks should be preferred, guiding the Selector Agent to prioritize stocks with higher scores in the relevant dimensions."""


# ═══════════════════════════════════════════════════════════════════════════
# DATA COLLECTION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def fetch_price_and_indicators(ticker: str, weeks: int = 4) -> str:
    """
    Fetch daily stock prices and technical indicators for the past N weeks.
    Returns formatted text for the Technical Agent.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=weeks)
        
        df = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)
        
        if df.empty:
            print(f"[3S-Trader] WARNING: yfinance returned empty DataFrame for {ticker}")
            return f"No price data available for {ticker}"
        
        # Flatten multi-level columns (yfinance >= 0.2.x returns MultiIndex columns)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # Verify required columns exist after flattening
        required_cols = ['Close', 'High', 'Low']
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            print(f"[3S-Trader] WARNING: Missing columns {missing} for {ticker}. Available: {list(df.columns)}")
            return f"Error fetching price data for {ticker}: missing columns {missing}"
        
        print(f"[3S-Trader] Fetched {len(df)} rows of price data for {ticker} ({start_date.date()} to {end_date.date()})")
        
        # Calculate technical indicators
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        
        # RSI
        delta = df['Close'].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        # Bollinger Bands
        df['BB_Middle'] = df['Close'].rolling(window=20).mean()
        bb_std = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
        df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
        
        # ATR
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['ATR'] = true_range.rolling(14).mean()
        
        # Format output
        output_lines = []
        for date, row in df.tail(20).iterrows():
            date_str = date.strftime('%Y-%m-%d')
            output_lines.append(
                f"{date_str}: Close={row['Close']:.2f}, "
                f"SMA20={row['SMA_20']:.2f}, SMA50={row['SMA_50']:.2f}, "
                f"RSI={row['RSI']:.2f}, MACD={row['MACD']:.2f}, "
                f"BB_Upper={row['BB_Upper']:.2f}, BB_Lower={row['BB_Lower']:.2f}, "
                f"ATR={row['ATR']:.2f}"
            )
        
        return "\n".join(output_lines)
    
    except Exception as e:
        import traceback
        print(f"[3S-Trader] ERROR in fetch_price_and_indicators for {ticker}: {str(e)}")
        print(traceback.format_exc())
        return f"Error fetching price data for {ticker}: {str(e)}"


def fetch_fundamentals(ticker: str) -> str:
    """
    Fetch fundamental data (quarterly reports) for the stock.
    Returns formatted text for the Fundamental Agent.
    """
    try:
        stock = yf.Ticker(ticker)
        
        # Get quarterly financials
        income_stmt = stock.quarterly_income_stmt
        balance_sheet = stock.quarterly_balance_sheet
        cash_flow = stock.quarterly_cashflow
        
        output_lines = ["=== QUARTERLY FINANCIAL DATA ===\n"]
        
        if not income_stmt.empty:
            output_lines.append("Income Statement (Last 4 Quarters):")
            for col in income_stmt.columns[:4]:
                output_lines.append(f"\nQuarter: {col.strftime('%Y-%m-%d')}")
                for idx in ['Total Revenue', 'Gross Profit', 'Operating Income', 'Net Income']:
                    if idx in income_stmt.index:
                        val = income_stmt.loc[idx, col]
                        output_lines.append(f"  {idx}: {val:,.0f}")
        
        if not balance_sheet.empty:
            output_lines.append("\n\nBalance Sheet (Last 4 Quarters):")
            for col in balance_sheet.columns[:4]:
                output_lines.append(f"\nQuarter: {col.strftime('%Y-%m-%d')}")
                for idx in ['Total Assets', 'Total Liabilities Net Minority Interest', 'Stockholders Equity']:
                    if idx in balance_sheet.index:
                        val = balance_sheet.loc[idx, col]
                        output_lines.append(f"  {idx}: {val:,.0f}")
        
        if not cash_flow.empty:
            output_lines.append("\n\nCash Flow (Last 4 Quarters):")
            for col in cash_flow.columns[:4]:
                output_lines.append(f"\nQuarter: {col.strftime('%Y-%m-%d')}")
                for idx in ['Operating Cash Flow', 'Investing Cash Flow', 'Financing Cash Flow']:
                    if idx in cash_flow.index:
                        val = cash_flow.loc[idx, col]
                        output_lines.append(f"  {idx}: {val:,.0f}")
        
        return "\n".join(output_lines)
    
    except Exception as e:
        import traceback
        print(f"[3S-Trader] ERROR in fetch_fundamentals for {ticker}: {str(e)}")
        print(traceback.format_exc())
        return f"Error fetching fundamentals for {ticker}: {str(e)}"


def fetch_news(ticker: str, weeks: int = 1) -> str:
    """
    Fetch recent news for the stock, filtered to the last `weeks` weeks.
    Returns formatted text for the News Agent.
    """
    try:
        stock = yf.Ticker(ticker)
        news = stock.news
        
        if not news:
            print(f"[3S-Trader] WARNING: No news returned by yfinance for {ticker}")
            return f"No recent news available for {ticker}"
        
        print(f"[3S-Trader] Fetched {len(news)} raw news items for {ticker}, filtering to last {weeks} week(s)...")
        
        cutoff_ts = datetime.now().timestamp() - (weeks * 7 * 24 * 3600)
        output_lines = []
        skipped = 0

        for item in news:
            # yfinance >= 0.2.x nests content under 'content' key
            if 'content' in item:
                content = item['content']
                title = content.get('title', 'No title')
                summary = content.get('summary', content.get('description', 'No summary'))
                publisher = content.get('provider', {}).get('displayName', 'Unknown') \
                    if isinstance(content.get('provider'), dict) else content.get('provider', 'Unknown')
                # pubDate is an ISO string like "2025-04-28T14:30:00Z"
                pub_date_str = content.get('pubDate') or content.get('displayTime', '')
                try:
                    from datetime import timezone
                    pub_ts = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00')).timestamp() \
                        if pub_date_str else None
                except Exception:
                    pub_ts = None
            else:
                title = item.get('title', 'No title')
                summary = item.get('summary', 'No summary')
                publisher = item.get('publisher', 'Unknown')
                pub_ts = item.get('providerPublishTime')  # Unix timestamp in old schema

            # Filter out articles older than cutoff
            if pub_ts and pub_ts < cutoff_ts:
                skipped += 1
                continue

            # Format publish date for the LLM context
            if pub_ts:
                pub_label = datetime.fromtimestamp(pub_ts).strftime('%Y-%m-%d %H:%M')
            else:
                pub_label = 'date unknown'

            output_lines.append(f"[{pub_label}] [{publisher}] {title}\n{summary}\n")

            if len(output_lines) >= 10:
                break

        print(f"[3S-Trader] News for {ticker}: {len(output_lines)} recent, {skipped} filtered out as older than {weeks}w")

        if not output_lines:
            return f"No news found for {ticker} in the last {weeks} week(s). Older articles were filtered out."

        return "\n".join(output_lines)
    
    except Exception as e:
        import traceback
        print(f"[3S-Trader] ERROR in fetch_news for {ticker}: {str(e)}")
        print(traceback.format_exc())
        return f"Error fetching news for {ticker}: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════
# AGENT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def news_agent(ticker: str, news_content: str) -> str:
    """News Agent: Analyzes recent market news for a stock."""
    prompt = NEWS_AGENT_PROMPT.format(stock_code=ticker, news_content=news_content)
    return generate_response(prompt, use_search=False)


def technical_agent(ticker: str, technical_text: str) -> str:
    """Technical Agent: Analyzes price and technical indicators."""
    prompt = TECHNICAL_AGENT_PROMPT.format(stock_code=ticker, technical_text=technical_text)
    return generate_response(prompt, use_search=False)


def fundamental_agent(ticker: str, fundamental_text: str) -> str:
    """Fundamental Agent: Analyzes company fundamentals."""
    prompt = FUNDAMENTAL_AGENT_PROMPT.format(stock_code=ticker, fundamental_text=fundamental_text)
    return generate_response(prompt, use_search=False)


def score_agent(ticker: str, news_summary: str, fundamental_analysis: str, technical_analysis: str) -> Dict[str, Any]:
    """
    Score Agent: Evaluates stock across 6 dimensions.
    Returns structured scoring data.
    """
    prompt = SCORE_AGENT_PROMPT.format(
        stock_code=ticker,
        news_summary=news_summary,
        fundamental_analysis=fundamental_analysis,
        technical_analysis=technical_analysis
    )
    
    response = generate_response(prompt, use_search=False)
    
    # Parse JSON response
    try:
        cleaned = re.sub(r"```(?:json)?", "", response).strip().strip("`").strip()
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            raise ValueError("No JSON found in response")
    except Exception as e:
        print(f"Error parsing score agent response: {e}")
        # Return default scores
        return {
            "stock": ticker,
            "financial_health": {"score": 5, "reason": "Unable to parse response"},
            "growth_potential": {"score": 5, "reason": "Unable to parse response"},
            "news_sentiment": {"score": 5, "reason": "Unable to parse response"},
            "news_impact": {"score": 5, "reason": "Unable to parse response"},
            "price_momentum": {"score": 5, "reason": "Unable to parse response"},
            "volatility_risk": {"score": 5, "reason": "Unable to parse response"}
        }


def selector_agent(score_reports: List[Dict], strategy: str) -> Dict[str, Any]:
    """
    Selector Agent: Constructs portfolio based on scores and strategy.
    Returns selected stocks with weights.
    """
    score_reports_text = json.dumps(score_reports, indent=2)
    
    prompt = SELECTOR_AGENT_PROMPT.format(
        score_reports=score_reports_text,
        strategy=strategy
    )
    
    response = generate_response(prompt, use_search=False)
    
    # Parse JSON response
    try:
        cleaned = re.sub(r"```(?:json)?", "", response).strip().strip("`").strip()
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            raise ValueError("No JSON found in response")
    except Exception as e:
        print(f"Error parsing selector agent response: {e}")
        # Return equal weight portfolio
        return {
            "selected_stocks": [{"stock_code": report["stock"], "weight": 1.0/len(score_reports)} 
                               for report in score_reports[:5]],
            "reasoning": "Default equal-weight allocation due to parsing error"
        }


def strategy_agent(
    strategy_history: List[Dict],
    last_week_result: Dict,
    market_outlook: str
) -> Dict[str, str]:
    """
    Strategy Agent: Refines selection strategy based on historical performance.
    Returns updated strategy.
    """
    history_text = json.dumps(strategy_history, indent=2)
    last_week_text = json.dumps(last_week_result, indent=2)
    
    prompt = STRATEGY_AGENT_PROMPT.format(
        history_length=len(strategy_history),
        strategy_history=history_text,
        last_week_result=last_week_text,
        market_outlook=market_outlook
    )
    
    response = generate_response(prompt, use_search=False)
    
    # Parse JSON response
    try:
        cleaned = re.sub(r"```(?:json)?", "", response).strip().strip("`").strip()
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            raise ValueError("No JSON found in response")
    except Exception as e:
        print(f"Error parsing strategy agent response: {e}")
        return {
            "strategy": "Balanced approach focusing on financial health and low volatility",
            "reasoning": "Default strategy due to parsing error"
        }


# ═══════════════════════════════════════════════════════════════════════════
# MAIN 3S-TRADER WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════

def run_3s_trader(
    tickers: List[str],
    initial_strategy: Optional[str] = None,
    strategy_history: Optional[List[Dict]] = None,
    last_week_result: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Main 3S-Trader workflow.
    
    Args:
        tickers: List of stock tickers to analyze
        initial_strategy: Initial selection strategy (optional)
        strategy_history: Historical strategy performance (optional)
        last_week_result: Last week's portfolio result (optional)
    
    Returns:
        Dictionary containing portfolio construction results
    """
    
    # Default initial strategy
    if initial_strategy is None:
        initial_strategy = "Balanced approach: favor financially healthy stocks with positive momentum and moderate volatility"
    
    print(f"\n{'='*80}")
    print("3S-TRADER: Multi-LLM Portfolio Optimization Framework")
    print(f"{'='*80}\n")
    
    # ═══════════════════════════════════════════════════════════════════════
    # STAGE 1: DATA ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════
    
    print("STAGE 1: Data Analysis")
    print("-" * 80)
    
    stock_overviews = []
    
    for ticker in tickers:
        print(f"\nAnalyzing {ticker}...")
        
        # Fetch data
        news_data = fetch_news(ticker)
        technical_data = fetch_price_and_indicators(ticker)
        fundamental_data = fetch_fundamentals(ticker)
        
        # Run analysis agents
        news_summary = news_agent(ticker, news_data)
        technical_summary = technical_agent(ticker, technical_data)
        fundamental_summary = fundamental_agent(ticker, fundamental_data)
        
        stock_overviews.append({
            "ticker": ticker,
            "news_summary": news_summary,
            "technical_summary": technical_summary,
            "fundamental_summary": fundamental_summary
        })
        
        print(f"  ✓ News analysis complete")
        print(f"  ✓ Technical analysis complete")
        print(f"  ✓ Fundamental analysis complete")
    
    # ═══════════════════════════════════════════════════════════════════════
    # STAGE 2: STOCK SCORING
    # ═══════════════════════════════════════════════════════════════════════
    
    print(f"\n{'='*80}")
    print("STAGE 2: Stock Scoring")
    print("-" * 80)
    
    score_reports = []
    
    for overview in stock_overviews:
        print(f"\nScoring {overview['ticker']}...")
        
        scores = score_agent(
            overview['ticker'],
            overview['news_summary'],
            overview['fundamental_summary'],
            overview['technical_summary']
        )
        
        score_reports.append(scores)
        
        print(f"  ✓ Multi-dimensional scoring complete")
    
    # ═══════════════════════════════════════════════════════════════════════
    # STAGE 3: STOCK SELECTION
    # ═══════════════════════════════════════════════════════════════════════
    
    print(f"\n{'='*80}")
    print("STAGE 3: Stock Selection")
    print("-" * 80)
    
    # Use strategy from history or initial strategy
    current_strategy = initial_strategy
    if strategy_history and len(strategy_history) > 0:
        current_strategy = strategy_history[-1].get("strategy", initial_strategy)
    
    print(f"\nCurrent Strategy: {current_strategy}\n")
    
    portfolio = selector_agent(score_reports, current_strategy)
    
    print("Portfolio Construction:")
    for stock in portfolio["selected_stocks"]:
        print(f"  {stock['stock_code']}: {stock['weight']*100:.1f}%")
    
    # ═══════════════════════════════════════════════════════════════════════
    # STAGE 4: STRATEGY ITERATION (if historical data available)
    # ═══════════════════════════════════════════════════════════════════════
    
    new_strategy = None
    if strategy_history and last_week_result:
        print(f"\n{'='*80}")
        print("STAGE 4: Strategy Iteration")
        print("-" * 80)
        
        market_outlook = "The market remains volatile with mixed signals across sectors."
        
        strategy_update = strategy_agent(
            strategy_history[-10:],  # Last 10 weeks
            last_week_result,
            market_outlook
        )
        
        new_strategy = strategy_update["strategy"]
        print(f"\nUpdated Strategy: {new_strategy}")
        print(f"Reasoning: {strategy_update['reasoning']}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # RETURN RESULTS
    # ═══════════════════════════════════════════════════════════════════════
    
    print(f"\n{'='*80}\n")
    
    return {
        "stock_overviews": stock_overviews,
        "score_reports": score_reports,
        "portfolio": portfolio,
        "current_strategy": current_strategy,
        "new_strategy": new_strategy,
        "timestamp": datetime.now().isoformat()
    }
