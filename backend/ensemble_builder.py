import asyncio
import json
import numpy as np
import pandas as pd
from typing import List, Dict, Any
from llm_factory import generate_response
from backtester import run_strategy_backtest

ENSEMBLE_PROMPT = """
You are an expert quantitative researcher building a multi-strategy ensemble portfolio.
The user wants to build an ensemble of 3 diverse trading strategies based on the following request:

USER REQUEST: {user_request}

Your task is to generate 3 distinct, uncorrelated strategies that will be run concurrently and combined.
For example, if the user asks for TSLA, you might generate:
1. A Trend Following strategy (e.g., SMA crossover)
2. A Mean Reversion strategy (e.g., RSI oversold/overbought)
3. A Volatility Breakout strategy (e.g., Bollinger Bands)

IMPORTANT RULES:
1. Divide the initial capital equally among the 3 strategies. If the user specifies $30,000, each strategy should use $10,000. If no capital is specified, use $10,000 for each.
2. Ensure the timeframe/period and ticker exactly match the user's request for all 3 strategies.
3. Write the strategies in plain English so they can be parsed by our standard backtester.

Return EXACTLY a JSON array of 3 strings. Example:
[
  "10/50 SMA crossover on AAPL for 2 years with $10000 capital",
  "RSI strategy on AAPL: buy when RSI < 30, sell when RSI > 70, 2 years, $10000 capital",
  "Bollinger Bands mean reversion on AAPL, 20-period, 2 std dev, 2 years, $10000 capital"
]

Respond with ONLY the JSON array. Do not include markdown formatting or explanations.
"""

def _calculate_ensemble_metrics(combined_df: pd.DataFrame, initial_capital: float) -> dict:
    """Calculate standard metrics on the aggregated portfolio time series."""
    if combined_df.empty:
        return {}

    # Sort by date
    combined_df = combined_df.sort_values('date').reset_index(drop=True)
    
    final_value = combined_df['portfolio'].iloc[-1]
    total_return_pct = ((final_value / initial_capital) - 1.0) * 100

    # Calculate max drawdown
    combined_df['peak'] = combined_df['portfolio'].cummax()
    combined_df['drawdown'] = (combined_df['portfolio'] - combined_df['peak']) / combined_df['peak'] * 100
    max_drawdown_pct = combined_df['drawdown'].min()

    # Calculate annualized return
    days = (combined_df['date'].iloc[-1] - combined_df['date'].iloc[0]).days
    if days > 0:
        years = days / 365.25
        annualized_return_pct = (((final_value / initial_capital) ** (1 / years)) - 1.0) * 100
    else:
        annualized_return_pct = 0.0

    return {
        "initial_capital": initial_capital,
        "final_value": final_value,
        "total_return_pct": total_return_pct,
        "annualized_return_pct": annualized_return_pct,
        "max_drawdown_pct": max_drawdown_pct,
        # We don't calculate Sharpe here because we don't have the risk-free rate or precise daily returns easily,
        # but the UI mainly needs Return and Drawdown for the ensemble.
    }

