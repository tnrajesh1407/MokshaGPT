"""
LangGraph Agent for MokshaGPT
âââââââââââââââââââââââââââââââââââââ
Graph structure:

  [START]
     â
     â¼
 [classify]          â LLM decides which tool to call
     â
     ââââº [analyze]  â stock analysis tool
     â
     ââââº [backtest] â strategy backtester tool
     â
     ââââº [unknown]  â fallback for unrecognised intent
     â
     â¼
  [END]

State flows through the graph as a TypedDict.
Each node reads from state, writes its result back, and the graph ends.
"""

from typing import TypedDict, Literal, Any
from langgraph.graph import StateGraph, START, END
from llm_factory import generate_response, PROMPTS, format_prompt, _env
from backtester import run_strategy_backtest
from screener import run_stock_screener
from asset_detector import detect_assets, get_primary_asset_type, AssetType
from forex_data import analyze_forex_pair
from options_data import get_options_chain, analyze_covered_call
from futures_data import analyze_contango_backwardation
from langfuse import observe as traceable
import json
import re
import yfinance as yf

# ââ 1. State Schema âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# Every node reads from and writes to this shared state dict.

class AgentState(TypedDict):
    user_message: str                        # raw input from the user
    intent: str                              # classified intent
    asset_type: str                          # detected asset type (stock, forex, options, futures)
    detected_assets: list                    # list of detected assets
    tool_result: Any                         # output from whichever tool ran
    error: str                               # error message if something failed


# ââ 2. Tool Definitions âââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# These are the "tools" the agent can invoke.
# In LangGraph terms they are just regular nodes, but we label them as tools
# ââ 3. Nodes ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

TOOLS = {
    "price":    "Fetch the latest real-time price for stocks, forex, crypto, or futures",
    "analyze":  "Analyse stocks, forex pairs, options, or futures and provide trading insights",
    "backtest": "Backtest trading strategies across multiple asset classes",
    "screen":   "Find assets matching specific criteria using natural language",
    "ensemble": "Build a multi-strategy ensemble portfolio",
    "forex":    "Analyze forex pairs with technical indicators and economic events",
    "options":  "Analyze options chains, calculate Greeks, and evaluate strategies",
    "futures":  "Analyze futures contracts, contango/backwardation, and roll strategies",
    "unknown":  "Handle unrecognised or out-of-scope requests",
}


