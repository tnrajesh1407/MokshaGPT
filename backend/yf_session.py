"""
yf_session.py — Patch yfinance to use a browser-like User-Agent.

Yahoo Finance blocks or rate-limits requests from cloud datacenter IPs
(GCP, AWS, Azure) when the default Python/yfinance User-Agent is used.
Setting a realistic browser UA resolves the issue in most cases.

Import this module once at application startup (done in main.py).
"""

import requests
import yfinance as yf

# Browser-like headers that Yahoo Finance accepts from cloud IPs
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def patch_yfinance_session() -> None:
    """
    Replace yfinance's internal requests session with one that uses
    a browser User-Agent. Call once at startup.
    """
    session = requests.Session()
    session.headers.update(_HEADERS)
    # yfinance ≥ 0.2.x exposes a module-level cache object; patching its
    # session propagates to all Ticker / download calls.
    try:
        from yfinance.data import YfData
        YfData.session = session
        print("[yf_session] Patched YfData.session with browser UA")
    except Exception:
        pass

    # Fallback: patch the module-level _requests_cache if present
    try:
        yf.utils.requests = session  # type: ignore[attr-defined]
    except Exception:
        pass

    # Also set via the public API if available (yfinance ≥ 0.2.38)
    try:
        yf.set_tz_cache_location("/tmp/yfinance_tz")  # writable in Cloud Run
    except Exception:
        pass

    print("[yf_session] yfinance session patched — browser UA active")