async def run_ensemble_builder(user_request: str) -> dict:
    """
    Executes the multi-strategy ensemble workflow.
    """
    print(f"[Ensemble] Generating 3 diverse strategies for: {user_request}")
    
    # 1. Generate 3 strategies via LLM
    prompt = ENSEMBLE_PROMPT.replace("{user_request}", user_request)
    raw_response = generate_response(prompt, use_search=False)
    
    # Clean JSON
    raw_response = raw_response.strip().strip('`').replace('json\n', '')
    
    try:
        strategies_text = json.loads(raw_response)
        if not isinstance(strategies_text, list) or len(strategies_text) != 3:
            raise ValueError("LLM did not return exactly 3 strategies.")
    except Exception as e:
        print(f"[Ensemble] Failed to parse LLM response: {raw_response}")
        raise ValueError("Failed to generate diverse strategies. Please try rephrasing your request.")

    print(f"[Ensemble] Generated strategies: {strategies_text}")

    # 2. Run backtests concurrently
    loop = asyncio.get_event_loop()
    tasks = []
    for st in strategies_text:
        # run_strategy_backtest is blocking, run in thread
        tasks.append(loop.run_in_executor(None, run_strategy_backtest, st))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out failures
    valid_results = []
    for idx, res in enumerate(results):
        if isinstance(res, Exception):
            print(f"[Ensemble] Strategy {idx+1} failed: {res}")
        else:
            valid_results.append(res)
            
    if not valid_results:
        raise ValueError("All strategies failed to backtest. Please check the asset or parameters.")

    # 3. Aggregate results
    all_series = []
    total_initial_capital = 0.0
    
    for res in valid_results:
        total_initial_capital += res['metrics']['initial_capital']
        series = res['chart_data']['price_series']
        df = pd.DataFrame(series)
        df['date'] = pd.to_datetime(df['date'])
        # Keep only date and portfolio value
        df = df[['date', 'portfolio']]
        all_series.append(df)
        
    # Merge portfolio values by date
    if all_series:
        combined_df = all_series[0].copy()
        combined_df.rename(columns={'portfolio': 'portfolio_0'}, inplace=True)
        
        for i in range(1, len(all_series)):
            df = all_series[i].copy()
            df.rename(columns={'portfolio': f'portfolio_{i}'}, inplace=True)
            combined_df = pd.merge(combined_df, df, on='date', how='outer')
            
        # Forward fill missing values (if one strategy started later/ended earlier)
        combined_df = combined_df.sort_values('date').fillna(method='ffill').fillna(method='bfill')
        
        # Sum the portfolios
        portfolio_cols = [c for c in combined_df.columns if c.startswith('portfolio_')]
        combined_df['portfolio'] = combined_df[portfolio_cols].sum(axis=1)
        
        ensemble_metrics = _calculate_ensemble_metrics(combined_df, total_initial_capital)
        
        # Format chart data
        ensemble_chart_data = []
        for _, row in combined_df.iterrows():
            data_point = {
                "date": row['date'].strftime('%Y-%m-%d'),
                "ensemble_portfolio": float(row['portfolio'])
            }
            # Add individual portfolios
            for i in range(len(all_series)):
                col = f'portfolio_{i}'
                if col in row and pd.notna(row[col]):
                    data_point[f'strategy_{i+1}_portfolio'] = float(row[col])
            
            ensemble_chart_data.append(data_point)
            
        # Generate summary
        summary_prompt = f"""
You are a financial advisor explaining an ensemble backtest result to a user.
The user requested: {user_request}

The ensemble consists of {len(valid_results)} strategies running concurrently with equal capital allocation.

Overall Ensemble Performance:
- Total Return: {ensemble_metrics.get('total_return_pct', 0):.2f}%
- Max Drawdown: {ensemble_metrics.get('max_drawdown_pct', 0):.2f}%

Individual Strategy Performances:
"""
        for idx, res in enumerate(valid_results):
            m = res['metrics']
            summary_prompt += f"Strategy {idx+1}: Total Return: {m.get('total_return_pct', 0):.2f}%, Max Drawdown: {m.get('max_drawdown_pct', 0):.2f}%\n"

        summary_prompt += """
Write a short, professional 2-3 sentence summary explaining how the ensemble's diversification affected the overall portfolio (e.g. smoothing returns, reducing max drawdown compared to individual strategies). Focus on the comparison between the ensemble's metrics and the individual strategies. Do not mention the prompt instructions.
"""
        try:
            ensemble_summary = generate_response(summary_prompt, use_search=False)
        except Exception as e:
            print(f"[Ensemble] Summary generation failed: {e}")
            ensemble_summary = "Ensemble backtest complete. Combining multiple uncorrelated strategies helps diversify risk and smooth out returns over time."
            
    else:
        ensemble_metrics = {}
        ensemble_chart_data = []
        ensemble_summary = "No valid strategies were generated to form an ensemble."

    return {
        "strategies_text": strategies_text,
        "results": valid_results,
        "ensemble_metrics": ensemble_metrics,
        "ensemble_chart_data": ensemble_chart_data,
        "ensemble_summary": ensemble_summary
    }