def classify_node(state: AgentState) -> AgentState:
    """
    CLASSIFY node â the router with multi-asset detection.
    First detects asset types, then classifies intent based on both
    the message content and detected asset types.
    """
    msg = state['user_message'].lower()
    
    # Detect assets in the message
    detected_assets = detect_assets(state['user_message'])
    primary_asset_type = get_primary_asset_type(state['user_message'])
    
    print(f"[LangGraph] Detected assets: {[f'{a.asset_type.value}:{a.symbol}' for a in detected_assets]}")
    print(f"[LangGraph] Primary asset type: {primary_asset_type.value}")

    # ââ General / educational question guard â must run BEFORE all asset patterns ââ
    # Catches "what is X", "explain X", "how does X work", "define X", etc.
    # These should never be routed to price/analyze/backtest nodes.
    general_question_patterns = [
        # "what is meant by X", "what does X mean", "what is X trading/strategy/technique"
        r'\bwhat (is|are) meant by\b',
        r'\bwhat does .{0,60} mean\b',
        r'\bwhat is .{0,60} (trading|strategy|technique|method|approach|style|indicator|pattern|concept|theory|principle|analysis)\b',
        r'\bwhat are .{0,60} (strategies|techniques|methods|indicators|patterns|concepts|principles)\b',
        # explain / describe / define
        r'^(explain|describe|define|tell me about|what\'?s? the difference between|compare|contrast)\b',
        r'\b(explain|describe|define)\b.{0,60}\b(trading|strategy|technique|indicator|pattern|concept|analysis|method)\b',
        # "how does X work", "how do X work"
        r'\bhow (does|do|can|should|would)\b.{0,60}\b(work|function|operate|help|apply|be used)\b',
        # "can you explain", "help me understand", "teach me"
        r'\b(can you explain|could you explain|please explain|help me understand|teach me|i want to (know|understand|learn) (about|what|how))\b',
        # "introduction to", "basics of", "overview of", "guide to"
        r'\b(introduction to|basics of|overview of|guide to|tutorial on|fundamentals of)\b',
    ]
    for pattern in general_question_patterns:
        if re.search(pattern, msg):
            print(f"[LangGraph] classify_node â intent=unknown (general/educational question)")
            return {**state, "intent": "unknown", "asset_type": primary_asset_type.value, "detected_assets": []}

    # Fast regex pre-check for backtest queries â must run BEFORE price patterns
    # Fast regex pre-check for ensemble queries
    ensemble_patterns = [
        r'\b(ensemble|multi.?strategy)\b',
        r'\bcombine\b.{0,30}\bstrategies\b',
    ]
    for pattern in ensemble_patterns:
        if re.search(pattern, msg):
            return {**state, "intent": "ensemble", "asset_type": primary_asset_type.value, "detected_assets": detected_assets}

    backtest_patterns = [
        r'\bbacktest\b',
        r'\bback.?test\b',
        r'\bstrategy\b.{0,60}\b(on|for)\b',
        r'\b(sma|ema)\b.{0,40}\b(crossover|cross over|cross above|cross below)\b',
        r'\b(crossover|cross over)\b.{0,40}\b(sma|ema)\b',
        r'\bmacd\b.{0,40}\b(crossover|cross|signal|histogram)\b',
        r'\bbollinger\b.{0,40}\b(band|squeeze|breakout)\b',
        r'\b(camarilla|pivot)\b.{0,40}\b(strategy|trade|signal|level)\b',
        r'\b(buy when|sell when|entry|exit)\b',
        r'\b(simulate|simulation)\b.{0,30}\b(trade|strategy|portfolio)\b',
    ]
    for pattern in backtest_patterns:
        if re.search(pattern, msg):
            print(f"[LangGraph] classify_node â intent=backtest (regex match)")
            return {**state, "intent": "backtest", "asset_type": primary_asset_type.value, "detected_assets": detected_assets}

    # Fast regex pre-check for price queries
    price_patterns = [
        r'\b(latest|current|today\'?s?|live|now|real.?time)\b.{0,30}\b(price|rate|value|trading|quote)\b',
        r'\b(price|rate|value|trading|quote)\b.{0,30}\b(of|for)\b',
        r'\bstock price\b',
        r'\bshare price\b',
        r'\bforex rate\b',
        r'\bcurrency rate\b',
        r'\bhow much is\b.{0,30}\b(trading|worth|priced)\b',
        r'\bwhat is\b.{0,10}\b(the price|the quote|the rate)\b',
    ]
    for pattern in price_patterns:
        if re.search(pattern, msg):
            print(f"[LangGraph] classify_node â intent=price (regex match)")
            return {**state, "intent": "price", "asset_type": primary_asset_type.value, "detected_assets": detected_assets}

    # Asset-specific routing based on detected type and keywords
    if primary_asset_type == AssetType.FOREX:
        forex_keywords = ['forex', 'fx', 'currency', 'exchange rate', 'central bank', 'carry trade']
        if any(keyword in msg for keyword in forex_keywords) or len([a for a in detected_assets if a.asset_type == AssetType.FOREX]) > 0:
            print(f"[LangGraph] classify_node â intent=forex (asset type match)")
            return {**state, "intent": "forex", "asset_type": primary_asset_type.value, "detected_assets": detected_assets}
    
    elif primary_asset_type == AssetType.OPTIONS:
        options_keywords = ['options', 'call', 'put', 'strike', 'expiry', 'greeks', 'delta', 'gamma', 'theta', 'vega', 'implied volatility']
        if any(keyword in msg for keyword in options_keywords) or len([a for a in detected_assets if a.asset_type == AssetType.OPTIONS]) > 0:
            print(f"[LangGraph] classify_node â intent=options (asset type match)")
            return {**state, "intent": "options", "asset_type": primary_asset_type.value, "detected_assets": detected_assets}
    
    elif primary_asset_type == AssetType.FUTURES:
        futures_keywords = ['futures', 'contango', 'backwardation', 'roll', 'commodity', 'commodities', 'crude oil', 'gold', 'natural gas', 'spot price', 'silver', 'copper', 'corn', 'wheat', 'coffee']
        if any(keyword in msg for keyword in futures_keywords) or len([a for a in detected_assets if a.asset_type == AssetType.FUTURES]) > 0:
            print(f"[LangGraph] classify_node â intent=futures (asset type match)")
            return {**state, "intent": "futures", "asset_type": primary_asset_type.value, "detected_assets": detected_assets}

    # Fast regex pre-check for screener queries
    screener_patterns = [
        r'\b(nifty|sensex|s&p|nasdaq|dow|ftse|dax|nikkei)\b.{0,60}\b(stocks?|companies|shares)\b',
        r'\bstocks?\b.{0,60}\b(above|below|with|having|where)\b.{0,60}\b(sma|ema|rsi|macd|pe|p/e|volume|market cap)\b',
        r'\b(find|show|list|filter|screen|get|give me)\b.{0,60}\b(stocks?|forex|options|futures)\b',
        r'\b(stocks?|currencies|options|futures)\b.{0,30}\b(above|below)\b.{0,30}\b(200|50|20)\b.{0,20}\b(sma|ema|ma|moving average)\b',
    ]
    for pattern in screener_patterns:
        if re.search(pattern, msg):
            print(f"[LangGraph] classify_node â intent=screen (regex match)")
            return {**state, "intent": "screen", "asset_type": primary_asset_type.value, "detected_assets": detected_assets}

    # Fast regex pre-check for analysis queries
    analysis_patterns = [
        r'\bhow is\b.{0,40}\b(looking|doing|performing|trading)\b',
        r'\b(will|should|would)\b.{0,30}\b(go up|go down|rise|fall|rally|drop|buy|sell)\b',
        r'\b(outlook|forecast|prediction|target|sentiment)\b.{0,30}\b(for|on)\b',
        r'\b(bullish|bearish)\b.{0,30}\b(on|for)\b',
        r'\banalyse\b|\banalyze\b',
        r'\bwhat do you think (about|of)\b',
    ]
    for pattern in analysis_patterns:
        if re.search(pattern, msg):
            # Route to asset-specific analysis if detected
            if primary_asset_type == AssetType.FOREX:
                intent = "forex"
            elif primary_asset_type == AssetType.OPTIONS:
                intent = "options"
            elif primary_asset_type == AssetType.FUTURES:
                intent = "futures"
            else:
                intent = "analyze"
            
            print(f"[LangGraph] classify_node â intent={intent} (analysis regex match)")
            return {**state, "intent": intent, "asset_type": primary_asset_type.value, "detected_assets": detected_assets}

    # Fallback to LLM classification
    prompt = format_prompt(PROMPTS["agent_classify_prompt"], message=state['user_message'])
    raw = generate_response(prompt, use_search=False).strip()

    try:
        cleaned = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            intent = result.get("intent", "unknown")
        else:
            intent = cleaned.strip()
    except Exception:
        intent = raw.strip()

    # Normalize intent
    intent = re.sub(r"[^a-z]", "", intent.lower())
    intent_remap = {"analysis": "analyze", "analyse": "analyze", "screening": "screen"}
    intent = intent_remap.get(intent, intent)

    # Route to asset-specific nodes if appropriate
    if intent == "analyze":
        if primary_asset_type == AssetType.FOREX:
            intent = "forex"
        elif primary_asset_type == AssetType.OPTIONS:
            intent = "options"
        elif primary_asset_type == AssetType.FUTURES:
            intent = "futures"

    if intent not in TOOLS:
        intent = "unknown"

    print(f"[LangGraph] classify_node â intent={intent}")
    return {**state, "intent": intent, "asset_type": primary_asset_type.value, "detected_assets": detected_assets}


def price_node(state: AgentState) -> AgentState:
    """
    PRICE node â live stock price lookup via yfinance.
    Extracts the ticker from the message using the LLM, then fetches
    real-time price data directly from Yahoo Finance (no search API needed).
    """
    print("[LangGraph] price_node â fetching live stock price")
    try:
        # Use LLM to extract ticker symbol
        prompt = format_prompt(PROMPTS["price_extract_ticker_prompt"], message=state["user_message"])
        raw = generate_response(prompt, use_search=False).strip()

        ticker = None
        try:
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                ticker = data.get("ticker", "").strip()
        except Exception:
            pass

        if not ticker:
            return {**state, "tool_result": {"type": "price", "content": "Could not identify a stock ticker in your query. Please mention the stock name or symbol."}}

        # Fetch live data via yfinance
        info = yf.Ticker(ticker).fast_info
        price = info.last_price
        prev_close = info.previous_close
        currency = getattr(info, "currency", "")

        if price is None:
            return {**state, "tool_result": {"type": "price", "content": f"Could not fetch price for **{ticker}**. The ticker may be incorrect or delisted."}}

        change = price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0
        direction = "â²" if change >= 0 else "â¼"

        content = (
            f"**{ticker}** â Latest Price\n\n"
            f"Current Price: **{currency} {price:,.2f}**\n"
            f"Change: {direction} {abs(change):,.2f} ({abs(change_pct):.2f}%)\n"
            f"Previous Close: {currency} {prev_close:,.2f}\n\n"
            f"*Data sourced from Yahoo Finance via yfinance*"
        )
        return {**state, "tool_result": {"type": "price", "content": content}}

    except Exception as e:
        return {**state, "error": str(e)}


def analyze_node(state: AgentState) -> AgentState:
    """
    ANALYZE node â stock analysis tool.
    Extracts the ticker from the message and calls generate_response.
    """
    print("[LangGraph] analyze_node â running stock analysis")
    try:
        result = generate_response(state["user_message"], use_search=_use_search)
        return {**state, "tool_result": {"type": "analysis", "content": result}}
    except Exception as e:
        import traceback
        print(f"[LangGraph] analyze_node ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()
        return {**state, "error": f"{type(e).__name__}: {e}"}


def backtest_node(state: AgentState) -> AgentState:
    """
    BACKTEST node â strategy backtester tool.
    Passes the full user message to run_strategy_backtest which uses the LLM
    internally to parse the strategy and generate signal code.
    """
    print("[LangGraph] backtest_node â running strategy backtest")
    try:
        result = run_strategy_backtest(state["user_message"])
        return {**state, "tool_result": {"type": "backtest", "content": result}}
    except Exception as e:
        return {**state, "error": str(e)}


def screen_node(state: AgentState) -> AgentState:
    """
    SCREEN node â stock screener tool.
    Passes the full user message to run_stock_screener which uses the LLM
    internally to parse the screening criteria.
    """
    print("[LangGraph] screen_node â running stock screener")
    try:
        result = run_stock_screener(state["user_message"])
        return {**state, "tool_result": {"type": "screen", "content": result}}
    except Exception as e:
        return {**state, "error": str(e)}


def forex_node(state: AgentState) -> AgentState:
    """
    FOREX node â forex pair analysis with technical indicators and economic events.
    """
    print("[LangGraph] forex_node â analyzing forex pair")
    try:
        # Extract forex pair from detected assets or message
        forex_pair = None
        for asset in state.get("detected_assets", []):
            if asset.asset_type == AssetType.FOREX:
                forex_pair = asset.symbol
                break
        
        if not forex_pair:
            # Fallback: try to extract from message
            forex_pair = "EUR/USD"  # Default major pair
        
        result = analyze_forex_pair(forex_pair)
        
        # Format the result for display
        if 'error' in result:
            content = f"Error analyzing {forex_pair}: {result['error']}"
        else:
            current_rate = result.get('current_rate', {})
            technicals = result.get('technicals', {})
            trend = result.get('trend', 'neutral')
            signals = result.get('signals', [])
            
            content = f"# {forex_pair} Analysis\n\n"
            content += f"**Current Rate:** {current_rate.get('last', 'N/A'):.5f}\n"
            content += f"**Change:** {current_rate.get('change_pct', 0):+.2f}%\n"
            content += f"**Spread:** {current_rate.get('spread', 0):.5f}\n\n"
            
            content += f"## Technical Analysis\n"
            content += f"**Trend:** {trend.title()}\n"
            
            if technicals:
                content += f"**RSI:** {technicals.get('rsi', 'N/A')}\n"
                content += f"**20-day SMA:** {technicals.get('sma20', 'N/A')}\n"
                content += f"**50-day SMA:** {technicals.get('sma50', 'N/A')}\n\n"
            
            if signals:
                content += f"## Trading Signals\n"
                for signal in signals:
                    content += f"- **{signal.get('type', '').upper()}** ({signal.get('indicator', '')}): {signal.get('message', '')}\n"
            
            content += f"\n*Analysis generated at {result.get('analysis_timestamp', '')}*"
        
        return {**state, "tool_result": {"type": "forex", "content": content}}
    except Exception as e:
        return {**state, "error": str(e)}


def options_node(state: AgentState) -> AgentState:
    """
    OPTIONS node â options analysis, Greeks calculation, and strategy evaluation.
    """
    print("[LangGraph] options_node â analyzing options")
    try:
        # Extract options symbol or underlying from detected assets
        options_symbol = None
        underlying = None
        
        for asset in state.get("detected_assets", []):
            if asset.asset_type == AssetType.OPTIONS:
                if asset.metadata.get("is_chain_request"):
                    underlying = asset.metadata.get("underlying")
                else:
                    options_symbol = asset.symbol
                break
        
        if options_symbol:
            # Specific option contract analysis
            from options_data import get_option_contract
            contract = get_option_contract(options_symbol)
            
            if not contract:
                content = f"Could not find option contract: {options_symbol}"
            else:
                content = f"# {contract.symbol} Option Analysis\n\n"
                content += f"**Underlying:** {contract.underlying}\n"
                content += f"**Strike:** {contract.currency} {contract.strike}\n"
                content += f"**Expiry:** {contract.expiry.strftime('%Y-%m-%d')}\n"
                content += f"**Type:** {contract.option_type.title()}\n"
                content += f"**Currency:** {contract.currency}\n"
                content += f"**Exchange:** {contract.exchange}\n\n"
                
                content += f"## Pricing\n"
                content += f"**Last Price:** {contract.currency} {contract.last:.2f}\n"
                content += f"**Bid/Ask:** {contract.currency} {contract.bid:.2f} / {contract.currency} {contract.ask:.2f}\n"
                content += f"**Intrinsic Value:** {contract.currency} {contract.intrinsic_value:.2f}\n"
                content += f"**Time Value:** {contract.currency} {contract.time_value:.2f}\n\n"
                
                content += f"## Greeks\n"
                content += f"**Delta:** {contract.delta:.3f}\n"
                content += f"**Gamma:** {contract.gamma:.3f}\n"
                content += f"**Theta:** {contract.theta:.3f}\n"
                content += f"**Vega:** {contract.vega:.3f}\n"
                content += f"**Implied Volatility:** {contract.implied_volatility:.1%}\n\n"
                
                content += f"**Days to Expiry:** {contract.days_to_expiry}\n"
                content += f"**Volume:** {contract.volume:,}\n"
                content += f"**Open Interest:** {contract.open_interest:,}"
        
        elif underlying:
            # Options chain analysis
            chain = get_options_chain(underlying)
            
            if not chain:
                content = f"Could not fetch options chain for {underlying}"
            else:
                content = f"# {underlying} Options Chain\n\n"
                content += f"**Underlying Price:** {chain.currency} {chain.spot_price:.2f}\n"
                content += f"**Currency:** {chain.currency}\n"
                content += f"**Exchange:** {chain.exchange}\n"
                content += f"**IV Rank:** {chain.iv_rank:.1f}%\n"
                content += f"**30-day Avg IV:** {chain.iv_30d_avg:.1%}\n\n"
                
                content += f"## Available Expiries\n"
                for expiry in chain.expiry_dates[:5]:  # Show first 5
                    content += f"- {expiry.strftime('%Y-%m-%d')}\n"
                
                # Show some near-the-money options
                content += f"\n## Near-the-Money Options (Next Expiry)\n"
                next_expiry_calls = [c for c in chain.calls if c.expiry == chain.expiry_dates[0]]
                next_expiry_calls.sort(key=lambda x: abs(x.strike - chain.spot_price))
                
                content += f"**Calls:**\n"
                for call in next_expiry_calls[:5]:
                    content += f"- {call.currency} {call.strike} Call: {call.currency} {call.last:.2f} (IV: {call.implied_volatility:.1%}, Î: {call.delta:.3f})\n"
        
        else:
            content = "Please specify an option symbol (e.g., AAPL240315C150) or underlying stock for options chain analysis."
        
        return {**state, "tool_result": {"type": "options", "content": content}}
    except Exception as e:
        return {**state, "error": str(e)}


def futures_node(state: AgentState) -> AgentState:
    """
    FUTURES node â futures analysis, contango/backwardation, roll strategies, and commodity spot prices.
    """
    print("[LangGraph] futures_node â analyzing futures/commodities")
    try:
        # Extract futures symbol from detected assets or message
        futures_symbol = None
        commodity_symbol = None
        
        for asset in state.get("detected_assets", []):
            if asset.asset_type == AssetType.FUTURES:
                futures_symbol = asset.symbol
                break
        
        # Check if this is a commodity spot price query
        commodity_keywords = ['spot price', 'gold price', 'oil price', 'silver price', 'copper price']
        msg_lower = state.get("user_message", "").lower()
        
        # Look for commodity assets in detected assets
        commodity_assets = [a for a in state.get("detected_assets", []) 
                          if a.metadata.get("is_spot_commodity", False)]
        
        if commodity_assets or any(keyword in msg_lower for keyword in commodity_keywords):
            # Handle as commodity spot price
            commodity_symbol = None
            
            if commodity_assets:
                commodity_symbol = commodity_assets[0].symbol
            else:
                # Infer from keywords
                if 'gold' in msg_lower:
                    commodity_symbol = 'XAUUSD'
                elif 'silver' in msg_lower:
                    commodity_symbol = 'XAGUSD'
                elif 'oil' in msg_lower or 'crude' in msg_lower:
                    commodity_symbol = 'XTIUSD'
                elif 'copper' in msg_lower:
                    commodity_symbol = 'XCOPUSD'
                elif 'natural gas' in msg_lower:
                    commodity_symbol = 'XNGUSD'
                elif 'corn' in msg_lower:
                    commodity_symbol = 'XCORNUSD'
                elif 'wheat' in msg_lower:
                    commodity_symbol = 'XWHEUSD'
                elif 'coffee' in msg_lower:
                    commodity_symbol = 'XCOFUSD'
            
            if commodity_symbol:
                # Analyze commodity spot price
                from futures_data import analyze_commodity_spot
                spot_analysis = analyze_commodity_spot(commodity_symbol)
                
                if 'error' in spot_analysis:
                    content = f"Error analyzing {commodity_symbol}: {spot_analysis['error']}"
                else:
                    content = f"# {spot_analysis.get('name', commodity_symbol)} Spot Analysis\n\n"
                    content += f"**Current Price:** ${spot_analysis.get('current_price', 0):.2f} {spot_analysis.get('unit', 'USD')}\n"
                    content += f"**Change:** {spot_analysis.get('change_pct', 0):+.2f}%\n"
                    content += f"**Type:** {spot_analysis.get('type', 'Unknown').replace('_', ' ').title()}\n\n"
                    
                    technicals = spot_analysis.get('technicals', {})
                    if technicals:
                        content += f"## Technical Analysis\n"
                        if technicals.get('rsi'):
                            content += f"**RSI:** {technicals['rsi']:.1f}\n"
                        if technicals.get('sma20'):
                            content += f"**20-day SMA:** ${technicals['sma20']:.2f}\n"
                        if technicals.get('sma50'):
                            content += f"**50-day SMA:** ${technicals['sma50']:.2f}\n"
                        if technicals.get('pct_from_52w_high') is not None:
                            content += f"**From 52W High:** {technicals['pct_from_52w_high']:+.1f}%\n"
                        content += "\n"
                    
                    insights = spot_analysis.get('market_insights', [])
                    if insights:
                        content += f"## Market Insights\n"
                        for insight in insights:
                            content += f"- {insight}\n"
                    
                    content += f"\n*Analysis generated at {spot_analysis.get('analysis_timestamp', '')}*"
                
                return {**state, "tool_result": {"type": "futures", "content": content}}
        
        # Handle futures contracts
        if not futures_symbol:
            futures_symbol = "/ES"  # Default to E-mini S&P 500
        
        # Analyze contango/backwardation
        curve_analysis = analyze_contango_backwardation(futures_symbol)
        
        if 'error' in curve_analysis:
            content = f"Error analyzing {futures_symbol}: {curve_analysis['error']}"
        else:
            content = f"# {futures_symbol} Futures Analysis\n\n"
            
            front_month = curve_analysis.get('front_month', {})
            back_month = curve_analysis.get('back_month', {})
            
            content += f"## Current Contracts\n"
            content += f"**Front Month ({front_month.get('contract', 'N/A')}):** ${front_month.get('price', 0):.2f}\n"
            content += f"**Back Month ({back_month.get('contract', 'N/A')}):** ${back_month.get('price', 0):.2f}\n\n"
            
            content += f"## Curve Analysis\n"
            content += f"**Shape:** {curve_analysis.get('curve_shape', 'Unknown').title()}\n"
            content += f"**Price Difference:** ${curve_analysis.get('price_difference', 0):.2f} ({curve_analysis.get('price_difference_pct', 0):+.2f}%)\n"
            content += f"**Annualized Difference:** {curve_analysis.get('annualized_difference', 0):+.2f}%\n"
            content += f"**Roll Yield Estimate:** {curve_analysis.get('roll_yield_estimate', 0):+.2f}%\n\n"
            
            # Explain curve shape
            curve_shape = curve_analysis.get('curve_shape', '')
            if curve_shape == 'contango':
                content += "**Contango** means future prices are higher than current prices. This typically indicates storage costs or convenience yield factors.\n\n"
            elif curve_shape == 'backwardation':
                content += "**Backwardation** means future prices are lower than current prices. This often occurs when there's immediate demand or supply constraints.\n\n"
            
            # Show curve data
            curve_data = curve_analysis.get('curve_data', [])
            if curve_data:
                content += f"## Futures Curve\n"
                for contract_data in curve_data[:6]:  # Show first 6 contracts
                    content += f"- **{contract_data.get('contract', 'N/A')}:** ${contract_data.get('price', 0):.2f} "
                    content += f"({contract_data.get('days_to_expiry', 0)} days, Vol: {contract_data.get('volume', 0):,})\n"
            
            content += f"\n*Analysis generated at {curve_analysis.get('analysis_timestamp', '')}*"
        
        return {**state, "tool_result": {"type": "futures", "content": content}}
    except Exception as e:
        return {**state, "error": str(e)}
def ensemble_node(state: AgentState) -> AgentState:
    """
    ENSEMBLE node — routes users requesting multi-strategy ensembles to the builder dashboard.
    """
    print("[LangGraph] ensemble_node → redirecting to Ensemble Builder dashboard")
    msg = (
        "I see you want to build a multi-strategy ensemble portfolio! I have a dedicated, highly-visual dashboard specifically for that.\n\n"
        "Please click on the **Ensemble Builder** tab in the top navigation, or go directly to `/ensemble-builder` to configure and run your portfolio."
    )
    return {**state, "tool_result": {"type": "ensemble", "content": msg}}


def unknown_node(state: AgentState) -> AgentState:
    """
    UNKNOWN node â fallback.
    Tries to answer with the LLM's general knowledge first.
    Only shows the help menu if the query is truly off-topic.
    """
    print("[LangGraph] unknown_node â attempting general LLM response")
    try:
        prompt = format_prompt(PROMPTS.get("general_response_prompt", ""), message=state["user_message"])
        response = generate_response(prompt, use_search=False).strip()
        if response:
            return {**state, "tool_result": {"type": "analysis", "content": response}}
    except Exception:
        pass

    # Hard fallback â truly unrecognised
    msg = (
        "I can help you with:\n"
        "- **Stock Analysis** â ask about any ticker, e.g. 'Analyse AAPL' or 'How is TSLA looking?'\n"
        "- **Forex Analysis** â analyze currency pairs, e.g. 'How is EUR/USD looking?' or 'GBP/JPY analysis'\n"
        "- **Options Analysis** â analyze options chains and Greeks, e.g. 'AAPL call options' or 'TSLA240315C250 Greeks'\n"
        "- **Futures Analysis** â analyze futures curves, e.g. '/ES futures trend' or '/GC contango analysis'\n"
        "- **Strategy Backtesting** â describe a strategy, e.g. "
        "'Backtest a 10/50 SMA crossover on AAPL for 2 years with $50,000'\n"
        "- **Multi-Asset Screening** â find assets by criteria, e.g. "
        "'Find tech stocks with P/E under 20' or 'High volatility forex pairs'\n\n"
        "What would you like to do?"
    )
    return {**state, "tool_result": {"type": "unknown", "content": msg}}


# ââ 4. Routing Function âââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# LangGraph calls this after classify_node to decide which node to visit next.

def route_by_intent(state: AgentState) -> Literal["price", "analyze", "backtest", "screen", "forex", "options", "futures", "ensemble", "unknown"]:
    return state["intent"]  # type: ignore


# ââ 5. Build the Graph ââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def build_agent() -> StateGraph:
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("classify", classify_node)
    graph.add_node("price",    price_node)
    graph.add_node("analyze",  analyze_node)
    graph.add_node("backtest", backtest_node)
    graph.add_node("screen",   screen_node)
    graph.add_node("ensemble", ensemble_node)
    graph.add_node("forex",    forex_node)
    graph.add_node("options",  options_node)
    graph.add_node("futures",  futures_node)
    graph.add_node("unknown",  unknown_node)

    # Edges
    graph.add_edge(START, "classify")

    # Conditional edge: after classify, route to the right tool node
    graph.add_conditional_edges(
        "classify",
        route_by_intent,
        {
            "price":    "price",
            "analyze":  "analyze",
            "backtest": "backtest",
            "screen":   "screen",
            "ensemble": "ensemble",
            "forex":    "forex",
            "options":  "options",
            "futures":  "futures",
            "unknown":  "unknown",
        },
    )

    # All tool nodes go straight to END
    graph.add_edge("price",    END)
    graph.add_edge("analyze",  END)
    graph.add_edge("backtest", END)
    graph.add_edge("screen",   END)
    graph.add_edge("ensemble", END)
    graph.add_edge("forex",    END)
    graph.add_edge("options",  END)
    graph.add_edge("futures",  END)
    graph.add_edge("unknown",  END)

    return graph.compile()


# Compile once at import time â reused across all requests
agent = build_agent()


# ââ 6. Public Entry Point âââââââââââââââââââââââââââââââââââââââââââââââââââââ

@traceable(name="run-agent", as_type="chain")
def run_agent(user_message: str) -> dict:
    """
    Run the LangGraph agent with a user message.
    Returns a dict with `type` and `content` (or `error`).
    """
    initial_state: AgentState = {
        "user_message": user_message,
        "intent": "",
        "asset_type": "",
        "detected_assets": [],
        "tool_result": None,
        "error": "",
    }

    final_state = agent.invoke(initial_state)

    if final_state.get("error"):
        raise RuntimeError(final_state["error"])

    return final_state["tool_result"]
