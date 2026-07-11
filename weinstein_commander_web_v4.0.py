# =============================================================================
# weinstein_commander_web_v4.0.py — Weinstein Commander Web
# v4.0 — Phase 1: Pre-Market Hub | Post-Market | Breadth Engine | Macro+ | Gemini AI
# Trailing SL Note: SL > Entry is VALID for locked-profit trailing states.
#   Pre-Flight checks SL < entry (new trades). Existing positions show LOCKED badge.
# =============================================================================

import streamlit as st
import pandas as pd
import os, sys, sqlite3, base64, math, importlib, logging, json
import numpy as np
import plotly.express as px
import plotly.figure_factory as ff          # BUG-14: moved to top-level
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from dotenv import load_dotenv
from dhan_auth import ensure_valid_token
from dhanhq import dhanhq
from ai_risk_manager import (
    get_market_health, get_noise_risk_stats, get_atr,
    get_portfolio_correlation_matrix,
    get_adaptive_atr_multiplier,                                       # FIXED: removed dead imports
)
from ai_grading_engine import get_weinstein_score
import yfinance as yf
from pine_generator import generate_pine_code
# ── v4.0 Phase-1 imports ─────────────────────────────────────────────────────
try:
    from market_data_hub import (
        build_premarket_snapshot, build_postmarket_snapshot,
        fetch_global_overview, fetch_fii_dii_data, fetch_india_vix_history,
        fetch_nse_options_summary, fetch_economic_calendar, fetch_fno_ban_list,
        fetch_nse_breadth,
    )
    _HUB_OK = True
except ImportError as _e:
    _HUB_OK = False
    logger = logging.getLogger(__name__)
    logging.getLogger(__name__).warning(f"market_data_hub not available: {_e}")

try:
    from gemini_reporter import (
        generate_premarket_brief, generate_postmarket_summary,
        generate_weekly_market_report,
        generate_portfolio_review,   # used by AI Lab → Generative → Portfolio Review
                                     # AND by Autopsy → Trade Quality AI review
    )
    _GEMINI_OK = True
except ImportError:
    _GEMINI_OK = False

try:
    from breadth_engine import (
        calculate_breadth_metrics, build_breadth_regime,
        get_sector_breadth, get_broad_market_breadth,
        calculate_mcclellan, format_breadth_for_report,
    )
    _BREADTH_OK = True
except ImportError:
    _BREADTH_OK = False

try:
    from scheduler_daemon import (
        start_scheduler, get_scheduler_status, load_latest_report,
        trigger_manual_report,
    )
    _SCHED_OK = True
except ImportError:
    _SCHED_OK = False

try:
    from fundamental_hub import (
        fetch_stock_fundamentals, get_valuation_scorecard,
        screen_fundamentals, fetch_financial_statements,
        fetch_quarterly_results, format_fundamentals_for_report,
    )
    _FUND_OK = True
except ImportError:
    _FUND_OK = False

try:
    from news_feed import (
        fetch_all_news, add_sentiment, filter_by_symbol,
        get_market_news_summary, get_feed_health,
    )
    _NEWS_OK = True
except ImportError:
    _NEWS_OK = False

try:
    from portfolio_analytics import (
        parse_holdings, portfolio_overview,
        compute_factor_exposure, compute_var,
        run_stress_test, run_walkforward_backtest,
    )
    _PORT_OK = True
except ImportError:
    _PORT_OK = False

try:
    from broker_options import get_option_chain, dhan_subscription_check
    from dhan_auth import get_valid_token, token_status as dhan_token_status, refresh_token
    _BROKER_OK = True
except ImportError:
    _BROKER_OK = False

try:
    from watchlist_ranker import rank_watchlist, load_watchlist_symbols
    _RANKER_OK = True
except ImportError:
    _RANKER_OK = False

# ETF Trading System (Phases 1-3 — added 11 May 2026)
#   etf_universe   : 55 curated NSE ETFs with category metadata
#   etf_screener   : per-ETF 4-axis scoring (Liquidity / Trend / RS / Rotation)
#   etf_rotation   : sector rotation + asset-class regime + RRG coords + picks
# All three power the new ETF page (Phase 4) below.
try:
    import etf_universe as _etf_u
    import etf_screener as _etf_s
    import etf_rotation as _etf_r
    _ETF_OK = True
except ImportError:
    _ETF_OK = False

# Start background scheduler — singleton via cache_resource (WARN-3 fix)
# Prevents duplicate scheduler instances when multiple browser tabs are open.
@st.cache_resource
def _get_scheduler():
    if not _SCHED_OK:
        return None
    try:
        sched = start_scheduler()
        logging.getLogger(__name__).info("Scheduler started via cache_resource singleton")
        return sched
    except Exception as _se:
        logging.getLogger(__name__).warning(f"Scheduler start failed: {_se}")
        return None

_sched = _get_scheduler()


# NOTE: dhan_journal_v7 is a full Streamlit app — importing it at module level
# triggers st.set_page_config() and other top-level Streamlit calls, which
# hijacks the Commander's page and opens the Journal instead.
# get_sector is therefore imported LAZILY inside the Pre-Flight block only.
def get_sector(symbol):
    """Fallback sector lookup that avoids importing the UI-heavy dhan_journal_v7."""
    try:
        import sector_lookup as sl
        rec = sl.get_sector(symbol)
        if rec:
            return rec.get('display_name') or rec.get('sector_name') or "Unknown"
    except Exception:
        pass
    return "Unknown"

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
# Suppress noisy yfinance download errors (sector indices that Yahoo doesn't serve)
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("peewee").setLevel(logging.CRITICAL)

# ── PAGE CONFIG ──────────────────────────────────────────────────────────────
def clean_symbol(symbol):
    """Clean Dhan broker symbols → plain NSE ticker. BUG-15: single source of truth."""
    s = str(symbol).strip().upper().replace("NSE:", "").replace("BSE:", "")
    if s in ("NIFTY", "CNX NIFTY"): return "^NSEI"
    if s in ("BANKNIFTY", "NIFTYBANK"): return "^NSEBANK"
    if s == "CNX500": return "^CNX500"
    for suffix in ['-EQ', '-BE', '-SM', '-ST', '-BZ', '.NS']:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
    return s

def yf_symbol(symbol):
    """Convert clean NSE ticker to Yahoo Finance symbol."""
    s = clean_symbol(symbol)
    if s.startswith("^"):
        return s
    return f"{s}.NS"

st.set_page_config(
    page_title="Weinstein Commander Web",
    page_icon="🦁", layout="wide",
    initial_sidebar_state="expanded"
)

# BUG-11: load_dotenv called twice intentionally —
#   1st call: load env before auth check
#   2nd call: reload after auth writes refreshed token to .env
load_dotenv(override=True)

# Loud-failure guard: if the startup auto-refresh raises, keep the reason so the
# UI can show a red banner instead of silently degrading to a dead token.
_AUTH_REFRESH_ERROR = None

def check_auth_cached():
    global _AUTH_REFRESH_ERROR
    try: return ensure_valid_token()
    except Exception as e:
        _AUTH_REFRESH_ERROR = str(e)
        logger.warning(f"Auth check failed: {e}"); return None

check_auth_cached()
load_dotenv(override=True)   # Reload after token refresh

CLIENT_ID    = os.getenv("DHAN_CLIENT_ID")
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
_APP_DIR     = os.path.dirname(os.path.abspath(__file__))  # REC-4: absolute base dir
DB_FILE      = os.path.join(_APP_DIR, "trade_journal_v6.db")  # BUG-H1: absolute path

JOURNAL_RENAME_MAP = {
    'symbol':'Symbol','trade_type':'Type','stoploss':'StopLoss','target':'Target',
    'rationale':'Rationale','timeframe':'Timeframe','entry_date':'EntryDate',
    'quantity':'Quantity','buy_price':'BuyPrice','exit_date':'ExitDate',
    'exit_price':'ExitPrice','exit_reason':'ExitReason','status':'Status',
    'sector':'Sector','trade_quality':'Quality','compromises':'Compromises',
    'lessons':'Lessons','screenshot_path':'Screenshot','planned_rr':'PlannedRR',
    'ai_analysis':'AI Analysis'
}

# ── FORMATTERS ───────────────────────────────────────────────────────────────
def format_inr(number):
    """Indian comma format: 1,23,456.78"""
    try:
        if number is None: return "0"
        val = float(number); sign = "-" if val < 0 else ""; val = abs(val)
        s, *d = str("{:.2f}".format(val)).partition(".")
        r = ",".join([s[x-2:x] for x in range(-3, -len(s), -2)][::-1] + [s[-3:]])
        return sign + "".join([r] + d)
    except (ValueError, TypeError, AttributeError):
        return str(number)

def format_inr_int(number):
    """Indian comma format, no decimals: 1,23,456"""
    try:
        if number is None: return "0"
        val = float(number); sign = "-" if val < 0 else ""; val = abs(val)
        s = str(int(round(val)))
        r = ",".join([s[x-2:x] for x in range(-3, -len(s), -2)][::-1] + [s[-3:]])
        return sign + r
    except (ValueError, TypeError, AttributeError):
        return str(number)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
def get_script_path(f): return os.path.join(_SCRIPT_DIR, f)
def get_img_as_base64(file):
    with open(file, "rb") as f: return base64.b64encode(f.read()).decode()

# Check for local virtual environment Python first
_VENV_PY = os.path.join(_SCRIPT_DIR, ".venv", "Scripts", "python.exe")
if not os.path.exists(_VENV_PY):
    _VENV_PY = os.path.join(_SCRIPT_DIR, ".venv", "bin", "python")
_PYTHON_EXE = _VENV_PY if os.path.exists(_VENV_PY) else sys.executable

def launch_script(script_name, args=None, is_streamlit=False):
    try:
        full_path = get_script_path(script_name)
        if not os.path.exists(full_path):
            st.error(f"❌ File not found: {script_name}"); return
        env_setup = "set PYTHONIOENCODING=utf-8&&set PYTHONUTF8=1&&"
        cmd = f'{env_setup}streamlit run "{full_path}"' if is_streamlit else f'{env_setup}"{_PYTHON_EXE}" "{full_path}"'
        if args: cmd += f" {args}"
        os.system(f'start cmd /k "cd /d "{os.getcwd()}" && {cmd}"')
        st.toast(f"🚀 Launched: {script_name}")
    except Exception as e:
        st.error(f"Failed to launch: {e}")

# ── DATA FETCH (with caching) ─────────────────────────────────────────────────

def _get_dhan_client(force_refresh=False):
    """Fetch token with auto-refresh if expired."""
    try:
        from dhan_auth import get_valid_token
        load_dotenv(override=True)
        cid = os.getenv("DHAN_CLIENT_ID") or CLIENT_ID
        tok = get_valid_token(force_refresh=force_refresh)
        if not cid or not tok:
            return None, None
        return cid, tok
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Dhan auth error: {e}")
        return None, None

def get_dhanhq_client(force_refresh=False):
    """Returns (dhanhq_instance, DhanContext_instance) or (None, None)."""
    cid, tok = _get_dhan_client(force_refresh=force_refresh)
    if not cid or not tok:
        return None, None
    try:
        from dhanhq import DhanContext, dhanhq
        ctx = DhanContext(cid, tok)
        return dhanhq(ctx), ctx
    except Exception as e:
        # Fallback to older SDK init if DhanContext is not available
        try:
            from dhanhq import dhanhq
            return dhanhq(cid, tok), None
        except Exception as fallback_e:
            import logging
            logging.getLogger(__name__).error(f"Failed to init dhanhq: {e}")
            return None, None

def get_dhan_balance():
    """Fetch available cash balance from Dhan fund-limits API.

    IMPORTANT — Dhan API returns two different response shapes depending on
    the dhanhq library version in use:

      v1-style (older lib):  {'status': 'success', 'data': {balance_fields}}
      v2-style (newer lib):  {balance_fields}   ← flat dict, NO 'status' key

    Field name variants across Dhan API releases:
      'availableBalance'    — correct spelling (2024+)
      'availabelBalance'    — Dhan's own legacy typo (pre-2024)
      'withdrawableBalance' — alternate field
      'netAvailableMargin'  — margin-account variant

    NOTE: A balance of ₹0 is valid (all funds deployed). We return it as-is
    rather than treating it as an error.
    """
    _BALANCE_KEYS = (
        "availableBalance",    # correct spelling (current)
        "availabelBalance",    # Dhan's own legacy typo — DO NOT REMOVE
        "withdrawableBalance", # alternate field
        "netAvailableMargin",  # margin variant
    )
    try:
        from net_utils import is_internet_available
        if not is_internet_available():
            return 0.0, "SYSTEM OFFLINE"
        dhan, ctx = get_dhanhq_client()
        if not dhan:
            return 0.0, "AUTH MISSING"
        resp = dhan.get_fund_limits()

        if not isinstance(resp, dict):
            return 0.0, "API OFFLINE"

        # ── Determine which dict holds the balance fields ─────────────────────
        _status = resp.get('status')
        
        # --- Handle early expiry by forcing refresh ---
        if _status in ('failure', 'error') and any(k in str(resp).lower() for k in ["expired", "access token", "unauthorized", "invalid"]):
            import logging
            logging.getLogger(__name__).info("Dhan token rejected. Forcing refresh...")
            dhan, ctx = get_dhanhq_client(force_refresh=True)
            if dhan:
                resp = dhan.get_fund_limits()
                _status = resp.get('status') if isinstance(resp, dict) else "error"
            else:
                return 0.0, "AUTH RATE LIMIT (Wait 2 min)"

        if _status == 'success':
            # v1-style: nested under 'data'; fall back to root if 'data' absent
            data = resp.get('data') or resp
        elif _status in ('failure', 'error'):
            err = str(resp).lower()
            if any(k in err for k in ["expired", "access token", "unauthorized"]):
                return 0.0, "AUTH EXPIRED"
            return 0.0, "API OFFLINE"
        else:
            # No 'status' key at all → v2 flat response; use root dict directly
            data = resp

        # ── Try every known field name ────────────────────────────────────────
        for _key in _BALANCE_KEYS:
            if _key in data:
                try:
                    _v = float(data[_key] if data[_key] is not None else 0)
                    return _v, "SYSTEM ONLINE"   # ₹0 is valid (fully deployed)
                except (ValueError, TypeError):
                    continue

        # No recognisable field found — log for diagnosis
        logger.warning(
            "get_dhan_balance: none of %s found in response. "
            "Keys present: %s",
            _BALANCE_KEYS, list(data.keys()),
        )
        return 0.0, "SYSTEM ONLINE"

    except Exception as e:
        logger.warning("get_dhan_balance: %s", e)
        return 0.0, f"OFFLINE ({type(e).__name__})"

def get_live_holdings_stats():
    try:
        from net_utils import is_internet_available
        if not is_internet_available():
            return 0, 0.0, pd.DataFrame()
        dhan, ctx = get_dhanhq_client()
        if not dhan: return 0, 0.0, pd.DataFrame()
        
        # --- Fetch historical trades to map Entry Dates ---
        from datetime import date
        today_str = date.today().isoformat()
        entry_dates_map = {}
        try:
            trade_resp = dhan.get_trade_history(from_date="2024-01-01", to_date=today_str)
            if isinstance(trade_resp, dict) and trade_resp.get('status') == 'success':
                trades = trade_resp.get('data', [])
                for tr in trades:
                    if tr.get('transactionType') == 'BUY':
                        isin = tr.get('isin')
                        dt_str = tr.get('exchangeTime')
                        if isin and dt_str:
                            entry_dates_map[isin] = dt_str.split('T')[0]
        except Exception as e:
            logger.warning(f"Failed to fetch trade history: {e}")

        resp = dhan.get_holdings()
        if isinstance(resp, dict) and resp.get('status') == 'success':
            data = resp.get('data', [])
            valid_data = [item for item in data if float(item.get('totalQty', 0)) > 0]
            total_deployed = sum(
                float(item.get('avgCostPrice', 0)) * float(item.get('totalQty', 0))
                for item in valid_data
            )
            if valid_data:
                df_live = pd.DataFrame(valid_data).rename(columns={
                    'tradingSymbol': 'Symbol',
                    'avgCostPrice':  'BuyPrice',
                    'totalQty':      'Quantity',
                    'lastTradedPrice': 'LTP'
                })
                # BUG-01: also store cleaned symbol for reliable mapping
                df_live['CleanSymbol'] = df_live['Symbol'].apply(clean_symbol)
                # Apply EntryDate based on ISIN
                df_live['EntryDate'] = df_live.apply(lambda row: entry_dates_map.get(row.get('isin', ''), ''), axis=1)
            else:
                df_live = pd.DataFrame()
            return len(valid_data), total_deployed, df_live
        return 0, 0.0, pd.DataFrame()
    except Exception as e:
        logger.warning(f"get_live_holdings_stats: {e}")
        return 0, 0.0, pd.DataFrame()

@st.cache_data(ttl=60, show_spinner=False)
def get_batch_ltps(symbols_tuple):
    """BUG-12 / E-06: Batch yfinance fetch with correct column layout.
    IMPORTANT: Only adds keys for SUCCESSFUL fetches (val > 0).
    This lets callers use  live_map.get(sym) or fallback  correctly.
    group_by='column' (default) → raw['Close'] is a DataFrame keyed by ticker."""
    import data_provider as dp
    symbols = list(symbols_tuple)
    if not symbols: return {}

    result = {}
    
    try:
        batch_data = dp.fetch_batch_ohlcv(symbols, period="2d", interval="1d", use_cache=True, auto_adjust=True)
        
        for sym, raw in batch_data.items():
            if raw is not None and not raw.empty and "Close" in raw.columns:
                try:
                    val = float(raw['Close'].dropna().iloc[-1])
                    if val > 0: result[sym] = val
                except Exception as e:
                    logger.warning(f"LTP parse {sym}: {e}")
    except Exception as e:
        logger.warning(f"Batch LTP error: {e}")

    return result

@st.cache_data(ttl=86400, show_spinner=False)
def get_earnings_date_cached(sym):
    import yfinance as yf
    from datetime import date
    try:
        cal = yf.Ticker(f"{sym}.NS").calendar
        if isinstance(cal, dict) and 'Earnings Date' in cal and cal['Earnings Date']:
            edate = cal['Earnings Date'][0]
            if isinstance(edate, date): return edate
    except Exception as e:
        pass
    return None

@st.cache_data(ttl=300, show_spinner=False)
def fetch_sector_momentum_cached():
    """BUG-13 / E-03: Cached sector data + corrected acceleration + RRG quadrant.
    FIX: yfinance None-guard, MultiIndex flatten for benchmark, log suppression.

    P2 expansion (10 May 2026 — user feedback "Expand to the full list of sectors"):
    grew the sector universe from 11 → 19 by adding Healthcare, PSU Bank, Private
    Bank, Services, Consumption, Commodities, MNC and Financial Services.
    """
    # Tickers verified against Yahoo Finance 10 May 2026. ^CNXHEALTH and
    # ^CNXCOMMOD return 0 rows (Yahoo data gap); ^CNXFIN returns only 1 row
    # (effectively dead). Replaced or excluded accordingly so the rendered
    # table reflects what actually fetched, not a list with silent gaps.
    sector_indices = {
        # Core 11 (existing)
        'Nifty Bank':       '^NSEBANK',
        'Nifty IT':         '^CNXIT',
        'Nifty Pharma':     '^CNXPHARMA',
        'Nifty Auto':       '^CNXAUTO',
        'Nifty Metal':      '^CNXMETAL',
        'Nifty FMCG':       '^CNXFMCG',
        'Nifty Realty':     '^CNXREALTY',
        'Nifty Energy':     '^CNXENERGY',
        'Nifty Infra':      '^CNXINFRA',
        'Nifty PSE':        '^CNXPSE',
        'Nifty Media':      '^CNXMEDIA',
        # Expanded set (10 May 2026)
        'Nifty Fin Svc':    'NIFTY_FIN_SERVICE.NS',  # was ^CNXFIN (broken)
        'Nifty PSU Bank':   '^CNXPSUBANK',
        'Nifty Pvt Bank':   'NIFTY_PVT_BANK.NS',
        'Nifty Services':   '^CNXSERVICE',
        'Nifty Consumption':'^CNXCONSUM',
        'Nifty Commodities':'^CNXCMDT',              # was ^CNXCOMMOD (0 rows)
        'Nifty MNC':        '^CNXMNC',
        # Healthcare excluded — no Yahoo ticker serves daily data reliably
        # (^CNXHEALTH, ^NIFTYHEALTH, NIFTYHEALTHCARE.NS all return 0 rows).
        # Pharma (^CNXPHARMA above) covers the health-adjacent universe.
    }

    def _dl(sym):
        """Fetch weekly data using the centralized data provider."""
        import data_provider as dp
        try:
            df = dp.fetch_ohlcv(sym, period="6mo", interval="1wk",
                             auto_adjust=True, use_cache=True)
            if df is None or df.empty:
                return pd.DataFrame()
            return df
        except Exception:
            return pd.DataFrame()

    # ── Benchmark (Nifty 500) ─────────────────────────────────────────────────
    bench_df = _dl("^CRSLDX")
    if bench_df.empty:
        bench_df = _dl("^NSEI")
    bench_close = (
        bench_df["Close"].dropna()
        if not bench_df.empty and "Close" in bench_df.columns
        else pd.Series(dtype=float)
    )

    momentum_data = []
    for name, sym in sector_indices.items():
        try:
            sd = _dl(sym)
            if sd.empty or "Close" not in sd.columns or len(sd) < 10:
                continue
            close = sd["Close"].dropna()
            if len(close) < 9:
                continue

            # FORM-01 FIX: correct acceleration = recent_4w - prior_4w
            recent_4w = ((close.iloc[-1] / close.iloc[-5]) - 1) * 100 if len(close) >= 5 else 0.0
            prior_4w  = ((close.iloc[-5] / close.iloc[-9]) - 1) * 100 if len(close) >= 9 else 0.0
            rs_8w     = ((close.iloc[-1] / close.iloc[-9]) - 1) * 100 if len(close) >= 9 else 0.0
            accel     = recent_4w - prior_4w

            # E-03: RRG quadrant classification
            quadrant, rs_ratio, rs_momentum = "—", 100.0, 100.0
            if len(bench_close) >= 14:
                bench_aligned = bench_close.reindex(close.index, method="ffill").dropna()
                common        = close.index.intersection(bench_aligned.index)
                if len(common) >= 14:
                    rs_series = (close.loc[common] / bench_aligned.loc[common] * 100).dropna()
                    if len(rs_series) >= 14:
                        rs_sma      = rs_series.rolling(14).mean()
                        last_sma    = float(rs_sma.iloc[-1])
                        prev_sma    = float(rs_sma.iloc[-5]) if len(rs_sma) >= 5 else last_sma
                        rs_ratio    = (float(rs_series.iloc[-1])  / last_sma * 100) if last_sma else 100.0
                        rs_mom_prev = (float(rs_series.iloc[-5])  / prev_sma * 100) if (len(rs_series) >= 5 and prev_sma) else 100.0
                        rs_momentum = (rs_ratio / rs_mom_prev * 100) if rs_mom_prev else 100.0
                        if rs_ratio >= 100 and rs_momentum >= 100:
                            quadrant = "🟢 Leading"
                        elif rs_ratio >= 100:
                            quadrant = "🟡 Weakening"
                        elif rs_momentum >= 100:
                            quadrant = "🔵 Improving"
                        else:
                            quadrant = "🔴 Lagging"

            momentum_data.append({
                "Sector":      name,
                "4W %":        round(recent_4w, 1),
                "Prior 4W %":  round(prior_4w, 1),
                "8W %":        round(rs_8w, 1),
                "Acceleration":round(accel, 1),
                "RS-Ratio":    round(rs_ratio, 1),
                "RRG Quadrant":quadrant,
                "Signal": "🟢 Accelerating" if accel > 2 else "🔴 Decelerating" if accel < -2 else "🟡 Neutral",
            })
        except Exception as e:
            logger.debug(f"Sector {name} ({sym}): {e}")   # downgraded to DEBUG — not shown

    if momentum_data:
        return pd.DataFrame(momentum_data).sort_values("Acceleration", ascending=False)
    return pd.DataFrame()

@st.cache_data(ttl=300, show_spinner=False)
def fetch_macro_data_cached():
    """E-08: Macro indicators — VIX, INR, Crude, Gold, US10Y, Nifty 50, Nifty 500.

    P2.1 (10 May 2026 — user feedback #3 + #5): added Nifty 500 (^CRSLDX) so the
    Snapshot row and 12-month trend graph cover the broad market in addition to
    Nifty 50. The system screens Nifty 500; the Snapshot should reflect it.
    """
    tickers = {
        'India VIX':   '^INDIAVIX',
        'USD/INR':     'USDINR=X',
        'Brent Crude': 'BZ=F',
        'Gold':        'GC=F',
        'US 10Y':      '^TNX',
        'Nifty 50':    '^NSEI',
        'Nifty 500':   '^CRSLDX',   # NEW — broad market reference
    }
    import data_provider as dp
    result = {}
    for name, sym in tickers.items():
        try:
            d = dp.fetch_ohlcv(sym, period="1y", interval="1d", auto_adjust=True, use_cache=True)
            if d is None or d.empty: continue
            close = d['Close'].dropna()
            ltp   = float(close.iloc[-1])
            sma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else ltp
            sma200= float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else ltp
            pct_1m = ((ltp / close.iloc[-22]) - 1)*100 if len(close) >= 22 else 0
            pct_1y = ((ltp / close.iloc[0]) - 1)*100
            # Percentile rank vs 1-year range
            high1y, low1y = float(close.max()), float(close.min())
            pctile = ((ltp - low1y)/(high1y - low1y)*100) if high1y > low1y else 50
            stage = "Stage 2 ▲" if ltp > sma200 and sma200 < float(close.rolling(200).mean().iloc[-2] if len(close) >= 201 else sma200) * 1.001 \
                    else "Above 200MA" if ltp > sma200 else "Below 200MA"
            result[name] = {
                'LTP': ltp, 'SMA50': sma50, 'SMA200': sma200,
                '1M%': round(pct_1m, 1), '1Y%': round(pct_1y, 1),
                'Pctile': round(pctile, 0), 'Stage': stage,
                'series': close
            }
        except Exception as e:
            logger.warning(f"Macro {name}: {e}")
    return result

def load_journal_db():
    conn = None
    try:
        if not os.path.exists(DB_FILE): return pd.DataFrame()
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql("SELECT * FROM journal WHERE status='OPEN'", conn)
        df = df.rename(columns=JOURNAL_RENAME_MAP)
        if 'Quantity' in df.columns and 'BuyPrice' in df.columns:
            df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
            df['BuyPrice'] = pd.to_numeric(df['BuyPrice'], errors='coerce').fillna(0)
            df = df[df['Quantity'] > 0].copy()
        return df
    except Exception as e:
        logger.warning(f"load_journal_db: {e}"); return pd.DataFrame()
    finally:
        if conn: conn.close()

def load_closed_trades_db():
    conn = None
    try:
        if not os.path.exists(DB_FILE): return pd.DataFrame()
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql("SELECT * FROM journal WHERE status='CLOSED'", conn)
        return df.rename(columns=JOURNAL_RENAME_MAP)  # BUG-02: renamed once here only
    except Exception as e:
        logger.warning(f"load_closed_trades_db: {e}"); return pd.DataFrame()
    finally:
        if conn: conn.close()

# ── E-01: Portfolio Analytics helpers ────────────────────────────────────────

def compute_portfolio_analytics(df_closed, total_cap):
    """Compute Sharpe, Sortino, Max Drawdown, Profit Factor, Expectancy from closed trades."""
    if df_closed is None or df_closed.empty:
        return {}
    try:
        dfc = df_closed.copy()
        for col in ['ExitPrice','BuyPrice','Quantity']:
            dfc[col] = pd.to_numeric(dfc.get(col, 0), errors='coerce').fillna(0)
        dfc['PnL'] = (dfc['ExitPrice'] - dfc['BuyPrice']) * dfc['Quantity']
        dfc['PnL_pct'] = np.where(dfc['BuyPrice'] > 0, (dfc['ExitPrice'] - dfc['BuyPrice']) / dfc['BuyPrice'] * 100, 0)
        dfc['ExitDate'] = pd.to_datetime(dfc['ExitDate'], errors='coerce')
        dfc = dfc.dropna(subset=['ExitDate']).sort_values('ExitDate')

        pnls = dfc['PnL'].values
        wins  = pnls[pnls > 0];  losses = pnls[pnls <= 0]
        win_rate    = len(wins) / len(pnls) * 100 if len(pnls) > 0 else 0
        avg_win_rs  = float(wins.mean())   if len(wins)   > 0 else 0
        avg_loss_rs = float(losses.mean()) if len(losses) > 0 else 0
        profit_factor = abs(wins.sum() / losses.sum()) if losses.sum() != 0 else float('inf')
        expectancy    = (win_rate/100 * avg_win_rs) + ((1 - win_rate/100) * avg_loss_rs)

        # Equity curve for drawdown + Sharpe
        cum = np.cumsum(pnls)
        peak = np.maximum.accumulate(cum)
        dd   = cum - peak
        max_dd = float(dd.min())
        # Max Drawdown %: drawdown / peak_equity. Use starting equity + best point as peak.
        starting_equity = total_cap - float(pnls.sum())   # approx starting capital
        peak_equity     = starting_equity + max(float(cum.max()), 0)
        max_dd_pct      = (max_dd / peak_equity * 100) if peak_equity > 0 else 0

        # Sharpe / Sortino (using daily grouped PnL as proxy returns)
        daily = dfc.groupby(dfc['ExitDate'].dt.date)['PnL'].sum()
        daily_ret = daily / total_cap * 100  # daily return %
        rf_daily  = 6.5 / 252                 # 6.5% India T-bill
        excess    = daily_ret - rf_daily
        sharpe    = float(excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0
        downside  = daily_ret[daily_ret < rf_daily] - rf_daily
        sortino   = float(excess.mean() / downside.std() * np.sqrt(252)) if len(downside) > 0 and downside.std() > 0 else 0

        return {
            'total_trades': len(pnls), 'win_rate': round(win_rate, 1),
            'avg_win_rs': round(avg_win_rs, 0), 'avg_loss_rs': round(avg_loss_rs, 0),
            'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else '∞',
            'expectancy': round(expectancy, 0),
            'max_dd': round(max_dd, 0), 'max_dd_pct': round(max_dd_pct, 1),
            'sharpe': round(sharpe, 2), 'sortino': round(sortino, 2),
            'total_realized': round(float(pnls.sum()), 0)
        }
    except Exception as e:
        logger.warning(f"compute_portfolio_analytics: {e}"); return {}

# ── REC-8: Persistent NSE India session ──────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _nse_session_resource():
    """Build a requests.Session with the NSE India cookie handshake.

    REC-8: st.cache_resource creates this ONCE per Streamlit process —
    cookies are reused across option-chain data refreshes instead of
    re-doing the 2-step handshake on every 2-minute cache miss."""
    import requests as _req, time as _time
    _h = {
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection":      "keep-alive",
    }
    sess = _req.Session()
    sess.headers.update(_h)
    try:
        sess.get("https://www.nseindia.com", timeout=12)
        _time.sleep(0.6)
        sess.get("https://www.nseindia.com/option-chain", timeout=12)
        _time.sleep(0.4)
    except Exception:
        pass   # proceed — cookies may have partially set; fetch will retry
    return sess

# ── STARTUP DATA LOAD ─────────────────────────────────────────────────────────

balance, sys_status              = get_dhan_balance()
live_pos, live_dep, df_live_holdings = get_live_holdings_stats()
is_healthy, mkt_ltp, mkt_sma     = get_market_health("^CNX500")   # BUG-2 fix: yfinance ticker

df_active_global = load_journal_db()

# BUG-01 FIX: use CleanSymbol column so mapping always succeeds
if not df_active_global.empty and not df_live_holdings.empty and 'CleanSymbol' in df_live_holdings.columns:
    ltp_dict = dict(zip(df_live_holdings['CleanSymbol'], df_live_holdings['LTP']))
    df_active_global['LTP'] = df_active_global['Symbol'].map(ltp_dict).fillna(df_active_global['BuyPrice'])
elif not df_active_global.empty:
    df_active_global['LTP'] = df_active_global['BuyPrice']

if not df_active_global.empty:
    noise_count_g, noise_syms_g = get_noise_risk_stats(df_active_global)
else:
    noise_count_g, noise_syms_g = 0, []

h_color = "#00f260" if is_healthy        else "#ff4b4b"
h_text  = "BULLISH" if is_healthy        else "BEARISH (<200DMA)"
w_color = "#ff4b4b" if noise_count_g > 0 else "#00f260"
w_text  = f"⚠ {noise_count_g} AT RISK"  if noise_count_g > 0 else "✔ SECURE"
s_color = "#00f260" if sys_status == "SYSTEM ONLINE" else "#ff4b4b"

total_deployed_g = live_dep
open_pos         = live_pos
# FORM-03 FIX: total_cap = full portfolio equity (basis for all sizing/risk)
total_cap    = balance + total_deployed_g if (balance + total_deployed_g) > 0 else 5_000_000
deployed_pct = round((total_deployed_g / total_cap) * 100, 1) if total_cap > 0 else 0.0

for k, v in [
    ('page','DASHBOARD'), ('huntertab','SCANNERS'), ('watchlisttab','GENERATION'),
    ('commandtab','ACTIVEOPS'), ('ailabtab','PREFLIGHT'),
    ('macrotab','OVERVIEW'), ('autopsytab','OVERVIEW'),
    ('premarkettab','BRIEF'), ('postmarkettab','SUMMARY'), ('breadthtab','OVERVIEW'),
    ('newstab','MARKET'), ('fundamentalstab','SNAPSHOT'),
    ('port_holdings_raw', ''), ('port_value', 0.0),
]:
    if k not in st.session_state: st.session_state[k] = v

# ══════════════════════════════════════════════════════════════════════════════
#  CSS
# ══════════════════════════════════════════════════════════════════════════════
bg_str = ""
if os.path.exists("trading_bg_pro.png"):
    bg_img = get_img_as_base64("trading_bg_pro.png")
    bg_str = f', url("data:image/png;base64,{bg_img}")'

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=JetBrains+Mono:wght@400;600&family=Inter:wght@300;400;500&display=swap');
*, *::before, *::after {{ box-sizing: border-box; }}
.stApp {{
    background: linear-gradient(160deg,#050d18 0%,#0a1628 60%,#060e1a 100%){bg_str};
    background-attachment: fixed; background-size: cover;
    font-family: 'Inter', sans-serif; color: #c9d1d9;
}}
.block-container {{ padding: 0 !important; margin: 0 !important; max-width: 100% !important; }}
header, footer {{ visibility: hidden !important; }}
#MainMenu {{ visibility: hidden !important; }}
[data-testid="collapsedControl"] {{ display: none !important; }}
[data-testid="stSidebarCollapseButton"] {{ display: none !important; }}
button[kind="header"] {{ display: none !important; }}
section[data-testid="stSidebar"] > div:first-child > div > button {{ display: none !important; }}
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg,#0d1b2a 0%,#0a1628 100%) !important;
    border-right: 1px solid #1e3a5f !important;
    width: 270px !important; min-width: 270px !important; padding: 0 !important;
    transform: none !important; visibility: visible !important; display: block !important;
}}
[data-testid="stSidebar"] > div {{ padding: 0 !important; }}
[data-testid="stSidebarContent"] {{
    padding: 0 !important; overflow-y: auto !important; overflow-x: hidden !important;
    scrollbar-width: thin; scrollbar-color: #1e3a5f #0a1628;
}}
[data-testid="stSidebarContent"]::-webkit-scrollbar {{ width: 4px; }}
[data-testid="stSidebarContent"]::-webkit-scrollbar-track {{ background: #0a1628; }}
[data-testid="stSidebarContent"]::-webkit-scrollbar-thumb {{ background: #1e3a5f; border-radius: 2px; }}
.statusbar {{
    display: grid; grid-template-columns: repeat(8, 1fr);
    gap: 1px; background: #1e3a5f; border-bottom: 2px solid #1e3a5f;
}}
.sb-cell {{ background: #0a1628; padding: 6px 16px; display: flex; flex-direction: column; justify-content: center; }}
.sb-label {{ font-family: 'JetBrains Mono',monospace; font-size: 0.58rem; color: #5a8a9f; letter-spacing: 2px; text-transform: uppercase; }}
.sb-value {{ font-family: 'JetBrains Mono',monospace; font-size: 0.95rem; font-weight: 600; margin-top: 1px; letter-spacing: 0.5px; }}
.page-title {{
    font-family: 'Rajdhani',sans-serif; font-size: 1.5rem; font-weight: 700;
    letter-spacing: 3px; text-transform: uppercase; color: #e6edf3;
    border-left: 3px solid #238636; padding-left: 12px; margin: 14px 0 2px 0;
}}
.page-desc {{ font-size: 0.68rem; color: #5a8a9f; letter-spacing: 2px; text-transform: uppercase; margin: 0 0 12px 15px; font-family: 'JetBrains Mono',monospace; }}
.section-hdr {{
    font-family: 'JetBrains Mono',monospace; font-size: 0.62rem; color: #5a8a9f;
    letter-spacing: 3px; text-transform: uppercase; margin: 14px 0 8px 0;
    display: flex; align-items: center; gap: 10px;
}}
.section-hdr::after {{ content:''; flex:1; height:1px; background:#1e3a5f; }}
.section-sub-lbl {{
    font-family: 'Rajdhani', sans-serif; font-size: 1.0rem; font-weight: 600;
    color: #e6edf3; letter-spacing: 1.5px; text-transform: uppercase;
    padding: 5px 12px; background: rgba(88,166,255,0.08);
    border-left: 3px solid #58a6ff; border-radius: 0 4px 4px 0; margin-bottom: 8px;
}}
.metric-card {{
    background: #0d1b2a; border: 1px solid #1e3a5f; border-radius: 6px;
    padding: 10px 14px; text-align: center; position: relative;
}}
.metric-card:has(.expand-toggle:checked) {{
    position: fixed !important;
    top: 5% !important; left: 5% !important;
    width: 90vw !important; height: 90vh !important;
    z-index: 9999999 !important;
    background: #0d1117 !important;
    border: 2px solid #58a6ff !important;
    box-shadow: 0 0 50px rgba(0,0,0,0.9) !important;
    overflow-y: auto !important;
}}
.metric-card:has(.expand-toggle:checked) .expand-btn {{
    color: #ff4b4b !important;
}}
.expand-btn {{
    position: absolute; right: 8px; top: 8px; cursor: pointer; color: #8b949e;
    font-size: 1.1rem; transition: color 0.2s;
}}
.expand-btn:hover {{ color: #e6edf3; }}
.metric-label {{ font-family: 'JetBrains Mono',monospace; font-size: 0.58rem; color: #5a8a9f; letter-spacing: 2px; text-transform: uppercase; }}
.metric-value {{ font-family: 'JetBrains Mono',monospace; font-size: 1.1rem; font-weight: 600; color: #e6edf3; margin-top: 3px; }}
button[kind="secondary"] {{
    background: #0d1b2a !important; border: 1px solid #1e3a5f !important;
    border-radius: 5px !important; color: #c9d1d9 !important;
    font-family: 'Inter', sans-serif !important; font-size: 0.82rem !important;
    padding: 12px 16px !important; width: 100% !important;
    text-align: left !important; line-height: 1.6 !important;
    min-height: 76px !important; transition: all .15s ease !important;
}}
button[kind="secondary"]:hover {{
    background: #12243a !important; border-color: #238636 !important;
    color: #e6edf3 !important;
    box-shadow: inset 3px 0 0 #238636, 0 0 0 1px rgba(35,134,54,.2) !important;
}}
button[kind="secondary"] p {{ white-space: pre-line !important; text-align: left !important; margin: 0 !important; color: #c9d1d9 !important; font-size: 0.82rem !important; line-height: 1.6 !important; }}
button[kind="primary"] {{
    background: rgba(35,134,54,0.15) !important; border: 1px solid #238636 !important;
    border-radius: 5px !important; color: #3fb950 !important;
    font-family: 'Inter', sans-serif !important; font-size: 0.82rem !important;
    padding: 12px 16px !important; width: 100% !important;
    text-align: left !important; line-height: 1.6 !important;
    min-height: 76px !important; box-shadow: 0 0 0 1px rgba(35,134,54,.15) !important;
    transition: all .15s ease !important;
}}
button[kind="primary"]:hover {{
    background: rgba(35,134,54,0.25) !important;
    box-shadow: 0 0 16px rgba(35,134,54,.3), inset 3px 0 0 #3fb950 !important;
    color: #e6edf3 !important;
}}
button[kind="primary"] p {{ white-space: pre-line !important; text-align: left !important; margin: 0 !important; color: inherit !important; font-size: 0.82rem !important; line-height: 1.6 !important; }}
[data-testid="stSidebar"] button {{
    background: transparent !important; border: none !important; border-radius: 0 !important;
    border-left: 3px solid transparent !important; padding: 7px 16px !important;
    font-family: 'Inter', sans-serif !important; font-size: 0.85rem !important;
    font-weight: 500 !important; color: #8b949e !important; letter-spacing: 0.3px !important;
    text-transform: none !important; text-align: left !important; width: 100% !important;
    min-height: 0 !important; line-height: 1.3 !important; box-shadow: none !important;
    transition: all .12s ease !important;
}}
[data-testid="stSidebar"] button:hover {{ background: rgba(255,255,255,0.04) !important; color: #e6edf3 !important; border-left-color: #30363d !important; box-shadow: none !important; }}
[data-testid="stSidebar"] button[kind="primary"] {{ background: rgba(35,134,54,0.12) !important; color: #3fb950 !important; border-left-color: #238636 !important; font-weight: 600 !important; box-shadow: none !important; }}
[data-testid="stSidebar"] button[kind="primary"]:hover {{ background: rgba(35,134,54,0.20) !important; box-shadow: none !important; }}
[data-testid="stSidebar"] button p {{ white-space: nowrap !important; text-align: left !important; font-size: 0.85rem !important; color: inherit !important; }}
[data-testid="stRadio"] {{ margin: 1px 0 !important; }}
[data-testid="stRadio"] label {{
    background: transparent !important; border: none !important; border-radius: 0 !important;
    border-left: 3px solid transparent !important; padding: 6px 14px 6px 28px !important;
    font-family: 'Inter', sans-serif !important; font-size: 0.88rem !important;
    color: #adbac7 !important; cursor: pointer !important; transition: all .12s !important;
    margin: 0 !important; display: block !important;
}}
[data-testid="stRadio"] label:hover {{ background: rgba(255,255,255,0.04) !important; color: #e6edf3 !important; border-left-color: #30363d !important; }}
[data-testid="stRadio"] label[data-checked="true"] {{ background: rgba(35,134,54,0.10) !important; color: #3fb950 !important; border-left-color: #238636 !important; font-weight: 600 !important; }}
[role="radiogroup"] input {{ display: none !important; }}
[role="radiogroup"] [data-testid="stMarkdownContainer"] p {{ margin: 0 !important; font-size: 0.88rem !important; color: inherit !important; }}
/* Group labels (DAILY INTEL, MARKET INTEL, etc) — brighter, more legible.
   Was #3d5a6e (very dim — user feedback: "hardly visible"). Now #8aa4b8 with
   slightly larger size and weight. */
.sb-section-lbl {{ font-family: 'JetBrains Mono', monospace; font-size: 0.66rem; font-weight: 600; color: #8aa4b8; letter-spacing: 2.5px; text-transform: uppercase; padding: 10px 16px 5px; border-top: 1px solid #1e3a5f; margin-top: 2px; }}
/* Hide Streamlit's auto-generated multi-page nav at the top of the sidebar.
   The pages/ folder (1_home, 2_xray, 3_journal, 4_autopsy) was originally
   created for mobile access; we recreate the same links at the BOTTOM of the
   sidebar via st.page_link() so the top is reserved for the v4.0 status strip
   + Auto-Pilot button + main NAV_GROUPS. */
[data-testid="stSidebarNav"] {{ display: none !important; }}
/* Trim Streamlit's default sidebar top padding (~3rem of empty space above
   the first widget). User feedback: "Some empty space is still left at the
   top left". This pulls the WEINSTEIN logo to within ~12px of the top edge. */
section[data-testid="stSidebar"] > div:first-child {{ padding-top: 0.5rem !important; }}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{ padding-top: 0 !important; }}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"]:first-child {{ gap: 0.25rem !important; }}
/* Left-align all sidebar button labels (PRE-MARKET, DASHBOARD, MACRO, etc).
   Default Streamlit st.button text is centred via inline flex styles with high
   specificity. To win the cascade we (a) drop the button's display from flex
   to block, (b) override align/justify on every nested wrapper, and (c) force
   the inner <p> to text-align:left with full width.
   Note: Streamlit buttons render as: button > div > div[data-testid="stMarkdownContainer"] > p */
section[data-testid="stSidebar"] div[data-testid="stButton"] > button,
section[data-testid="stSidebar"] button[kind="primary"],
section[data-testid="stSidebar"] button[kind="secondary"],
section[data-testid="stSidebar"] button[kind="primaryFormSubmit"],
section[data-testid="stSidebar"] button[kind="secondaryFormSubmit"] {{
    display: block !important;
    text-align: left !important;
    padding-left: 32px !important; /* indent sub-menu items 16px past the group label */
    justify-content: flex-start !important;
    align-items: flex-start !important;
}}
section[data-testid="stSidebar"] div[data-testid="stButton"] > button > div,
section[data-testid="stSidebar"] div[data-testid="stButton"] > button > div > div,
section[data-testid="stSidebar"] div[data-testid="stButton"] > button [data-testid="stMarkdownContainer"] {{
    display: block !important;
    text-align: left !important;
    width: 100% !important;
    justify-content: flex-start !important;
}}
section[data-testid="stSidebar"] div[data-testid="stButton"] > button p {{
    text-align: left !important;
    width: 100% !important;
    margin: 0 !important;
}}
[data-testid="metric-container"] {{ background: #0d1b2a !important; border: 1px solid #1e3a5f !important; border-radius: 6px !important; padding: 10px 14px !important; }}
[data-testid="metric-container"] label {{ font-family: 'JetBrains Mono',monospace !important; font-size: 0.60rem !important; color: #5a8a9f !important; letter-spacing: 2px !important; text-transform: uppercase !important; }}
[data-testid="metric-container"] [data-testid="stMetricValue"] {{ font-family: 'JetBrains Mono',monospace !important; font-size: 1.2rem !important; font-weight: 600 !important; color: #e6edf3 !important; }}
[data-testid="stDataFrame"] {{ border: 1px solid #1e3a5f !important; border-radius: 6px !important; }}
iframe {{ border-radius: 6px !important; }}
hr {{ border-color: #1e3a5f !important; margin: 8px 0 !important; }}
[data-testid="stToast"] {{ background: #0d1b2a !important; border: 1px solid #238636 !important; border-radius: 6px !important; color: #c9d1d9 !important; font-family: 'Inter', sans-serif !important; }}
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {{
    background: #0a1628 !important; border: 1px solid #1e3a5f !important;
    border-radius: 4px !important; color: #e6edf3 !important;
    font-family: 'JetBrains Mono',monospace !important; font-size: 0.82rem !important;
}}
[data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus {{ border-color: #238636 !important; box-shadow: 0 0 0 2px rgba(35,134,54,.2) !important; }}
label {{ color: #8b949e !important; font-size: 0.75rem !important; }}
[data-testid="stSelectbox"] > div > div {{ background: #0a1628 !important; border-color: #1e3a5f !important; color: #e6edf3 !important; border-radius: 4px !important; }}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style="padding:12px 16px 10px;border-bottom:1px solid #1e3a5f;background:#080f1a;">
      <div style="font-family:'Rajdhani',sans-serif;font-size:1.3rem;font-weight:700;color:#e6edf3;letter-spacing:1.5px;">🦁 WEINSTEIN</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:0.55rem;color:#3d5a6e;letter-spacing:3px;margin-top:2px;">COMMANDER WEB v4.0</div>
    </div>
    """, unsafe_allow_html=True)

    # ── TOP STATUS STRIP — always visible, no scroll needed ──────────────────
    # Per user feedback: API Health + Available Capital must be at the top, not
    # buried below all menu groups. Token is also surfaced here as a compact
    # color indicator; the detailed Token expander (with paste-new-token) stays
    # at its original bottom location for the rare manual-refresh action.
    try:
        _ts_top = dhan_token_status() if _BROKER_OK else {"valid": False, "expires_at": "—"}
        _tk_top_valid = _ts_top.get("valid", False)
        _tk_top_col   = "#00f260" if _tk_top_valid else "#ff4b4b"
        _tk_top_label = "VALID" if _tk_top_valid else "EXPIRED"
    except Exception:
        _tk_top_valid, _tk_top_col, _tk_top_label = False, "#3d5a6e", "—"

    st.markdown(f"""
    <div style="padding:8px 14px 6px;border-bottom:1px solid #1e3a5f;background:#0a131f;font-family:'JetBrains Mono',monospace;">
      <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;">
        <span style="font-size:0.55rem;color:#3d5a6e;letter-spacing:2px;">API HEALTH</span>
        <span style="font-size:0.72rem;font-weight:600;color:{s_color};">{sys_status}</span>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;">
        <span style="font-size:0.55rem;color:#3d5a6e;letter-spacing:2px;">CAPITAL</span>
        <span style="font-size:0.82rem;font-weight:600;color:#e6edf3;">₹{format_inr_int(balance)}</span>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:baseline;">
        <span style="font-size:0.55rem;color:#3d5a6e;letter-spacing:2px;">TOKEN</span>
        <span style="font-size:0.68rem;font-weight:600;color:{_tk_top_col};">{_tk_top_label}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # 🤖 Run Auto-Pilot — direct shortcut to the Bible §6E watchlist pipeline.
    # Per user feedback (point F): Auto-Pilot, Dashboard's old "Complete Workflow"
    # button, and the WATCHLIST tab's "Run Full Auto-Pilot" button must all call
    # the SAME script (run_pipeline.py). This sidebar button is the canonical
    # entry point — clicking it (a) launches the pipeline subprocess and (b)
    # navigates to WATCHLIST so the user lands on the page that consumes the
    # output. The Dashboard "Complete Workflow" button has been removed.
    if st.button("🤖 Run Auto-Pilot", key="sb_auto_pilot",
                 use_container_width=True, type="secondary",
                 help="Run Full Auto-Pilot pipeline: Scanners → Conviction Filter → Combined Watchlist → TradingView Sync"):
        try:
            launch_script("run_pipeline.py")
        except Exception as _ape:
            st.error(f"Auto-Pilot launch failed: {_ape}")
        st.session_state["page"] = "WATCHLIST"
        st.session_state["wf_run_trigger"] = True   # consumed by WATCHLIST page so it scrolls to the run-status section
        st.rerun()

    # ── v4.0 Grouped Navigation ─────────────────────────────────────────────
    EXTERNAL_PAGES = {'JOURNAL': 'dhan_journal_v7.py'}
    # X-RAY, TV SIDECAR and PYRAMID are inline pages (no external script needed)

    # NAV reorg (10 May 2026):
    #   • New STATE OF MARKET group at the top (MACRO + BREADTH + NEWS) — these
    #     gate every other workflow; per Bible §7D Steps 1–2 they should be the
    #     first thing the trader checks each morning.
    #   • DAILY INTEL keeps the time-of-day pages; NEWS moved out (it's market
    #     state, not a daily-routine page).
    #   • AI LAB moved from ACTIVE TRADING → ANALYSIS (its tabs — Pre-Flight,
    #     Generative, Workflows, Weekly Report — are research/analysis, not
    #     intraday execution).
    #   • RESEARCH renamed DISCOVERY (Bible terminology).
    #   • EXECUTION group is what you actually do during market hours.
    NAV_GROUPS = [
        ("🎛️  CONTROL CENTER", [
            ("📊 DASHBOARD",   "DASHBOARD"),
            ("🗂️ PORTFOLIO",   "PORTFOLIO"),
            ("⚡ COMMAND",     "COMMAND"),
            ("🛡️ RISK SHIELD", "RISK SHIELD"),
            ("⚖️ PYRAMID / TRIM", "PYRAMID"),
        ]),
        ("🩺  STATE OF MARKET", [
            ("🌐 MACRO",       "MACRO"),
            ("📈 BREADTH",     "BREADTH"),
            ("📰 NEWS",        "NEWS"),
        ]),
        ("📅  DAILY INTEL", [
            ("🌅 PRE-MARKET",  "PRE-MARKET"),
            ("🌙 POST-MARKET", "POST-MARKET"),
        ]),
        ("🔍  DISCOVERY", [
            ("🎯 HUNTER",      "HUNTER"),
            ("📋 WATCHLIST",   "WATCHLIST"),
            # X-Ray absorbed Fundamentals on 10 May 2026 (same fundamental_hub
            # backend, overlapping Snapshot + Scorecard tabs; Screen tab from
            # Fundamentals now lives as the 5th tab in X-Ray).
            ("🧬 X-RAY",       "X-RAY"),
            # ETF Trading System (Phase 4, added 11 May 2026) — sector rotation
            # + asset-class regime + RRG. Sits in DISCOVERY because it's a
            # research/selection workflow, parallel to HUNTER for stocks.
            ("🪙 ETF",         "ETF"),
        ]),
        ("⚡  EXECUTION", [
            ("📐 OPTIONS",     "OPTIONS"),
            ("📺 TV SIDECAR",  "TV SIDECAR"),
            ("🪙 GOLDEN MATCHER", "GOLDEN MATCHER"),
        ]),
        ("🔬  ANALYSIS", [
            ("🔬 AUTOPSY",     "AUTOPSY"),
            ("📈 BACKTEST",    "BACKTEST"),
            ("🧪 AI LAB",      "AI LAB"),
        ]),
        ("📁  RECORDS", [
            ("📓 JOURNAL",     "JOURNAL"),
        ]),
    ]

    for group_label, group_pages in NAV_GROUPS:
        st.markdown(f'<div class="sb-section-lbl">{group_label}</div>', unsafe_allow_html=True)
        for display_name, page_key in group_pages:
            btn_type = "primary" if st.session_state.page == page_key else "secondary"
            if st.button(display_name, key=f"nav_{page_key}",
                         use_container_width=True, type=btn_type):
                if page_key in EXTERNAL_PAGES:
                    launch_script(EXTERNAL_PAGES[page_key], is_streamlit=True)
                else:
                    st.session_state.page = page_key
                    st.rerun()

    # (Watchlist quick-access removed to declutter sidebar)

    page = st.session_state.page

    # ── Bottom: Token detail + paste-new-token (full status moved to top strip) ──
    if sys_status == "AUTH EXPIRED":
        st.warning("⚠️ Dhan token expired — paste new below.")

    if _BROKER_OK:
        try:
            _ts = dhan_token_status()
            _tk_valid   = _ts.get("valid", False)
            _tk_expires = _ts.get("expires_at", "unknown")
            with st.expander(f"🔑 Token detail (expires {_tk_expires})",
                             expanded=(not _tk_valid)):
                _new_tok = st.text_area("Paste new Dhan Access Token", height=80,
                                        key="sb_new_token",
                                        placeholder="From web.dhan.co → API → Access Token")
                if st.button("💾 Save Token", key="sb_save_token", type="primary"):
                    if _new_tok.strip():
                        try:
                            from dotenv import set_key as _sk
                            import os as _os
                            _env_p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".env")
                            _sk(_env_p, "DHAN_ACCESS_TOKEN", _new_tok.strip())
                            _os.environ["DHAN_ACCESS_TOKEN"] = _new_tok.strip()
                            st.success("✅ Token saved — reload the app")
                        except Exception as _te:
                            st.error(f"Save failed: {_te}")
                    else:
                        st.warning("Paste a token first.")
        except Exception:
            pass

    # ── Bottom: Mobile / Standalone page links ────────────────────────────
    # These are the originally-mobile-friendly standalone Streamlit pages
    # (pages/1_home.py etc.). Streamlit auto-renders them at the TOP of the
    # sidebar; we hide that with CSS (see [data-testid="stSidebarNav"] rule
    # above) and re-render them here at the bottom so the top is reserved
    # for status + nav. Using st.page_link() preserves all routing behaviour.
    st.markdown('<div class="sb-section-lbl">📱 Mobile / Standalone</div>', unsafe_allow_html=True)
    try:
        st.page_link("pages/1_home.py",    label="🏠 Home",    icon=None)
        st.page_link("pages/2_xray.py",    label="🧬 X-Ray",   icon=None)
        st.page_link("pages/3_journal.py", label="📓 Journal", icon=None)
        st.page_link("pages/4_autopsy.py", label="🔬 Autopsy", icon=None)
    except Exception:
        # Fallback for older Streamlit versions: just show plain text references
        st.caption("pages/1_home.py · pages/2_xray.py · pages/3_journal.py · pages/4_autopsy.py")

# ══════════════════════════════════════════════════════════════════════════════
#  TOP STATUS BAR
# ══════════════════════════════════════════════════════════════════════════════
# v4.0 extended status bar — fetch VIX + FII for top bar
# C1 sweep: VIX hits on every page render — route through data_provider so a
# single 15-min cache window covers all reruns.
try:
    from net_utils import is_internet_available
    _vix_bar = pd.DataFrame()
    if is_internet_available():
        import data_provider as _dp_vix
        _vix_bar = _dp_vix.fetch_ohlcv("^INDIAVIX", period="5d", interval="1d")
    if not _vix_bar.empty:
        if isinstance(_vix_bar.columns, pd.MultiIndex): _vix_bar.columns = _vix_bar.columns.get_level_values(0)
        _vix_val = float(_vix_bar["Close"].iloc[-1])
        _vix_col = "#ff4b4b" if _vix_val > 20 else "#e3b341" if _vix_val > 15 else "#00f260"
        _vix_txt = f"{_vix_val:.1f}"
    else:
        _vix_val, _vix_col, _vix_txt = 0, "#5a8a9f", "N/A"
except Exception:
    _vix_val, _vix_col, _vix_txt = 0, "#5a8a9f", "N/A"

_fii_txt, _fii_col = "–", "#5a8a9f"
if _HUB_OK:
    try:
        _fii_df = fetch_fii_dii_data()
        if not _fii_df.empty and "fii_net" in _fii_df.columns:
            _fii_net = float(_fii_df["fii_net"].iloc[-1])
            _dii_net = float(_fii_df["dii_net"].iloc[-1]) if "dii_net" in _fii_df.columns else 0.0
            # Combined display per user feedback (#4): one cell, FII / DII separated by /
            _fii_arrow = "▲" if _fii_net >= 0 else "▼"
            _dii_arrow = "▲" if _dii_net >= 0 else "▼"
            _fii_part_col = "#00f260" if _fii_net >= 0 else "#ff4b4b"
            _dii_part_col = "#00f260" if _dii_net >= 0 else "#ff4b4b"
            # HTML inline-coloured spans so each side colours independently
            _fii_txt = (
                f"<span style='color:{_fii_part_col};'>{_fii_arrow} ₹{abs(_fii_net):,.0f}Cr</span>"
                f"<span style='color:#5a8a9f;'> / </span>"
                f"<span style='color:{_dii_part_col};'>{_dii_arrow} ₹{abs(_dii_net):,.0f}Cr</span>"
            )
            # Net colour for the cell border-tinge: dominant flow direction
            _fii_col = "#00f260" if (_fii_net + _dii_net) >= 0 else "#ff4b4b"
    except Exception:
        pass

# Regime text — composite verdict from market_regime.compute_regime() persisted
# in regime_state.json by the daily scheduler. Replaces the prior breadth-only
# build_breadth_regime() label which could read "BULL HEALTHY" even while the
# benchmark was below 200DMA with a death cross. The breadth-only label is
# still surfaced (correctly named) in the EOD "Breadth Regime" panel.
_regime_txt, _regime_col = "–", "#5a8a9f"
_regime_age_html = ""   # freshness sub-line for the Market Regime tile (filled below)
try:
    import json as _json, os as _os
    from datetime import datetime as _dt, timedelta as _td
    _rs_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                              "regime_state.json")
    _stale = True
    if _os.path.exists(_rs_path):
        with open(_rs_path, "r", encoding="utf-8") as _f:
            _rs = _json.load(_f) or {}
        _last = (_rs.get("last") or {})
        _v = (_last.get("verdict") or "").strip()
        _s = _last.get("score")
        _comp_str = _last.get("computed_at")
        if _v:
            _regime_txt = f"{_v} ({_s}/10)" if _s is not None else _v
            _vu = _v.upper()
            if "BULL" in _vu or "RISK-ON" in _vu:
                _regime_col = "#00f260"
            elif "BEAR" in _vu or "DEFENSIVE" in _vu:
                _regime_col = "#ff4b4b"
            else:
                _regime_col = "#e3b341"
        if _comp_str:
            try:
                _comp_dt = _dt.fromisoformat(_comp_str)
                # If calculated today and less than 12 hours ago, it is fresh
                if _dt.now() - _comp_dt < _td(hours=12) and _comp_dt.date() == _dt.now().date():
                    _stale = False
                # Freshness sub-line: "as of HH:MM · Xh ago" (+ amber STALE flag).
                _mins = int((_dt.now() - _comp_dt).total_seconds() // 60)
                if _mins < 60:
                    _age = f"{_mins}m ago"
                elif _mins < 1440:
                    _age = f"{_mins // 60}h ago"
                else:
                    _age = f"{_mins // 1440}d ago"
                _age_col = "#e3b341" if _stale else "#5a8a9f"
                _flag = " · <b>STALE</b>" if _stale else ""
                _regime_age_html = (
                    f'<div style="font-family:JetBrains Mono,monospace;font-size:0.5rem;'
                    f'color:{_age_col};margin-top:1px;">as of {_comp_dt:%H:%M} · {_age}{_flag}</div>'
                )
            except Exception:
                pass
    if _stale:
        from net_utils import is_internet_available
        if is_internet_available():
            import threading as _threading
            import market_regime as _mr
            # PC-HANG FIX (20 Jun 2026): acquire the process-wide lock in the MAIN
            # thread BEFORE spawning. Streamlit reruns the script sequentially, so
            # this check is race-free; the lock stays held for the thread's whole
            # lifetime, so reruns that happen while an update is in-flight do NOT
            # spawn another thread. (Old code spawned a thread per rerun and made
            # the lock lazily inside the thread -> thread/socket storm -> freeze.)
            _lk = getattr(_mr, "_regime_update_lock", None)
            if _lk is not None and _lk.acquire(blocking=False):
                def _silent_regime_update():
                    try:
                        _bm = None
                        _ad = None
                        try:
                            import breadth_engine as _be
                            _bm = _be.calculate_breadth_metrics()
                            _ad = _be.load_or_bootstrap_ad_history(min_rows=40)
                        except Exception:
                            pass
                        _mr.compute_regime(_bm, _ad, persist=True)
                    except Exception:
                        pass
                    finally:
                        try:
                            _mr._regime_update_lock.release()
                        except Exception:
                            pass
                _threading.Thread(target=_silent_regime_update, daemon=True).start()
except Exception:
    pass

# Fallback: if regime_state.json is missing (fresh install / scheduler hasn't
# run yet) fall back to the breadth-only label so the pill isn't blank.
if _regime_txt == "–" and _BREADTH_OK:
    try:
        _br = calculate_breadth_metrics()
        _regime_txt = build_breadth_regime(_br)
        _regime_col = "#00f260" if "BULL" in _regime_txt else "#ff4b4b" if "BEAR" in _regime_txt else "#e3b341"
    except Exception:
        pass

st.markdown(f"""
<div class="statusbar">
  <div class="sb-cell"><div class="sb-label">Nifty 500</div><div class="sb-value" style="color:{h_color};">{h_text}</div></div>
  <div class="sb-cell"><div class="sb-label">Market Regime</div><div class="sb-value" style="color:{_regime_col};font-size:0.75rem;">{_regime_txt}</div>{_regime_age_html}</div>
  <div class="sb-cell"><div class="sb-label">India VIX</div><div class="sb-value" style="color:{_vix_col};">{_vix_txt}</div></div>
  <div class="sb-cell"><div class="sb-label">FII / DII (prev)</div><div class="sb-value" style="font-size:0.74rem;">{_fii_txt}</div></div>
  <div class="sb-cell"><div class="sb-label">Risk Watchdog</div><div class="sb-value" style="color:{w_color};">{w_text}</div></div>
  <div class="sb-cell"><div class="sb-label">Deployment</div><div class="sb-value" style="color:#58a6ff;">{deployed_pct}%</div></div>
  <div class="sb-cell"><div class="sb-label">Open Positions</div><div class="sb-value" style="color:#e6edf3;">{open_pos}</div></div>
  <div class="sb-cell"><div class="sb-label">Total Deployed</div><div class="sb-value" style="color:#e3b341;">₹{format_inr(total_deployed_g)}</div></div>
</div>
""", unsafe_allow_html=True)

page = st.session_state.page

def section(label):
    st.markdown(f'<div class="section-hdr">{label}</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# ET + Moneycontrol (paid) feed helper — used by NEWS, PRE-MARKET, POST-MARKET
# Added 10 May 2026: leverages user's paid ET Prime + MC Pro subscriptions via
# cookie-loaded sessions in paid_news_cookies.py. Renders a 4-column responsive
# grid of headline cards. `keyword_filter` lets PRE/POST-MARKET pages narrow to
# pre-market or EOD-related articles only.
# ─────────────────────────────────────────────────────────────────────────────
def _render_paid_news_grid(key_prefix: str,
                           keyword_filter: list = None,
                           default_limit: int = 40,
                           show_recos_only: bool = False,
                           caption: str = "") -> None:
    """Render ET + MC headlines from paid sessions in a 4-column grid.

    Parameters
    ----------
    key_prefix       : Streamlit widget-key prefix (must be unique per call site)
    keyword_filter   : Optional list[str] — only show items whose title contains
                       at least one of these (case-insensitive). e.g.
                       ["pre-market","premarket","gift nifty","opening bell"] for
                       Pre-Market page; ["closing bell","eod","market wrap",
                       "post-market","postmarket"] for Post-Market page.
    default_limit    : How many headlines per source to fetch.
    show_recos_only  : If True, only render items where action ∈ BUY/HOLD/SELL.
    caption          : Optional intro line.
    """
    try:
        import et_scraper as _et
        import mc_scraper as _mc
        import paid_news_cookies as _pnc
    except ImportError as _ie:
        st.info(f"ET/MC scraper modules not available: {_ie}")
        return

    # Cookie status row
    _cs = _pnc.cookie_status()
    _et_meta = _cs.get("et", {})
    _mc_meta = _cs.get("mc", {})
    _csa, _csb, _csc = st.columns([1, 1, 4])
    with _csa:
        _icon = "🟢" if _et_meta.get("fresh") else ("🟡" if _et_meta.get("present") else "🔴")
        _age  = _et_meta.get("age_days")
        _age_s = f"{_age:.1f}d" if _age is not None else "—"
        st.markdown(
            f'<div style="font-family:JetBrains Mono,monospace;font-size:0.74rem;color:#c9d1d9">'
            f'{_icon} ET cookies · {_et_meta.get("cookie_count",0)} · age {_age_s}</div>',
            unsafe_allow_html=True)
    with _csb:
        _icon = "🟢" if _mc_meta.get("fresh") else ("🟡" if _mc_meta.get("present") else "🔴")
        _age  = _mc_meta.get("age_days")
        _age_s = f"{_age:.1f}d" if _age is not None else "—"
        st.markdown(
            f'<div style="font-family:JetBrains Mono,monospace;font-size:0.74rem;color:#c9d1d9">'
            f'{_icon} MC cookies · {_mc_meta.get("cookie_count",0)} · age {_age_s}</div>',
            unsafe_allow_html=True)
    with _csc:
        if not (_et_meta.get("present") or _mc_meta.get("present")):
            st.warning("No paid cookies loaded. Run `python setup_paid_news_cookies.py` "
                       "to enable ET Prime + MC Pro feeds.")
            return

    if caption:
        st.caption(caption)

    _ctrl1, _ctrl2, _ctrl3 = st.columns([1, 1, 4])
    _force = _ctrl1.button("🔄 Refresh", key=f"{key_prefix}_refresh", type="primary")
    _src_pick = _ctrl2.selectbox("Source", ["Both", "ET only", "MC only"],
                                 index=0, key=f"{key_prefix}_src")
    _limit = _ctrl3.slider("Headlines per source", 10, 80, default_limit,
                           step=10, key=f"{key_prefix}_lim")

    # Fetch
    items: list = []
    with st.spinner("Fetching ET + MC paid feeds..."):
        if _src_pick in ("Both", "ET only") and _et_meta.get("present"):
            try:
                items.extend(_et.fetch_recos(limit=_limit, force=_force))
            except Exception as _ee:
                st.warning(f"ET fetch failed: {_ee}")
        if _src_pick in ("Both", "MC only") and _mc_meta.get("present"):
            try:
                items.extend(_mc.fetch_news_listing(limit=_limit, force=_force))
            except Exception as _me:
                st.warning(f"MC fetch failed: {_me}")

    # Optional keyword filter
    if keyword_filter:
        kws = [k.lower() for k in keyword_filter]
        items = [it for it in items
                 if any(k in (it.get("title") or "").lower() for k in kws)]

    # Optional recos-only filter
    if show_recos_only:
        items = [it for it in items
                 if it.get("action") in ("STRONG_BUY", "BUY", "HOLD",
                                          "SELL", "STRONG_SELL")]

    # Dedupe by URL
    _seen = set(); _deduped = []
    for it in items:
        u = it.get("url")
        if not u or u in _seen:
            continue
        _seen.add(u); _deduped.append(it)
    items = _deduped

    if not items:
        st.info("No headlines matched. Try clicking **Refresh**, broadening the "
                "filter, or checking that cookies are still fresh.")
        return

    # Counts strip
    _bull = sum(1 for it in items if it.get("action") in ("BUY", "STRONG_BUY"))
    _bear = sum(1 for it in items if it.get("action") in ("SELL", "STRONG_SELL"))
    _hold = sum(1 for it in items if it.get("action") == "HOLD")
    _other = len(items) - _bull - _bear - _hold
    _m1, _m2, _m3, _m4, _m5 = st.columns(5)
    _m1.metric("Headlines", len(items))
    _m2.metric("🟢 Buy/StrongBuy", _bull)
    _m3.metric("🔴 Sell/StrongSell", _bear)
    _m4.metric("⚪ Hold", _hold)
    _m5.metric("📰 News", _other)

    st.markdown("---")

    # Action → colour map
    _ACT_COL = {
        "STRONG_BUY":  "#00f260",
        "BUY":         "#3fb950",
        "HOLD":        "#e3b341",
        "SELL":        "#ff7b72",
        "STRONG_SELL": "#ff4b4b",
        "OTHER":       "#8b949e",
    }
    _ACT_LBL = {
        "STRONG_BUY":  "🟢 STRONG BUY",
        "BUY":         "🟢 BUY",
        "HOLD":        "🟡 HOLD",
        "SELL":        "🔴 SELL",
        "STRONG_SELL": "🔴 STRONG SELL",
        "OTHER":       "📰 NEWS",
    }
    _SRC_COL = {"Economic Times": "#ff7b72", "Moneycontrol": "#58a6ff"}

    # 4-column grid
    _N_COLS = 4
    for _i in range(0, len(items), _N_COLS):
        _row = items[_i:_i + _N_COLS]
        _cols = st.columns(_N_COLS, gap="small")
        for _col, _it in zip(_cols, _row):
            _act    = _it.get("action") or "OTHER"
            _act_col = _ACT_COL.get(_act, "#8b949e")
            _act_lbl = _ACT_LBL.get(_act, _act)
            _src     = _it.get("source", "")
            _src_col = _SRC_COL.get(_src, "#8b949e")
            _brk     = _it.get("brokerage") or ""
            _ttl     = (_it.get("title") or "").replace("<","&lt;").replace(">","&gt;")
            _url     = _it.get("url") or "#"
            _ts      = (_it.get("fetched_at") or "")[:16]
            _stocks  = _it.get("stocks_mentioned") or []
            _stk_html = ""
            if _stocks:
                _stk_pills = " ".join(
                    f'<span style="background:#1c2937;color:#58a6ff;padding:1px 6px;'
                    f'border-radius:8px;font-size:0.62rem;margin-right:3px">{s}</span>'
                    for s in _stocks[:4]
                )
                _stk_html = f'<div style="margin-top:5px">{_stk_pills}</div>'
            _brk_html = (
                f'<div style="font-size:0.66rem;color:#adbac7;margin-top:4px">'
                f'🏛 {_brk}</div>' if _brk else ""
            )
            with _col:
                st.markdown(
                    f'<div class="metric-card" style="padding:10px 12px;'
                    f'margin-bottom:8px;min-height:130px;border-left:3px solid {_act_col}">'
                    f'<div style="display:flex;justify-content:space-between;'
                    f'align-items:center;margin-bottom:5px">'
                    f'<span style="color:{_act_col};font-size:0.62rem;'
                    f'font-weight:700;letter-spacing:0.5px">{_act_lbl}</span>'
                    f'<span style="color:{_src_col};font-size:0.6rem;'
                    f'font-weight:600">{_src}</span></div>'
                    f'<div style="font-size:0.78rem;color:#e6edf3;line-height:1.3">'
                    f'<a href="{_url}" target="_blank" '
                    f'style="color:#e6edf3;text-decoration:none">{_ttl}</a></div>'
                    f'{_brk_html}{_stk_html}'
                    f'<div style="font-size:0.58rem;color:#5a8a9f;margin-top:6px">{_ts}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )


def _render_analyst_sentiment_panel(csv_path: str, symbol_col: str,
                                     key_prefix: str, label: str,
                                     extra_caption: str = "") -> None:
    """Reusable Analyst Sentiment block.

    Renders a collapsible-by-button section that pulls per-symbol ET + MC
    consensus for the top N picks in a results CSV. Used by Bull / Recovery /
    X-Ray / Golden Matcher tabs to avoid copy-paste of ~70 lines.

    Parameters
    ----------
    csv_path     : Absolute path to the screener's output CSV.
    symbol_col   : Column name holding the NSE ticker (varies by screener).
    key_prefix   : Streamlit widget-key prefix (must be unique per call site).
    label        : Section label, e.g. "Bull Screener Picks".
    extra_caption: Optional secondary caption line.
    """
    import os as _os_loc, pandas as _pd_loc
    section(f"📊 Analyst Sentiment — {label}  (ET + Moneycontrol, paid)")

    try:
        import analyst_sentiment as _ans_loc
    except ImportError:
        st.info("analyst_sentiment module unavailable.")
        return

    _h = _ans_loc.health_check()
    _et_ok = _h.get("et", {}).get("ok", False)
    _mc_ok = _h.get("mc", {}).get("ok", False)
    _hc1, _hc2 = st.columns(2)
    _hc1.markdown(
        f'<div style="font-family:JetBrains Mono,monospace;font-size:0.78rem">'
        f'ET: <b style="color:{"#00f260" if _et_ok else "#ff4b4b"}">'
        f'{"✓ live" if _et_ok else "✗ down"}</b></div>',
        unsafe_allow_html=True)
    _hc2.markdown(
        f'<div style="font-family:JetBrains Mono,monospace;font-size:0.78rem">'
        f'MC: <b style="color:{"#00f260" if _mc_ok else "#ff4b4b"}">'
        f'{"✓ live" if _mc_ok else "✗ down"}</b></div>',
        unsafe_allow_html=True)

    if not (_et_ok or _mc_ok):
        st.warning("Both ET and MC sessions are down. Re-run "
                   "`python setup_paid_news_cookies.py`.")
        return

    if not _os_loc.path.exists(csv_path):
        st.info(f"No results file at `{_os_loc.path.basename(csv_path)}`. "
                f"Run the screener above first.")
        return

    if extra_caption:
        st.caption(extra_caption)
    st.caption("Pulls Buy/Hold/Sell consensus + recent analyst headlines. "
               "Cached 6h per symbol — first run can take ~20–40s for 10 symbols.")

    _topn = st.slider("Symbols to pull sentiment for (top N)",
                       min_value=5, max_value=30, value=10,
                       key=f"{key_prefix}_ans_topn")
    _force = st.checkbox("Force refresh (bypass 6h cache)",
                          value=False, key=f"{key_prefix}_ans_force")

    if not st.button(f"📊 Pull Analyst Sentiment", key=f"{key_prefix}_ans_btn",
                      type="secondary"):
        return

    try:
        _df_full = _pd_loc.read_csv(csv_path)
    except Exception as _e:
        st.error(f"Could not read {_os_loc.path.basename(csv_path)}: {_e}")
        return

    if symbol_col not in _df_full.columns:
        # Try a couple of common fallbacks
        _alt = next((c for c in ["Symbol", "NSECode", "Ticker", "Scrip"]
                      if c in _df_full.columns), None)
        if not _alt:
            st.warning(f"No symbol column found. Tried `{symbol_col}`. "
                       f"Columns: {list(_df_full.columns)}")
            return
        symbol_col = _alt

    if "Score" in _df_full.columns:
        _df_full = _df_full.sort_values("Score", ascending=False)

    _syms = (_df_full[symbol_col].dropna().astype(str)
              .head(int(_topn)).tolist())
    if not _syms:
        st.info("No symbols in CSV after filtering.")
        return

    _results = []
    _prog = st.progress(0)
    for i, sym in enumerate(_syms, 1):
        r = _ans_loc.get_for_symbol(sym, force=_force)
        _results.append({
            "Symbol":         sym,
            "Consensus":      r["consensus"],
            "★ STRONG BUY":   r.get("strong_buy", 0),
            "BUY":            r["buy"],
            "HOLD":           r["hold"],
            "SELL":           r["sell"],
            "★ STRONG SELL":  r.get("strong_sell", 0),
            "Items":          len(r["items"]),
            "ET":             "✓" if r["sources_ok"]["et"] else "✗",
            "MC":             "✓" if r["sources_ok"]["mc"] else "✗",
        })
        _prog.progress(int(i / len(_syms) * 100))
    _prog.empty()

    _ans_df = _pd_loc.DataFrame(_results)
    _crank = {"STRONG_BUY": 0, "BUY": 1, "MIXED": 2, "HOLD": 3,
               "NONE": 4, "SELL": 5, "STRONG_SELL": 6}
    _ans_df["_rank"] = _ans_df["Consensus"].map(_crank).fillna(7)
    _ans_df = (_ans_df.sort_values(
        ["_rank", "★ STRONG BUY", "BUY"],
        ascending=[True, False, False]).drop(columns=["_rank"]))
    st.dataframe(_ans_df, use_container_width=True, hide_index=True)

    _strong = _ans_df[(_ans_df["Consensus"] == "STRONG_BUY") |
                       (_ans_df["★ STRONG BUY"] > 0)]
    if not _strong.empty:
        st.success(
            f"⭐ **{len(_strong)} Strong Buy candidate(s)** — "
            f"{', '.join(_strong['Symbol'].astype(str).tolist())}"
        )
    st.caption(f"Pulled at {_pd_loc.Timestamp.now().strftime('%H:%M IST')}. "
               "Drill into a single symbol on **🧬 X-RAY → 📰 News** "
               "for full headlines + brokerage details.")


def _csv_freshness_caption(csv_path: str, label: str = "Results") -> None:
    """Render a freshness caption for a CSV file.

    10 May 2026 update — replaced the binary "Stale yes/no" with row-count-aware
    labels per user feedback ("instead of saying Stale, why can't it say
    '0 entries as of DD-MMM'"):

        Missing       → orange caption "<label> file not found"
        Fresh + N rows→ "<label>: N entries as of DD-MMM HH:MM (Xh ago)"
        Fresh + 0 rows→ "<label>: 0 entries as of DD-MMM HH:MM — ran today, no signals"
        Stale + N rows→ warning "<label>: N entries as of DD-MMM (Xh old) — re-run"
        Stale + 0 rows→ warning "<label>: 0 entries as of DD-MMM (Xh old) — re-run"
    """
    import os as _os_loc, datetime as _dt_loc, pandas as _pd_loc
    if not _os_loc.path.exists(csv_path):
        st.caption(f"_{label}: file not found at `{_os_loc.path.basename(csv_path)}`._")
        return

    _mtime = _dt_loc.datetime.fromtimestamp(_os_loc.path.getmtime(csv_path))
    _age_h = (_dt_loc.datetime.now() - _mtime).total_seconds() / 3600
    _ts = _mtime.strftime("%d %b %Y  %H:%M")

    # Count data rows (header excluded). Defensively try; on parse failure
    # treat as unknown count.
    try:
        _n = len(_pd_loc.read_csv(csv_path))
    except Exception:
        _n = None

    _n_str = f"**{_n}** {'entry' if _n == 1 else 'entries'}" if _n is not None else "?? entries"

    if _age_h > 28:
        st.warning(f"⚠ {label}: {_n_str} as of **{_ts}** ({_age_h:.0f}h old) — "
                   "re-run for fresh signals.")
    elif _n == 0:
        st.caption(f"⚪ {label}: **0 entries** as of **{_ts}** "
                   f"({_age_h:.1f}h ago) — ran today, no signals fired.")
    else:
        st.caption(f"✅ {label}: {_n_str} as of **{_ts}** ({_age_h:.1f}h ago)")

def _render_ai_report(text: str, header_color: str = "#e3b341"):
    """
    Parse Gemini's === Title === format and render each section as a styled card.
    Uses re.split with a capturing group so titles and bodies are properly paired —
    avoids the duplicate-heading bug caused by naive split('===') on alternating chunks.
    """
    import re
    if not text or not text.strip():
        st.info("No report content.")
        return
    # re.split with capturing group: ['preamble', 'Title1', 'Body1', 'Title2', 'Body2', ...]
    parts = re.split(r'===\s*(.+?)\s*===', text)
    sections = []
    i = 1
    while i < len(parts) - 1:
        title = parts[i].strip()
        body  = parts[i + 1].strip()
        if title:
            sections.append((title, body))
        i += 2

    if sections:
        for _title, _body in sections:
            # Convert newlines to <br> so multi-line bodies render correctly in HTML
            _body_html = _body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            _body_html = _body_html.replace("\n", "<br>")
            st.markdown(f"""
            <div class="metric-card" style="text-align:left;margin-bottom:10px;padding:14px 18px;">
              <div style="font-family:'Rajdhani',sans-serif;font-size:1.05rem;font-weight:700;
                          color:{header_color};letter-spacing:1px;margin-bottom:8px;
                          text-transform:uppercase;">{_title}</div>
              <div style="font-family:'Inter',sans-serif;font-size:0.85rem;color:#c9d1d9;
                          line-height:1.75;">{_body_html}</div>
            </div>""", unsafe_allow_html=True)
    else:
        # Fallback: plain text (no === markers found)
        _safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        st.markdown(f'<div style="font-size:0.85rem;color:#c9d1d9;line-height:1.75;'
                    f'white-space:pre-wrap;">{_safe}</div>', unsafe_allow_html=True)

def sub_label(label):
    st.markdown(f'<div class="section-sub-lbl">{label}</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
#  DHAN AUTH FAILURE BANNER (renders on EVERY page)
#  Token invalid at this point means the startup auto-refresh already ran and
#  did NOT produce a valid token — never let that degrade silently to yfinance.
# ════════════════════════════════════════════════════════════════════════════
try:
    from dhan_auth import token_status as _auth_ts
    _auth_now = _auth_ts()
    if not _auth_now.get("valid", False):
        _auth_reason = _AUTH_REFRESH_ERROR or _auth_now.get("error") or (
            "Auto-refresh did not raise but token is still invalid "
            "(possible causes: internet offline, or another process holds the 2-min rate limit)."
        )
        st.markdown(f"""
        <div style="background:#3d0c0c;border:2px solid #ff4b4b;border-radius:8px;
                    padding:14px 20px;margin-bottom:14px;">
          <div style="font-family:'Rajdhani',sans-serif;font-size:1.1rem;font-weight:700;
                      color:#ff4b4b;letter-spacing:1px;">
            🚨 DHAN TOKEN INVALID — AUTO-REFRESH FAILED</div>
          <div style="font-family:'Inter',sans-serif;font-size:0.85rem;color:#ffb3b3;
                      line-height:1.6;margin-top:6px;">
            Live broker data is DOWN (prices may silently fall back to delayed yfinance).<br>
            <b>Reason:</b> {str(_auth_reason).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")}<br>
            <b>Fix:</b> check DHAN_PIN / DHAN_TOTP_KEY in .env, or paste a fresh token in the
            sidebar &rarr; 🔑 Token detail, then reload.</div>
        </div>""", unsafe_allow_html=True)
except Exception as _auth_banner_err:
    logger.warning(f"Auth banner render failed: {_auth_banner_err}")

# ════════════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ════════════════════════════════════════════════════════════════════════════
def inr(x) -> str:
    """Indian-format a number: 1234567 -> 12,34,567."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    if math.isnan(x) or math.isinf(x):   # NaN/inf (e.g. a missing T2) → dash, never crash
        return "—"
    neg = x < 0
    x = abs(x)
    whole = int(round(x))
    s = str(whole)
    if len(s) > 3:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:]); rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        s = ",".join(parts) + "," + last3
    return ("-₹" if neg else "₹") + s


def fnum(x, dp=2, suffix="") -> str:
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return "—"
        return f"{float(x):,.{dp}f}{suffix}"
    except (TypeError, ValueError):
        return "—"


def row(label: str, value: str, status: str, note: str = ""):
    """Render a single colored checklist row. status in pass/watch/fail/na."""
    rhs = f"{value}" + (f"  <span style='opacity:.65'>· {note}</span>" if note else "")
    st.markdown(f"<div class='chk {status}'><b>{label}</b><span>{rhs}</span></div>",
                unsafe_allow_html=True)


def _g(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _cat_on(cat) -> bool:
    """True when a bull catalyst value means 'firing'. One definition for the
    header, compute_decision and compute_workflow — a Catalyst of None/NaN/
    ''/'None'/'NONE'/'—'/0 (any type) must read as NOT firing everywhere."""
    if cat is None or (isinstance(cat, float) and math.isnan(cat)):
        return False
    return str(cat).strip() not in ("NONE", "None", "none", "—", "-", "0", "")


def _stg_digit(stage_val):
    """Extract the Weinstein stage digit as a string ('1'..'4') from any
    representation — int 1, float 1.0 (batch CSV), 'Stage 2', '2A'. Returns
    '' when no digit is present (missing / NaN)."""
    s = str(stage_val)
    return next((d for d in "1234" if d in s), "")


def _canon_sym(sym: str) -> str:
    """Normalize a TradingView-style symbol (underscore separators) to the
    canonical NSE ticker the loaders expect. TV emits 'BAJAJ_AUTO.NS' /
    'NAM_INDIA.NS'; Dhan + yfinance want 'BAJAJ-AUTO' / 'NAM-INDIA' (and a few
    names use '&'). Resolves via the Dhan scrip master (separator-insensitive),
    preserving the '.NS' suffix and passing indices ('^...') through. Falls
    back to the input unchanged on any error."""
    if not sym:
        return sym
    s = str(sym).strip().upper()
    if s.startswith("^") or s.endswith(("=X", "=F")):
        return s
    had_ns = s.endswith(".NS")
    try:
        import dhan_ohlcv as _dohlcv
        canon = _dohlcv.canonical_nse_symbol(s)   # bare canonical ticker
        if canon and not canon.startswith("^"):
            return f"{canon}.NS" if had_ns else canon
        return canon or s
    except Exception:
        # Minimal safety net if dhan_ohlcv is unavailable: TV underscore→hyphen.
        return s.replace("_", "-") if "_" in s else s


def _rec_cfg():
    """(beaten_down_floor_pct, rff_min_score) from recovery_screener.CONFIG —
    single source of truth so the web never drifts from the engine."""
    try:
        import recovery_screener as _rsm
        return (float(_rsm.CONFIG.get("min_stock_correction_pct", 10.0)),
                int(_rsm.CONFIG.get("rff_min_score", 4)))
    except Exception:
        return (10.0, 4)


def _expected_last_session():
    """Date of the most-recently COMPLETED NSE session as of now (IST clock).

    The freshness target must be SESSION-AWARE, not just 'yesterday': while
    today's session is still live (or pre-open) the last completed session is
    the previous trading day, but AFTER today's 15:30 IST close the freshest bar
    should be TODAY. Using a flat `today-1` made the tool sit happily on
    yesterday's bar all evening (false-green, one session behind). Weekends are
    handled; NSE holidays are not modelled (a holiday briefly shows a benign
    amber — it errs loud, never silently stale)."""
    now = datetime.now()
    d = now.date()
    market_closed_today = (d.weekday() < 5) and (now.hour * 60 + now.minute) >= (15 * 60 + 30)
    if market_closed_today:
        return d
    d = d - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


# Golden Matcher user settings (capital / risk%) — persisted across restarts.
_GM_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gm_settings.json")


def _gm_settings() -> dict:
    try:
        with open(_GM_SETTINGS_FILE, encoding="utf-8") as _f:
            return json.load(_f) or {}
    except Exception:
        return {}


def _gm_settings_save(**kw):
    d = _gm_settings(); d.update(kw)
    try:
        with open(_GM_SETTINGS_FILE, "w", encoding="utf-8") as _f:
            json.dump(d, _f, indent=2)
    except Exception:
        pass


# ----------------------------------------------------------------------------------------
# Graphical primitives (pure HTML/SVG — no extra deps)
# ----------------------------------------------------------------------------------------
def _sc(state: str) -> str:
    return {"pass": "#26A69A", "watch": "#FF9800", "fail": "#EF5350", "na": "#787B86"}.get(state, "#787B86")


def _gauge(label, value, vmin, vmax, gradient, state, valtxt) -> str:
    col = _sc(state)
    if value is None or (isinstance(value, float) and math.isnan(value)):
        pct = 0.0; valtxt = "—"; col = "#787B86"
    else:
        pct = max(0.0, min(100.0, (float(value) - vmin) / (vmax - vmin) * 100.0))
    return (f"<div style='margin:5px 0;'>"
            f"<div style='display:flex;justify-content:space-between;font-size:11.5px;margin-bottom:3px;'>"
            f"<span style='font-weight:600'>{label}</span>"
            f"<span style='font-weight:800;color:{col}'>{valtxt}</span></div>"
            f"<div style='position:relative;height:9px;border-radius:5px;background:{gradient};'>"
            f"<div style='position:absolute;left:calc({pct:.1f}% - 1px);top:-2px;width:2px;height:13px;"
            f"background:#111;box-shadow:0 0 0 1px #fff;border-radius:1px;'></div></div></div>")


def _crit(ok: bool, label: str) -> str:
    col = "#26A69A" if ok else "#EF5350"; mk = "✓" if ok else "✗"
    return (f"<div style='display:flex;align-items:center;gap:6px;font-size:11px;margin:1.5px 0;'>"
            f"<span style='flex:0 0 15px;width:15px;height:15px;border-radius:50%;background:{col};"
            f"color:#fff;display:inline-flex;align-items:center;justify-content:center;font-size:10px;"
            f"font-weight:700'>{mk}</span><span>{label}</span></div>")


def _pill(state: str, label: str, val: str) -> str:
    col = _sc(state)
    return (f"<div style='border-left:3px solid {col};background:{col}22;border-radius:4px;padding:3px 7px;'>"
            f"<div style='opacity:.65;font-size:9.5px;text-transform:uppercase;letter-spacing:.3px'>{label}</div>"
            f"<b style='color:{col};font-size:12px'>{val}</b></div>")


def _donut(passed: int, total: int) -> str:
    r = 22.0; circ = 2 * math.pi * r
    frac = (passed / total) if total else 0
    col = "#26A69A" if frac >= 0.75 else ("#FF9800" if frac >= 0.5 else "#EF5350")
    off = circ * (1 - frac)
    return (f"<svg width='54' height='54' viewBox='0 0 52 52'>"
            f"<circle cx='26' cy='26' r='{r}' fill='none' stroke='#80808033' stroke-width='6'/>"
            f"<circle cx='26' cy='26' r='{r}' fill='none' stroke='{col}' stroke-width='6'"
            f" stroke-dasharray='{circ:.1f}' stroke-dashoffset='{off:.1f}' stroke-linecap='round'"
            f" transform='rotate(-90 26 26)'/>"
            f"<text x='26' y='31' text-anchor='middle' font-size='14' font-weight='800' fill='{col}'>{passed}/{total}</text></svg>")


def _range_bar(low, high, cmp_, marks) -> str:
    if not (low and high and high > low and cmp_):
        return "<div style='font-size:11px;opacity:.6'>52W range unavailable</div>"
    span = high - low
    def p(x): return max(0.0, min(100.0, (x - low) / span * 100.0))
    ticks = ""
    for x, lab, col in marks:
        if x is None:
            continue
        ticks += (f"<div style='position:absolute;left:{p(x):.1f}%;top:11px;width:1px;height:7px;"
                  f"background:{col};transform:translateX(-50%)'></div>"
                  f"<div style='position:absolute;left:{p(x):.1f}%;top:18px;transform:translateX(-50%);"
                  f"font-size:8.5px;color:{col};white-space:nowrap'>{lab}</div>")
    cp = p(cmp_)
    return (f"<div style='position:relative;margin:6px 0 30px;'>"
            f"<div style='position:relative;height:9px;border-radius:5px;"
            f"background:linear-gradient(90deg,#EF535055,#FF980055,#26A69A55);'>"
            f"<div style='position:absolute;left:{cp:.1f}%;top:-5px;transform:translateX(-50%);width:0;height:0;"
            f"border-left:6px solid transparent;border-right:6px solid transparent;border-top:11px solid #111;'></div>"
            f"{ticks}</div>"
            f"<div style='display:flex;justify-content:space-between;font-size:9px;opacity:.6;margin-top:2px'>"
            f"<span>52WL {inr(low)}</span><span>52WH {inr(high)}</span></div></div>")


def minervini_checks(ctx: dict, cmp_px, mansfield):
    """Minervini 8-point trend template — shared by the board and the decision engine."""
    e20 = _g(ctx, "ema20"); s50 = _g(ctx, "sma50"); s150 = _g(ctx, "sma150")
    s200 = _g(ctx, "sma200"); s200p = _g(ctx, "sma200_prev")
    low = _g(ctx, "low52w"); high = _g(ctx, "high52w")
    checks = [
        (bool(s150 and s200 and cmp_px > s150 and cmp_px > s200), "Price > 150 & 200 SMA"),
        (bool(s150 and s200 and s150 > s200), "150 SMA > 200 SMA"),
        (bool(s200 and s200p and s200 > s200p), "200 SMA trending up (1m)"),
        (bool(s50 and s150 and s200 and s50 > s150 and s50 > s200), "50 SMA > 150 & 200"),
        (bool(s50 and cmp_px > s50), "Price > 50 SMA"),
        (bool(low and cmp_px >= 1.30 * low), "≥30% above 52W low"),
        (bool(high and cmp_px >= 0.75 * high), "≤25% from 52W high"),
        (bool((mansfield or -1) > 0), "RS positive (vs N500)"),
    ]
    return sum(1 for ok, _ in checks if ok), checks


def compute_decision(rec: dict, ctx: dict, cmp_px, mansfield) -> dict:
    """Synthesize all signals into a verdict via a 3-gate funnel (Decision Mode)."""
    stage = str(_g(rec, "Stage", default="")); s2 = "2" in stage
    s34 = ("3" in stage or "4" in stage)
    above30w = bool(_g(ctx, "sma150") and cmp_px > _g(ctx, "sma150"))
    regime = _g(rec, "Regime", default="—"); counter = bool(_g(rec, "Counter_Trend"))
    rs = (mansfield or 0) > 0
    alpha = _g(rec, "Alpha") or 0
    mpass, _ = minervini_checks(ctx, cmp_px, mansfield)
    rrg = _g(rec, "RRG_Quadrant", default=""); rrg_ok = rrg in ("LEADING", "IMPROVING")
    catalyst = _g(rec, "Catalyst", default="NONE")
    cat_on = _cat_on(catalyst)
    rsi = _g(rec, "RSI") or 0; not_ob = rsi < 75
    s2w = _g(ctx, "stage2_weeks"); fresh = (s2w is None) or (s2w <= 26)
    macro = bool(_g(ctx, "shelf_ok") and _g(ctx, "acc_ok"))
    micro = bool(_g(ctx, "cpr_p") and cmp_px > _g(ctx, "cpr_p") and _g(ctx, "mvwap") and cmp_px > _g(ctx, "mvwap"))
    vcp = bool(_g(rec, "VCP_Valid")); broke = bool(_g(rec, "Broke_Pivot"))
    # Daily PA battery (v67-mirror, 17) — same source as the Step-5 workflow trigger,
    # so both views speak one "trigger" language.
    _pa_pats = _g(ctx, "pa_patterns", default=[]) or []
    _pa_tier = sum(t for _, f, t, _ in _pa_pats if f)
    _pa_fired = sorted([(nm, t) for nm, f, t, _ in _pa_pats if f], key=lambda x: -x[1])
    pa_fired = len(_pa_fired) > 0
    _pa_names = ", ".join(nm for nm, _ in _pa_fired[:3])

    # D1 fix (9-Jul-2026): every displayed check now states the threshold the
    # gate ACTUALLY enforces; rows that inform but do not gate say "(info)" —
    # a gate must never show ✓ while its listed criteria show ✗ (or vice versa).
    g1_checks = [("Stage 2 advancing", s2), ("Above 30W MA", above30w),
                 (f"Market regime {regime} (info)", (regime == "BULL") or not counter)]
    g1 = s2 and above30w
    g2_checks = [("Mansfield RS positive", rs), (f"Alpha ≥ 50 (now {alpha:.0f})", alpha >= 50),
                 (f"Minervini ≥ 5/8 (now {mpass}/8)", mpass >= 5), ("RRG leading/improving (info)", rrg_ok)]
    g2 = rs and (alpha >= 50) and (mpass >= 5)
    g3_checks = [(f"Catalyst firing ({catalyst})", cat_on), ("Not over-extended", fresh and not_ob),
                 ("Macro/Micro edge active (info)", macro or micro), ("VCP / pivot break (info)", vcp or broke),
                 (f"PA trigger fired{(' · ' + _pa_names) if pa_fired else ''} (info)", pa_fired)]
    g3 = cat_on and fresh and not_ob

    gates = [
        {"name": "CONTEXT", "sub": "Trend & Regime", "ok": g1, "checks": g1_checks},
        {"name": "STRENGTH", "sub": "Quality & RS", "ok": g2, "checks": g2_checks},
        {"name": "TIMING", "sub": "Location & Trigger", "ok": g3, "checks": g3_checks},
    ]

    if s34 or not rs:
        verdict, color = "AVOID / EXIT", "#EF5350"
        reason = "Stage 3/4 or RS negative — fails the no-Stage-3-holds rule."
        action = "No long. If held, plan the exit per the Sell-to-Buy matrix."
    elif g1 and g2 and g3 and pa_fired:
        verdict, color = "STRONG BUY · TRIGGER LIVE", "#26A69A"
        reason = f"All 3 gates pass · PA trigger LIVE ({_pa_names} · Σ+{_pa_tier})."
        action = f"Confirm a CLOSED 75/125m trigger → buy-STOP above its high. Size {_g(rec,'Suggested_Size','—')}."
    elif g1 and g2 and g3:
        verdict, color = "READY · AWAIT TRIGGER", "#FF9800"
        reason = f"All 3 gates pass · catalyst {catalyst} firing; no daily PA trigger printed yet."
        action = "Set an alert at the fresh zone; act ONLY on a fired PA pattern + closed 75/125m trigger bar."
    elif g1 and g2:
        verdict, color = "BUY ON TRIGGER", "#FF9800"
        reason = "Context + strength pass; timing/location gate still pending."
        action = "Set an alert at the fresh zone; act ONLY on a closed 75/125m trigger bar."
    elif g1:
        verdict, color = "WATCHLIST", "#FF9800"
        reason = "Stage-2 context OK but strength is incomplete."
        action = "Track only — needs RS / Alpha / Minervini to firm up."
    else:
        verdict, color = "NOT YET", "#787B86"
        reason = "Context gate not met (Stage 2 + above 30W MA)."
        action = "No setup. Re-check when context turns."
    if counter and verdict not in ("AVOID / EXIT", "WATCHLIST", "NOT YET"):
        reason += "  ⚠ Counter-trend (index not bull) — size halved."
    return {"verdict": verdict, "color": color, "reason": reason, "action": action, "gates": gates}


# (render_decision / render_pine_mirror removed 9-Jul-2026 — dead code, never
#  invoked; compute_decision remains live as the STRUCTURE card's gate source.)


# ----------------------------------------------------------------------------------------
# Panel-mirror cards (replace the 5 Pine panel tables)
# ----------------------------------------------------------------------------------------
# Per-section scores collected by card() on each render pass — feeds the
# score strip at the top of the Full Metrics expander (v2, 2026-07-03: every
# panel-mirror card now carries a pass-count score like the WCL FINAL SCORE).
SECTION_SCORES: dict = {}


def card(title: str, rows, accent: str = "#2962FF", chip_text: str = None,
         chip_color: str = None) -> str:
    """Compact label:value table card mirroring a Pine panel.

    v2: computes a section score from its own rows — passes / evaluated
    (state 'na' rows excluded) — shown as a chip in the header and registered
    in SECTION_SCORES for the summary strip. Zero per-section score logic.
    chip_text/chip_color override the auto-score for sections where a
    pass-count is the wrong benchmark (e.g. PA patterns: bonus tier, not x/N).
    """
    body = ""
    for label, value, state in rows:
        col = _sc(state)
        body += (f"<div style='display:flex;justify-content:space-between;gap:8px;padding:2.5px 0;"
                 f"font-size:11.5px;border-bottom:1px solid rgba(136,136,136,.18)'>"
                 f"<span style='opacity:.78'>{label}</span>"
                 f"<b style='color:{col};text-align:right'>{value}</b></div>")
    if chip_text is not None:
        hdr = chip_color or accent
        chip = (f"<span style='float:right;background:rgba(255,255,255,.25);padding:0 8px;"
                f"border-radius:9px;font-weight:800'>{chip_text}</span>")
        return (f"<div style='border:1px solid rgba(136,136,136,.28);border-radius:7px;overflow:hidden;margin-bottom:9px'>"
                f"<div style='background:{hdr};color:#fff;font-weight:700;font-size:10.5px;"
                f"letter-spacing:.4px;padding:4px 9px'>{title}{chip}</div>"
                f"<div style='padding:4px 9px 6px'>{body}</div></div>")
    evaluated = [s for _, _, s in rows if s in ("pass", "watch", "fail")]
    passed = sum(1 for s in evaluated if s == "pass")
    total = len(evaluated)
    chip = ""
    hdr = accent  # neutral fallback when a card has nothing to evaluate
    if total:
        frac = passed / total
        # RAG header (2026-07-03, Jay): the header band IS the status —
        # green >=70% pass, amber >=40%, red below.
        hdr = "#1B7A6E" if frac >= 0.7 else ("#C77700" if frac >= 0.4 else "#C62828")
        scol = "#26A69A" if frac >= 0.7 else ("#FF9800" if frac >= 0.4 else "#EF5350")
        short = title.split("·")[0].strip().title()
        SECTION_SCORES[short] = (passed, total, scol)
        chip = (f"<span style='float:right;background:rgba(255,255,255,.25);padding:0 8px;"
                f"border-radius:9px;font-weight:800'>{passed}/{total}</span>")
    return (f"<div style='border:1px solid rgba(136,136,136,.28);border-radius:7px;overflow:hidden;margin-bottom:9px'>"
            f"<div style='background:{hdr};color:#fff;font-weight:700;font-size:10.5px;"
            f"letter-spacing:.4px;padding:4px 9px'>{title}{chip}</div>"
            f"<div style='padding:4px 9px 6px'>{body}</div></div>")


def render_score_strip(mpass: int = None) -> str:
    """One-glance chips of every section score (populated by card() calls)."""
    chips = ""
    if mpass is not None:
        mc = "#26A69A" if mpass >= 6 else ("#FF9800" if mpass >= 4 else "#EF5350")
        chips += (f"<span style='border:1.5px solid {mc};color:{mc};border-radius:9px;"
                  f"padding:2px 10px;font-size:11.5px;font-weight:800'>Minervini {mpass}/8</span>")
    for name, (p, t, col) in SECTION_SCORES.items():
        disp = f"{p}/{t}" if t else str(p)  # t=None -> custom display string (e.g. 'Σ +3')
        chips += (f"<span style='border:1.5px solid {col};color:{col};border-radius:9px;"
                  f"padding:2px 10px;font-size:11.5px;font-weight:800'>{name} {disp}</span>")
    return (f"<div style='display:flex;gap:7px;flex-wrap:wrap;align-items:center;"
            f"margin:2px 0 10px'>{chips}</div>")


def _grade(a) -> str:
    a = a or 0
    return ("A+ Excellent" if a >= 80 else "A Strong" if a >= 70 else "B Good" if a >= 55
            else "C Fair" if a >= 40 else "D Weak")


def section_structure(rec, ctx, cmp_px, mansfield, decision) -> str:
    """Mirror of the v67 Weinstein Dashboard header rows."""
    stage = str(_g(rec, "Stage", default="—"))
    cat = str(_g(rec, "Catalyst", default="NONE"))
    style = ("Positional" if cat.startswith("POS") else "Swing" if cat.startswith("SWG")
             else "Recovery" if cat.startswith("REV") else "Both / —")
    alpha = _g(rec, "Alpha") or 0
    s2w = _g(ctx, "stage2_weeks")
    fresh = ("—" if s2w is None else f"Fresh ({s2w:.0f}w)" if s2w <= 13
             else f"Maturing ({s2w:.0f}w)" if s2w <= 26 else f"Extended ({s2w:.0f}w)")
    subs = [ok for g in decision["gates"] for _, ok in g["checks"]]
    act = round(10 * sum(1 for x in subs if x) / max(1, len(subs)))
    persona = ("LEADER" if (mansfield or 0) > 0 and _g(rec, "RRG_Quadrant") in ("LEADING", "IMPROVING")
               else "Improving" if (mansfield or 0) > 0 else "Laggard")
    v = decision["verdict"]
    rows = [
        ("Recommendation", v, "pass" if "BUY" in v else "fail" if "AVOID" in v else "watch"),
        ("Recommended Style", style, "na"),
        ("Action Signal", f"{act}/10", "pass" if act >= 7 else "watch" if act >= 5 else "fail"),
        ("Asset Quality", f"{alpha:.0f}/100 [{_grade(alpha)}]",
         "pass" if alpha >= 70 else "watch" if alpha >= 50 else "fail"),
        ("Weekly Stage", f"Stage {stage} · {fresh}",
         "pass" if "2" in stage else "fail" if ("3" in stage or "4" in stage) else "watch"),
        ("Momentum", f"RSI {fnum(_g(rec,'RSI'),0)} · ADX {fnum(_g(ctx,'adx'),0)} · Vol {fnum(_g(ctx,'relvol'),1)}x", "na"),
        ("Persona", persona, "pass" if persona == "LEADER" else "watch"),
        ("ML Win Prob", fnum(_g(rec, "ML_Prob"), 1, "%"), "pass" if (_g(rec, "ML_Prob") or 0) >= 60 else "watch"),
    ]
    return card("WEINSTEIN STRUCTURE · " + str(_g(rec, "Symbol", default="")), rows, "#1565C0")


def section_bull_gates(rec, ctx, cmp_px, mansfield) -> str:
    """Mirror of the Commander Bull Screener POS-BO gate panel."""
    s2 = "2" in str(_g(rec, "Stage", default=""))
    g200 = bool(_g(ctx, "sma200") and cmp_px > _g(ctx, "sma200"))
    rrg_ok = _g(rec, "RRG_Quadrant") in ("LEADING", "IMPROVING")
    mpass, _ = minervini_checks(ctx, cmp_px, mansfield)
    tpl = mpass >= 6
    vacc = bool(_g(ctx, "acc_ok"))
    s2w = _g(ctx, "stage2_weeks")
    freshg = (s2w is not None and s2w <= 6)
    # v3: G4 now real — sector_score (>0 = sector outperforming) from
    # sector_strength, the same module the screener's score uses.
    _g4ss = _g(ctx, "sector_score")
    g4 = (None if _g4ss is None else _g4ss > 0)
    gates = [("G1 Stage 2", s2), ("G2 Price > 200DMA", g200), ("G3 N500 RRG lead", rrg_ok),
             ("G4 Sector strength" + (f" ({_g4ss:+d})" if _g4ss is not None else ""), g4),
             ("G5 Trend Template", tpl), ("G6 Vol Accum", vacc),
             ("G7 Fresh ≤6w" + (f" ({s2w:.0f}w)" if s2w is not None else ""), freshg)]
    passed = sum(1 for _, ok in gates if ok)
    total = sum(1 for _, ok in gates if ok is not None)
    cat = str(_g(rec, "Catalyst", default="NONE")); firing = _cat_on(cat)
    rows = [("VERDICT", (cat + " · FIRING") if firing else "NONE · WATCH", "pass" if firing else "watch")]
    for lab, ok in gates:
        rows.append((lab, "n/a", "na") if ok is None else (lab, "✓ pass" if ok else "✗ block", "pass" if ok else "fail"))
    # Explicit chip (D3 fix 9-Jul-2026): the auto-chip also counted the VERDICT
    # row, so header said e.g. 4/6 while the chip said 5/8. Gates only, once.
    _frac = (passed / total) if total else 0
    _scol = "#26A69A" if _frac >= 0.7 else ("#FF9800" if _frac >= 0.4 else "#EF5350")
    _hdr = "#1B7A6E" if _frac >= 0.7 else ("#C77700" if _frac >= 0.4 else "#C62828")
    SECTION_SCORES["Bull Screener"] = (passed, total, _scol)
    return card(f"BULL SCREENER · POS-BO gates", rows, "#00695C",
                chip_text=f"{passed}/{total}", chip_color=_hdr)


def section_context(rec, ctx, cmp_px) -> str:
    """Mirror of the Context Layers panel — SMC / Wyckoff / Volume Profile."""
    adir = str(_g(rec, "Active_Dir", default="")).upper()
    smc = "BULLISH" if adir.startswith("UP") else "BEARISH" if adir.startswith("DOWN") else "NEUTRAL"
    stage = str(_g(rec, "Stage", default=""))
    bfvg = _g(ctx, "bull_fvg", default=0); rfvg = _g(ctx, "bear_fvg", default=0)
    wyk = ("ACCUMULATION" if (_g(ctx, "acc_ok") and ("1" in stage or "2" in stage))
           else "DISTRIBUTION" if "3" in stage else "NEUTRAL")
    poc = _g(ctx, "poc"); vah = _g(ctx, "vah"); val = _g(ctx, "val")
    vp_pos = _g(ctx, "vp_pos", default="—"); dpoc = _g(ctx, "dist_poc")
    # WCL-mirror weighted score (replicates Weinstein_Context_Layers v1.2 FINAL
    # SCORE composition: Wyk(-4..+4) + VP(+3/+1/-1/-3) + SMC(±2) + OB(±2) + Stage).
    # Wyckoff here is the accumulation-bias proxy (no event decay); OB (order
    # blocks) not computed on this surface -> 0, shown as '—'.
    wyk_s = 3 if wyk == "ACCUMULATION" else (-3 if wyk == "DISTRIBUTION" else 0)
    if vp_pos == "ABOVE VAH":
        vp_s = 3
    elif vp_pos == "INSIDE VA":
        vp_s = 1 if (dpoc or 0) >= 0 else -1
    elif vp_pos == "BELOW VAL":
        vp_s = -3
    else:
        vp_s = 0
    smc_s = 2 if smc == "BULLISH" else (-2 if smc == "BEARISH" else 0)
    stg_s = 3 if "2" in stage else (1 if "1" in stage else (-1 if "3" in stage else -3))
    wcl_total = wyk_s + vp_s + smc_s + stg_s
    wcl_band = "BULL" if wcl_total >= 6 else ("NEUTRAL" if wcl_total >= 0 else "BEAR")
    rows = [
        ("WCL Score (mirror)", f"{wcl_total:+d} → {wcl_band}",
         "pass" if wcl_band == "BULL" else ("watch" if wcl_band == "NEUTRAL" else "fail")),
        ("· components", f"Wyk:{wyk_s:+d} VP:{vp_s:+d} SMC:{smc_s:+d} Stg:{stg_s:+d} OB:—", "na"),
        ("SMC Trend", smc, "pass" if smc == "BULLISH" else "fail" if smc == "BEARISH" else "na"),
        ("Open FVGs", f"Bull {bfvg} · Bear {rfvg}", "pass" if bfvg >= rfvg else "watch"),
        ("Wyckoff Bias", wyk, "pass" if wyk == "ACCUMULATION" else "fail" if wyk == "DISTRIBUTION" else "na"),
        ("VP Position", vp_pos,
         "pass" if vp_pos == "ABOVE VAH" else "watch" if vp_pos == "INSIDE VA" else "fail" if vp_pos == "BELOW VAL" else "na"),
        ("POC", inr(poc) if poc else "—", "na"),
        ("VAH / VAL", (inr(vah) + " / " + inr(val)) if (vah and val) else "—", "na"),
        ("Dist to POC", fnum(dpoc, 1, "%"), "na"),
    ]
    return card("CONTEXT LAYERS · SMC / VP / Wyckoff", rows, "#6A1B9A")


def section_edges(rec, ctx, cmp_px) -> str:
    """Macro/Micro mathematical edges + CPR/MVWAP/squeeze."""
    macro = bool(_g(ctx, "shelf_ok") and _g(ctx, "acc_ok"))
    cpr_p = _g(ctx, "cpr_p"); mv = _g(ctx, "mvwap")
    micro = bool(cpr_p and cmp_px > cpr_p and mv and cmp_px > mv and _g(ctx, "squeeze_on"))
    rows = [
        ("Macro Edge (Inst Vol)", "ACTIVE" if macro else "inactive today", "pass" if macro else "na"),
        ("Micro Edge (CPR+VWAP+Sqz)", "ACTIVE" if micro else "inactive today", "pass" if micro else "na"),
        ("vs CPR Pivot", ("above " + inr(cpr_p)) if (cpr_p and cmp_px > cpr_p) else "below",
         "pass" if (cpr_p and cmp_px > cpr_p) else "watch"),
        ("vs Monthly VWAP", ("above " + inr(mv)) if (mv and cmp_px > mv) else "below",
         "pass" if (mv and cmp_px > mv) else "watch"),
        ("Accumulation", f"{_g(ctx,'acc_days',default=0)}/10 days", "pass" if _g(ctx, "acc_ok") else "na"),
        ("Squeeze 20/50", "ON" if _g(ctx, "squeeze_on") else "off", "pass" if _g(ctx, "squeeze_on") else "na"),
        ("VCP / Base", ("valid · " + str(_g(rec, "Days_Since_Pivot", default="—")) + "d") if _g(rec, "VCP_Valid") else "no",
         "pass" if _g(rec, "VCP_Valid") else "na"),
    ]
    return card("MATHEMATICAL EDGES", rows, "#7B1FA2")


def section_recovery(rec_r, cmp_px) -> str:
    """Recovery engine read (REV-CB/RS/EARLY + WYC-*), parallel to the bull side.

    The bull screener above only sees the 6 bull catalysts; recovery setups
    (fundamentally strong, beaten-down, turning up) come from a separate
    engine. This card surfaces its signal, the RFF fundamental HARD GATE
    (≥4/6 — the whole point of the recovery thesis), Stage/RS context, and the
    daily plan when a signal actually fires. When nothing fires it reports WHY
    (RFF vs setup) rather than going silent.
    """
    if not rec_r:
        return card("RECOVERY ENGINE · REV / WYC",
                    [("Status", "not evaluated (engine error)", "na")], "#00838F")
    _dd_floor, _rff_min = _rec_cfg()
    sig    = int(_g(rec_r, "Signal", default=0) or 0)
    label  = str(_g(rec_r, "Signal_Label", default="None"))
    rff_b  = _g(rec_r, "RFF_Base", default=0)
    if isinstance(rff_b, float) and math.isnan(rff_b):
        rff_b = 0
    rff_q  = str(_g(rec_r, "RFF_Quality", default="INSUFFICIENT"))
    if rff_q.lower() in ("nan", "none", ""):
        rff_q = "INSUFFICIENT"
    rff_ok = (rff_q != "INSUFFICIENT") and (rff_b or 0) >= _rff_min
    corr   = _g(rec_r, "Correction_52W_pct")
    if isinstance(corr, float) and math.isnan(corr):
        corr = None
    reg_ok = bool(_g(rec_r, "Regime_OK", default=False))
    actionable = sig >= 2          # 2=REV-CB 3=REV-RS 4=REV-EARLY 5-8=WYC-*
    watch      = sig == 1          # CB-Watch — climax seen, no turn yet
    # A "recovery" only makes sense if the STOCK is genuinely beaten down. The
    # engine can fire REV/WYC via the market-recovery path even at ATH — flag
    # that as NOT a real recovery (engine's own configured floor).
    beaten_down = (corr is not None) and (corr >= _dd_floor)

    if actionable and beaten_down:
        sig_state, sig_txt = "pass", label
    elif actionable and not beaten_down:
        sig_state, sig_txt = "watch", f"{label} (market-path only — stock near highs, not a recovery)"
    elif watch:
        sig_state, sig_txt = "watch", label
    else:
        sig_state, sig_txt = "na", "No recovery setup"
    rows = [
        ("Signal", sig_txt, sig_state),
        (f"Beaten down (≥{_dd_floor:.0f}% off 52WH)", fnum(corr, 1, "%") if corr is not None else "—",
         "pass" if beaten_down else "fail"),
        (f"RFF gate (≥{_rff_min}/6)", f"{rff_b}/6 · {rff_q}", "pass" if rff_ok else "fail"),
        ("Stage (weekly)", f"Stage {_stg_digit(_g(rec_r, 'Weinstein_Stage', default='')) or '—'}", "na"),
        ("In recovery band (15-35%)", fnum(corr, 1, "%") if corr is not None else "—",
         "pass" if (corr is not None and 15 <= corr <= 35) else "watch"),
        ("RS vs N500", fnum(_g(rec_r, "Mansfield_RS_x100"), 1), "na"),
        ("RRG", str(_g(rec_r, "RRG_Quadrant", default="—")),
         "pass" if _g(rec_r, "RRG_Quadrant") in ("LEADING", "IMPROVING") else "watch"),
        ("Recovery regime", "OPEN" if reg_ok else "closed",
         "pass" if reg_ok else "watch"),
    ]
    # Daily plan only when a GENUINE beaten-down recovery fired (levels are
    # meaningful then; a market-path artifact at highs gets no recovery plan).
    entry = _g(rec_r, "Entry"); sl = _g(rec_r, "SL")
    t1 = _g(rec_r, "T1"); t2 = _g(rec_r, "T2"); rr = _g(rec_r, "RR_T1"); slp = _g(rec_r, "SL_pct")
    # NaN → None (batch CSV rows carry float NaN for missing levels; NaN is truthy).
    entry, sl, t1, t2, rr, slp = [
        (None if (v is None or (isinstance(v, float) and math.isnan(v))) else v)
        for v in (entry, sl, t1, t2, rr, slp)]
    if actionable and beaten_down and entry and sl:
        rows.append(("Entry", inr(entry), "na"))
        rows.append(("Stop-Loss", inr(sl) + (f" (-{slp:.1f}%)" if slp is not None else ""), "fail"))
        if t1:
            rows.append(("Target 1", inr(t1) + (f" ({fnum(rr,1)}R)" if rr is not None else ""), "pass"))
        if t2:
            rows.append(("Target 2", inr(t2), "pass"))
    _src = _g(rec_r, "_source")
    if _src:
        _fage = _g(rec_r, "_as_of")
        _adays = _g(rec_r, "_age_days")
        _src_txt = f"{_src} · {_fage}" if _fage else str(_src)
        _src_state = "watch" if (_adays is not None and _adays > 5) else "na"
        if _src_state == "watch":
            _src_txt += f" (⚠ {_adays}d old — re-run the recovery scan)"
        rows.append(("Read from", _src_txt, _src_state))
    return card("RECOVERY ENGINE · REV / WYC", rows, "#00838F")


def section_trade(rec, cmp_px) -> str:
    entry = _g(rec, "Entry", default=cmp_px); sl_pct = _g(rec, "SL_pct")
    t1_pct = _g(rec, "T1_pct"); t2_pct = _g(rec, "T2_pct")
    if not (entry and sl_pct is not None):
        return card("TRADE GEOMETRY", [("Status", "No active catalyst", "na"),
                                       ("Levels", "reference only", "na")], "#E65100")
    sl = entry * (1 - sl_pct / 100)
    t1 = entry * (1 + t1_pct / 100) if t1_pct is not None else None
    t2 = entry * (1 + t2_pct / 100) if t2_pct is not None else None
    rr = (t1_pct / sl_pct) if (t1_pct and sl_pct) else None
    rows = [
        ("Entry", inr(entry), "na"),
        ("Stop-Loss", f"{inr(sl)} (-{sl_pct:.1f}%)", "fail"),
        ("Target 1", f"{inr(t1)} (+{t1_pct:.1f}% · {fnum(rr,1)}R)", "pass"),
        ("Target 2", f"{inr(t2)} (+{t2_pct:.1f}%)", "pass"),
        ("Suggested Size", str(_g(rec, "Suggested_Size", default="—")), "na"),
        ("Regime", str(_g(rec, "Regime", default="—")), "pass" if _g(rec, "Regime") == "BULL" else "watch"),
    ]
    if _g(rec, "Counter_Trend"):
        rows.append(("⚠ Counter-trend", "size halved", "watch"))
    return card("TRADE GEOMETRY · daily plan", rows, "#E65100")


def section_levels(rec, ctx, cmp_px) -> str:
    d52 = _g(ctx, "dist52wh")
    rows = [
        ("Room to 52WH", fnum(d52, 1, "%"), "pass" if (d52 is not None and -15 <= d52 <= -1) else "watch"),
        ("EMA20 distance", fnum(_g(rec, "EMA20_Dist_ATR"), 2, " ATR"), "na"),
        ("VCP Pivot age", f"formed {_g(rec,'Days_Since_Pivot','—')}d ago" + (" · broke ↑" if _g(rec, "Broke_Pivot") else " · not broken"),
         "pass" if _g(rec, "Broke_Pivot") else "na"),
        ("Turnover", fnum(_g(ctx, "turnover_cr"), 1) + " Cr", "na"),
    ]
    # Auto support zones (OB / FVG / pivot-low) on Daily AND Weekly — twin of
    # the S4 Pine v2.1. Trading TF is 125/75m; zones come from D+W structure.
    _sup = _g(ctx, "support", default={}) or {}
    for _tf_key, _tf_lbl in (("daily", "D"), ("weekly", "W")):
        _z = _sup.get(_tf_key) or {}
        _ot, _ob = _z.get("ob_top"), _z.get("ob_bot")
        _ft, _fb = _z.get("fvg_top"), _z.get("fvg_bot")
        _pv = _z.get("pivot")
        _obt = bool(_z.get("ob_tested")); _fvt = bool(_z.get("fvg_tested"))
        # Tested zones show greyed ('na') + a TESTED tag — they're excluded from
        # the trigger; fresh zones show green ('pass').
        rows.append((f"{_tf_lbl} · Order Block",
                     (f"{inr(_ob)}–{inr(_ot)}" + (" · TESTED" if _obt else " · fresh")) if _ot else "none active",
                     "na" if (not _ot or _obt) else "pass"))
        rows.append((f"{_tf_lbl} · FVG",
                     (f"{inr(_fb)}–{inr(_ft)}" + (" · TESTED" if _fvt else " · fresh")) if _ft else "none active",
                     "na" if (not _ft or _fvt) else "pass"))
        rows.append((f"{_tf_lbl} · Pivot support", inr(_pv) if _pv else "none active",
                     "pass" if _pv else "na"))
        _pvr = _z.get("pivot_res")
        if _pvr:
            rows.append((f"{_tf_lbl} · Pivot S→R (resist)", inr(_pvr) + " · overhead", "watch"))
    rows.append(("Price at fresh support (D/W)", _sup.get("zone", "—"),
                 "pass" if _sup.get("at_support") else "watch"))
    return card("LEVELS & ROOM", rows, "#EF6C00")


def section_sector(rec, ctx, mansfield) -> str:
    rows = [
        ("Market Regime", str(_g(rec, "Regime", default="—")), "pass" if _g(rec, "Regime") == "BULL" else "watch"),
        ("RS vs N500", fnum(mansfield, 1) + (" Positive" if (mansfield or 0) > 0 else " Negative"),
         "pass" if (mansfield or 0) > 0 else "fail"),
        ("RS Momentum 4w", fnum(_g(rec, "JdK_RS_Momentum"), 1), "na"),
        ("RRG Quadrant", f"{_g(rec,'RRG_Quadrant',default='—')} {_g(rec,'RRG_Arrow','')}",
         "pass" if _g(rec, "RRG_Quadrant") in ("LEADING", "IMPROVING") else "watch"),
        ("RRG Trajectory", str(_g(rec, "RRG_Trajectory", default="—")), "na"),
    ]
    # v3: real sector + futures-OI values (loader wires sector_lookup /
    # sector_strength + the matcher CSV's Futures_OI_Chg_Pct).
    _si = _g(ctx, "sector_idx"); _sw = _g(ctx, "sector_w_pct"); _sm2 = _g(ctx, "sector_m_pct")
    _ss = _g(ctx, "sector_score"); _oi = _g(ctx, "fut_oi")
    if _si:
        rows.append(("Sector Index", str(_si).replace("NSE:", ""), "na"))
        rows.append(("Sector Move W / M", f"{fnum(_sw,1,'%')} / {fnum(_sm2,1,'%')}",
                     "pass" if (_sw or 0) > 0 else ("watch" if (_sm2 or 0) > 0 else "fail")))
        if _ss is not None:
            rows.append(("Sector Score", f"{_ss:+d} / 5",
                         "pass" if _ss > 0 else ("watch" if _ss == 0 else "fail")))
    else:
        rows.append(("Sector", "unmapped (sector_lookup)", "na"))
    rows.append(("Futures OI Δ", fnum(_oi, 1, "%") if _oi is not None else "not in F&O / matcher run",
                 ("pass" if _oi > 0 else "watch") if _oi is not None else "na"))
    return card("SECTOR / MACRO / RRG", rows, "#283593")


def section_fundamentals(fun, bff=None) -> str:
    roe = _g(fun, "roe"); roce = _g(fun, "roce"); de = _g(fun, "debt_equity")
    prom = _g(fun, "promoter_holding", "promoter"); piot = _g(fun, "piotroski", "piotroski_score")
    qpv = _g(fun, "qtr_profit_var", "quarterly_profit_growth")
    qsv = _g(fun, "qtr_sales_var", "quarterly_sales_growth")
    pe = _g(fun, "pe_ratio"); mcap = _g(fun, "market_cap")
    rows = []
    if roe is not None: rows.append(("ROE %", fnum(roe, 1, "%"), "pass" if roe >= 15 else "watch" if roe >= 10 else "fail"))
    if roce is not None: rows.append(("ROCE %", fnum(roce, 1, "%"), "pass" if roce >= 15 else "watch" if roce >= 10 else "fail"))
    if de is not None: rows.append(("Debt / Equity", fnum(de, 2), "pass" if de < 0.5 else "watch" if de < 1.0 else "fail"))
    if prom is not None: rows.append(("Promoter %", fnum(prom, 1, "%"), "pass" if prom >= 50 else "watch"))
    if piot is not None: rows.append(("Piotroski", fnum(piot, 0, "/9"), "pass" if piot >= 7 else "watch" if piot >= 5 else "fail"))
    if qpv is not None: rows.append(("Qtr Profit Δ", fnum(qpv, 1, "%"), "pass" if qpv > 0 else "fail"))
    if qsv is not None: rows.append(("Qtr Sales Δ", fnum(qsv, 1, "%"), "pass" if qsv > 0 else "fail"))
    if pe is not None: rows.append(("P/E", fnum(pe, 1), "na"))
    if mcap is not None: rows.append(("Market Cap", inr(mcap) + " Cr", "na"))
    # BFF (Bull Fundamental Filter) — Minervini growth-leg summary, leading the
    # card. Display-only; the driver string shows the components behind the badge.
    if bff and bff.get("source") == "screener.in":
        _q = str(bff.get("quality", "—")); _sc = bff.get("score")
        _drv = " · ".join(bff.get("drivers", [])[:4])
        _val = (f"{_q} {_sc}/5" if _sc is not None else _q) + (f"   ·   {_drv}" if _drv else "")
        _st = "pass" if _q == "STRONG" else "watch" if _q in ("OK", "INSUFFICIENT") else "fail"
        rows.insert(0, ("BFF · Bull growth", _val, _st))
    if not rows:
        rows = [("Fundamentals", "unavailable — refresh cookie", "na")]
    return card("FUNDAMENTALS · Screener.in", rows, "#00838F")


# ----------------------------------------------------------------------------------------
# DECISION WORKFLOW — the sequential path (crucial metrics only)
# ----------------------------------------------------------------------------------------
def compute_workflow(rec, ctx, cmp_px, mansfield) -> dict:
    """Order the decision as a gated sequence: CONTEXT → QUALITY → SETUP → LOCATION → TRIGGER → EXECUTE."""
    stage = str(_g(rec, "Stage", default="")); s2 = "2" in stage; s34 = ("3" in stage or "4" in stage)
    regime = _g(rec, "Regime", default="—")
    rs = (mansfield or 0) > 0
    alpha = _g(rec, "Alpha") or 0
    ml = _g(rec, "ML_Prob")
    # Weekly trend (price-action): above the 30W-MA proxy AND the MA rising
    _s150 = _g(ctx, "sma150"); _s150p = _g(ctx, "sma150_prev")
    wk_up = bool(_s150 and cmp_px > _s150 and (_s150p is None or _s150 > _s150p))
    mpass, _ = minervini_checks(ctx, cmp_px, mansfield)
    rrg = _g(rec, "RRG_Quadrant", default="—"); rrg_ok = rrg in ("LEADING", "IMPROVING")
    cat = str(_g(rec, "Catalyst", default="NONE")); cat_on = _cat_on(cat)
    # PA pattern battery (v67-mirror, 17 conditions) — status in SETUP, TRIGGER in Step 5
    _pa_pats = _g(ctx, "pa_patterns", default=[]) or []
    _pa_tier = sum(t for _, f, t, _ in _pa_pats if f)
    _pa_fired_list = sorted([(nm, t) for nm, f, t, _ in _pa_pats if f], key=lambda x: -x[1])
    pa_fired = len(_pa_fired_list) > 0
    _pa_names = ", ".join(nm for nm, _ in _pa_fired_list[:4])
    s2w = _g(ctx, "stage2_weeks"); fresh = (s2w is None) or (s2w <= 26)
    vcp = bool(_g(rec, "VCP_Valid"))
    cpr_p = _g(ctx, "cpr_p"); mv = _g(ctx, "mvwap")
    above_value = bool(cpr_p and cmp_px > cpr_p and mv and cmp_px > mv)
    vp_pos = _g(ctx, "vp_pos", default="—"); d52 = _g(ctx, "dist52wh")
    not_ext = (d52 is None) or (d52 <= -1)

    # POS-ACCUM is the ACCUMULATION catalyst — buy the base BEFORE the Stage-2
    # breakout (bull_screener accum_base: Stage 1/2 + above 200-DMA + RS not
    # lagging + volume accumulation). Applying the Stage-2 breakout template to
    # it (require Stage 2 + weekly-up) wrongly fails it at Step 1. So Steps 1-2
    # switch to the accumulation playbook for POS-ACCUM.
    is_accum = cat == "POS-ACCUM"
    _s200 = _g(ctx, "sma200")
    above200 = bool(_s200 and cmp_px and cmp_px > _s200)
    stage1or2 = ("1" in stage or "2" in stage) and not s34
    acc_ok = bool(_g(ctx, "acc_ok"))
    if is_accum:
        g1 = stage1or2 and rs and above200                 # accumulation base context
        g2 = (alpha >= 40) and (rrg_ok or acc_ok)          # accumulation quality (RS turning / vol accum)
    else:
        g1 = s2 and rs and not s34                         # Stage-2 breakout context
        g2 = alpha >= 50 and mpass >= 5                     # Stage-2 leadership
    g3 = cat_on
    g4 = above_value and not_ext

    entry = _g(rec, "Entry", default=cmp_px); sl_pct = _g(rec, "SL_pct"); t1_pct = _g(rec, "T1_pct")
    # NaN → None so `if x` guards behave and formats never print "nan".
    entry, sl_pct, t1_pct = [
        (None if (v is None or (isinstance(v, float) and math.isnan(v))) else v)
        for v in (entry, sl_pct, t1_pct)]
    if entry and sl_pct is not None:
        sl = entry * (1 - sl_pct / 100); t1 = entry * (1 + t1_pct / 100) if t1_pct else None
        rr = (t1_pct / sl_pct) if (t1_pct and sl_pct) else None
        plan = (f"Set SL {inr(sl)} (-{sl_pct:.1f}%), size at 0.25% risk, place order + GTT. "
                f"Target T1 {inr(t1)} ({fnum(rr,1)}R).")
    else:
        sl = t1 = None
        plan = "No active catalyst → no plan yet. Levels are reference only."

    # Auto support zones (OB / FVG / pivot-low) — twin of the S4 Pine v2.0.
    _sup = _g(ctx, "support", default={}) or {}
    _at_support = bool(_sup.get("at_support"))
    _sup_zone = str(_sup.get("zone", "outside"))
    # Trigger TF (75m/125m/Daily) — the PA battery ran on this TF, so the Step-5
    # wording must name it (was hardcoded "fired on the daily").
    _tf_lbl = str(_g(ctx, "_trigger_tf", default="Daily"))
    _is_intra = _tf_lbl in ("75m", "125m")
    _fired_on = _tf_lbl if _is_intra else "daily"
    _confirm_lbl = f"{_tf_lbl} close" if _is_intra else "75/125m close"

    # Bull Fundamental Filter (BFF) — Minervini growth leg (screener.in). DISPLAY-
    # ONLY status shown at QUALITY, parallel to Recovery's RFF; it NEVER gates g2
    # (structure fires, quality is status Jay eyeballs). INSUFFICIENT/WEAK show
    # amber/red but never block a technically-valid leader.
    _bff = _g(ctx, "bff") or {}
    _bff_q = str(_bff.get("quality", "—"))
    _bff_sc = _bff.get("score")
    _bff_val = (f"{_bff_q} {_bff_sc}/5" if _bff_sc is not None else _bff_q)
    _bff_ok = _bff_q in ("STRONG", "OK")

    steps = [
        dict(n=1, title="CONTEXT", sub="Accumulation base" if is_accum else "Weekly trend", hard=True, ok=g1,
             metrics=([("Stage", stage or "—", stage1or2),
                       ("Above 200-DMA", "yes" if above200 else "no", above200),
                       ("RS vs N500", f"{(mansfield or 0):+.1f}", rs),
                       ("Regime", regime, regime == "BULL")] if is_accum else
                      [("Stage", stage or "—", s2 and not s34),
                       ("Weekly Trend", "UP" if wk_up else "DOWN", wk_up),
                       ("RS vs N500", f"{(mansfield or 0):+.1f}", rs),
                       ("Regime", regime, regime == "BULL")]),
             do_pass=("Stage 1/2 accumulation base above 200-DMA with positive RS — accumulate before the breakout."
                      if is_accum else "Weekly Stage 2 + positive RS — confirmed by the engine."),
             do_fail=("Not a valid accumulation base (Stage 3/4, below 200-DMA, or RS negative). SKIP."
                      if is_accum else "Not a Stage-2 leader (or RS negative). SKIP — go to the next name.")),
        dict(n=2, title="QUALITY", sub="Accumulation" if is_accum else "Leadership", hard=True, ok=g2,
             metrics=([("Asset Qual", f"{alpha:.0f}/100", alpha >= 60),
                       ("Accum days", f"{_g(ctx,'acc_days',default=0)}/10", acc_ok),
                       ("RRG", rrg, rrg_ok),
                       ("BFF (funda)", _bff_val, _bff_ok),
                       ("ML Prob", fnum(ml, 0, "%"), (ml or 0) >= 60)] if is_accum else
                      [("Asset Qual", f"{alpha:.0f}/100", alpha >= 70),
                       ("Minervini", f"{mpass}/8", mpass >= 6),
                       ("RRG", rrg, rrg_ok),
                       ("BFF (funda)", _bff_val, _bff_ok),
                       ("ML Prob", fnum(ml, 0, "%"), (ml or 0) >= 60)]),
             do_pass=("Accumulation confirmed (RS turning up / volume accumulation)." if is_accum else
                      "Leadership confirmed (Alpha + trend template + RRG)."),
             do_fail=("Accumulation not confirmed yet (RS lagging & no volume accumulation). WATCHLIST." if is_accum else
                      "Not a leader yet. WATCHLIST — revisit when RS / Alpha firm up.")),
        dict(n=3, title="SETUP", sub="Catalyst & base", hard=False, ok=g3,
             metrics=[("Catalyst", cat, cat_on),
                      ("Freshness", (f"{s2w:.0f}w" if s2w is not None else "—"), fresh),
                      ("VCP/Base", "valid" if vcp else "no", vcp),
                      ("PA Patterns", (f"+{_pa_tier}" if _pa_tier else "none"), _pa_tier >= 2)],
             do_pass=f"Catalyst {cat} is LIVE — proceed to location.",
             do_fail="No live catalyst. Add to watchlist & set a price alert at the zone; wait."),
        dict(n=4, title="LOCATION", sub="Price at value", hard=False, ok=g4,
             metrics=[("vs CPR+VWAP", "above" if above_value else "below", above_value),
                      ("VP", vp_pos, vp_pos in ("ABOVE VAH", "INSIDE VA")),
                      ("Room 52WH", fnum(d52, 1, "%"), not_ext),
                      ("Support (auto)", _sup_zone, _at_support)],
             do_pass=("Price at value & not extended"
                      + (f" — auto-zone: {_sup_zone}." if _at_support else ". No auto demand-zone under price yet (mark one on TV).")),
             do_fail="Extended / below value. WAIT for a pullback into a fresh demand zone."),
        dict(n=5, title="TRIGGER", sub=(f"{_tf_lbl} PA battery" if _is_intra else "Daily PA battery + intraday confirm"),
             hard=False, ok=None, manual=True,
             metrics=[("PA trigger", (_pa_names if pa_fired else "none yet"), pa_fired),
                      ("Σ tier", (f"+{_pa_tier}" if _pa_tier else "0"), _pa_tier >= 2),
                      ("Confirm on", _confirm_lbl, None)],
             do_now=((f"TRIGGER LIVE — {_pa_names} (Σ+{_pa_tier}) fired on the {_fired_on}"
                      + (f" bar at the zone → buy-STOP above that {_tf_lbl} bar's high. Never buy the touch."
                         if _is_intra else
                         ". Drop to 75/125m, confirm a CLOSED bar at the zone → buy-STOP above its high. Never buy the touch."))
                     if pa_fired else
                     (f"No {_fired_on} PA trigger yet. Wait for a closed-bar pattern (VCP-BO / Pocket / 3-Bar / "
                      f"Undercut / Spring / IB-NR7 …) at the zone on the {_tf_lbl} chart, then buy-STOP above the trigger bar high."))),
        dict(n=6, title="EXECUTE", sub="Plan & GTT", hard=False, ok=None, execute=True,
             metrics=[], do_now=plan),
    ]

    stop_at = None
    for s in steps:
        if s.get("hard") and not s["ok"]:
            stop_at = s["n"]; break

    if s34 or not rs:
        verdict, color = "AVOID / EXIT", "#EF5350"
    elif stop_at == 1:
        verdict, color = "AVOID", "#EF5350"
    elif stop_at == 2:
        verdict, color = "WATCHLIST", "#FF9800"
    elif not g3:
        verdict, color = "BUY-WATCH · no catalyst", "#FF9800"
    elif not g4:
        verdict, color = "WAIT FOR PULLBACK", "#FF9800"
    elif pa_fired:
        verdict, color = "BUY — TRIGGER LIVE", "#26A69A"
    else:
        verdict, color = "ARMED · AWAIT TRIGGER", "#FF9800"

    # The single step that needs attention right now
    if stop_at:
        current = stop_at
    elif not g3:
        current = 3
    elif not g4:
        current = 4
    else:
        current = 5
    actionable = verdict not in ("AVOID", "AVOID / EXIT", "WATCHLIST")
    return dict(steps=steps, verdict=verdict, color=color, stop_at=stop_at,
                current=current, actionable=actionable,
                # numeric plan levels for the page's position sizer / journal form
                plan_entry=(entry if sl is not None else None),
                plan_sl=sl, plan_t1=t1)


def compute_recovery_workflow(rec_r, ctx, cmp_px) -> dict:
    """Recovery-specific decision path — used when the primary signal is a
    RECOVERY catalyst (REV-CB/RS/EARLY + WYC-*). The bull compute_workflow()
    hard-requires Stage 2 at Step 1, which every beaten-down recovery name
    fails by definition. Recovery gates are different:
      1. CONTEXT  — beaten down (≥10% off 52WH) in an open recovery regime
      2. QUALITY  — fundamentally strong (RFF ≥ 4/6) — the recovery thesis
      3. SETUP    — a recovery catalyst actually fired (Signal ≥ 2)
      4. LOCATION — not chased far above the engine's recovery entry
      5. TRIGGER  — closed-bar confirmation (manual)
      6. EXECUTE  — the recovery engine's Entry/SL/T1/T2 plan
    Returns the SAME dict shape as compute_workflow() so render_workflow()
    renders it unchanged.
    """
    _dd_floor, _rff_min = _rec_cfg()
    sig    = int(_g(rec_r, "Signal", default=0) or 0)
    label  = str(_g(rec_r, "Signal_Label", default="None"))
    rff_b  = _g(rec_r, "RFF_Base", default=0) or 0
    if isinstance(rff_b, float) and math.isnan(rff_b):
        rff_b = 0
    rff_q  = str(_g(rec_r, "RFF_Quality", default="INSUFFICIENT"))
    if rff_q.lower() in ("nan", "none", ""):
        rff_q = "INSUFFICIENT"
    rff_ok = (rff_q != "INSUFFICIENT") and rff_b >= _rff_min
    # Batch-CSV rows carry Weinstein_Stage as a float (1.0) — normalize to the
    # bare digit so display reads "Stage 1" and the chip test works.
    stage_num = _stg_digit(_g(rec_r, "Weinstein_Stage", default="")) or "—"
    corr   = _g(rec_r, "Correction_52W_pct")
    if isinstance(corr, float) and math.isnan(corr):
        corr = None
    reg_ok = bool(_g(rec_r, "Regime_OK", default=False))
    rrg    = str(_g(rec_r, "RRG_Quadrant", default="—")); rrg_ok = rrg in ("LEADING", "IMPROVING")
    rs_val = _g(rec_r, "Mansfield_RS_x100")
    beaten = (corr is not None) and (corr >= _dd_floor)
    # RS turning up (Mansfield survivor read) — Step-2 quality confirmation. IMPROVING =
    # RS-momentum turning up from a lagging base; LEADING = already outperforming.
    rs_up = rrg in ("LEADING", "IMPROVING")
    # Recovery PA battery (10) — the Step-5 trigger, mirror of S4 Recovery mode.
    _rpa = _g(ctx, "recovery_pa_patterns", default=[]) or []
    _rpa_tier = sum(t for _, f, t, _ in _rpa if f)
    _rpa_fired = sorted([(nm, t) for nm, f, t, _ in _rpa if f], key=lambda x: -x[1])
    rpa_fired = len(_rpa_fired) > 0
    _rpa_names = ", ".join(nm for nm, _ in _rpa_fired[:4])
    # Trigger TF (75m/125m/Daily) so Step-5 wording names the actual TF the
    # recovery battery ran on (was hardcoded "fired on the daily").
    _tf_lbl = str(_g(ctx, "_trigger_tf", default="Daily"))
    _is_intra = _tf_lbl in ("75m", "125m")
    _fired_on = _tf_lbl if _is_intra else "daily"
    _confirm_lbl = f"{_tf_lbl} close" if _is_intra else "75/125m close"

    entry = _g(rec_r, "Entry"); sl = _g(rec_r, "SL")
    t1 = _g(rec_r, "T1"); t2 = _g(rec_r, "T2"); rr = _g(rec_r, "RR_T1"); sl_pct = _g(rec_r, "SL_pct")
    # NaN → None. A batch CSV row (rec_r from Recovery_Screener_Results.csv)
    # yields float NaN for a missing level (e.g. ANTHEM had T2=NaN); NaN is
    # truthy in Python, so it would slip past `if x` guards and reach inr()/format.
    entry, sl, t1, t2, rr, sl_pct = [
        (None if (v is None or (isinstance(v, float) and math.isnan(v))) else v)
        for v in (entry, sl, t1, t2, rr, sl_pct)]

    # LIVE timing gate (the real recovery funnel). The recovery ENGINE already
    # enforced beaten-down + RFF + regime + RS-positive before firing, so those
    # gates are tautologically true for every fired name (all pass). The
    # decision-stage discriminator is TIMING: has the turn actually confirmed
    # (price reclaimed the 20-EMA) and is it not already extended (bounce not
    # chased)? Uses LIVE ctx (same daily data the bull path uses), so a recovery
    # still below its 20-EMA (turn unconfirmed) or already run up is held at
    # WAIT — only genuinely-timed entries reach the trigger step.
    _ema20 = _g(ctx, "ema20")
    turn_ok = bool(_ema20) and cmp_px is not None and cmp_px >= _ema20    # reclaimed 20-EMA
    ext_ema = ((cmp_px - _ema20) / _ema20 * 100) if (_ema20 and cmp_px) else None
    not_chased = (ext_ema is None) or (ext_ema <= 8.0)                    # ≤8% above 20-EMA
    loc_ok = turn_ok and not_chased

    g1 = beaten and reg_ok
    g2 = rff_ok
    g3 = sig >= 2

    if entry and sl:
        plan = (f"Set SL {inr(sl)}" + (f" (-{sl_pct:.1f}%)" if sl_pct is not None else "") +
                f", size at 0.25% risk, place order + GTT. "
                f"Target T1 {inr(t1)}" + (f" ({fnum(rr,1)}R)" if rr is not None else "") +
                (f", T2 {inr(t2)}" if t2 else "") + ".")
    else:
        plan = "No recovery levels available."

    steps = [
        dict(n=1, title="CONTEXT", sub="Beaten-down + regime", hard=True, ok=g1,
             metrics=[("Off 52W high", fnum(corr, 1, "%") if corr is not None else "—", beaten),
                      ("Recovery regime", "OPEN" if reg_ok else "closed", reg_ok),
                      ("Stage", f"Stage {stage_num}", stage_num in ("1", "2")),
                      ("RS vs N500", fnum(rs_val, 1), rrg_ok)],
             do_pass="Beaten-down in an open recovery regime — the recovery context.",
             do_fail="Not beaten-down / regime closed — not a recovery setup. SKIP."),
        dict(n=2, title="QUALITY", sub="Fundamentals (RFF) + RS", hard=True, ok=g2,
             metrics=[("RFF gate", f"{rff_b}/6 (min {_rff_min})", rff_ok),
                      ("RFF quality", rff_q, rff_q == "FULL"),
                      ("RS turning up", ("yes · " + rrg) if rs_up else ("no · " + rrg), rs_up),
                      ("Mansfield RS", fnum(rs_val, 1), (rs_val or 0) > 0)],
             do_pass="Fundamentally strong (RFF ≥ 4/6) with RS turning up — a survivor, quality on sale.",
             do_fail="Fundamentals insufficient (RFF < 4). SKIP — recovery needs strong fundamentals."),
        dict(n=3, title="SETUP", sub="Recovery catalyst", hard=True, ok=g3,
             metrics=[("Signal", label, sig >= 2),
                      ("Type", ("Wyckoff" if sig >= 5 else "REV"), sig >= 2),
                      ("PA Patterns", (f"+{_rpa_tier}" if _rpa_tier else "none"), _rpa_tier >= 2)],
             do_pass=f"Recovery catalyst {label} is LIVE — proceed to location.",
             do_fail="No recovery catalyst fired."),
        dict(n=4, title="LOCATION", sub="Turn confirmed & not chased", hard=False, ok=loc_ok,
             metrics=[("Turn (≥20-EMA)", "confirmed" if turn_ok else "below 20-EMA", turn_ok),
                      ("Ext vs 20-EMA", fnum(ext_ema, 1, "%") if ext_ema is not None else "—", not_chased),
                      ("Entry (engine)", inr(entry) if entry else "—", True),
                      ("Support (auto)", str((_g(ctx, "support", default={}) or {}).get("zone", "outside")),
                       bool((_g(ctx, "support", default={}) or {}).get("at_support")))],
             do_pass="Turn confirmed (reclaimed 20-EMA) & not extended — mark the FRESH demand zone on Daily+.",
             do_fail=("Below 20-EMA — turn not yet confirmed; WAIT for the base to reclaim it."
                      if not turn_ok else
                      "Bounce already extended > 8% above 20-EMA — WAIT for a pullback into the zone.")),
        dict(n=5, title="TRIGGER", sub=(f"Recovery PA battery · {_tf_lbl}" if _is_intra else "Recovery PA battery + intraday confirm"),
             hard=False, ok=None, manual=True,
             metrics=[("PA trigger", (_rpa_names if rpa_fired else "none yet"), rpa_fired),
                      ("Σ tier", (f"+{_rpa_tier}" if _rpa_tier else "0"), _rpa_tier >= 2),
                      ("Confirm on", _confirm_lbl, None)],
             do_now=((f"TRIGGER LIVE — {_rpa_names} (Σ+{_rpa_tier}) fired on the {_fired_on}"
                      + (f" bar at the zone → buy-STOP above that {_tf_lbl} bar's high. Never buy the touch."
                         if _is_intra else
                         ". Drop to 75/125m, confirm a CLOSED bar at the zone → buy-STOP above its high. Never buy the touch."))
                     if rpa_fired else
                     (f"No {_fired_on} recovery PA trigger yet. Wait for a closed-bar reversal (Climax reclaim / Spring / "
                      f"Higher-Low-2B / Base-Breakout / Engulf / Hammer …) at the base on the {_tf_lbl} chart."))),
        dict(n=6, title="EXECUTE", sub="Recovery plan & GTT", hard=False, ok=None, execute=True,
             metrics=[], do_now=plan),
    ]

    stop_at = None
    for s in steps:
        if s.get("hard") and not s["ok"]:
            stop_at = s["n"]; break

    if stop_at == 1:
        verdict, color = "NOT A RECOVERY CONTEXT", "#EF5350"
    elif stop_at == 2:
        verdict, color = "SKIP · weak fundamentals", "#EF5350"
    elif stop_at == 3:
        verdict, color = "NO RECOVERY CATALYST", "#FF9800"
    elif not loc_ok:
        verdict, color = "WAIT FOR PULLBACK", "#FF9800"
    elif rpa_fired:
        verdict, color = "BUY — TRIGGER LIVE · Recovery", "#26A69A"
    else:
        verdict, color = "ARMED · AWAIT TRIGGER · Recovery", "#FF9800"

    if stop_at:
        current = stop_at
    elif not loc_ok:
        current = 4
    else:
        current = 5
    actionable = verdict.startswith("BUY") or verdict.startswith("ARMED") or verdict.startswith("WAIT")
    return dict(steps=steps, verdict=verdict, color=color, stop_at=stop_at,
                current=current, actionable=actionable, recovery=True,
                plan_entry=entry, plan_sl=sl, plan_t1=t1)


def render_workflow(wf: dict) -> str:
    cmap = {"pass": "#26A69A", "fail": "#EF5350", "wait": "#FF9800",
            "pending": "#2962FF", "skip": "#9aa0a6", "plan": "#26A69A"}
    pill = {"pass": "DONE", "fail": "STOP", "wait": "WAIT", "pending": "YOUR MOVE", "skip": "LOCKED", "plan": "PLAN"}
    cur = wf.get("current")
    steps_html = ""; prior_fail = False; n = len(wf["steps"])
    for i, s in enumerate(wf["steps"]):
        if prior_fail:
            status = "skip"
        elif s.get("manual"):
            status = "pending"
        elif s.get("execute"):
            status = "plan"
        elif s["ok"] is True:
            status = "pass"
        elif s["ok"] is False:
            status = "fail" if s.get("hard") else "wait"
        else:
            status = "pending"
        col = cmap[status]
        is_cur = (s["n"] == cur and status != "skip")
        chips = ""
        for lab, val, ok in s["metrics"]:
            cc = "#26A69A" if ok else ("#EF5350" if ok is False else "#9aa0a6")
            mk = "✓" if ok else ("✗" if ok is False else "·")
            chips += (f"<span style='display:inline-block;margin:3px 9px 0 0;font-size:11.5px'>"
                      f"<span style='opacity:.7'>{lab}</span> <b>{val}</b> "
                      f"<span style='color:{cc};font-weight:700'>{mk}</span></span>")
        # imperative guidance line — this is the "do this" of the sequence
        if status == "skip":
            guide = ""
        elif status == "pass":
            guide = "✓ " + s.get("do_pass", "")
        elif status == "fail":
            guide = "⛔ " + s.get("do_fail", "")
        elif status == "wait":
            guide = "⏳ " + s.get("do_fail", "")
        else:
            guide = "▶ " + s.get("do_now", "")
        guide_html = (f"<div style='font-size:11.5px;margin-top:3px;color:{col};font-weight:600'>{guide}</div>"
                      if guide else "")
        nowbadge = ("<span style='font-size:9px;font-weight:800;color:#fff;background:#111;"
                    "padding:1px 7px;border-radius:9px;margin-left:6px'>← NOW</span>" if is_cur else "")
        line = "" if i == n - 1 else f"<div style='width:2px;flex:1;background:{col}55;min-height:10px;margin:2px 0'></div>"
        bg = f"background:{col}14;border-radius:7px;padding:5px 8px;margin:-4px 0;" if is_cur else "padding:0 8px;"
        steps_html += (
            f"<div style='display:flex;gap:11px;align-items:stretch'>"
            f"<div style='display:flex;flex-direction:column;align-items:center;flex:0 0 28px'>"
            f"<div style='width:28px;height:28px;border-radius:50%;background:{col};color:#fff;display:flex;"
            f"align-items:center;justify-content:center;font-weight:800;font-size:13px;"
            f"{'box-shadow:0 0 0 3px ' + col + '44;' if is_cur else ''}'>{s['n']}</div>{line}</div>"
            f"<div style='flex:1;padding-bottom:10px'><div style='{bg}'>"
            f"<div style='display:flex;align-items:center;gap:8px'>"
            f"<span style='font-weight:800;font-size:12.5px;color:{col}'>STEP {s['n']} · {s['title']}</span>"
            f"<span style='font-size:9.5px;opacity:.55'>{s['sub']}</span>{nowbadge}"
            f"<span style='margin-left:auto;font-size:9.5px;font-weight:800;color:#fff;background:{col};"
            f"padding:1px 8px;border-radius:9px'>{pill[status]}</span></div>"
            f"{('<div>' + chips + '</div>') if chips else ''}{guide_html}</div></div></div>")
        if s.get("hard") and s["ok"] is False:
            prior_fail = True
    sub = (f"⛔ stops at Step {wf['stop_at']}" if wf["stop_at"] else f"→ you are at Step {cur}")
    return (f"<div style='border:2px solid {wf['color']};border-radius:10px;padding:12px 16px;"
            f"background:{wf['color']}11;max-width:880px'>"
            f"<div style='display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:11px'>"
            f"<span style='font-size:11px;letter-spacing:1px;opacity:.55'>DECISION PATH</span>"
            f"<span style='font-size:26px;font-weight:900;color:{wf['color']}'>{wf['verdict']}</span>"
            f"<span style='font-size:11px;opacity:.6'>{sub}</span></div>{steps_html}</div>")


def render_technical_board(rec: dict, ctx: dict, cmp_px, mansfield) -> str:
    """Build the full graphical technical board as one HTML string."""
    rsi = _g(rec, "RSI"); adx = _g(ctx, "adx"); alpha = _g(rec, "Alpha"); ml = _g(rec, "ML_Prob")
    vdry = _g(ctx, "vol_dry")
    rsi_state = ("watch" if (rsi or 0) >= 70 else "pass" if (rsi or 0) >= 50 else "watch" if (rsi or 0) >= 40 else "fail")
    gauges = "".join([
        _gauge("RSI (14)", rsi, 0, 100,
               "linear-gradient(90deg,#EF5350,#FF9800 30%,#26A69A 50%,#26A69A 68%,#FF9800 78%,#EF5350)",
               rsi_state, fnum(rsi, 0)),
        _gauge("ADX (14)", adx, 0, 50,
               "linear-gradient(90deg,#EF5350,#FF9800 40%,#26A69A 50%)",
               ("pass" if (adx or 0) >= 25 else "watch" if (adx or 0) >= 20 else "fail"), fnum(adx, 0)),
        _gauge("Alpha Score", alpha, 0, 100,
               "linear-gradient(90deg,#EF5350,#FF9800 50%,#26A69A 70%)",
               ("pass" if (alpha or 0) >= 70 else "watch" if (alpha or 0) >= 50 else "fail"), fnum(alpha, 0)),
        _gauge("ML Win Prob", ml, 0, 100,
               "linear-gradient(90deg,#EF5350,#FF9800 55%,#26A69A 65%)",
               ("pass" if (ml or 0) >= 65 else "watch" if (ml or 0) >= 55 else "fail"), fnum(ml, 1, "%")),
        _gauge("Mansfield RS", mansfield, -50, 50,
               "linear-gradient(90deg,#EF5350,#80808055 50%,#26A69A)",
               ("pass" if (mansfield or 0) > 0 else "fail"), fnum(mansfield, 1)),
        _gauge("Vol Dry-up 5/20d", vdry, 0, 2,
               "linear-gradient(90deg,#26A69A,#FF9800 50%,#EF5350)",
               ("pass" if (vdry if vdry is not None else 9) < 0.8 else "na"), fnum(vdry, 2, "×")),
    ])

    rng = _range_bar(_g(ctx, "low52w"), _g(ctx, "high52w"), cmp_px, [
        (_g(ctx, "sma200"), "200", "#EF5350"),
        (_g(ctx, "sma50"), "50", "#2962FF"),
        (_g(ctx, "ema20"), "20e", "#FF9800"),
    ])

    # Minervini 8-point trend template (shared with the decision engine)
    e20 = _g(ctx, "ema20"); s50 = _g(ctx, "sma50"); s150 = _g(ctx, "sma150"); s200 = _g(ctx, "sma200")
    passed, c8 = minervini_checks(ctx, cmp_px, mansfield)
    dots = "".join(_crit(ok, lab) for ok, lab in c8)

    # Price-action signal pills
    stage = str(_g(rec, "Stage", default="—")); s2 = "2" in stage
    stacked = bool(e20 and s50 and cmp_px > e20 > s50 and (not s200 or s50 > s200))
    above30w = bool(s150 and cmp_px > s150)
    adir = _g(rec, "Active_Dir", default="—"); vacc = _g(rec, "Vel_Accel", default="")
    vcp = bool(_g(rec, "VCP_Valid")); rrg = _g(rec, "RRG_Quadrant", default="—")
    broke = bool(_g(rec, "Broke_Pivot")); rv = _g(ctx, "relvol"); d52 = _g(ctx, "dist52wh")
    # v3 (Jay's dissection): Trend W/D replaces "Swing Structure" (weekly PA trend /
    # daily Zigzag swing dir); Px vs EMA20 replaces Px vs 30W-MA (Stage 2 already
    # implies above 30WMA); 52WH dist paired with 2y-high dist.
    s150p = _g(ctx, "sma150_prev")
    wk_up = bool(s150 and cmp_px > s150 and (s150p is None or s150 > s150p))
    d_up = str(adir).upper().startswith("UP")
    above_e20 = bool(e20 and cmp_px > e20)
    dath = _g(ctx, "dist_ath")
    # Trend qualifiers (Jay): Weekly accel from the 30W-MA-proxy slope change
    # (recent 21d slope vs the prior 21d slope, direction-aware); Daily from the
    # swing engine's Vel_Accel.
    # Qualifier vocabulary names the IMPLICATION, not the mechanics (Jay:
    # "Down (Decelerating)" read wrong): Strengthening / Losing Steam for
    # uptrends, Deepening / Easing for downtrends, Steady when unchanged.
    s150p2 = _g(ctx, "sma150_prev2")
    w_q = ""
    if s150 and s150p and s150p2:
        _sl1, _sl2 = s150 - s150p, s150p - s150p2
        _eps = s150 * 0.0005
        _diff = _sl1 - _sl2
        if wk_up:
            w_q = "Strengthening" if _diff > _eps else ("Losing Steam" if _diff < -_eps else "Steady")
        else:
            w_q = "Deepening" if _diff < -_eps else ("Easing" if _diff > _eps else "Steady")
    _va = str(vacc).upper()
    if d_up:
        d_q = {"UP": "Strengthening", "DOWN": "Losing Steam", "FLAT": "Steady"}.get(_va, "")
    else:
        d_q = {"UP": "Deepening", "DOWN": "Easing", "FLAT": "Steady"}.get(_va, "")
    _wtxt = ("Up" if wk_up else "Down") + (f" ({w_q})" if w_q else "")
    _dtxt = ("Up" if d_up else "Down") + (f" ({d_q})" if d_q else "")
    pills = "".join([
        _pill("pass" if s2 else ("watch" if "1" in stage else "fail"), "Weinstein Stage", stage),
        _pill("pass" if stacked else "watch", "EMA Stack", "Px&gt;20&gt;50&gt;200" if stacked else "broken"),
        _pill("pass" if above_e20 else "watch", "Px vs EMA20", "above" if above_e20 else "below"),
        _pill("pass" if (wk_up and d_up) else ("watch" if (wk_up or d_up) else "fail"),
              "Trend W / D", f"{_wtxt} / {_dtxt}"),
        _pill("pass" if vcp else "na", "VCP / Base", (f"valid · {_g(rec,'Days_Since_Pivot','—')}d" if vcp else "no")),
        _pill("pass" if rrg in ("LEADING", "IMPROVING") else "watch", "RRG", f"{rrg} {_g(rec,'RRG_Arrow','')}"),
        _pill("pass" if broke else "na", "Pivot", ("broke ↑" if broke else (inr(_g(rec, "Pivot_Price")) if _g(rec, "Pivot_Price") else "—"))),
        _pill("pass" if (rv or 0) >= 1 else "na", "Rel Volume", fnum(rv, 2, "×")),
        _pill(("pass" if (d52 is not None and -15 <= d52 <= -1) else ("watch" if (d52 or -99) > -1 else "na")),
              "52WH / ATH Dist", f"{fnum(d52, 1, '%')} / {fnum(dath, 1, '%')}"),
    ])

    sub = ("<div style='font-size:11px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;"
           "opacity:.6;margin:11px 0 4px'>{}</div>")
    return (
        sub.format("Momentum &amp; Strength")
        + f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:2px 16px;'>{gauges}</div>"
        + sub.format("52-Week Range (●=CMP, ticks=MAs)")
        + rng
        + sub.format(f"Minervini Trend Template — {passed}/8")
        + ("<div style='display:flex;gap:12px;align-items:center;'>"
           f"<div>{_donut(passed, 8)}</div>"
           f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:0 14px;flex:1'>{dots}</div></div>")
        + sub.format("Price-Action Signals")
        + f"<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:5px;'>{pills}</div>"
    )


# ----------------------------------------------------------------------------------------
# Data (cached; the Refresh button clears it)
# ----------------------------------------------------------------------------------------
# PA batteries moved to the shared pa_patterns.py module (E5, 9-Jul-2026) —
# single source of truth for every Python surface; the local names are kept
# as thin aliases so all existing call sites are untouched.
from pa_patterns import (
    detect_bull_patterns as _detect_pa_patterns,
    detect_recovery_patterns as _detect_recovery_pa_patterns,
)


def section_pa_patterns(ctx) -> str:
    """PA pattern battery card — fired patterns highlighted, quiet ones dim."""
    pats = _g(ctx, "pa_patterns", default=[]) or []
    if not pats:
        return card("PA PATTERNS · v67 mirror", [("Patterns", "unavailable", "na")], "#455A64")
    rows = [(f"{name}  (+{tier})", ("FIRED — " + note) if fired else "quiet",
             "pass" if fired else "na") for name, fired, tier, note in pats]
    tier_sum = sum(t for _, f, t, _ in pats if f)
    # Tier-weighted score, NO denominator (Jay: 11/11 is not the benchmark —
    # patterns are bonuses). Purple = Power-Play-grade Σ, grey = quiet (normal).
    scol = ("#7B1FA2" if tier_sum >= 4 else "#26A69A" if tier_sum >= 2
            else "#FF9800" if tier_sum >= 1 else "#787B86")
    SECTION_SCORES["Pa Patterns"] = (f"Σ +{tier_sum}", None, scol)
    hdr_col = scol if tier_sum >= 1 else "#455A64"
    return card("PA PATTERNS · v67 mirror", rows, "#455A64",
                chip_text=f"Σ +{tier_sum}", chip_color=hdr_col)


def render_pa_banner(ctx) -> str:
    """High-visibility banner when strong PA patterns are live — Jay can't
    spot these on the chart; the dashboard must shout them."""
    pats = [(n, t) for n, f, t, _ in (_g(ctx, "pa_patterns", default=[]) or []) if f]
    if not pats:
        return ""
    tier_sum = sum(t for _, t in pats)
    chips = " · ".join(f"{n} (+{t})" for n, t in sorted(pats, key=lambda x: -x[1]))
    col = "#7B1FA2" if tier_sum >= 4 else "#26A69A"
    return (f"<div style='border:2px solid {col};background:{col}18;border-radius:9px;"
            f"padding:8px 14px;margin:8px 0;font-size:14px'>"
            f"<b style='color:{col}'>🔥 PA PATTERNS LIVE (Σ +{tier_sum}):</b> {chips}</div>")


@st.cache_data(ttl=120, show_spinner=False)
def gm_load_symbol(symbol: str) -> dict:
    """Pull everything for one symbol from the existing validated modules."""
    out = {"symbol": symbol, "errors": []}

    # --- Technical record (Stage / RS / Alpha / Catalyst / levels / ML) ---
    try:
        import bull_screener as bs
        out["rec"] = bs.screen_one(symbol, force_output=True)
    except Exception as e:
        out["rec"] = None
        out["errors"].append(f"screen_one: {e}")
    # NOTE: the Recovery engine is loaded SEPARATELY via gm_load_recovery() so a
    # slow/blocking live fundamental fetch can never stall this hot path (which
    # the 2s TV auto-sync depends on staying fast). See gm_load_recovery below.

    # --- Daily indicator context (EMA stack / 200-DMA / RelVol / 52WH dist) ---
    try:
        import data_provider as dp
        df = dp.fetch_ohlcv(symbol, period="2y", interval="1d", use_cache=True, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        out["df"] = df
        c = df["Close"]; h = df["High"]; l = df["Low"]; v = df["Volume"]
        ema20 = c.ewm(span=20, adjust=False).mean()
        sma50 = c.rolling(50).mean()
        sma150 = c.rolling(150).mean()
        sma200 = c.rolling(200).mean()
        h52 = h.rolling(min(252, len(h))).max()
        l52 = l.rolling(min(252, len(l))).min()
        last = float(c.iloc[-1])
        # Wilder ADX(14) + directional indices
        up = h.diff(); dn = -l.diff()
        plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
        minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
        tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/14, adjust=False).mean()
        pdi = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / atr
        mdi = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / atr
        dx = (100 * (pdi - mdi).abs() / (pdi + mdi)).replace([np.inf, -np.inf], np.nan)
        adx = dx.ewm(alpha=1/14, adjust=False).mean()
        # Bollinger width (20,2) + 5d/20d volume dry-up ratio
        mid = c.rolling(20).mean(); sd = c.rolling(20).std()
        bbw = float(((mid + 2*sd) - (mid - 2*sd)).iloc[-1] / mid.iloc[-1]) if mid.iloc[-1] else None
        vol20 = float(v.rolling(20).mean().iloc[-1]); vol5 = float(v.rolling(5).mean().iloc[-1])

        def _f(s):
            x = float(s.iloc[-1]); return None if math.isnan(x) else x

        def _fprev(s, n):
            if len(s) > n and not math.isnan(s.iloc[-1 - n]):
                return float(s.iloc[-1 - n])
            return None

        # --- Pine-panel primitives (mirror of v67 Decision Mode composite rows) ---
        # CPR (Central Pivot Range) from the prior bar
        try:
            ph, pl, pc = float(h.iloc[-2]), float(l.iloc[-2]), float(c.iloc[-2])
            cpr_p = (ph + pl + pc) / 3.0
            cpr_bc = (ph + pl) / 2.0
            cpr_tc = 2 * cpr_p - cpr_bc
        except Exception:
            cpr_p = cpr_bc = cpr_tc = None
        # Monthly anchored VWAP (current calendar month)
        try:
            tp = (h + l + c) / 3.0
            mper = df.index.to_period("M")
            msk = (mper == mper[-1])
            mvwap = float((tp[msk] * v[msk]).sum() / v[msk].sum()) if v[msk].sum() else None
        except Exception:
            mvwap = None
        # Macro edge — volume shelf: VWMA(20) > SMA(50)
        try:
            vwma20 = float((c * v).rolling(20).sum().iloc[-1] / v.rolling(20).sum().iloc[-1])
            shelf_ok = bool(_f(sma50) and vwma20 > _f(sma50))
        except Exception:
            vwma20 = None; shelf_ok = False
        # Accumulation days — green close in upper-60% of range on above-avg vol (last 10)
        try:
            rng = (h - l).replace(0, np.nan)
            acc_mask = ((c - l) / rng >= 0.6) & (c > c.shift()) & (v > v.rolling(50).mean())
            acc_days = int(acc_mask.iloc[-10:].sum())
            acc_ok = acc_days >= 2
        except Exception:
            acc_days = 0; acc_ok = False
        # TTM-style squeeze — BB(20,2) inside Keltner(20, 1.5*ATR)
        try:
            kc_up = mid + 1.5 * atr; kc_dn = mid - 1.5 * atr
            squeeze_on = bool((mid.iloc[-1] + 2 * sd.iloc[-1] < kc_up.iloc[-1]) and
                              (mid.iloc[-1] - 2 * sd.iloc[-1] > kc_dn.iloc[-1]))
        except Exception:
            squeeze_on = False
        # Stage-2 freshness — weeks since price last reclaimed ~30W MA (SMA150)
        try:
            above150 = (c > sma150).tolist()
            since = 0
            for val in reversed(above150):
                if val:
                    since += 1
                else:
                    break
            stage2_weeks = since / 5.0
        except Exception:
            stage2_weeks = None

        # Volume Profile (POC / VAH / VAL) over the last 120 bars
        try:
            win = df.iloc[-120:]
            tp_w = ((win["High"] + win["Low"] + win["Close"]) / 3.0).values
            volw = win["Volume"].values
            lo_p, hi_p = float(win["Low"].min()), float(win["High"].max())
            nb = 40
            edges = np.linspace(lo_p, hi_p, nb + 1)
            bidx = np.clip(np.digitize(tp_w, edges) - 1, 0, nb - 1)
            prof = np.zeros(nb)
            for bi, vv in zip(bidx, volw):
                prof[bi] += vv
            pb = int(prof.argmax())
            poc = (edges[pb] + edges[pb + 1]) / 2.0
            tgt = prof.sum() * 0.70; lo_b = hi_b = pb; acc_v = prof[pb]
            while acc_v < tgt and (lo_b > 0 or hi_b < nb - 1):
                lft = prof[lo_b - 1] if lo_b > 0 else -1.0
                rgt = prof[hi_b + 1] if hi_b < nb - 1 else -1.0
                if rgt >= lft:
                    hi_b += 1; acc_v += prof[hi_b]
                else:
                    lo_b -= 1; acc_v += prof[lo_b]
            val_lo = (edges[lo_b] + edges[lo_b + 1]) / 2.0
            vah_hi = (edges[hi_b] + edges[hi_b + 1]) / 2.0
            dist_poc = (last - poc) / poc * 100 if poc else None
            vp_pos = "ABOVE VAH" if last > vah_hi else ("BELOW VAL" if last < val_lo else "INSIDE VA")
        except Exception:
            poc = vah_hi = val_lo = dist_poc = None; vp_pos = "—"

        # Open Fair-Value-Gaps (3-bar) in the last 30 bars
        try:
            Hs = df["High"].values; Ls = df["Low"].values
            bull_fvg = bear_fvg = 0
            for i in range(max(2, len(df) - 30), len(df)):
                if Ls[i] > Hs[i - 2]:
                    bull_fvg += 1
                if Hs[i] < Ls[i - 2]:
                    bear_fvg += 1
        except Exception:
            bull_fvg = bear_fvg = 0

        out["ctx"] = {
            "cmp": last,
            "prev": float(c.iloc[-2]) if len(c) > 1 else last,
            "ema20": _f(ema20), "sma50": _f(sma50), "sma150": _f(sma150), "sma200": _f(sma200),
            "sma200_prev": _fprev(sma200, 21), "sma150_prev": _fprev(sma150, 21),
            "sma150_prev2": _fprev(sma150, 42),
            "ath2y": float(h.max()) if len(h) else None,
            "dist_ath": (last - float(h.max())) / float(h.max()) * 100 if len(h) and float(h.max()) else None,
            "adx": _f(adx), "plus_di": _f(pdi), "minus_di": _f(mdi),
            "high52w": _f(h52), "low52w": _f(l52),
            "dist52wh": (last - _f(h52)) / _f(h52) * 100 if _f(h52) else None,
            "relvol": (float(v.iloc[-1] / vol20)
                       if (vol20 and not math.isnan(vol20)) else None),
            "vol_dry": (vol5 / vol20) if vol20 else None,
            "bbw": bbw,
            "cpr_p": cpr_p, "cpr_tc": cpr_tc, "cpr_bc": cpr_bc,
            "mvwap": mvwap, "vwma20": vwma20, "shelf_ok": shelf_ok,
            "acc_days": acc_days, "acc_ok": acc_ok, "squeeze_on": squeeze_on,
            "stage2_weeks": stage2_weeks,
            "poc": poc, "vah": vah_hi, "val": val_lo, "dist_poc": dist_poc, "vp_pos": vp_pos,
            "bull_fvg": bull_fvg, "bear_fvg": bear_fvg,
            "turnover_cr": last * float(v.iloc[-1]) / 1e7,
        }
    except Exception as e:
        out["ctx"] = None
        out["errors"].append(f"daily ctx: {e}")

    # --- Fundamentals (Screener.in via fundamental_hub) ---
    try:
        import fundamental_hub as fh
        yf_sym = symbol if symbol.endswith((".NS", ".BO")) else symbol + ".NS"
        out["fun"] = fh.fetch_stock_fundamentals(yf_sym)
    except Exception as e:
        out["fun"] = {}
        out["errors"].append(f"fundamentals: {e}")

    # --- Bull Fundamental Filter (BFF) — Minervini growth leg (screener.in),
    #     DISPLAY-ONLY status for the Bull QUALITY step (never gates). Computed
    #     once per symbol load (cached with this result + 24h in the module), so
    #     no inline fetch on rerun. Guarded: a failure can't break the load. ---
    try:
        from bull_fundamental_filter import compute_bff
        out["bff"] = compute_bff(symbol)
    except Exception as e:
        out["bff"] = None
        out["errors"].append(f"bff: {e}")

    # --- Sector strength (sector_lookup + sector_strength, same modules the
    #     bull screener's score uses) + Futures OI from the latest matcher CSV ---
    _bare = symbol.replace(".NS", "").replace(".BO", "").upper()
    if isinstance(out.get("ctx"), dict):
        # True ATH via 10y weekly (Dhan-native, cached 24h) — replaces the 2y proxy
        try:
            import data_provider as _dp2
            _w10 = _dp2.fetch_ohlcv(symbol, period="10y", interval="1wk", use_cache=True, auto_adjust=True)
            if _w10 is not None and len(_w10):
                _athv = max(float(_w10["High"].max()), float(out["ctx"].get("high52w") or 0))
                if _athv > 0:
                    out["ctx"]["ath"] = _athv
                    out["ctx"]["dist_ath"] = (out["ctx"]["cmp"] - _athv) / _athv * 100
        except Exception:
            pass
        # v67-mirror PA pattern battery (Jay: can't spot these by eye — detect them)
        try:
            if out.get("df") is not None:
                _stage0 = str((out.get("rec") or {}).get("Stage", ""))
                out["ctx"]["pa_patterns"] = _detect_pa_patterns(out["df"], _stage0)
                out["ctx"]["recovery_pa_patterns"] = _detect_recovery_pa_patterns(out["df"], _stage0)
        except Exception:
            pass
        # Auto support zones (OB / FVG / pivot-low) on BOTH Daily AND Weekly —
        # the Python twin of the S4 Pine v2.1 trackers (trading TF is 125/75m,
        # but the demand zones come from D+W structure). Automates Steps 1-2.
        try:
            import pa_patterns as _pap
            if out.get("df") is not None:
                out["ctx"]["support"] = _pap.detect_support_zones_dw(out["df"])
        except Exception:
            out["ctx"]["support"] = {}
        try:
            from sector_lookup import get_sector_index
            from sector_strength import get_sector_status, get_sector_score
            _si = get_sector_index(_bare)
            if _si:
                _st = get_sector_status(_si) or {}
                out["ctx"].update({
                    "sector_idx":   _si,
                    "sector_w_pct": _st.get("weekly_pct"),
                    "sector_m_pct": _st.get("monthly_pct"),
                    "sector_score": get_sector_score(_si),
                })
        except Exception as e:
            out["errors"].append(f"sector: {e}")
        try:
            for _p in (os.path.join("Screener CSVs", "Golden_Matcher_Results.csv"),
                       "FINAL_WATCHLIST.csv"):
                if os.path.exists(_p):
                    _m = pd.read_csv(_p)
                    if "Futures_OI_Chg_Pct" in _m.columns and "Symbol" in _m.columns:
                        _r = _m[_m["Symbol"].astype(str).str.upper() == _bare]
                        if len(_r) and pd.notna(_r.iloc[0]["Futures_OI_Chg_Pct"]):
                            out["ctx"]["fut_oi"] = float(_r.iloc[0]["Futures_OI_Chg_Pct"])
                            break
        except Exception:
            pass

    out["fetched_at"] = datetime.now().strftime("%d-%b %H:%M:%S")
    return out


@st.cache_data(ttl=300, show_spinner=False)
def gm_load_recovery(symbol: str, deep: bool = False) -> dict:
    """Recovery engine read (REV-CB/RS/EARLY + WYC-*), loaded SEPARATELY from
    gm_load_symbol so it never stalls the 2s TV auto-sync.

    Resolution order (fast → authoritative):
      1. AUTHORITATIVE BATCH RESULT — if the symbol is in the last pipeline's
         Recovery_Screener_Results.csv, return that row. It was computed with
         FULL RFF (live fundamentals), so a genuine recovery signal shows on
         Golden Matcher even when the name's fundamentals aren't in the local
         cache — keeping GM consistent with the file (fixes "file shows 16,
         GM shows 3"). Instant (CSV read, no network).
      2. LIVE RECOMPUTE — for a symbol NOT in that scan (e.g. an ad-hoc name
         you typed/scrolled that was never a recovery candidate). ``deep=False``
         = cache-only (no blocking fetch); ``deep=True`` (on-demand button) =
         full live Screener.in/yfinance RFF for this one symbol.
    """
    try:
        import recovery_screener as rs
        sym = str(symbol).strip().upper().replace("NSE:", "").replace("BSE:", "").replace(".NS", "").replace(".BO", "")
        # 1. Authoritative batch result (skip only when a deep re-fetch is forced).
        if not deep:
            try:
                _p = os.path.join(rs.DATA_DIR, rs.OUTPUT_FILE)  # Recovery_Screener_Results.csv
                if os.path.exists(_p):
                    _rdf = pd.read_csv(_p)
                    _hit = _rdf[_rdf["Symbol"].astype(str).str.upper() == sym]
                    if len(_hit):
                        d = _hit.iloc[0].to_dict()
                        d["_source"] = "batch scan"
                        # Freshness disclosure (G2, 9-Jul-2026): a batch row is
                        # only as current as the CSV — carry the file date so
                        # the card can show/flag it instead of serving a
                        # weeks-old Signal/Entry/SL as if it were live.
                        try:
                            d["_as_of"] = datetime.fromtimestamp(os.path.getmtime(_p)).strftime("%d-%b")
                            d["_age_days"] = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(_p))).days
                        except Exception:
                            pass
                        return d
            except Exception:
                pass
        # 2. Live recompute (symbol not scanned in the batch, or deep forced).
        r = rs.screen_one(symbol, allow_live_fundamentals=deep) or {}
        if isinstance(r, dict):
            r["_source"] = "live (deep)" if deep else "live (cache-only)"
        return r
    except Exception as e:
        return {"_error": str(e)}


@st.cache_data(ttl=180, show_spinner=False)
def gm_load_intraday(symbol: str, minutes: int) -> dict:
    """Intraday (75/125-min) trigger data for the Golden Matcher's Step-5 battery
    + momentum board. Fetches Dhan 25-min bars (90d), session-anchor resamples to
    `minutes`, then recomputes the PA batteries (intraday=True → weekly patterns
    suppressed) and the momentum metrics (RSI/ADX/RelVol/Vol-dry) on that TF.

    Cached (ttl 180s) so the 2s TV auto-sync never re-hits Dhan. Returns
    {ok, pa, rpa, rsi, adx, relvol, vol_dry, last_ts, bars} — ok=False + reason
    when intraday is unavailable (page then falls back to the daily read).
    """
    try:
        import dhan_ohlcv as _dh, pa_patterns as _pap, numpy as _np
        df25 = _dh.fetch_intraday(symbol,
                                  from_date=(datetime.now().date() - timedelta(days=90)).isoformat(),
                                  to_date=datetime.now().date().isoformat(), interval=25)
        if df25 is None or df25.empty:
            return {"ok": False, "reason": "no intraday data from Dhan"}
        df = _pap.resample_intraday(df25, minutes, base_minutes=25)
        if df is None or len(df) < 60:
            return {"ok": False, "reason": f"only {0 if df is None else len(df)} {minutes}m bars (<60)"}
        # DNA rule: EMA20 is a DAILY anchor — on an intraday TF the engulfing
        # trend-context must use the DAILY EMA20/EMA10 overlaid on the 75/125m
        # bars, not a fresh intraday EMA. Pull the (cached) daily close for them.
        _d_e10 = _d_e20 = None
        try:
            import data_provider as _dpi
            _dfd = _dpi.fetch_ohlcv(symbol, period="1y", interval="1d", use_cache=True, auto_adjust=True)
            if isinstance(_dfd.columns, pd.MultiIndex):
                _dfd.columns = _dfd.columns.get_level_values(0)
            if _dfd is not None and len(_dfd) >= 20:
                _dc = _dfd["Close"]
                _d_e10 = float(_dc.ewm(span=10, adjust=False).mean().iloc[-1])
                _d_e20 = float(_dc.ewm(span=20, adjust=False).mean().iloc[-1])
        except Exception:
            pass
        c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
        # RSI(14)
        _d = c.diff()
        _up = _d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        _dn = (-_d.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        _rsi = 100 - 100 / (1 + _up / _dn.replace(0, _np.nan))
        # ADX(14) (Wilder)
        _upm = h.diff(); _dnm = -l.diff()
        _pdm = _np.where((_upm > _dnm) & (_upm > 0), _upm, 0.0)
        _mdm = _np.where((_dnm > _upm) & (_dnm > 0), _dnm, 0.0)
        _tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        _atr = _tr.ewm(alpha=1/14, adjust=False).mean()
        _pdi = 100 * pd.Series(_pdm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / _atr
        _mdi = 100 * pd.Series(_mdm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / _atr
        _dx = (100 * (_pdi - _mdi).abs() / (_pdi + _mdi)).replace([_np.inf, -_np.inf], _np.nan)
        _adx = _dx.ewm(alpha=1/14, adjust=False).mean()
        _vol20 = float(v.rolling(20).mean().iloc[-1]); _vol5 = float(v.rolling(5).mean().iloc[-1])

        def _f(s):
            x = float(s.iloc[-1]); return None if math.isnan(x) else x
        return {
            "ok": True, "bars": len(df),
            "pa":  _pap.detect_bull_patterns(df, "", intraday=True, ema20_ref=_d_e20, ema10_ref=_d_e10),
            "rpa": _pap.detect_recovery_patterns(df, "", intraday=True, ema20_ref=_d_e20, ema10_ref=_d_e10),
            "rsi": _f(_rsi), "adx": _f(_adx),
            "relvol": (float(v.iloc[-1] / _vol20) if (_vol20 and not math.isnan(_vol20)) else None),
            "vol_dry": (_vol5 / _vol20) if _vol20 else None,
            "cmp": (float(df["Close"].iloc[-1]) if len(df) else None),   # live intraday last price
            "last_ts": df.index[-1].strftime("%d-%b %H:%M"),
        }
    except Exception as e:
        return {"ok": False, "reason": str(e)}


if page == 'DASHBOARD':
    st.markdown('<div class="page-title">📊 Mission Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Real-Time Market Intelligence // Sector Radar // Risk Audit</div>', unsafe_allow_html=True)

    df_active = df_active_global

    # BUG-12 FIX: batch yfinance fetch instead of per-symbol loop
    live_map = {}
    if not df_active.empty:
        syms = tuple(df_active['Symbol'].unique().tolist())
        live_map = get_batch_ltps(syms)

    # ── AI Quick Brief ────────────────────────────────────────────────────────
    _db_brief_text = None
    if _SCHED_OK:
        try:
            _db_cached = load_latest_report("premarket")
            _db_brief_text = _db_cached.get("text") if _db_cached else None
            _db_brief_age  = _db_cached.get("generated_at", "") if _db_cached else ""
        except Exception:
            _db_brief_text = None; _db_brief_age = ""

    # Dashboard's AI Brief is INTENTIONALLY a quick snippet (first ~300 words)
    # of the latest pre-market briefing. It exists so the trader gets context
    # the moment they land on the dashboard. The full briefing — with global
    # indices, FII/DII, calendar, options snapshot — lives on PRE-MARKET → Brief.
    # Per user feedback (B, 10 May 2026): the role distinction is now explicit
    # in the expander label and caption.
    with st.expander("📰 AI Brief — Quick Preview" + (f"  ·  {_db_brief_age}" if _db_brief_text and _db_brief_age else "  ·  click to generate") + "  ·  full briefing in PRE-MARKET → Brief", expanded=False):
        if _db_brief_text:
            st.caption(
                "Snippet from the latest pre-market briefing (~300 words). "
                "For the full report + global indices + FII/DII + calendar + options, "
                "open **🌅 PRE-MARKET → 📋 Brief**."
            )
            _db_words  = _db_brief_text.split()
            _db_snippet = " ".join(_db_words[:300]) + ("…" if len(_db_words) > 300 else "")
            st.markdown(f'<div style="font-size:0.85rem;line-height:1.65;color:#c9d1d9;">{_db_snippet}</div>',
                        unsafe_allow_html=True)
            if st.button("📖 Open Full Brief in PRE-MARKET", key="db_full_brief"):
                st.session_state.page = "PRE-MARKET"; st.rerun()
        else:
            st.caption(
                "No cached report yet. Generate one here for the snippet, OR open "
                "**🌅 PRE-MARKET → 📋 Brief** to generate the full briefing in its proper home."
            )
            if _GEMINI_OK and _HUB_OK:
                if st.button("⚡ Generate Quick Brief (~30s)", key="db_gen_brief", type="primary"):
                    with st.spinner("Building market snapshot and generating AI brief…"):
                        try:
                            _db_snap  = build_premarket_snapshot()
                            _db_brief = generate_premarket_brief(_db_snap)
                            st.session_state["db_quick_brief"] = _db_brief
                        except Exception as _dbe:
                            st.error(f"Generation failed: {_dbe}")
                if st.session_state.get("db_quick_brief"):
                    _render_ai_report(st.session_state["db_quick_brief"], header_color="#58a6ff")

    st.markdown("---")
    section("Quick Launch")
    # Dashboard reorg (10 May 2026 — user feedback A + F + later):
    #   • Sector Radar moved to MACRO → Sector RRG
    #   • Complete Workflow / Auto-Pilot lives in sidebar + WATCHLIST tab (one script)
    #   • Sector Momentum Heatmap removed (lives in MACRO and BREADTH)
    #   • Export PDF removed — Market Briefing already produces a PDF (no separate btn needed)
    # Dashboard now hosts only the daily portfolio-decision action: Market Briefing.
    if st.button("📝  Market Briefing\nDaily strategic analysis and sector rotation — produces PDF.\n→  Generate Report", key="db_brief", use_container_width=True, type="primary"):
        launch_script("workflow_strategic_briefing.py")

    st.markdown("---")

    # ── OPEN PORTFOLIO HEALTH VITALS ──
    if not df_live_holdings.empty:
        section("Open Portfolio Health Vitals")

        pos_pnls, pos_pnl_pcts, pos_names = [], [], []
        total_unrealized = 0.0
        deployed_cost    = 0.0   # BUG-06: renamed from total_deployed to avoid shadowing

        for _, row in df_live_holdings.iterrows():
            sym = row.get('CleanSymbol', clean_symbol(row.get('Symbol', '')))
            bp  = float(row.get('BuyPrice', 0) or 0)
            qty = float(row.get('Quantity', 0) or 0)
            # Priority: broker LTP (most reliable for Indian stocks) → yfinance batch → BuyPrice
            broker_ltp = float(row.get('LTP', 0) or 0)
            ltp = broker_ltp if broker_ltp > 0 else (live_map.get(sym) or bp)
            if bp > 0 and qty > 0:
                pnl_rs  = (ltp - bp) * qty
                pnl_pct = ((ltp - bp) / bp) * 100
                pos_pnls.append(pnl_rs); pos_pnl_pcts.append(pnl_pct); pos_names.append(sym)
                total_unrealized += pnl_rs
                deployed_cost    += bp * qty

        n_eval    = len(pos_pnl_pcts)
        win_pcts  = [p for p in pos_pnl_pcts if p > 0]
        loss_pcts = [p for p in pos_pnl_pcts if p <= 0]
        winning, losing = len(win_pcts), len(loss_pcts)
        win_rate    = (winning / n_eval * 100) if n_eval > 0 else 0
        avg_gain_pct = sum(win_pcts)  / winning if winning > 0 else 0
        avg_loss_pct = sum(loss_pcts) / losing  if losing  > 0 else 0

        # BUG-03 FIX: show ∞ when no losing positions
        if avg_loss_pct != 0:
            risk_reward_str = f"{abs(avg_gain_pct / avg_loss_pct):.2f}"
        else:
            risk_reward_str = "∞" if winning > 0 else "N/A"

        # BUG-05 FIX: Open Return uses deployed capital, not total capital
        open_return_pct     = (total_unrealized / deployed_cost * 100) if deployed_cost > 0 else 0
        portfolio_return_pct = (total_unrealized / total_cap * 100)    if total_cap > 0 else 0

        v1, v2, v3, v4 = st.columns(4, gap="small")
        v1.metric("Unrealized P&L",    f"₹{format_inr_int(total_unrealized)}", help="Total unrealized P&L across all open positions.")
        v2.metric("Return on Deployed", f"{open_return_pct:.1f}%",             help="Unrealized P&L / Total deployed cost.")
        v3.metric("Portfolio Return",  f"{portfolio_return_pct:.1f}%",          help="Unrealized P&L / Total portfolio capital.")
        v4.metric("Current Value",     f"₹{format_inr_int(deployed_cost + total_unrealized)}", help="Current market value of all open positions.")

        ev1, ev2, ev3, ev4 = st.columns(4, gap="small")
        ev1.metric("Win Rate",    f"{win_rate:.1f}%  ({winning}W / {losing}L)")
        ev2.metric("Avg Gain %",  f"{avg_gain_pct:.1f}%")
        ev3.metric("Avg Loss %",  f"{avg_loss_pct:.1f}%")
        ev4.metric("Risk/Reward", risk_reward_str, help="Avg Gain% / |Avg Loss%|. ∞ = all positions in profit.")

        # ── E-6 (v2.3): Exit Signal Engine — Auto-Scan ───────────────────
        # Pipe exit_signal_engine alerts directly into the dashboard so the
        # trader sees which open positions need attention *alongside* the
        # portfolio vitals — no separate CLI run required.
        with st.expander("🔴 Exit Signal Scan — Check Positions for Exit Alerts", expanded=False):
            st.caption(
                "Runs the Exit Signal Engine on all open positions: checks stop-loss proximity, "
                "R-multiple targets, Weinstein stage decay, and RS fading. Regime-aware (v2.3)."
            )
            if st.button("⚡ Run Exit Scan", key="e6_exit_scan", type="primary"):
                with st.spinner("Scanning open positions for exit signals..."):
                    try:
                        from exit_signal_engine import run_exit_scan
                        _exit_df = run_exit_scan(silent=True)
                        st.session_state["e6_exit_results"] = _exit_df
                    except Exception as _e6e:
                        st.error(f"Exit scan failed: {_e6e}")
                        st.session_state["e6_exit_results"] = None

            _exit_cached = st.session_state.get("e6_exit_results")
            if _exit_cached is not None and not _exit_cached.empty:
                _action_df = _exit_cached[_exit_cached["Exit_Flag"] == "ACTION"]
                _hold_df   = _exit_cached[_exit_cached["Exit_Flag"] != "ACTION"]

                if not _action_df.empty:
                    st.markdown(
                        f'<div style="background:rgba(255,75,75,0.1);border-left:3px solid #ff4b4b;'
                        f'padding:8px 12px;border-radius:4px;margin-bottom:8px;">'
                        f'<strong style="color:#ff4b4b;">⚠ {len(_action_df)} position(s) need attention</strong>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    # Display the ACTION rows in a clean table
                    _display_cols = ["Symbol", "LTP", "R_Multiple", "Weinstein_Stage",
                                     "Mansfield_RS", "Exit_Reasons"]
                    _show_cols = [c for c in _display_cols if c in _action_df.columns]
                    _show_df = _action_df[_show_cols].copy()
                    if "R_Multiple" in _show_df.columns:
                        _show_df["R_Multiple"] = _show_df["R_Multiple"].apply(
                            lambda x: f"{x:+.1f}R" if pd.notna(x) else "—"
                        )
                    if "Mansfield_RS" in _show_df.columns:
                        _show_df["Mansfield_RS"] = _show_df["Mansfield_RS"].apply(
                            lambda x: f"{x:.2f}" if pd.notna(x) else "—"
                        )
                    if "LTP" in _show_df.columns:
                        _show_df["LTP"] = _show_df["LTP"].apply(
                            lambda x: f"{x:.2f}" if pd.notna(x) else "—"
                        )
                    st.dataframe(_show_df, use_container_width=True, hide_index=True)

                    # Show recommendations if available
                    if "Recommendations_Str" in _action_df.columns:
                        for _, _ar in _action_df.iterrows():
                            _rec_str = _ar.get("Recommendations_Str", "")
                            if _rec_str:
                                st.markdown(
                                    f'<div style="font-size:0.8rem;color:#c9d1d9;padding:2px 0;">'
                                    f'<strong>{_ar["Symbol"]}</strong>: {_rec_str}</div>',
                                    unsafe_allow_html=True,
                                )
                else:
                    st.success(f"✅ All {len(_hold_df)} positions healthy — no exit signals triggered.")
            elif _exit_cached is not None:
                st.info("No open positions to scan.")

        st.markdown("---")

    # ── E-01: CLOSED TRADE ANALYTICS ──
    df_closed = load_closed_trades_db()
    if df_closed is not None and not df_closed.empty:
        section("Portfolio Analytics — Closed Trade Performance")
        analytics = compute_portfolio_analytics(df_closed, total_cap)
        if analytics:
            a1,a2,a3,a4,a5,a6 = st.columns(6, gap="small")
            a1.metric("Sharpe Ratio",    str(analytics.get('sharpe','—')),   help="Annualised Sharpe. >1.0 = good, >2.0 = excellent.")
            a2.metric("Sortino Ratio",   str(analytics.get('sortino','—')),  help="Downside-adjusted Sharpe. Penalises losing days only.")
            a3.metric("Max Drawdown",   f"₹{format_inr_int(abs(analytics.get('max_dd',0)))} ({analytics.get('max_dd_pct',0):.1f}%)", help="Largest peak-to-trough equity drop.")
            a4.metric("Profit Factor",  str(analytics.get('profit_factor','—')), help="Gross Profit / Gross Loss. >1.5 = solid, >2.0 = excellent.")
            a5.metric("Expectancy",     f"₹{format_inr_int(analytics.get('expectancy',0))}", help="Average ₹ expected per trade.")
            a6.metric("Total Realized", f"₹{format_inr_int(analytics.get('total_realized',0))}", help="Cumulative realized P&L from all closed trades.")
        st.markdown("---")

    if not df_active.empty:
        left_col, right_col = st.columns([3, 2], gap="medium")
        with left_col:
            section("Portfolio Heatmap — Capital Allocation")
            hmap = df_active.copy()
            # Phase-2A: enrich blank Sector cells from sectors.db before falling
            # back to "Unassigned". The treemap groups by Sector — accurate cells
            # mean meaningful clusters instead of one giant grey "Unassigned" tile.
            try:
                import sector_lookup as _hm_sl
                def _hm_sec(row):
                    cur = str(row.get('Sector', '') or '').strip()
                    if cur and cur.lower() not in ('', 'nan', 'unassigned', 'other', 'unknown'):
                        return cur
                    rec = _hm_sl.get_sector(row.get('Symbol', ''))
                    return (rec.get('display_name') or rec.get('sector_name')) if rec else 'Unassigned'
                hmap['Sector'] = hmap.apply(_hm_sec, axis=1)
            except Exception:
                hmap['Sector'] = hmap['Sector'].fillna("Unassigned").replace("", "Unassigned")
            hmap['Deployment'] = hmap['Quantity'] * hmap['BuyPrice']
            # Use clean_symbol so "NSE:RELIANCE" etc. resolve against live_map keys.
            # Fallback via `or p` ensures a 0-LTP key in the dict never corrupts the calc.
            hmap['PnLPct']     = [((live_map.get(clean_symbol(s)) or p) - p) / p * 100 if p > 0 else 0
                                   for s, p in zip(hmap['Symbol'], hmap['BuyPrice'])]
            # Format PnLPct for display
            hmap['PnL_Str'] = hmap['PnLPct'].apply(lambda x: f"{x:+.2f}%")
            fig = px.treemap(hmap, path=[px.Constant("Portfolio"), "Sector", "Symbol"],
                             values="Deployment", color="PnLPct",
                             color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
                             custom_data=["PnL_Str", "Quantity", "BuyPrice"])
            fig.update_traces(
                hovertemplate="<b>%{label}</b><br>Capital Deployed: ₹%{value:,.0f}<br>Unrealized PnL: %{customdata[0]}<br>Qty: %{customdata[1]} | Buy Price: ₹%{customdata[2]:,.2f}"
            )
            fig.update_layout(margin=dict(t=10,l=0,r=0,b=0), height=320,
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        with right_col:
            section("Alpha Benchmarking vs Nifty 500")
            if df_closed is not None and not df_closed.empty:
                try:
                    # BUG-02 FIX: load_closed_trades_db() already renames — no second rename
                    dfc = df_closed.copy()
                    for col in ['ExitPrice','BuyPrice','Quantity']:
                        dfc[col] = pd.to_numeric(dfc.get(col, 0), errors='coerce').fillna(0)
                    dfc['ExitDate'] = pd.to_datetime(dfc['ExitDate'], errors='coerce')
                    dfc = dfc.dropna(subset=['ExitDate']).sort_values('ExitDate')
                    dfc['PnL'] = (dfc['ExitPrice'] - dfc['BuyPrice']) * dfc['Quantity']
                    pc = dfc.groupby('ExitDate').agg({'PnL': 'sum'}).reset_index()
                    pc['CumulativePnL'] = pc['PnL'].cumsum()

                    # FORM-02 FIX: normalise to starting equity, not current capital
                    starting_equity = total_cap - pc['CumulativePnL'].iloc[-1]
                    if starting_equity <= 0: starting_equity = total_cap
                    pc['Portfolio_%'] = (pc['CumulativePnL'] / starting_equity) * 100
                    pc = pc.rename(columns={'ExitDate': 'Date'})

                    import data_provider as _dp_bench
                    nifty_raw = _dp_bench.fetch_ohlcv("^NSEI", period="max", interval="1d")
                    nifty = nifty_raw.loc[pc['Date'].min() - pd.Timedelta(days=7) : pc['Date'].max() + pd.Timedelta(days=1)]
                    if not nifty.empty:
                        nifty = nifty['Close'].reset_index()
                        nifty.columns = ['Date', 'NiftyClose']
                        nifty['Date'] = pd.to_datetime(nifty['Date']).dt.tz_localize(None)
                        if isinstance(nifty['NiftyClose'], pd.DataFrame):
                            nifty['NiftyClose'] = nifty['NiftyClose'].iloc[:, 0]
                        nifty['Benchmark_%'] = ((nifty['NiftyClose'] - nifty['NiftyClose'].iloc[0]) / nifty['NiftyClose'].iloc[0]) * 100
                        merged = pd.merge_asof(pc, nifty[['Date', 'Benchmark_%']], on='Date')
                        fig2 = px.line(merged, x='Date', y=['Portfolio_%', 'Benchmark_%'],
                                       labels={'value': 'Return (%)', 'variable': 'Metric'})
                        fig2.update_layout(height=300, margin=dict(t=10,l=0,r=0,b=0),
                                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                           legend=dict(font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
                                           yaxis_title="% Return (from starting equity)")
                        st.plotly_chart(fig2, use_container_width=True)
                except Exception as e:
                    st.error(f"Chart error: {e}")
            else:
                st.info("No closed trades to benchmark yet.")

        # ── ACTIVE POSITIONS P&L TABLE ──
        section("Active Positions — Live P&L")
        pnl_rows = []
        for _, row in df_active.iterrows():
            sym  = row['Symbol']
            bp   = float(row.get('BuyPrice', 0) or 0)
            qty  = float(row.get('Quantity', 0) or 0)
            # `or bp` guards against 0-valued keys that bypass the dict default
            ltp  = live_map.get(sym) or live_map.get(clean_symbol(sym)) or bp
            sl   = float(row.get('StopLoss', 0) or 0)
            tgt  = float(row.get('Target', 0) or 0)
            pnl_rs  = (ltp - bp) * qty
            pnl_pct = ((ltp - bp) / bp * 100) if bp > 0 else 0
            dist_sl  = ((ltp - sl) / ltp * 100) if sl > 0 and ltp > 0 else None
            dist_tgt = ((tgt - ltp) / ltp * 100) if tgt > 0 and ltp > 0 else 0

            atr_val = get_atr(sym)
            sl_atr  = round((ltp - sl) / atr_val, 1) if atr_val > 0 and sl > 0 else None

            entry_dt  = row.get('EntryDate', '')
            try: days_held = (pd.Timestamp.now() - pd.to_datetime(entry_dt)).days if entry_dt else 0
            except (ValueError, TypeError): days_held = 0

            # BUG-10 FIX: Trailing SL awareness (SL > entry is valid for locked-profit trailing)
            if sl > 0 and ltp > 0:
                if sl > bp:
                    sl_status = f"🔒 LOCKED +₹{format_inr_int((sl-bp)*qty)}"
                elif dist_sl is not None and dist_sl < 0:
                    sl_status = f"⚠️ BREACHED {dist_sl:.1f}%"
                else:
                    sl_status = f"{dist_sl:.1f}%" if dist_sl is not None else "—"
            else:
                sl_status = "—"

            pnl_rows.append({
                'Symbol': sym, 'Entry': round(bp,2), 'LTP': round(ltp,2),
                'P&L ₹': round(pnl_rs, 0), 'P&L %': round(pnl_pct,1),
                'SL Status': sl_status, 'Dist Tgt %': round(dist_tgt,1),
                'SL (ATR×)': sl_atr, 'Days': days_held
            })

        if pnl_rows:
            df_pnl = pd.DataFrame(pnl_rows)
            st.dataframe(df_pnl, use_container_width=True, hide_index=True, height=300)

        # ── CORRELATION RISK MATRIX ──
        section("Portfolio Correlation Risk")
        with st.expander("🔍 View Correlation Matrix & Shadow Concentration", expanded=False):
            syms_for_corr = df_active['Symbol'].unique().tolist()
            if len(syms_for_corr) >= 2:
                try:
                    with st.spinner("Computing correlation matrix..."):
                        corr_df, shadows, div_score = get_portfolio_correlation_matrix(syms_for_corr)
                    dc1, dc2 = st.columns([1, 1])
                    with dc1: st.metric("Diversification Score", f"{div_score}/10")
                    with dc2:
                        if shadows:
                            st.warning(f"⚠️ {len(shadows)} Shadow Concentration pair(s) detected!")
                            for sp in shadows:
                                st.caption(f"  {sp['Pair']} → r={sp['Correlation']} ({sp['Risk']})")
                        else:
                            st.success("✅ No shadow concentration detected.")
                    if not corr_df.empty:
                        fig_corr = ff.create_annotated_heatmap(
                            z=corr_df.values.round(2).tolist(),
                            x=corr_df.columns.tolist(), y=corr_df.index.tolist(),
                            colorscale='RdYlGn', showscale=True
                        )
                        fig_corr.update_layout(height=350, margin=dict(t=30,l=0,r=0,b=0),
                                               paper_bgcolor="rgba(0,0,0,0)")
                        st.plotly_chart(fig_corr, use_container_width=True)
                except Exception as e:
                    st.error(f"Correlation Error: {e}")
            else:
                st.info("Need at least 2 open positions for correlation analysis.")
    else:
        st.info("No open positions found. Launch a scanner to populate your portfolio.")

    # NOTE (10 May 2026): Recovery Alerts widget removed from Dashboard per user
    # feedback. Recovery signals are stock-level discovery signals; they belong in
    # HUNTER → Recovery Screener tab where you actually act on them. Dashboard is
    # for OPEN portfolio state, not for discovery-output overlay.

# ════════════════════════════════════════════════════════════════════════════
#  HUNTER
# ════════════════════════════════════════════════════════════════════════════
elif page == 'HUNTER':
    st.markdown('<div class="page-title">🎯 Hunter</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Stock Discovery Engine — unified Bull · Recovery · Chartink scanners + Fundamentals enrichment + Matcher selection</div>', unsafe_allow_html=True)
    # P1.6 + P2 follow-up (10 May 2026 — user feedback #13): split the former
    # "Matcher + Recovery" mega-tab into discrete tabs so each discovery tool
    # has its own real estate. Tab order reflects the workflow:
    #   Chartink Scans (Layer 1) → Fundamentals (Layer 2) → Golden Matcher
    #   (Layer 3 conviction-filter combine) → Bull Screener (Pine-aligned live)
    #   → Recovery Screener (REV signals) → X-Ray Screener (deep fundamentals).
    # Note: X-Ray here is the BATCH screener; the single-ticker X-Ray deep-dive
    # remains its own top-level page in DISCOVERY.
    _ht1, _ht2, _ht3, _ht4, _ht5, _ht6 = st.tabs([
        "🔍 Chartink Scans",
        "🧬 Fundamentals",
        "🥇 Golden Matcher",
        "🐂 Bull Screener",
        "🔄 Recovery Screener",
        "🧬 X-Ray Screener",
    ])

    with _ht1:
        section("Chartink Scanners")
        left, right = st.columns(2, gap="medium")
        with left:
            sub_label("📌  Positional Strategies")
            if st.button("Stage 2 Hunter\nLong-horizon stage-based breakout entries.\n→  Run Scanner", use_container_width=True, key="h_s2"):
                launch_script("chartink_scanner_pro.py", "1")
            if st.button("Early Birds Accumulation\nEarly-stage accumulation zone detection.\n→  Run Scanner", use_container_width=True, key="h_eb"):
                launch_script("chartink_scanner_pro.py", "3")
        with right:
            sub_label("📈  Swing Strategies")
            if st.button("Stage 2 Pullback\nShort-term pullback within an uptrend.\n→  Run Scanner", use_container_width=True, key="h_pb"):
                launch_script("chartink_scanner_pro.py", "2")
            if st.button("Strong Leaders\nMomentum leaders with relative strength.\n→  Run Scanner", use_container_width=True, key="h_sl"):
                launch_script("chartink_scanner_pro.py", "4")

        st.markdown("---")
        section("Recovery Phase Scanners  (Post-Shock Mode)")
        st.caption("Use when market has corrected ≥7% from 52W high or is in recovery. Complements Stage 2 scanners.")
        rc1, rc2, rc3 = st.columns(3, gap="medium")
        with rc1:
            if st.button("REV-RS: RS Survivor Breakout\nStocks beating CNX500 now breaking 20D high.\n→  Run Scanner", use_container_width=True, key="h_rev_rs"):
                launch_script("chartink_scanner_pro.py", "5")
        with rc2:
            if st.button("REV-CB: Climax Bottom Bounce\nDeeply stretched stocks with panic-volume signature.\n→  Run Scanner", use_container_width=True, key="h_rev_cb"):
                launch_script("chartink_scanner_pro.py", "6")
        with rc3:
            if st.button("REV-EARLY: Early Bird VCP\nNear golden cross — VCP base compressing.\n→  Run Scanner", use_container_width=True, key="h_rev_early"):
                launch_script("chartink_scanner_pro.py", "7")

    with _ht2:
        section("Fundamental Data")
        left, right = st.columns(2, gap="medium")
        with left:
            if st.button("🌐  Fetch Screener.in Data\nPull raw fundamental HTML from Screener.in.\n→  Fetch Now", use_container_width=True, key="e_fetch"):
                launch_script("screener_fetcher.py")
        with right:
            if st.button("⚙️  Process HTML to CSV\nConvert raw HTML into structured CSV for analysis.\n→  Process Now", use_container_width=True, key="e_proc"):
                launch_script("screener_processor.py")

    with _ht3:
        section("Golden Matcher Engine")
        st.caption("Combines technical scans (Chartink Layer 1) with fundamental filters "
                   "(Screener.in conviction) to find 5-Star setups. Output: FINAL_*.csv files "
                   "+ Ultimate Golden Meta-Ranking (below).")

        # Show last-generated timestamp across all 4 FINAL_*_Picks.csv files
        # so the user knows whether their watchlist is fresh.
        _gm_files = ["FINAL_Hunter_Picks.csv", "FINAL_Pullback_Picks.csv",
                      "FINAL_EarlyBird_Picks.csv", "FINAL_Leader_Picks.csv"]
        _gm_root = os.path.dirname(os.path.abspath(__file__))
        import datetime as _dt_gm
        _gm_mtimes = []
        for _f in _gm_files:
            _p = os.path.join(_gm_root, _f)
            if os.path.exists(_p):
                _gm_mtimes.append((os.path.getmtime(_p), _f))
        if _gm_mtimes:
            _newest_t, _newest_f = max(_gm_mtimes)
            _newest_str = _dt_gm.datetime.fromtimestamp(_newest_t).strftime("%d %b %Y  %H:%M")
            _age_h = (_dt_gm.datetime.now().timestamp() - _newest_t) / 3600
            if _age_h > 28:
                st.warning(f"⚠ Latest FINAL_*.csv from **{_newest_str}** "
                           f"({_age_h:.0f}h old) — re-run **🤖 Run Auto-Pilot** "
                           f"or click below to refresh.")
            else:
                st.caption(f"✓ Last generated: **{_newest_str}** "
                           f"({_age_h:.1f}h ago, freshest: `{_newest_f}`)")
        else:
            st.info("No FINAL_*.csv files found yet. Click **🤖 Run Auto-Pilot** "
                    "in the sidebar OR run the Golden Matcher button below.")

        if st.button("🏆  Run Golden Matcher\nCombines Technical Scans with Fundamental Filters to find 5-Star setups.\n→  Initiate Matching", type="primary", use_container_width=True, key="sel_run"):
            launch_script("brute_force_match_pro.py")

        st.markdown("---")
        section("Ultimate Golden Meta-Ranking")
        _gm_pmap = {"Stage 2 Hunter":"FINAL_Hunter_Picks.csv",
                    "Stage 2 Pullback":"FINAL_Pullback_Picks.csv",
                    "Early Birds":"FINAL_EarlyBird_Picks.csv",
                    "Strong Leaders":"FINAL_Leader_Picks.csv"}
        _gm_master_dfs = []
        for _gm_strat_name, _gm_fname in _gm_pmap.items():
            if os.path.exists(_gm_fname):
                try:
                    _gm_df_t = pd.read_csv(_gm_fname); _gm_df_t.insert(0, 'Strategy', _gm_strat_name)
                    _gm_master_dfs.append(_gm_df_t)
                except Exception as _gm_e:
                    logger.warning(f"Loading {_gm_fname}: {_gm_e}")

        if _gm_master_dfs:
            _gm_master_df = pd.concat(_gm_master_dfs, ignore_index=True)
            _gm_conv_map  = {'High': 3, 'Medium': 2, 'Low': 1, 'N/A': 0}
            if 'Conviction' in _gm_master_df.columns:
                _gm_master_df['Conv_Score'] = _gm_master_df['Conviction'].map(_gm_conv_map).fillna(0)
            else:
                _gm_master_df['Conv_Score'] = 0
            _gm_sort_cols, _gm_asc_opts = ['Conv_Score'], [False]
            if '%Chg' in _gm_master_df.columns:
                _gm_sort_cols.append('%Chg'); _gm_asc_opts.append(False)
            _gm_master_df = _gm_master_df.sort_values(by=_gm_sort_cols, ascending=_gm_asc_opts)
            _gm_show_cols = ['Strategy','Symbol']
            for _c in ['Conviction','AI Catalyst','AI_Catalyst','%Chg','Volume']:
                if _c in _gm_master_df.columns: _gm_show_cols.append(_c)

            # Strategy filter — "All" shows the full combined ranking; specific
            # strategy narrows the table to that bucket. Per user feedback
            # (10 May 2026), the drill-down dropdown belongs HERE next to the
            # Meta-Ranking, not on the Bull Screener tab.
            _gm_strategies_avail = ["All"] + sorted(_gm_master_df["Strategy"].unique().tolist())
            _gm_pick_strat = st.selectbox(
                "Filter by Strategy",
                _gm_strategies_avail,
                key="gm_strat_filter",
                help="Narrows the Meta-Ranking to a single strategy bucket.",
            )
            if _gm_pick_strat != "All":
                _gm_view = _gm_master_df[_gm_master_df["Strategy"] == _gm_pick_strat]
                st.caption(f"Showing top picks for **{_gm_pick_strat}** ({len(_gm_view)} candidates).")
            else:
                _gm_view = _gm_master_df
                st.caption(f"Showing top 25 across all strategies ({len(_gm_view)} total candidates).")

            st.dataframe(
                _gm_view[_gm_show_cols].head(25 if _gm_pick_strat == "All" else len(_gm_view)),
                use_container_width=True, hide_index=True,
            )

            # ── Analyst Sentiment for Golden Matcher picks ────────────────────
            # Pulls sentiment for the top-N picks of the currently-filtered
            # strategy. Uses FINAL_Hunter_Picks.csv if "Stage 2 Hunter" filter
            # is active, etc. — single source per click.
            st.markdown("---")
            _gm_sentiment_csv = (_gm_pmap.get(_gm_pick_strat)
                                  if _gm_pick_strat != "All"
                                  else "FINAL_Hunter_Picks.csv")  # default to Hunter
            _gm_sentiment_path = os.path.join(_gm_root, _gm_sentiment_csv) \
                                  if _gm_sentiment_csv else ""
            _render_analyst_sentiment_panel(
                csv_path=_gm_sentiment_path,
                symbol_col="Symbol",
                key_prefix="gm",
                label=f"Golden Matcher — {_gm_pick_strat}",
                extra_caption=(f"Source: `{_gm_sentiment_csv}` "
                               f"(filter currently set to **{_gm_pick_strat}**)"),
            )
        else:
            st.info("No Final Golden Pick CSVs found. Run the Golden Matcher first.")

    with _ht5:
        section("Recovery Screener  (Python Edition)")
        st.caption("Signal hold-window aware — safe to run post-market or over the weekend. Uses Chartink CSVs 5-7 + yfinance data.")

        # ── Input source selector ──────────────────────────────────────────────
        # P1.6 + #14 (10 May 2026): added Nifty 500 source for backtest-aligned runs.
        _rec_src = st.radio(
            "Symbol Source",
            [
                "📂 Default  (Chartink Recovery CSVs 5-7)",
                "🌐 Nifty 500  (full universe — backtest-aligned)",
                "⚡ F&O Basket  (NSE derivatives universe ~210 stocks)",
                "⬆️ Upload CSV Watchlist",
            ],
            horizontal=True, key="rec_src_radio",
        )

        _rec_custom_syms = None
        _rec_out_file    = "Recovery_Screener_Results.csv"

        if _rec_src.startswith("🌐"):
            try:
                import validation as _val
                _rec_custom_syms = list(_val.default_universe("nifty500"))
                _rec_out_file = "Recovery_Screener_N500_Results.csv"
                st.success(f"✅ {len(_rec_custom_syms)} Nifty 500 symbols loaded.")
                st.caption("Results → **Recovery_Screener_N500_Results.csv**")
            except Exception as _n500re:
                st.error(f"Could not load Nifty 500: {_n500re}")
                _rec_custom_syms = None

        if _rec_src.startswith("⚡"):
            try:
                import validation as _val
                _rec_custom_syms = list(_val.default_universe("fno"))
                _rec_out_file = "Recovery_Screener_FNO_Results.csv"
                st.success(f"✅ {len(_rec_custom_syms)} F&O symbols loaded.")
                st.caption(
                    "Results → **Recovery_Screener_FNO_Results.csv**. "
                    "Refresh `fno_symbols.json` periodically per NSE F&O circulars."
                )
            except Exception as _fnore:
                st.error(f"Could not load F&O basket: {_fnore}")
                _rec_custom_syms = None

        if _rec_src.startswith("⬆️"):
            _rec_upload = st.file_uploader(
                "Upload a CSV/TXT with Symbols (NSE codes, TradingView exports)",
                type=["csv", "txt"],
                key="rec_upload_csv",
                help="CSV: Symbol, NSECode, Ticker, Scrip. TXT: Comma-separated (NSE:VBL,NSE:NAM_INDIA)",
            )
            if _rec_upload is not None:
                try:
                    if _rec_upload.name.lower().endswith(".txt"):
                        import re
                        text_content = _rec_upload.getvalue().decode("utf-8")
                        raw_syms = re.split(r'[,;\n\s]+', text_content)
                        _rec_custom_syms = []
                        for s in raw_syms:
                            s = s.strip().strip("'").strip('"').upper()
                            s = re.sub(r"^(NSE:|BSE:)", "", s)
                            s = re.sub(r"\.NS$", "", s)
                            if s and not s.isdigit():
                                _rec_custom_syms.append(s)
                        _rec_custom_syms = list(dict.fromkeys(_rec_custom_syms))
                        _rec_out_file = "Recovery_Screener_Custom_Results.csv"
                        st.success(f"✅ {len(_rec_custom_syms)} symbols loaded from **{_rec_upload.name}**")
                        st.caption("Results → **Recovery_Screener_Custom_Results.csv** (default run not overwritten)")
                    else:
                        _df_rec_up = pd.read_csv(_rec_upload)
                        _rec_col   = next(
                            (c for c in _df_rec_up.columns
                             if c.strip().lower() in ("symbol", "nsecode", "ticker", "scrip")),
                            None,
                        )
                        if _rec_col is None:
                            st.warning(f"No Symbol column found. Columns: {list(_df_rec_up.columns)}")
                        else:
                            _rec_custom_syms = (
                                _df_rec_up[_rec_col].dropna().astype(str)
                                .str.strip().str.upper()
                                .str.replace(r"^(NSE:|BSE:)", "", regex=True)
                                .str.replace(r"\.NS$", "", regex=True)
                                .unique().tolist()
                            )
                            _rec_custom_syms = [s for s in _rec_custom_syms if s and not s.isdigit()]
                            _rec_out_file    = "Recovery_Screener_Custom_Results.csv"
                            st.success(f"✅ {len(_rec_custom_syms)} symbols loaded from **{_rec_upload.name}**")
                            st.caption("Results → **Recovery_Screener_Custom_Results.csv** (default run not overwritten)")
                except Exception as _rue:
                    st.error(f"Could not parse upload: {_rue}")

        _rec_run_label = (
            f"Run Recovery Screener — Custom Watchlist\n{len(_rec_custom_syms)} symbols\n→  Screen Now"
            if _rec_custom_syms is not None
            else "Run Recovery Screener\nScores REV-CB / REV-RS / REV-EARLY across all watchlist symbols.\n→  Run Now"
        )
        if st.button(_rec_run_label, type="primary", use_container_width=True, key="sel_rec"):
            try:
                import recovery_screener as _rs
                _rec_prog  = st.progress(0)
                _rec_stat  = st.empty()

                def _on_rec_progress(idx, total, sym):
                    _rec_prog.progress(int(idx / total * 100))
                    _rec_stat.text(f"Scanning [{idx}/{total}]: {sym}")

                # strict=True for Nifty 500 / F&O — drop Signal=0 rows so the CSV
                # only contains actionable candidates. Upload-CSV keeps all rows.
                _rec_strict = _rec_src.startswith("🌐") or _rec_src.startswith("⚡")
                _df_rec_res = _rs.run_recovery_screener(
                    progress_callback=_on_rec_progress,
                    symbols=_rec_custom_syms,
                    out_file=_rec_out_file,
                    strict=_rec_strict,
                )
                _rec_prog.empty(); _rec_stat.empty()
                if not _df_rec_res.empty:
                    st.success(f"✅ Done — {len(_df_rec_res)} stocks screened, {(_df_rec_res['Signal'] >= 2).sum()} actionable.")
                else:
                    st.info("No candidates found. Check Chartink CSVs or uploaded symbols.")
            except Exception as _re:
                st.error(f"Recovery Screener error: {_re}")

        import datetime as _dt
        _script_dir = os.path.dirname(os.path.abspath(__file__))
        rec_csv = os.path.join(_script_dir, _rec_out_file)
        if not os.path.exists(rec_csv):
            rec_csv = _rec_out_file   # fallback: CWD
        if os.path.exists(rec_csv):
            try:
                df_rec = pd.read_csv(rec_csv)

                # ── Last-run timestamp & staleness warning ────────────────────
                _mtime = _dt.datetime.fromtimestamp(os.path.getmtime(rec_csv))
                _age_h = (_dt.datetime.now() - _mtime).total_seconds() / 3600
                _ts_str = _mtime.strftime("%d %b %Y  %H:%M")
                if _age_h > 28:
                    st.warning(f"Results last updated {_ts_str} — more than 1 trading day old. Re-run for fresh signals.")
                else:
                    st.caption(f"Results from {_ts_str}")

                # ── Signal age column (trading days since signal fired) ───────
                if "Signal_Date" in df_rec.columns:
                    _today = _dt.date.today()
                    def _td_age(d):
                        try:
                            sd = _dt.datetime.strptime(str(d).strip(), "%d %m %y").date() if len(str(d)) == 8 else _dt.datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
                            delta = (_today - sd).days
                            weeks, rem = divmod(delta, 7)
                            return weeks * 5 + min(rem, 5)
                        except Exception:
                            return None
                    df_rec.insert(df_rec.columns.get_loc("Signal_Date") + 1,
                                  "Age_Days", df_rec["Signal_Date"].apply(_td_age))

                st.markdown("**Latest Recovery Screener Results**")

                # ── Filters ──────────────────────────────────────────────────
                fc1, fc2, fc3 = st.columns([2, 2, 2], gap="small")
                with fc1:
                    sig_filter = st.selectbox("Signal", ["All (Actionable)", "Signal=4 (REV-EARLY)", "Signal=3 (REV-RS)", "Signal=2 (REV-CB)", "Signal=1 (CB-Watch)", "Show All"], key="rec_sig_filter")
                with fc2:
                    rs_min = st.number_input("Min Mansfield RS", min_value=0.0, max_value=10.0, value=0.0, step=0.5, key="rec_rs_min")
                with fc3:
                    max_age = st.number_input("Max Signal Age (trading days)", min_value=1, max_value=20, value=5, key="rec_age_max")

                sig_map = {"Signal=4 (REV-EARLY)": 4, "Signal=3 (REV-RS)": 3, "Signal=2 (REV-CB)": 2, "Signal=1 (CB-Watch)": 1}
                if sig_filter == "All (Actionable)":
                    df_rec = df_rec[df_rec["Signal"] >= 2]
                elif sig_filter in sig_map and "Signal" in df_rec.columns:
                    df_rec = df_rec[df_rec["Signal"] == sig_map[sig_filter]]

                if rs_min > 0 and "Mansfield_RS" in df_rec.columns:
                    df_rec = df_rec[pd.to_numeric(df_rec["Mansfield_RS"], errors="coerce") >= rs_min]

                if "Age_Days" in df_rec.columns:
                    _age_num = pd.to_numeric(df_rec["Age_Days"], errors="coerce")
                    df_rec = df_rec[_age_num.isna() | (_age_num <= max_age)]

                show_rec_cols = [c for c in [
                    "Symbol", "Signal_Label", "Signal_Date", "Age_Days", "Score", "RFF_Score",
                    "Weinstein_Stage", "Mansfield_RS", "RSI14", "Rel_Vol",
                    "Entry", "SL", "T1", "RR_T1", "SL_pct", "T1_pct", "Details"
                ] if c in df_rec.columns]
                st.dataframe(df_rec[show_rec_cols].head(50), use_container_width=True, hide_index=True)
                st.caption(f"{len(df_rec)} stocks shown after filters.")

                # ── Export buttons ────────────────────────────────────────────
                if not df_rec.empty and "Symbol" in df_rec.columns:
                    _rec_syms = df_rec["Symbol"].dropna().astype(str).str.strip().tolist()
                    _pine_export = (
                        f'// Commander Recovery Screener — Pine Symbol Array\n'
                        f'// Generated {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}\n\n'
                        f'recovery_syms = array.from(\n    '
                        + ",\n    ".join(f'"NSE:{s}"' for s in _rec_syms)
                        + '\n)'
                    )
                    _rec_col1, _rec_col2, _rec_col3 = st.columns([2, 1, 1])
                    with _rec_col1:
                        st.text_area(
                            "📋 Pine Symbol List",
                            value=", ".join(f'"NSE:{s}"' for s in _rec_syms),
                            height=80, key="rec_pine_syms"
                        )
                    with _rec_col2:
                        st.download_button(
                            label="⬇️ Export CSV",
                            data=df_rec[show_rec_cols].to_csv(index=False).encode("utf-8"),
                            file_name="Recovery_Screener_Export.csv",
                            mime="text/csv",
                            key="rec_csv_dl",
                        )
                    with _rec_col3:
                        st.download_button(
                            label="⬇️ Export Pine Array",
                            data=_pine_export,
                            file_name="Recovery_Pine_Symbols.pine",
                            mime="text/plain",
                            key="rec_pine_dl",
                            help="Download as a .pine snippet ready to paste into your indicator"
                        )
            except Exception as e:
                st.error(f"Error loading Recovery Screener results: {e}")
        else:
            st.info("No Recovery Screener results yet. Run the screener above (default or upload a custom watchlist).")

        # ── Analyst Sentiment for Recovery picks ─────────────────────────────
        st.markdown("---")
        _rec_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  _rec_out_file)
        _render_analyst_sentiment_panel(
            csv_path=_rec_path,
            symbol_col="Symbol",
            key_prefix="rec",
            label="Recovery Screener Picks",
            extra_caption=f"Reading from `{_rec_out_file}`",
        )

    with _ht6:
        # ── Quick Look — per-symbol analyst sentiment + paid news, inline ───
        # 10 May 2026: per user feedback, the bulk X-Ray Screener input was here
        # but the per-symbol News result was on the separate X-RAY page.
        # This Quick Look panel keeps both on the same screen — type a symbol,
        # see its sentiment + paid headlines without leaving the tab.
        section("🔍 Quick Look — Single-Symbol Analyst Sentiment + Paid News")
        st.caption("Type any NSE symbol below to see its consensus + ET/MC headlines "
                   "right here. For deep fundamentals (Income Statement, Quarterly "
                   "Results, Scorecard), open **🧬 X-RAY** in the sidebar.")

        _ql_c1, _ql_c2 = st.columns([2, 4])
        with _ql_c1:
            _ql_sym = st.text_input(
                "NSE Symbol", value="",
                placeholder="e.g. RELIANCE, INFY, DIXON",
                key="ht_xray_quicklook_sym"
            ).strip().upper().replace(".NS", "").replace(".BO", "")
        with _ql_c2:
            _ql_force = st.checkbox(
                "Force refresh (bypass 6h cache)",
                value=False, key="ht_xray_quicklook_force"
            )

        if _ql_sym:
            try:
                import analyst_sentiment as _ql_ans
                with st.spinner(f"Fetching ET + MC analyst sentiment for {_ql_sym}…"):
                    _ql_sent = _ql_ans.get_for_symbol(_ql_sym, force=_ql_force)

                _ql_cons = _ql_sent["consensus"]
                _ql_cons_color = {
                    "STRONG_BUY":  "#39ff14",
                    "BUY":         "#00f260",
                    "HOLD":        "#e3b341",
                    "SELL":        "#ff4b4b",
                    "STRONG_SELL": "#ff1744",
                    "MIXED":       "#a78bfa",
                    "NONE":        "#5a8a9f",
                }.get(_ql_cons, "#5a8a9f")
                _ql_cons_label = _ql_cons.replace("_", " ")

                _q1, _q2, _q3, _q4, _q5, _q6 = st.columns(6)
                _q1.markdown(
                    f'<div class="metric-card">'
                    f'<div class="metric-label">Consensus</div>'
                    f'<div class="metric-value" style="color:{_ql_cons_color}">{_ql_cons_label}</div>'
                    f'</div>', unsafe_allow_html=True)
                _q2.metric("⭐ STRONG BUY",  _ql_sent.get("strong_buy", 0))
                _q3.metric("BUY",            _ql_sent["buy"])
                _q4.metric("HOLD",           _ql_sent["hold"])
                _q5.metric("SELL",           _ql_sent["sell"])
                _q6.metric("⚠ STRONG SELL", _ql_sent.get("strong_sell", 0))

                _src_ok = _ql_sent.get("sources_ok", {})
                st.caption(
                    f"ET: {'✓' if _src_ok.get('et') else '✗'}  ·  "
                    f"MC: {'✓' if _src_ok.get('mc') else '✗'}  ·  "
                    f"Fetched: {_ql_sent.get('fetched_at', '—')}  ·  6h cache"
                )

                _ql_items = _ql_sent.get("items", [])
                if _ql_items:
                    # Action-priority ordering: STRONG_BUY → BUY → STRONG_SELL → SELL → HOLD → OTHER
                    _ql_order = {"STRONG_BUY": 0, "BUY": 1, "STRONG_SELL": 2,
                                  "SELL": 3, "HOLD": 4, "OTHER": 5}
                    _ql_sorted = sorted(
                        _ql_items,
                        key=lambda x: _ql_order.get(x.get("action", "OTHER"), 6)
                    )
                    with st.expander(f"📰 {len(_ql_items)} headlines (sorted by action)",
                                     expanded=True):
                        for _it in _ql_sorted[:30]:
                            _a = _it.get("action") or "?"
                            _ac = {
                                "STRONG_BUY":  "#39ff14",
                                "BUY":         "#00f260",
                                "HOLD":        "#e3b341",
                                "SELL":        "#ff4b4b",
                                "STRONG_SELL": "#ff1744",
                            }.get(_a, "#5a8a9f")
                            _origin = _it.get("_origin", "?").upper()
                            _origin_label = {"ET": "Economic Times",
                                              "MC": "Moneycontrol"}.get(_origin, _origin)
                            _brk = _it.get("brokerage") or ""
                            _brk_str = f"  ·  {_brk}" if _brk else ""
                            st.markdown(
                                f'<div style="margin:6px 0;padding:8px;background:#0a1628;'
                                f'border-left:3px solid {_ac};border-radius:4px;">'
                                f'<span style="color:{_ac};font-weight:600;'
                                f'font-family:JetBrains Mono,monospace;font-size:0.7rem;">'
                                f'{_a.replace("_"," ")}</span>'
                                f'  ·  <span style="color:#5a8a9f;font-size:0.72rem;">{_origin_label}</span>'
                                f'<span style="color:#8b9eb0;font-size:0.72rem;">{_brk_str}</span>'
                                f'<div style="margin-top:4px;">'
                                f'<a href="{_it.get("url","#")}" target="_blank" '
                                f'style="color:#e6edf3;font-size:0.86rem;text-decoration:none;">'
                                f'{_it.get("title","")}</a></div></div>',
                                unsafe_allow_html=True
                            )
                else:
                    st.info(
                        f"No paid ET/MC headlines mentioning **{_ql_sym}** in current cache. "
                        f"Try a different ticker or expand the company-name keyword map."
                    )
            except FileNotFoundError as _ql_e:
                st.warning(
                    "Paid news cookies not configured. Run "
                    "`python setup_paid_news_cookies.py` to enable ET + MC scraping."
                )
            except Exception as _ql_e:
                st.error(f"Quick Look fetch failed: {_ql_e}")

        st.markdown("---")
        section("📊 Bulk X-Ray Fundamental Screener (Python Edition)")
        st.caption("Scans watchlists OR custom symbols using the deep Weinstein Fundamental X-Ray v2.2 logic.")

        # ── Input source selector ──────────────────────────────────────────────
        _xray_src = st.radio(
            "Symbol Source",
            ["📂 Default  (Generated Watchlists)", "⬆️ Upload CSV Watchlist"],
            horizontal=True, key="xray_src_radio",
        )

        _xray_custom_syms = None
        _xray_out_file    = "FINAL_XRay_Picks.csv"

        if _xray_src.startswith("⬆️"):
            _xray_upload = st.file_uploader(
                "Upload a CSV/TXT with Symbols (NSE codes, TradingView exports)",
                type=["csv", "txt"],
                key="xray_upload_csv",
                help="CSV: Symbol, NSECode, Ticker, Scrip. TXT: Comma-separated (NSE:VBL,NSE:NAM_INDIA)",
            )
            if _xray_upload is not None:
                try:
                    if _xray_upload.name.lower().endswith(".txt"):
                        import re
                        text_content = _xray_upload.getvalue().decode("utf-8")
                        raw_syms = re.split(r'[,;\n\s]+', text_content)
                        _xray_custom_syms = []
                        for s in raw_syms:
                            s = s.strip().strip("'").strip('"').upper()
                            s = re.sub(r"^(NSE:|BSE:)", "", s)
                            s = re.sub(r"\.NS$", "", s)
                            if s and not s.isdigit():
                                _xray_custom_syms.append(s)
                        _xray_custom_syms = list(dict.fromkeys(_xray_custom_syms))
                        _xray_out_file = "XRay_Screener_Custom_Results.csv"
                        st.success(f"✅ {len(_xray_custom_syms)} symbols loaded from **{_xray_upload.name}**")
                        st.caption("Results → **XRay_Screener_Custom_Results.csv** (default run not overwritten)")
                    else:
                        _df_xr_up = pd.read_csv(_xray_upload)
                        _xr_col   = next(
                            (c for c in _df_xr_up.columns
                             if c.strip().lower() in ("symbol", "nsecode", "ticker", "scrip")),
                            None,
                        )
                        if _xr_col is None:
                            st.warning(f"No Symbol column found. Columns: {list(_df_xr_up.columns)}")
                        else:
                            _xray_custom_syms = (
                                _df_xr_up[_xr_col].dropna().astype(str)
                                .str.strip().str.upper()
                                .str.replace(r"^(NSE:|BSE:)", "", regex=True)
                                .str.replace(r"\.NS$", "", regex=True)
                                .unique().tolist()
                            )
                            _xray_custom_syms = [s for s in _xray_custom_syms if s and not s.isdigit()]
                            _xray_out_file    = "XRay_Screener_Custom_Results.csv"
                            st.success(f"✅ {len(_xray_custom_syms)} symbols loaded from **{_xray_upload.name}**")
                            st.caption("Results → **XRay_Screener_Custom_Results.csv** (default run not overwritten)")
                except Exception as _xue:
                    st.error(f"Could not parse upload: {_xue}")
        else:
            # Legacy text-area passthrough for backward compat
            _xray_text = st.text_area(
                "Custom Symbols (Optional — overrides watchlists when filled)",
                help="TradingView format (NSE:RELIANCE) or plain codes, comma/newline separated.",
                key="xray_custom_input", height=80,
                placeholder="NSE:WELCORP,NSE:APARINDS\nOr leave blank to scan all watchlists automatically."
            )
            if _xray_text.strip():
                _xray_custom_syms = [
                    s.strip().replace("NSE:", "").replace("BSE:", "").upper()
                    for s in _xray_text.replace(",", "\n").splitlines() if s.strip()
                ]

        _xray_run_label = (
            f"Run X-Ray Screener — Custom Watchlist\n{len(_xray_custom_syms)} symbols\n→  Screen Now"
            if _xray_custom_syms is not None
            else "Run X-Ray Screener\nEvaluates Minervini & Piotroski logic bypassing TV limits.\n→  Run Now"
        )
        if st.button(_xray_run_label, type="primary", use_container_width=True, key="sel_xray"):
            try:
                import xray_screener_job as _xj
                _xray_prog = st.progress(0)
                _xray_stat = st.empty()

                def _on_xray_progress(idx, total, sym):
                    _xray_prog.progress(int(idx / total * 100))
                    _xray_stat.text(f"Scanning [{idx}/{total}]: {sym}")

                _df_xray_res = _xj.run_xray_screener(
                    progress_callback=_on_xray_progress,
                    symbols=_xray_custom_syms,
                    out_file=_xray_out_file,
                )
                _xray_prog.empty(); _xray_stat.empty()
                if not _df_xray_res.empty:
                    st.success(f"✅ Done — {len(_df_xray_res)} stocks scored.")
                else:
                    st.info("No results. Check watchlists or uploaded symbols.")
            except Exception as _xe:
                st.error(f"X-Ray Screener error: {_xe}")

        import datetime as _dt
        xray_csv = os.path.join(_script_dir, _xray_out_file)
        if os.path.exists(xray_csv):
            try:
                df_xray = pd.read_csv(xray_csv)

                _xmtime  = _dt.datetime.fromtimestamp(os.path.getmtime(xray_csv))
                _xage_h  = (_dt.datetime.now() - _xmtime).total_seconds() / 3600
                _xts_str = _xmtime.strftime("%d %b %Y  %H:%M")
                if _xage_h > 28:
                    st.warning(f"Results last updated {_xts_str} — consider re-running.")
                else:
                    st.caption(f"Results from **{_xts_str}**")

                st.markdown("**Latest X-Ray Screener Results**")

                xc1, xc2 = st.columns([1, 1], gap="small")
                with xc1:
                    min_rating = st.number_input("Min Overall Rating", min_value=0, max_value=17, value=0, step=1, key="xray_rating")
                with xc2:
                    min_piotroski = st.number_input("Min Piotroski Score", min_value=0, max_value=9, value=0, step=1, key="xray_pio")

                df_xray_disp = df_xray[
                    (pd.to_numeric(df_xray["Overall_Rating"], errors="coerce").fillna(0) >= min_rating) &
                    (pd.to_numeric(df_xray["Piotroski_Score"], errors="coerce").fillna(0) >= min_piotroski)
                ]
                st.dataframe(df_xray_disp, use_container_width=True, hide_index=True)
                st.caption(f"{len(df_xray_disp)} stocks shown after filters.")

                if not df_xray_disp.empty:
                    _xray_syms = df_xray_disp["Symbol"].dropna().astype(str).unique().tolist()
                    _pine_xray = (
                        "// Commander X-Ray Screener — Pine Symbol Array\n"
                        f"// Generated {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                        "var string[] xray_symbols = array.from(\n    "
                        + ", ".join(f'"{s.replace(".NS", "")}"' for s in _xray_syms)
                        + "\n)"
                    )
                    _xdl1, _xdl2 = st.columns([3, 1])
                    with _xdl1:
                        st.download_button(
                            label="⬇️ Export Filtered to CSV",
                            data=df_xray_disp.to_csv(index=False).encode("utf-8"),
                            file_name="XRay_Screener_Export.csv",
                            mime="text/csv",
                            key="xray_csv_dl",
                        )
                    with _xdl2:
                        st.download_button(
                            label="⬇️ Export Pine Array",
                            data=_pine_xray,
                            file_name="XRay_Pine_Symbols.pine",
                            mime="text/plain",
                            key="xray_pine_dl",
                            help="Download as a .pine snippet ready to paste into your indicator"
                        )
            except Exception as e:
                st.error(f"Error loading X-Ray Screener results: {e}")
        # (Old in-tab Ultimate Golden Meta-Ranking removed — it now lives at the
        # top of the 🥇 Golden Matcher tab next to the Run Matcher button.)

        # ── Analyst Sentiment for X-Ray Screener picks (bulk run) ────────────
        st.markdown("---")
        _xray_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   _xray_out_file)
        _render_analyst_sentiment_panel(
            csv_path=_xray_path,
            symbol_col="Symbol",
            key_prefix="xray",
            label="X-Ray Screener Picks",
            extra_caption=f"Reading from `{_xray_out_file}` "
                          "(use the Quick Look box at the top of this tab for single-symbol drill-down)",
        )

    with _ht4:
        section("Bull Market Screener")
        st.caption("Implements 6 catalysts from Commander Screener Beta Edition v2.9 (Pine).")

        # ── Input source selector ──────────────────────────────────────────────
        # P1.6 + #14 (10 May 2026): added "Nifty 500 (full universe)" as a third
        # source option so the python screener can run on the same universe used
        # by the validation backtest (validation.default_universe('nifty500')).
        # Per Bible §14A this is the canonical universe for cross-platform
        # consistency between backtest and live screening.
        _bull_src = st.radio(
            "Symbol Source",
            [
                "📂 Default  (FINAL_COMBINED_BULL_PICKS.csv)",
                "🌐 Nifty 500  (full universe — backtest-aligned)",
                "⚡ F&O Basket  (NSE derivatives universe ~210 stocks)",
                "⬆️ Upload CSV Watchlist",
            ],
            horizontal=True, key="bull_src_radio",
        )

        _bull_custom_symbols = None   # None → screener reads default file
        _bull_out_file       = "Bull_Screener_Results.csv"

        if _bull_src.startswith("🌐"):
            # Nifty 500 — load via validation.default_universe('nifty500')
            try:
                import validation as _val
                _bull_custom_symbols = list(_val.default_universe("nifty500"))
                _bull_out_file = "Bull_Screener_N500_Results.csv"
                st.success(
                    f"✅ {len(_bull_custom_symbols)} Nifty 500 symbols loaded "
                    "(via validation.default_universe('nifty500'))."
                )
                st.caption(
                    "Results will be saved to **Bull_Screener_N500_Results.csv** "
                    "(separate from the default-watchlist run)."
                )
            except Exception as _n500e:
                st.error(f"Could not load Nifty 500: {_n500e}")
                _bull_custom_symbols = None

        if _bull_src.startswith("⚡"):
            # F&O Basket — load via validation.default_universe('fno')
            try:
                import validation as _val
                _bull_custom_symbols = list(_val.default_universe("fno"))
                _bull_out_file = "Bull_Screener_FNO_Results.csv"
                st.success(
                    f"✅ {len(_bull_custom_symbols)} F&O symbols loaded "
                    "(via validation.default_universe('fno') → fno_symbols.json)."
                )
                st.caption(
                    "Results will be saved to **Bull_Screener_FNO_Results.csv** "
                    "(separate from default / Nifty 500 runs). "
                    "Refresh `fno_symbols.json` periodically per NSE F&O circulars."
                )
            except Exception as _fnoe:
                st.error(f"Could not load F&O basket: {_fnoe}")
                _bull_custom_symbols = None

        if _bull_src.startswith("⬆️"):
            _bull_upload = st.file_uploader(
                "Upload a CSV/TXT with Symbols (NSE codes, TradingView exports)",
                type=["csv", "txt"],
                key="bull_upload_csv",
                help="CSV: Symbol, NSECode, Ticker, Scrip. TXT: Comma-separated (NSE:VBL,NSE:NAM_INDIA)",
            )
            if _bull_upload is not None:
                try:
                    if _bull_upload.name.lower().endswith(".txt"):
                        import re
                        text_content = _bull_upload.getvalue().decode("utf-8")
                        raw_syms = re.split(r'[,;\n\s]+', text_content)
                        _bull_custom_symbols = []
                        for s in raw_syms:
                            s = s.strip().strip("'").strip('"').upper()
                            s = re.sub(r"^(NSE:|BSE:)", "", s)
                            s = re.sub(r"\.NS$", "", s)
                            if s and not s.isdigit():
                                _bull_custom_symbols.append(s)
                        _bull_custom_symbols = list(dict.fromkeys(_bull_custom_symbols))
                        _bull_out_file = "Bull_Screener_Custom_Results.csv"
                        st.success(
                            f"✅ {len(_bull_custom_symbols)} symbols loaded from "
                            f"**{_bull_upload.name}**"
                        )
                        st.caption(
                            "Results will be saved to **Bull_Screener_Custom_Results.csv** "
                            "and will not overwrite your default run."
                        )
                    else:
                        _df_up = pd.read_csv(_bull_upload)
                        _col   = next(
                            (c for c in _df_up.columns
                             if c.strip().lower() in ("symbol", "nsecode", "ticker", "scrip")),
                            None,
                        )
                        if _col is None:
                            st.warning(
                                f"No Symbol column found. Columns in file: {list(_df_up.columns)}"
                            )
                        else:
                            _bull_custom_symbols = (
                                _df_up[_col].dropna().astype(str)
                                .str.strip().str.upper()
                                .str.replace(r"^(NSE:|BSE:)", "", regex=True)
                                .str.replace(r"\.NS$", "", regex=True)
                                .unique().tolist()
                            )
                            _bull_custom_symbols = [
                                s for s in _bull_custom_symbols if s and not s.isdigit()
                            ]
                            _bull_out_file = "Bull_Screener_Custom_Results.csv"
                            st.success(
                                f"✅ {len(_bull_custom_symbols)} symbols loaded from "
                                f"**{_bull_upload.name}**"
                            )
                            st.caption(
                                "Results will be saved to **Bull_Screener_Custom_Results.csv** "
                                "and will not overwrite your default run."
                            )
                except Exception as _ue:
                    st.error(f"Could not parse upload: {_ue}")

        # ── Run button ─────────────────────────────────────────────────────────
        _run_label = (
            "Run Bull Screener — Custom Watchlist\n"
            f"{len(_bull_custom_symbols)} symbols loaded\n→  Screen Now"
            if _bull_custom_symbols is not None
            else "Run Bull Screener — Default Watchlist\n"
                 "Reads FINAL_COMBINED_BULL_PICKS.csv\n→  Screen Now"
        )
        if st.button(_run_label, type="primary", use_container_width=True, key="sel_bull"):
            try:
                import bull_screener as _bs
                _prog_bar  = st.progress(0)
                _stat_text = st.empty()

                def _on_bull_progress(idx, total, sym):
                    _prog_bar.progress(int(idx / total * 100))
                    _stat_text.text(f"Scanning [{idx}/{total}]: {sym}")

                # strict=True for Nifty 500 / F&O — apply full catalyst gate (no tracker mode).
                # Upload-CSV path keeps tracker mode so users see every monitored stock.
                _bull_strict = _bull_src.startswith("🌐") or _bull_src.startswith("⚡")
                _df_result = _bs.run_bull_screener(
                    progress_callback=_on_bull_progress,
                    symbols=_bull_custom_symbols,   # None → uses default file
                    out_file=_bull_out_file,
                    strict=_bull_strict,
                )
                _prog_bar.empty(); _stat_text.empty()
                if not _df_result.empty:
                    st.success(f"✅ Done — {len(_df_result)} signals found.")
                else:
                    st.info("No catalyst signals fired for this watchlist.")
            except Exception as _be:
                st.error(f"Bull Screener error: {_be}")

        # ── Results display ────────────────────────────────────────────────────
        import datetime as _dt
        _script_dir_bs = os.path.dirname(os.path.abspath(__file__))
        _bull_csv_path = os.path.join(_script_dir_bs, _bull_out_file)
        _bull_input_path = os.path.join(_script_dir_bs, "FINAL_COMBINED_BULL_PICKS.csv")

        # Show INPUT file freshness alongside OUTPUT — if input is newer than
        # output, the user ran Auto-Pilot but hasn't re-run the Bull Screener.
        # 10 May 2026 fix: prevents "stale 5 May date" confusion when the
        # underlying watchlist was actually refreshed today.
        _bf_in_col, _bf_out_col = st.columns(2)
        with _bf_in_col:
            st.markdown("**📥 Input watchlist** (`FINAL_COMBINED_BULL_PICKS.csv`)")
            _csv_freshness_caption(_bull_input_path, label="Watchlist")
        with _bf_out_col:
            st.markdown(f"**📤 Last screen run** (`{_bull_out_file}`)")
            _csv_freshness_caption(_bull_csv_path, label="Last run")

        # Stale-input warning: if input is newer than output, alert user
        if os.path.exists(_bull_input_path) and os.path.exists(_bull_csv_path):
            _input_mt  = os.path.getmtime(_bull_input_path)
            _output_mt = os.path.getmtime(_bull_csv_path)
            if _input_mt > _output_mt + 60:  # 60-sec grace to avoid false-positives
                st.info(
                    "🆕 The input watchlist is **newer** than your last Bull Screener "
                    "run. Click **Run Bull Screener** above to refresh against the "
                    "current watchlist."
                )

        if os.path.exists(_bull_csv_path):
            try:
                _df_bull = pd.read_csv(_bull_csv_path)

                st.markdown("**Latest Bull Screener Results**")

                _fc1, _fc2 = st.columns([2, 2], gap="small")
                with _fc1:
                    _cat_choices = ["All"] + sorted(
                        _df_bull["Catalyst"].dropna().unique().tolist()
                    ) if "Catalyst" in _df_bull.columns else ["All"]
                    _cat_filt = st.selectbox(
                        "Catalyst Filter", _cat_choices, key="bull_cat_filter"
                    )
                with _fc2:
                    # v1.0 sync: bull_screener now uses 0-100 score scale (was 0-20).
                    # Default kept at 0 (no filter) so existing user behaviour preserved.
                    _min_scr = st.number_input(
                        "Min Score", min_value=0, max_value=100,
                        value=0, key="bull_score_filter"
                    )

                _df_view = _df_bull.copy()
                if _cat_filt != "All" and "Catalyst" in _df_view.columns:
                    _df_view = _df_view[_df_view["Catalyst"] == _cat_filt]
                if "Score" in _df_view.columns:
                    _df_view = _df_view[
                        pd.to_numeric(_df_view["Score"], errors="coerce").fillna(0) >= _min_scr
                    ]

                st.dataframe(_df_view, use_container_width=True, hide_index=True)
                st.caption(f"{len(_df_view)} stocks shown after filters.")

                if not _df_view.empty:
                    _dl1, _dl2 = st.columns([3, 1])
                    with _dl1:
                        st.download_button(
                            label="⬇️ Export Filtered to CSV",
                            data=_df_view.to_csv(index=False).encode("utf-8"),
                            file_name="Bull_Screener_Export.csv",
                            mime="text/csv",
                            key="bull_csv_dl",
                        )
                    with _dl2:
                        _pine_bull = (
                            "// Commander Bull Screener — Pine Symbol Array\n"
                            f"// Generated {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                            "var string[] bull_syms = array.from(\n    "
                            + ",\n    ".join(
                                f'"NSE:{s}"'
                                for s in _df_view["Symbol"].dropna().astype(str).tolist()
                            )
                            + "\n)"
                        )
                        st.download_button(
                            label="⬇️ Export Pine Array",
                            data=_pine_bull,
                            file_name="Bull_Pine_Symbols.pine",
                            mime="text/plain",
                            key="bull_pine_dl",
                        )
            except Exception as _be2:
                st.error(f"Error loading Bull Screener results: {_be2}")
        else:
            st.info(
                "No Bull Screener results yet. "
                "Run the screener above (default or upload a custom watchlist)."
            )

        # ── Catalyst Drill-Down ───────────────────────────────────────────
        # Note: the Strategy → fundamentals drill-down (FINAL_*_Picks.csv) was
        # moved to the Golden Matcher tab. This drill-down is purpose-built for
        # the Bull Screener: pick a catalyst (POS-AC / POS-BO / SWG-PB / SWG-BO
        # / SWG-REV / GAP-GO) and see ONLY that catalyst's signals with full
        # column detail. Useful when you want to focus on one playbook at a time.
        if os.path.exists(_bull_csv_path):
            try:
                _drill_df = pd.read_csv(_bull_csv_path)
                if not _drill_df.empty and "Catalyst" in _drill_df.columns:
                    section("Catalyst Drill-Down")
                    _cat_options = sorted(_drill_df["Catalyst"].dropna().unique().tolist())
                    if _cat_options:
                        _drill_pick = st.selectbox(
                            "Select Catalyst to drill down:",
                            _cat_options,
                            key="bull_drill_catalyst",
                            help="Filters the table to signals fired by ONE specific catalyst, "
                                 "with all columns visible.",
                        )
                        _drill_view = _drill_df[_drill_df["Catalyst"] == _drill_pick]
                        st.caption(
                            f"**{_drill_pick}** — {len(_drill_view)} signal(s). "
                            f"Refer to the Beta Screener v2.9 catalyst playbooks for entry/exit logic."
                        )
                        st.dataframe(_drill_view, use_container_width=True, hide_index=True)
                    else:
                        st.info("No catalysts to drill into. Run the Bull Screener first.")
            except Exception as _drill_e:
                st.error(f"Catalyst drill-down failed: {_drill_e}")

        # ── DEPRECATED inline Analyst Sentiment panel ──────────────────────
        # Removed 10 May 2026 — duplicated the helper-based panel at the top
        # of this tab (line ~2406, _render_analyst_sentiment_panel(...)). The
        # inline duplicate had a brittle r["consensus"] dict access that raised
        # KeyError('Consensus') when a cached result was missing keys. The
        # canonical panel uses .get() throughout. This block neutralised so
        # only one Analyst Sentiment section renders per tab.
        if False:  # original block kept inert below; never executes
            section("📊 Analyst Sentiment — ET + Moneycontrol (paid)")
        try:
            import analyst_sentiment as _ans
            _ans_health = _ans.health_check()
            _et_ok = _ans_health.get("et", {}).get("ok", False)
            _mc_ok = _ans_health.get("mc", {}).get("ok", False)
            _ans_h1, _ans_h2 = st.columns(2)
            _ans_h1.markdown(
                f'<div style="font-family:JetBrains Mono,monospace;font-size:0.78rem">'
                f'ET session: <b style="color:{"#00f260" if _et_ok else "#ff4b4b"}">'
                f'{"✓ live" if _et_ok else "✗ down — re-run setup_paid_news_cookies.py"}</b>'
                f'</div>', unsafe_allow_html=True)
            _ans_h2.markdown(
                f'<div style="font-family:JetBrains Mono,monospace;font-size:0.78rem">'
                f'MC session: <b style="color:{"#00f260" if _mc_ok else "#ff4b4b"}">'
                f'{"✓ live" if _mc_ok else "✗ down — re-run setup_paid_news_cookies.py"}</b>'
                f'</div>', unsafe_allow_html=True)

            if (_et_ok or _mc_ok) and os.path.exists(_bull_csv_path):
                st.caption("Pulls Buy/Hold/Sell consensus + recent analyst headlines for "
                           "each Bull Screener pick. Cached 6h per symbol — first run can "
                           "take ~20–40s for 10 symbols.")
                _ans_top_n = st.slider("Symbols to pull sentiment for (top N by Score)",
                                       min_value=5, max_value=30, value=10,
                                       key="bull_ans_topn")
                _ans_force = st.checkbox("Force refresh (bypass 6h cache)",
                                         value=False, key="bull_ans_force")
                if st.button("📊 Pull Analyst Sentiment", key="bull_ans_btn",
                             type="secondary"):
                    try:
                        _ans_df_full = pd.read_csv(_bull_csv_path)
                        _sym_col = next((c for c in ["Symbol","NSECode","Ticker"]
                                         if c in _ans_df_full.columns), None)
                        if _sym_col is None:
                            st.warning("No Symbol column in Bull Screener results.")
                        else:
                            # Sort by Score descending, take top N
                            if "Score" in _ans_df_full.columns:
                                _ans_df_full = _ans_df_full.sort_values(
                                    "Score", ascending=False
                                )
                            _ans_syms = (_ans_df_full[_sym_col].dropna().astype(str)
                                         .head(int(_ans_top_n)).tolist())
                            _ans_results = []
                            _prog = st.progress(0)
                            for i, sym in enumerate(_ans_syms, 1):
                                r = _ans.get_for_symbol(sym, force=_ans_force)
                                _ans_results.append({
                                    "Symbol":        sym,
                                    "Consensus":     r["consensus"],
                                    "★ STRONG BUY":  r.get("strong_buy", 0),
                                    "BUY":           r["buy"],
                                    "HOLD":          r["hold"],
                                    "SELL":          r["sell"],
                                    "★ STRONG SELL": r.get("strong_sell", 0),
                                    "Items":         len(r["items"]),
                                    "ET":            "✓" if r["sources_ok"]["et"] else "✗",
                                    "MC":            "✓" if r["sources_ok"]["mc"] else "✗",
                                })
                                _prog.progress(int(i / len(_ans_syms) * 100))
                            _prog.empty()
                            _ans_df = pd.DataFrame(_ans_results)
                            # Sort: STRONG_BUY → BUY → MIXED → HOLD → NONE → SELL → STRONG_SELL
                            _consensus_rank = {
                                "STRONG_BUY":  0, "BUY":  1, "MIXED": 2,
                                "HOLD":        3, "NONE": 4, "SELL":  5,
                                "STRONG_SELL": 6,
                            }
                            _ans_df["_rank"] = _ans_df["Consensus"].map(_consensus_rank).fillna(7)
                            _ans_df = (_ans_df.sort_values(
                                ["_rank", "★ STRONG BUY", "BUY"],
                                ascending=[True, False, False])
                                       .drop(columns=["_rank"]))
                            st.dataframe(_ans_df, use_container_width=True,
                                         hide_index=True)

                            # ── Strong Buy spotlight ──────────────────────────
                            _strong_only = _ans_df[
                                (_ans_df["Consensus"] == "STRONG_BUY") |
                                (_ans_df["★ STRONG BUY"] > 0)
                            ]
                            if not _strong_only.empty:
                                st.success(
                                    f"⭐ **{len(_strong_only)} Strong Buy candidate(s)** — "
                                    f"{', '.join(_strong_only['Symbol'].astype(str).tolist())}"
                                )
                            else:
                                st.caption(
                                    "_No Strong Buy candidates in this batch. "
                                    "Strong Buy requires at least one analyst headline with "
                                    "'strong buy' / 'top pick' / 'best idea' / 'high-conviction buy' "
                                    "AND no opposing actionable Sells._"
                                )

                            st.caption(f"Pulled at {pd.Timestamp.now().strftime('%H:%M IST')}. "
                                       "Drill into a single symbol on **🧬 X-RAY → 📰 News** "
                                       "for full headlines + brokerage details.")
                    except Exception as _ans_e:
                        st.error(f"Sentiment pull failed: {_ans_e}")
            elif not (_et_ok or _mc_ok):
                st.warning(
                    "Both ET and MC sessions are down. Re-run "
                    "`python setup_paid_news_cookies.py` to refresh cookies."
                )
            else:
                st.info("Run the Bull Screener above first — sentiment pulls from those picks.")
        except ImportError:
            st.info("Analyst sentiment module not installed. See `analyst_sentiment.py`.")


# ════════════════════════════════════════════════════════════════════════════
#  WATCHLIST
# ════════════════════════════════════════════════════════════════════════════
elif page == 'WATCHLIST':
    st.markdown('<div class="page-title">📋 Watchlist Sync</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Synchronize your selected setups across all platforms.</div>', unsafe_allow_html=True)

    # ── Auto-Pilot Output Panel (G — 10 May 2026) ────────────────────────────
    # Per user feedback: the WATCHLIST page should surface what Run Full
    # Auto-Pilot just produced. Without this, the user clicked Auto-Pilot in
    # the sidebar, landed here, and had no visual confirmation of the FINAL_*.csv
    # files that had been written. This panel solves that.
    import datetime as _dt_wl

    if st.session_state.get("wf_run_trigger"):
        st.success(
            "🤖 **Auto-Pilot pipeline launched.** It runs in a separate console window — "
            "Layer 1 Chartink scans → Layer 2 Screener.in conviction filter → Layer 3 "
            "combined files → Layer 4 TradingView sync. Files below refresh automatically "
            "as each layer completes (typical run: 5–10 minutes)."
        )
        st.session_state["wf_run_trigger"] = False  # consume the flag

    section("🤖 Latest Auto-Pilot Output")

    _ap_root = os.path.dirname(os.path.abspath(__file__))
    # Layer 2 (conviction-filtered) FINAL_*_Picks.csv files
    _ap_final_files = [
        ("🐂 Hunter Picks",          "FINAL_Hunter_Picks.csv"),
        ("🔄 Pullback Picks",        "FINAL_Pullback_Picks.csv"),
        ("🌅 EarlyBird Picks",       "FINAL_EarlyBird_Picks.csv"),
        ("👑 Leader Picks",          "FINAL_Leader_Picks.csv"),
        ("🔻 Recovery Climax",       "FINAL_Recovery_ClimaxBounce.csv"),
        ("📈 Recovery EarlyBirds",   "FINAL_Recovery_EarlyBirds.csv"),
        ("⚡ Recovery RS Leaders",   "FINAL_Recovery_RSLeaders.csv"),
    ]
    # Layer 3 — combined + golden
    _ap_combined_files = [
        ("📦 Combined Bull Picks",      "FINAL_COMBINED_BULL_PICKS.csv"),
        ("📦 Combined Recovery Picks",  "FINAL_COMBINED_RECOVERY_PICKS.csv"),
        ("📦 Combined All Picks",       "FINAL_COMBINED_PICKS.csv"),
        ("🏆 Golden Matcher Watchlist", "FINAL_WATCHLIST.csv"),
    ]

    def _ap_file_meta(fname):
        """Return (rows, mtime_str, age_h) for a CSV in project root, or (None, '—', None)."""
        p = os.path.join(_ap_root, fname)
        if not os.path.exists(p):
            return None, "—", None
        try:
            df_t = pd.read_csv(p)
            mt = _dt_wl.datetime.fromtimestamp(os.path.getmtime(p))
            age_h = (_dt_wl.datetime.now() - mt).total_seconds() / 3600.0
            return len(df_t), mt.strftime("%d %b %H:%M"), age_h
        except Exception:
            return None, "—", None

    # Top status strip — quick health-check across all FINAL_*.csv files
    _ap_total_rows = 0
    _ap_freshest_age = None
    for _label, _fname in _ap_final_files + _ap_combined_files:
        rows, _ts, age_h = _ap_file_meta(_fname)
        if rows is not None:
            _ap_total_rows += rows
            if _ap_freshest_age is None or (age_h is not None and age_h < _ap_freshest_age):
                _ap_freshest_age = age_h

    _ap_c1, _ap_c2, _ap_c3 = st.columns(3)
    _ap_c1.metric("FINAL_*.csv files present",
                  sum(1 for _, f in (_ap_final_files + _ap_combined_files)
                      if os.path.exists(os.path.join(_ap_root, f))))
    _ap_c2.metric("Total rows across all picks", f"{_ap_total_rows:,}")
    _ap_c3.metric("Freshest file age",
                  f"{_ap_freshest_age:.1f}h" if _ap_freshest_age is not None else "—",
                  delta="stale (>28h)" if _ap_freshest_age and _ap_freshest_age > 28 else "fresh",
                  delta_color="inverse" if _ap_freshest_age and _ap_freshest_age > 28 else "normal")

    # Two-column file inventory: Layer 2 (per-strategy) on left, Layer 3 (combined) on right
    _ap_left, _ap_right = st.columns(2, gap="medium")

    with _ap_left:
        st.markdown("**Layer 2 — Per-Strategy Picks (Conviction-Filtered)**")
        for _label, _fname in _ap_final_files:
            rows, ts, age_h = _ap_file_meta(_fname)
            if rows is None:
                st.caption(f"{_label} · `{_fname}` · _not found_")
            else:
                _stale_tag = " ⚠️" if age_h and age_h > 28 else ""
                with st.expander(f"{_label} — **{rows}** picks  ·  {ts}{_stale_tag}", expanded=False):
                    try:
                        df_view = pd.read_csv(os.path.join(_ap_root, _fname))
                        st.dataframe(df_view, use_container_width=True, hide_index=True,
                                     height=min(40 + 35 * len(df_view), 400))
                    except Exception as _e:
                        st.error(f"Failed to load: {_e}")

    with _ap_right:
        st.markdown("**Layer 3 — Combined & Golden Matcher**")
        for _label, _fname in _ap_combined_files:
            rows, ts, age_h = _ap_file_meta(_fname)
            if rows is None:
                st.caption(f"{_label} · `{_fname}` · _not found_")
            else:
                _stale_tag = " ⚠️" if age_h and age_h > 28 else ""
                _expand = (_fname == "FINAL_WATCHLIST.csv")  # auto-expand the golden one
                with st.expander(f"{_label} — **{rows}** picks  ·  {ts}{_stale_tag}", expanded=_expand):
                    try:
                        df_view = pd.read_csv(os.path.join(_ap_root, _fname))
                        st.dataframe(df_view, use_container_width=True, hide_index=True,
                                     height=min(40 + 35 * len(df_view), 500))
                    except Exception as _e:
                        st.error(f"Failed to load: {_e}")

    st.caption(
        "Files generated by **🤖 Run Auto-Pilot** (sidebar button) or `python run_pipeline.py`. "
        "Per Bible §6E, the Golden Matcher Watchlist (`FINAL_WATCHLIST.csv`) is the single best "
        "file to load into TradingView for Phase 3 validation."
    )

    # ── Pipeline Health & Targeted Regeneration ─────────────────────────────
    # 10 May 2026 — answers two questions:
    #   1. Which CSVs were not generated (or are stale)?
    #   2. How do I regenerate ONE without re-running the whole 5–10 min Auto-Pilot?
    #
    # Each row shows status (✅ fresh / ⚠ stale / ❌ missing) + a "Re-run this only"
    # button that fires the specific script for that file. Saves time when only
    # one Chartink scan failed or only the Bull Screener needs a refresh.
    st.markdown("---")
    section("🩺 Pipeline Health & Targeted Regeneration")
    st.caption(
        "Status of every file in the discovery pipeline. Click **Re-run** on any "
        "row to regenerate that file specifically — no need to re-run the full "
        "Auto-Pilot for one missing CSV."
    )

    # 10 May 2026: launch_script() fires a subprocess in a SEPARATE console
    # window and returns immediately. Streamlit re-renders before the
    # subprocess writes the file, so the panel shows OLD mtimes. Streamlit
    # has no way to know when the subprocess finishes. Manual refresh button
    # below lets the user re-render the panel after the script's console
    # window closes (visible cue that the run completed).
    _ph_rfc1, _ph_rfc2 = st.columns([1, 5])
    with _ph_rfc1:
        if st.button("🔄 Refresh status", key="ph_refresh",
                     help="Re-read all CSV mtimes + row counts. Click this AFTER "
                          "a launched subprocess's console window closes."):
            st.rerun()
    with _ph_rfc2:
        st.caption(
            "ℹ️ **After clicking Re-run** on any row below: a separate console "
            "window opens and runs the script. **Wait until the console window "
            "closes** (typically 30-60s for a single Chartink scan, ~2 min for "
            "the matcher), then click **🔄 Refresh status** above to see the "
            "updated row counts and timestamps."
        )

    import datetime as _dt_ph
    _ph_root = os.path.dirname(os.path.abspath(__file__))

    # ── File registry — maps file → generator script + args ─────────────────
    # Layer 1 = raw Chartink scans (chartink_scanner_pro.py <id>)
    # Layer 2 = conviction-filtered FINAL_*_Picks.csv (brute_force_match_pro.py)
    # Layer 3 = combined files (also brute_force_match_pro.py)
    # Standalone screeners run independently from each tab's Run button
    _ph_layers = [
        ("🥇 Layer 1 — Raw Chartink Scans (chartink_scanner_pro.py)", [
            ("Stage2_Hunter.csv",            "chartink_scanner_pro.py", "1", "Bull · Hunter"),
            ("Stage2_Pullback.csv",          "chartink_scanner_pro.py", "2", "Bull · Pullback"),
            ("Early_Birds.csv",              "chartink_scanner_pro.py", "3", "Bull · EarlyBird"),
            ("Strong_Leaders.csv",           "chartink_scanner_pro.py", "4", "Bull · Leader"),
            ("Recovery_RS_Survivors.csv",    "chartink_scanner_pro.py", "5", "Recovery · RS"),
            ("Recovery_Climax_Bounce.csv",   "chartink_scanner_pro.py", "6", "Recovery · Climax"),
            ("Recovery_Early_Birds.csv",     "chartink_scanner_pro.py", "7", "Recovery · EarlyBird"),
        ]),
        ("🧬 Layer 2 — Conviction-Filtered FINAL_*_Picks (brute_force_match_pro.py)", [
            ("FINAL_Hunter_Picks.csv",          "brute_force_match_pro.py", None, "Bull · Hunter"),
            ("FINAL_Pullback_Picks.csv",        "brute_force_match_pro.py", None, "Bull · Pullback"),
            ("FINAL_EarlyBird_Picks.csv",       "brute_force_match_pro.py", None, "Bull · EarlyBird"),
            ("FINAL_Leader_Picks.csv",          "brute_force_match_pro.py", None, "Bull · Leader"),
            ("FINAL_Recovery_RSLeaders.csv",    "brute_force_match_pro.py", None, "Recovery · RS"),
            ("FINAL_Recovery_ClimaxBounce.csv", "brute_force_match_pro.py", None, "Recovery · Climax"),
            ("FINAL_Recovery_EarlyBirds.csv",   "brute_force_match_pro.py", None, "Recovery · EarlyBird"),
        ]),
        ("📦 Layer 3 — Combined & Golden (brute_force_match_pro.py)", [
            ("FINAL_COMBINED_BULL_PICKS.csv",     "brute_force_match_pro.py", None, "Combined Bull union"),
            ("FINAL_COMBINED_RECOVERY_PICKS.csv", "brute_force_match_pro.py", None, "Combined Recovery union"),
            ("FINAL_COMBINED_PICKS.csv",          "brute_force_match_pro.py", None, "Everything, deduped"),
            ("FINAL_WATCHLIST.csv",               "brute_force_match_pro.py", None, "Golden Matcher conviction-ranked"),
        ]),
        ("🐂 Standalone Live Screeners (run from HUNTER tabs)", [
            ("Bull_Screener_Results.csv",     "bull_screener.py",     None, "HUNTER → 🐂 Bull Screener"),
            ("Recovery_Screener_Results.csv", "recovery_screener.py", None, "HUNTER → 🔄 Recovery Screener"),
            ("FINAL_XRay_Picks.csv",     "xray_screener_job.py", None, "HUNTER → 🧬 X-Ray Screener"),
        ]),
    ]

    def _ph_status(file_path):
        """Return (badge, color, mtime_str, age_h) for a file.

        Row-count-aware (10 May 2026 update). Five distinct states:
            ❌ Missing         — file doesn't exist
            ⚪ 0 entries       — fresh + empty (ran today, no signals)
            ✅ N entries       — fresh + has data
            ⚠ Stale: N entries → ranges back to N rows from when last good
            ⚠ Stale: 0 entries → empty AND old
        """
        if not os.path.exists(file_path):
            return ("❌ Missing", "#ff4b4b", "—", None)
        mtime = _dt_ph.datetime.fromtimestamp(os.path.getmtime(file_path))
        age_h = (_dt_ph.datetime.now() - mtime).total_seconds() / 3600
        ts = mtime.strftime("%d %b  %H:%M")
        # Count data rows
        try:
            _n_rows = len(pd.read_csv(file_path))
        except Exception:
            _n_rows = None
        _ent_str = (f"{_n_rows} entries" if _n_rows is not None else "?? entries")
        if age_h > 28:
            return (f"⚠ Stale: {_ent_str} ({age_h:.0f}h)", "#e3b341", ts, age_h)
        if _n_rows == 0:
            return (f"⚪ 0 entries ({age_h:.1f}h ago)", "#7a92a6", ts, age_h)
        return (f"✅ {_ent_str} ({age_h:.1f}h)", "#00f260", ts, age_h)

    for layer_label, files in _ph_layers:
        st.markdown(f"**{layer_label}**")
        for fname, script, arg, note in files:
            fpath = os.path.join(_ph_root, fname)
            badge, color, ts, age_h = _ph_status(fpath)
            _r1, _r2, _r3, _r4 = st.columns([3, 2, 2, 2])
            _r1.markdown(
                f'<div style="font-family:JetBrains Mono,monospace;font-size:0.78rem;'
                f'color:#c9d1d9;">{fname}</div>'
                f'<div style="font-size:0.66rem;color:#5a8a9f;">{note}</div>',
                unsafe_allow_html=True
            )
            _r2.markdown(
                f'<div style="font-family:JetBrains Mono,monospace;font-size:0.78rem;'
                f'color:{color};font-weight:600;">{badge}</div>',
                unsafe_allow_html=True
            )
            _r3.markdown(
                f'<div style="font-family:JetBrains Mono,monospace;font-size:0.74rem;'
                f'color:#9ba8b6;">{ts}</div>',
                unsafe_allow_html=True
            )
            with _r4:
                _btn_key = f"ph_regen_{fname.replace('.', '_')}"
                _btn_label = (f"▶ Re-run scan {arg}" if arg
                               else "▶ Re-run script")
                if st.button(_btn_label, key=_btn_key, use_container_width=True):
                    try:
                        if arg:
                            launch_script(script, arg)
                        else:
                            launch_script(script)
                        st.toast(
                            f"🚀 Launched {script} {arg or ''}. "
                            f"Wait for its console window to close, then click "
                            f"🔄 Refresh status above.".strip(),
                            icon="🚀",
                        )
                    except Exception as _e:
                        st.error(f"Launch failed: {_e}")
        st.markdown("")  # vertical breathing room between layer groups

    # Quick legend / regen guidance
    with st.expander("ℹ️ When to use which regeneration", expanded=False):
        st.markdown(
            "- **One Chartink scan failed** (e.g. Stage2_Hunter.csv missing): "
            "click the **▶ Re-run scan N** button on that row. ~10 seconds.\n"
            "- **Layer 2 / Layer 3 missing** (FINAL_*.csv files): the matcher "
            "needs Layer 1 to be present first. Check Layer 1 health, then "
            "click **▶ Re-run script** on any Layer 2/3 row — `brute_force_match_pro.py` "
            "regenerates ALL Layer 2 + Layer 3 outputs in one go (~2 min).\n"
            "- **Bull / Recovery / X-Ray Screener results stale**: these are "
            "INDEPENDENT of Auto-Pilot. They only refresh when you click their "
            "Run button on the respective HUNTER tab. The links in the right "
            "column are shortcuts.\n"
            "- **Everything missing or you want a clean refresh**: use the "
            "**🤖 Run Auto-Pilot** button in the sidebar (runs Layer 1 → Layer 2 → "
            "Layer 3 → Layer 4 sync in one shot, ~5–10 min)."
        )

    st.markdown("---")
    section("Sync & Tools")

    _wl1, _wl2, _wl3, _wl4, _wl5, _wl6, _wl7, _wl8 = st.tabs(
        ["🏗️ Generate", "☁️ Sync Cloud", "🏆 Smart Rank",
         "🏭 Sectors DB", "💾 Data Cache", "⚙️ Pipeline Status",
         "⏪ Replay", "📜 Track Record"]
    )

    with _wl1:
        left_col, right_col = st.columns(2, gap="medium")
        with left_col:
            section("1. Local Generation")
            if st.button("📁  Generate CSVs — Local\nGenerate clean CSVs for local analysis.\n→  Generate Now", key="wl_gen"):
                launch_script("watchlist_manager.py")
        with right_col:
            section("2. TV Pine Screener Generator")
            st.info("Upload a TradingView Watchlist (.txt) to automatically generate your Ultimate Screener indicator.")
            uploaded_wl = st.file_uploader("Upload Watchlist (.txt)", type=["txt"])
            if uploaded_wl is not None:
                raw_text = uploaded_wl.read().decode("utf-8")
                raw_syms = [s.strip() for s in raw_text.replace(',', '\n').split('\n') if s.strip()]
                # BUG-L6 / REC-9: Pine Screener hard cap is ~40 symbols per indicator
                _PINE_CAP = 40
                if len(raw_syms) > _PINE_CAP:
                    st.warning(
                        f"⚠️ **Pine Screener symbol cap:** TradingView Pine indicators support "
                        f"~{_PINE_CAP} symbols before hitting the execution time limit. "
                        f"You uploaded {len(raw_syms)} symbols — the generated script will include "
                        f"all of them but may show a 'Script execution timed out' error on TV. "
                        f"Consider splitting into two watchlists of ≤{_PINE_CAP} symbols each."
                    )
                pine_code = generate_pine_code(raw_syms)
                st.download_button(label="⬇️ Download Generated .pine", data=pine_code,
                                   file_name="Commander_Screener_Custom.pine", mime="text/plain")

    with _wl2:
        section("2. External Cloud Sync")
        c1, c2, c3 = st.columns(3, gap="small")
        with c1:
            if st.button("💸  Sync to Strike.Money\nPush watchlist to Strike.Money platform.\n→  Sync Now", use_container_width=True, key="wl_strike"):
                launch_script("strike_automation.py", "--mode watchlist")
        with c2:
            if st.button("📊  Sync to TradingView\nSync curated lists to TradingView.\n→  Sync Now", use_container_width=True, key="wl_tv"):
                launch_script("tradingview_automation_v2.py")
        with c3:
            if st.button("🔁  Master Sync — All\nPush to all connected platforms simultaneously.\n→  Sync All", type="primary", use_container_width=True, key="wl_master"):
                launch_script("master_portfolio_sync.py")
        section("3. Email Dispatches")
        c4, c5 = st.columns(2, gap="small")
        with c4:
            if st.button("📧  Send Test Email\nVerify SMTP Connection.\n→  Send Now", use_container_width=True, key="wl_em_test"):
                launch_script("gmail_dispatcher.py", "--mode test")
        with c5:
            if st.button("🏆  Email Golden Matches\nSend latest AI 5-Star picks to your inbox.\n→  Send Now", use_container_width=True, key="wl_em_match"):
                launch_script("gmail_dispatcher.py", "--mode matches")

    with _wl3:
        section("Smart Rank — Weinstein Setup Scorer")
        st.caption("Scores each stock 0–100 across Stage 2 status, RS vs CNX500, "
                   "52W position, volume surge and SMA200 slope. "
                   "Auto-loads symbols from watchlist CSVs in your project folder.")

        if not _RANKER_OK:
            st.error("❌ watchlist_ranker module not available.")
        else:
            # Symbol source
            _wr_auto = load_watchlist_symbols()
            _wr_src  = st.radio("Symbol source",
                                ["📂 Auto-load from watchlist CSVs",
                                 "✏️ Manual entry"],
                                horizontal=True, key="wr_src")

            if _wr_src == "📂 Auto-load from watchlist CSVs":
                if _wr_auto:
                    st.caption(f"Found **{len(_wr_auto)}** symbols in watchlist CSVs")
                    _wr_syms = _wr_auto
                else:
                    st.warning("No watchlist CSVs found. Run HUNTER scanners first, or switch to manual entry.")
                    _wr_syms = []
            else:
                _wr_raw = st.text_area("Enter symbols (one per line or comma-separated)",
                                       height=120, key="wr_manual",
                                       placeholder="RELIANCE\nINFY\nHDFCBANK\nTCS")
                _wr_syms = [s.strip() for s in
                            _wr_raw.replace(",", "\n").split("\n") if s.strip()]

            _wr_period = st.selectbox("Lookback period", ["3mo", "6mo", "1y"],
                                      index=1, key="wr_period")

            if _wr_syms and st.button("🏆 Rank Setups", key="wr_run",
                                       type="primary", use_container_width=True):
                with st.spinner(f"Scoring {len(_wr_syms)} stocks — fetching price data…"):
                    try:
                        _wr_df = rank_watchlist(_wr_syms, period=_wr_period)
                    except Exception as _wre:
                        _wr_df = pd.DataFrame()
                        st.error(f"Ranking failed: {_wre}")

                if not _wr_df.empty:
                    st.session_state["wr_last_df"] = _wr_df
                else:
                    st.warning("No results — check symbol names or network.")

            # Display cached result
            if st.session_state.get("wr_last_df") is not None:
                _wr_res = st.session_state["wr_last_df"]

                # Summary metrics
                _wr_s2  = int((_wr_res["Stage"].str.contains("Stage 2")).sum())
                _wr_top = int((_wr_res["Score"] >= 65).sum())
                _wr_c1, _wr_c2, _wr_c3, _wr_c4 = st.columns(4, gap="small")
                _wr_c1.metric("Stocks Ranked",  len(_wr_res))
                _wr_c2.metric("Stage 2",        _wr_s2)
                _wr_c3.metric("Grade A+ / A",   _wr_top)
                _wr_c4.metric("Top Score",
                              f"{_wr_res['Score'].iloc[0]:.1f}" if len(_wr_res) else "–")

                st.markdown("---")
                # Colour-coded table
                def _wr_colour(val):
                    if isinstance(val, str):
                        if "Stage 2" in val: return "color: #00f260"
                        if "Stage 4" in val: return "color: #ff4b4b"
                        if "A+" in val:      return "color: #00f260; font-weight:700"
                        if val == "⭐⭐ A":   return "color: #58a6ff"
                    return ""

                _wr_disp = _wr_res[["Symbol","Score","Grade","Stage","LTP",
                                     "RS_3M%","RS_Edge%","52W_Pos%","Vol_Surge"]].copy()
                # 10 May 2026: round numeric columns to 2 decimals so the table
                # reads cleanly (was showing values like 1.42857142857… for
                # Vol_Surge etc.).
                _wr_num_cols = ["Score", "LTP", "RS_3M%", "RS_Edge%",
                                 "52W_Pos%", "Vol_Surge"]
                _wr_styler = (_wr_disp.style
                              .applymap(_wr_colour, subset=["Grade","Stage"])
                              .format({c: "{:.2f}" for c in _wr_num_cols
                                        if c in _wr_disp.columns}))
                st.dataframe(
                    _wr_styler,
                    use_container_width=True, hide_index=True,
                )
                st.download_button(
                    "📥 Download Rankings (CSV)",
                    data=_wr_res.to_csv(index=False).encode("utf-8"),
                    file_name=f"WatchlistRank_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv", key="wr_dl",
                )

    # ── TAB 4 — SECTORS DB (unified Pine ↔ Python sector mapping) ────────
    with _wl4:
        section("Unified Sector Database")
        st.caption(
            "Single source of truth for stock→sector mappings, shared between "
            "the Pine Dashboard family and the Python pipeline. "
            "Curated entries come from `Weinstein and Swing Pro Dashboard v67`."
        )
        try:
            import sector_lookup as _sl
            _sl.refresh_cache()
            _sl_stats = _sl.stats()
        except Exception as _sle:
            _sl_stats = {}
            st.error(f"sector_lookup unavailable: {_sle}")

        if not _sl_stats.get("db_exists"):
            st.warning(
                "**sectors.db not found.** Run `python sector_manager.py` once "
                "in the project folder to build it from the v67 Pine block + "
                "legacy `sector_db.json`."
            )
        else:
            _sd_c1, _sd_c2, _sd_c3, _sd_c4 = st.columns(4, gap="small")
            _sd_c1.metric("Symbols",  _sl_stats.get("total_symbols", 0))
            _sd_c2.metric("Sectors",  _sl_stats.get("total_sectors", 0))
            _sd_c3.metric("Aliases",  _sl_stats.get("total_aliases", 0))
            _sd_c4.metric(
                "Last Update",
                str(_sl_stats.get("last_update", "—"))[:16] if _sl_stats.get("last_update") else "—",
            )

            _by_src = _sl_stats.get("by_source", {})
            if _by_src:
                st.markdown("**By source**")
                _src_rows = [{"source": s, "count": c} for s, c in
                             sorted(_by_src.items(), key=lambda x: -x[1])]
                st.dataframe(pd.DataFrame(_src_rows), hide_index=True,
                             use_container_width=False)

            st.markdown("---")
            section("Sector Index Coverage")
            try:
                _sec_df = _sl.list_sectors()
                if not _sec_df.empty:
                    _disp = _sec_df[["sector_index", "display_name", "yf_ticker",
                                      "fallback", "stock_count", "is_broad"]].copy()
                    st.dataframe(_disp, hide_index=True, use_container_width=True)
            except Exception as _sde:
                st.error(f"Sector list error: {_sde}")

            st.markdown("---")
            section("Lookup")
            _lu_c1, _lu_c2 = st.columns([2, 3], gap="small")
            with _lu_c1:
                _lu_sym = st.text_input(
                    "Symbol", placeholder="e.g. RELIANCE, NSE:TCS-EQ, M_M",
                    key="sd_lookup_sym",
                )
            with _lu_c2:
                if _lu_sym:
                    _rec = _sl.get_sector(_lu_sym)
                    if _rec:
                        st.success(
                            f"**{_rec['symbol']}** → **{_rec['sector_index']}** "
                            f"({_rec.get('display_name') or _rec['sector_name']})  ·  "
                            f"yf=`{_sl.sector_to_yf(_rec['sector_index'])}`  ·  "
                            f"source=`{_rec['source']}`  ·  "
                            f"confidence=`{_rec['confidence']}`"
                        )
                    else:
                        st.warning(
                            f"`{_lu_sym}` not in DB. Run `python sector_manager.py "
                            f"refresh-yf --symbols {_lu_sym}` to fetch from yfinance."
                        )

            st.markdown("---")
            section("Maintenance")
            _mt_c1, _mt_c2, _mt_c3 = st.columns(3, gap="small")
            with _mt_c1:
                if st.button(
                    "🔄  Re-import v67 Pine\nIngest the curated block.\n→  Run",
                    key="sd_imp_pine", use_container_width=True,
                ):
                    launch_script(
                        "sector_manager.py",
                        'import-pine "Weinstein and Swing Pro Dashboard v67.3.pine"',
                    )
            with _mt_c2:
                if st.button(
                    "🌐  Refresh from yfinance\nUpdate auto-sourced rows only.\n→  Run",
                    key="sd_ref_yf", use_container_width=True,
                ):
                    launch_script("sector_manager.py", "refresh-yf")
            with _mt_c3:
                if st.button(
                    "📊  Re-run Audit\nPrint DB statistics.\n→  Run",
                    key="sd_audit", use_container_width=True,
                ):
                    launch_script("sector_manager.py", "audit")

            st.caption(
                "Two-way sync: edit `sectors.db` (or re-import a newer Pine "
                "version) → run `python sector_manager.py export-pine "
                "<dashboard.pine>` to write the updated `<DB_LOOKUP_START>` "
                "block back into your Pine file."
            )

    # ── TAB 5 — DATA CACHE (C1.13: parquet-cached OHLCV health) ──────────
    with _wl5:
        section("Unified OHLCV Cache")
        st.caption(
            "All screeners, the breadth engine, the rotation guard and the "
            "sniper pre-flight route through `data_provider`. Each symbol's "
            "OHLCV is stored once on disk (parquet when available) with a "
            "TTL by interval — daily=1h, weekly=24h, intraday=15min."
        )
        try:
            import data_provider as _dp_admin
            _cs = _dp_admin.stats()
        except Exception as _ce:
            _cs = {}
            st.error(f"data_provider unavailable: {_ce}")

        if _cs:
            _dc1, _dc2, _dc3, _dc4 = st.columns(4, gap="small")
            _dc1.metric("Cache Entries", _cs.get("entry_count", 0))
            _dc2.metric("Fresh", _cs.get("fresh", 0))
            _dc3.metric("Expired", _cs.get("expired", 0),
                         delta=None if _cs.get("expired", 0) == 0 else "evict",
                         delta_color="off")
            _dc4.metric("Disk Size", f"{_cs.get('total_size_mb', 0):.2f} MB")

            _dc5, _dc6, _dc7, _dc8, _dc9 = st.columns(5, gap="small")
            _dc5.metric("Format", _cs.get("format", "—"))
            _dc6.metric("Parquet OK", "yes" if _cs.get("parquet_available") else "no")
            _dc7.metric(
                "NSE Fallback (nselib)",
                "active" if _cs.get("nselib_available") else "—",
                help="nselib kicks in when yfinance returns empty for a daily "
                     "NSE-equity request. Primary working secondary provider.",
            )
            _dc8.metric(
                "NSE Fallback (nsepython)",
                "active" if _cs.get("nsepython_available") else "—",
                help="nsepython is the tertiary provider — currently fails to "
                     "parse NSE's response shape (KeyError 'data') as of v2.97. "
                     "Kept in case it gets fixed upstream.",
            )
            _oldest = _cs.get("oldest_age_hours")
            _dc9.metric(
                "Oldest Entry",
                f"{_oldest:.1f}h" if _oldest is not None else "—",
            )

            st.caption(f"📁 `{_cs.get('cache_dir')}`")

            st.markdown("---")
            section("Maintenance")
            _mc1, _mc2, _mc3 = st.columns(3, gap="small")
            with _mc1:
                if st.button(
                    "🧹  Clear Expired\nRemove only TTL-expired entries.\n→  Run",
                    key="dc_clear_expired", use_container_width=True,
                ):
                    try:
                        n = _dp_admin.clear_expired()
                        st.success(f"Removed {n} expired cache files.")
                    except Exception as _ee:
                        st.error(f"Clear-expired failed: {_ee}")
            with _mc2:
                if st.button(
                    "💣  Clear All\nWipe the entire OHLCV cache.\n→  Run",
                    key="dc_clear_all", use_container_width=True,
                ):
                    try:
                        n = _dp_admin.clear_cache()
                        st.warning(f"Removed all {n} cache files. Next fetch is cold.")
                    except Exception as _ce2:
                        st.error(f"Clear-all failed: {_ce2}")
            with _mc3:
                if st.button(
                    "🔄  Refresh Stats\nRecount on-disk entries.\n→  Run",
                    key="dc_refresh", use_container_width=True,
                ):
                    st.rerun()

            st.caption(
                "Set `USE_DATA_PROVIDER = False` at the top of any consumer "
                "module (bull_screener, recovery_screener, exit_signal_engine, "
                "rotation_guard, breadth_engine, watchlist_ranker, ai_risk_manager, "
                "market_regime, market_data_hub) to fall back to direct yfinance "
                "calls if the cache misbehaves."
            )

    # ── TAB 6 — PIPELINE STATUS (E9) ──────────────────────────────────────
    with _wl6:
        section("Auto-Pilot Pipeline Status")
        st.caption(
            "Per-phase status from the most recent `run_pipeline.py` run. "
            "`run_pipeline.py` writes `pipeline_status.json` after every phase "
            "boundary, so this tab reflects live progress while a pipeline is "
            "running and the final outcome afterwards."
        )
        try:
            import pipeline_status as _ps
            _ps_state = _ps.load_status()
        except Exception as _pse:
            _ps_state = {}
            st.error(f"pipeline_status unavailable: {_pse}")

        if not _ps_state:
            st.info(
                "📋 No `pipeline_status.json` yet. Trigger the **Complete "
                "Workflow** button on the Dashboard to run the pipeline — "
                "this tab will populate as each phase completes."
            )
        else:
            _phases = _ps_state.get("phases", []) or []
            _started = _ps_state.get("started_at", "—")
            _ended   = _ps_state.get("ended_at")
            _current = _ps_state.get("current")
            _total_s = _ps.total_duration(_ps_state)

            # Top metrics row
            _ok   = sum(1 for p in _phases if p.get("status") == "OK")
            _fail = sum(1 for p in _phases if p.get("status") == "FAIL")
            _skip = sum(1 for p in _phases if p.get("status") == "SKIP")
            _run  = sum(1 for p in _phases if p.get("status") == "RUNNING")

            _ms1, _ms2, _ms3, _ms4, _ms5 = st.columns(5, gap="small")
            _ms1.metric("Phases OK",     _ok)
            _ms2.metric("Failed",        _fail,
                          delta=None if _fail == 0 else f"-{_fail}",
                          delta_color="inverse" if _fail else "normal")
            _ms3.metric("Skipped",       _skip)
            _ms4.metric("Running",       _run)
            _ms5.metric("Total Time",    f"{_total_s:.1f}s")

            if _current and not _ended:
                st.warning(f"🔄 **In progress** — current phase: `{_current}`")
            elif _ended:
                st.success(f"✅ Run completed at `{_ended[:19]}` "
                            f"(started `{_started[:19]}`)")

            # Per-phase grid
            if _phases:
                _rows = []
                for p in _phases:
                    _stat = p.get("status", "?")
                    _icon = ("✅" if _stat == "OK"
                               else "❌" if _stat == "FAIL"
                               else "⏭" if _stat == "SKIP"
                               else "🔄")
                    _dur = p.get("duration_s")
                    _rec = p.get("records")
                    _rows.append({
                        "":         _icon,
                        "Phase":    p.get("name", "?"),
                        "Status":   _stat,
                        "Duration": f"{_dur:.1f}s" if _dur is not None else "—",
                        "Records":  _rec if _rec is not None else "—",
                        "Last Run": (p.get("ended_at", "—") or "—")[11:19],
                        "Message":  (p.get("message", "") or "")[:80],
                    })
                _df_ps = pd.DataFrame(_rows)
                st.dataframe(_df_ps, hide_index=True, use_container_width=True)

                # Surface failures prominently
                _fails = [p for p in _phases if p.get("status") == "FAIL"]
                for fp in _fails:
                    st.error(
                        f"❌ **{fp.get('name')}** failed after "
                        f"{fp.get('duration_s', 0):.1f}s — {fp.get('message', '')}"
                    )

            with st.expander("Raw status payload"):
                st.json(_ps_state)

    # ── TAB 7 — REPLAY (E10) ───────────────────────────────────────────────
    with _wl7:
        section("Screener Replay — As-of-Date Backtest")
        st.caption(
            "Re-run a screener as of any historical date and grade the picks "
            "against their actual N-day forward returns. data_provider pins "
            "every OHLCV slice to that date so SMAs / RSI / Mansfield / VCP "
            "see exactly what they would have seen on the day."
        )

        try:
            import replay as _replay
        except Exception as _re:
            st.error(f"replay module unavailable: {_re}")
            _replay = None

        if _replay is not None:
            from datetime import date as _date_t, timedelta as _td_t
            _r_c1, _r_c2, _r_c3, _r_c4 = st.columns([2, 2, 2, 2], gap="small")
            with _r_c1:
                _r_date = st.date_input(
                    "As-of date",
                    value=_date_t.today() - _td_t(days=90),
                    max_value=_date_t.today() - _td_t(days=1),
                    key="rp_date",
                )
            with _r_c2:
                _r_screener = st.selectbox(
                    "Screener",
                    ["Bull (custom basket)", "Bull (default watchlist)", "Recovery"],
                    key="rp_screener",
                )
            with _r_c3:
                _r_forward = st.number_input(
                    "Forward (trading days)", min_value=5, max_value=120,
                    value=30, step=5, key="rp_forward",
                )
            with _r_c4:
                st.write("")  # spacer
                _r_go = st.button("⏪  Run Replay", type="primary",
                                    use_container_width=True, key="rp_go")

            _r_syms = None
            if _r_screener == "Bull (custom basket)":
                _r_basket = st.text_area(
                    "Custom basket (comma or newline separated, NSE symbols)",
                    value="HDFCBANK, TCS, RELIANCE, INFY, ITC, BHARTIARTL, LT, SBIN",
                    height=80, key="rp_basket",
                )
                _r_syms = [s.strip() for s in _r_basket.replace(",", "\n").split("\n")
                            if s.strip()]

            if _r_go:
                _as_of = str(_r_date)
                with st.spinner(f"Running replay @ {_as_of} …"):
                    try:
                        if _r_screener == "Recovery":
                            _r_result = _replay.run_recovery_replay(_as_of, int(_r_forward))
                        elif _r_screener == "Bull (default watchlist)":
                            _r_result = _replay.run_bull_replay(_as_of, int(_r_forward))
                        else:
                            _r_result = _replay.run_bull_replay(
                                _as_of, int(_r_forward), symbols=_r_syms,
                            )
                        st.session_state["rp_last"] = _r_result
                    except Exception as _re2:
                        st.error(f"Replay failed: {_re2}")

            _r_last = st.session_state.get("rp_last")
            if _r_last:
                _summary = _r_last.get("summary", {}) or {}
                _bench   = _r_last.get("benchmark_pct")
                _picks_df = _r_last.get("picks", pd.DataFrame())
                _perf_df  = _r_last.get("performance", pd.DataFrame())

                st.markdown("---")
                section(f"Result: {_r_last['as_of']} → +{_r_last['forward_days']} trading days")

                _m1, _m2, _m3, _m4, _m5 = st.columns(5, gap="small")
                _m1.metric("Picks", len(_picks_df))
                _m2.metric("Win rate", f"{_summary.get('win_rate_pct', 0):.1f}%"
                              if _summary.get("n_complete") else "—")
                _m3.metric("Avg return",
                              f"{_summary.get('avg_return_pct', 0):+.2f}%"
                              if _summary.get("n_complete") else "—")
                _m4.metric("Benchmark", f"{_bench:+.2f}%" if _bench is not None else "—")
                _alpha = _summary.get("alpha_vs_bench")
                _m5.metric(
                    "Alpha vs bench",
                    f"{_alpha:+.2f}%" if _alpha is not None else "—",
                    delta=None if _alpha is None
                          else (f"{_alpha:+.2f}%" if _alpha != 0 else None),
                    delta_color="normal" if _alpha is None or _alpha >= 0 else "inverse",
                )

                if not _perf_df.empty:
                    section("Forward Performance")
                    # Merge picks + performance for single combined view
                    _show_cols = ["Symbol", "Entry_Close", "Forward_Close",
                                   "Return_pct", "Forward_Date", "Status"]
                    _disp = _perf_df[[c for c in _show_cols if c in _perf_df.columns]].copy()
                    if not _picks_df.empty and "Symbol" in _picks_df.columns:
                        _join_cols = [c for c in ["Catalyst", "Score",
                                                    "VCP_Valid", "VCP_Score",
                                                    "Pivot_Price"]
                                        if c in _picks_df.columns]
                        if _join_cols:
                            _disp = _disp.merge(
                                _picks_df[["Symbol"] + _join_cols],
                                on="Symbol", how="left",
                            )
                    _disp = _disp.sort_values(
                        "Return_pct", ascending=False, na_position="last",
                    ).reset_index(drop=True)
                    st.dataframe(_disp, hide_index=True, use_container_width=True)

                    st.download_button(
                        "📥 Download Replay CSV",
                        data=_disp.to_csv(index=False).encode("utf-8"),
                        file_name=f"replay_{_r_last['as_of']}.csv",
                        mime="text/csv",
                        key="rp_dl",
                    )
                    st.caption(f"Saved to `{_r_last['out_csv']}`")

                with st.expander("Raw summary payload"):
                    st.json({k: v for k, v in _summary.items()})

            # ── 12-month validation (multi-anchor backtest) ──────────────────
            st.markdown("---")
            section("12-Month Validation Backtest")
            st.caption(
                "Runs the bull screener at monthly anchors over the last "
                "N months on a fixed Nifty 100 universe. Set filters to "
                "measure the screener's *selection* edge vs the universe's "
                "drift. Each anchor takes ~45s on a cold cache; subsequent "
                "runs are cache hits."
            )
            try:
                import validation as _val
            except Exception as _ve:
                _val = None
                st.error(f"validation module unavailable: {_ve}")

            if _val is not None:
                _v_c1, _v_c2, _v_c3, _v_c4 = st.columns(4, gap="small")
                with _v_c1:
                    _v_months = st.number_input(
                        "Months back", min_value=3, max_value=24,
                        value=12, step=3, key="val_months",
                    )
                with _v_c2:
                    _v_forward = st.number_input(
                        "Forward (TD)", min_value=5, max_value=120,
                        value=30, step=5, key="val_forward",
                    )
                with _v_c3:
                    _v_topn = st.number_input(
                        "Top-N filter (0=all)",
                        min_value=0, max_value=50, value=10, step=5,
                        key="val_topn",
                        help="Keep only the top-N picks by Score per anchor. "
                             "0 = no filter (baseline universe).",
                    )
                with _v_c4:
                    _v_cat = st.checkbox(
                        "Require catalyst",
                        value=False, key="val_cat",
                        help="Only count picks where Catalyst != 'None'.",
                    )

                _v_go = st.button(
                    f"⏱  Run validation ({int(_v_months)} anchors × Nifty 100, "
                    f"~{int(_v_months)*45}s)",
                    type="primary", use_container_width=False, key="val_go",
                )

                if _v_go:
                    _topn_arg = int(_v_topn) if int(_v_topn) > 0 else None
                    with st.spinner(f"Running {int(_v_months)}-anchor validation … "
                                     "this can take several minutes on cold cache."):
                        try:
                            _v_res = _val.run_validation(
                                months_back=int(_v_months),
                                forward_days=int(_v_forward),
                                basket=None,
                                min_score=0,
                                require_catalyst=bool(_v_cat),
                                top_n=_topn_arg,
                            )
                            st.session_state["val_last"] = _v_res
                            st.success(f"Completed in {_v_res['aggregate'].get('duration_s',0):.0f}s")
                        except Exception as _ve2:
                            st.error(f"Validation failed: {_ve2}")

                # Show last result (live or loaded from disk)
                _v_last = st.session_state.get("val_last")
                if _v_last is None:
                    try:
                        _v_last = _val.load_last_validation()
                    except Exception:
                        _v_last = None

                if _v_last:
                    _v_agg = _v_last.get("aggregate", {}) or {}
                    _v_sum = _v_last.get("summary_df", pd.DataFrame())

                    st.markdown(
                        f"**Run `{_v_last.get('run_id','—')}`**  ·  "
                        f"{_v_agg.get('n_anchors','?')} anchors · "
                        f"{_v_agg.get('n_picks_total','?')} picks total · "
                        f"forward {_v_agg.get('forward_days','?')}d"
                    )

                    _va1, _va2, _va3, _va4, _va5 = st.columns(5, gap="small")
                    _va1.metric("Anchor Avg Alpha",
                                  f"{_v_agg.get('anchor_avg_alpha_pct', 0):+.2f}%"
                                  if _v_agg.get('anchor_avg_alpha_pct') is not None
                                  else "—")
                    _va2.metric("Median Alpha",
                                  f"{_v_agg.get('anchor_median_alpha_pct', 0):+.2f}%"
                                  if _v_agg.get('anchor_median_alpha_pct') is not None
                                  else "—")
                    _va3.metric("Alpha Hit Rate",
                                  f"{_v_agg.get('alpha_hit_rate_pct', 0):.1f}%"
                                  if _v_agg.get('alpha_hit_rate_pct') is not None
                                  else "—")
                    _va4.metric("Avg Win Rate",
                                  f"{_v_agg.get('anchor_avg_winrate_pct', 0):.1f}%"
                                  if _v_agg.get('anchor_avg_winrate_pct') is not None
                                  else "—")
                    _va5.metric("Best / Worst Anchor",
                                  f"{_v_agg.get('best_anchor_alpha',0):+.1f}% / "
                                  f"{_v_agg.get('worst_anchor_alpha',0):+.1f}%"
                                  if _v_agg.get('best_anchor_alpha') is not None
                                  else "—")

                    if not _v_sum.empty:
                        _show_v = _v_sum[[
                            "as_of", "picks_filtered", "picks_with_data",
                            "win_rate_pct", "avg_return_pct",
                            "benchmark_pct", "alpha_pct",
                        ]].copy()
                        st.dataframe(_show_v, hide_index=True,
                                       use_container_width=True)

                        # Alpha-over-time bar chart
                        try:
                            import plotly.express as _px
                            _chart_df = _v_sum.dropna(subset=["alpha_pct"]).copy()
                            if not _chart_df.empty:
                                _chart_df["color"] = _chart_df["alpha_pct"].apply(
                                    lambda x: "#22c55e" if x >= 0 else "#ef4444"
                                )
                                _fig = _px.bar(
                                    _chart_df, x="as_of", y="alpha_pct",
                                    color="color", color_discrete_map="identity",
                                    title="Alpha vs Nifty 500 by anchor (positive = green)",
                                )
                                _fig.update_layout(showlegend=False, height=280,
                                                    paper_bgcolor="rgba(0,0,0,0)",
                                                    plot_bgcolor="rgba(0,0,10,0.4)",
                                                    font=dict(color="#c9d1d9"),
                                                    yaxis=dict(title="Alpha %",
                                                               gridcolor="#1e3a5f"),
                                                    xaxis=dict(gridcolor="#1e3a5f"))
                                _fig.add_hline(y=0, line_dash="dot",
                                                line_color="#5a8a9f")
                                st.plotly_chart(_fig, use_container_width=True)
                        except Exception:
                            pass

                        st.download_button(
                            "📥 Download Validation Summary (CSV)",
                            data=_v_sum.to_csv(index=False).encode("utf-8"),
                            file_name=f"validation_{_v_last['run_id']}.csv",
                            mime="text/csv", key="val_dl_sum",
                        )

                    with st.expander("Run config & aggregate (raw)"):
                        st.json(_v_agg)

    # ── TAB 8 — LIVE TRACK RECORD ──────────────────────────────────────────
    with _wl8:
        section("Live Pick Track Record")
        st.caption(
            "Every live screener run auto-logs its picks to `pick_log.db` "
            "(replay/validation runs are skipped). The evaluator computes "
            "the N-trading-day forward return for each pick once the window "
            "elapses — giving us a real-world track record that complements "
            "the 12-month replay backtest."
        )
        try:
            import pick_log as _pl_admin
            _pl_stats = _pl_admin.stats()
        except Exception as _ple:
            _pl_stats = {}
            st.error(f"pick_log unavailable: {_ple}")

        if not _pl_stats.get("db_exists") or _pl_stats.get("pick_count", 0) == 0:
            st.info(
                "📋 No live picks logged yet. As soon as you run the bull or "
                "recovery screener (HUNTER → Bull Screener tab, or via the "
                "auto-pilot pipeline), picks land here automatically."
            )
        else:
            _pl_c1, _pl_c2, _pl_c3, _pl_c4 = st.columns(4, gap="small")
            _pl_c1.metric("Total Picks Logged", _pl_stats.get("pick_count", 0))
            _pl_c2.metric("Evaluated",          _pl_stats.get("eval_count", 0))
            _pl_c3.metric("First Pick",         _pl_stats.get("first_pick") or "—")
            _pl_c4.metric("Last Pick",          _pl_stats.get("last_pick") or "—")

            _pl_btn_c1, _pl_btn_c2 = st.columns(2, gap="small")
            with _pl_btn_c1:
                _pl_fwd = st.number_input(
                    "Evaluation horizon (trading days)",
                    min_value=5, max_value=120, value=30, step=5,
                    key="pl_fwd",
                )
            with _pl_btn_c2:
                st.write("")
                if st.button(
                    "🔄  Evaluate pending picks "
                    "(fetch forward returns for picks ≥ horizon old)",
                    key="pl_eval", type="primary", use_container_width=True,
                ):
                    with st.spinner("Computing forward returns…"):
                        try:
                            _new = _pl_admin.evaluate_pending(int(_pl_fwd))
                            st.success(f"Wrote {_new} new evaluation(s).")
                            st.rerun()
                        except Exception as _eve:
                            st.error(f"Evaluation failed: {_eve}")

            st.markdown("---")
            section("Per-screener Summary")
            for _scr in (_pl_stats.get("screeners") or ["bull"]):
                try:
                    _sum = _pl_admin.summarize(_scr, forward_days=int(_pl_fwd))
                except Exception:
                    _sum = {"n": 0}
                if not _sum.get("n"):
                    st.caption(f"**{_scr}**: 0 evaluated picks at "
                                f"forward {int(_pl_fwd)}d (run evaluator above).")
                    continue
                _ss1, _ss2, _ss3, _ss4 = st.columns(4, gap="small")
                _ss1.metric(f"{_scr.title()} — Picks Evaluated", _sum["n"])
                _ss2.metric("Win Rate",      f"{_sum['win_rate_pct']:.1f}%")
                _ss3.metric("Avg Return",    f"{_sum['avg_return_pct']:+.2f}%")
                _ss4.metric("Median Return", f"{_sum['median_return_pct']:+.2f}%")
                st.caption(
                    f"  best: {_sum['best_pct']:+.2f}% ({_sum['best_symbol']})   "
                    f"worst: {_sum['worst_pct']:+.2f}% ({_sum['worst_symbol']})   "
                    f"window: {_sum['first_pick']} → {_sum['last_pick']}"
                )

            st.markdown("---")
            section("Recent Picks")
            try:
                _recent = _pl_admin.load_picks(limit=50)
            except Exception as _le:
                _recent = pd.DataFrame()
                st.error(f"load_picks failed: {_le}")
            if _recent.empty:
                st.caption("(no picks)")
            else:
                _show = _recent[["as_of_date", "screener", "symbol", "catalyst",
                                   "score", "entry_close", "forward_days",
                                   "forward_close", "return_pct"]].copy()
                _show.columns = ["Date", "Screener", "Symbol", "Catalyst",
                                  "Score", "Entry", "Fwd Days", "Fwd Close",
                                  "Return %"]
                st.dataframe(_show, hide_index=True, use_container_width=True)

                st.download_button(
                    "📥 Download Pick Log (CSV)",
                    data=_recent.to_csv(index=False).encode("utf-8"),
                    file_name="pick_log_export.csv",
                    mime="text/csv", key="pl_dl",
                )

# ════════════════════════════════════════════════════════════════════════════
#  COMMAND CENTER
# ════════════════════════════════════════════════════════════════════════════
elif page == 'COMMAND':
    st.markdown('<div class="page-title">⚡ Command Center</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Active trade management and execution protocols.</div>', unsafe_allow_html=True)
    _cm1, _cm2, _cm3 = st.tabs(["⚡ Active Ops", "📒 Ledger", "🔔 Price Alerts"])

    with _cm1:
        section("Active Operations")
        c1, c2, c3, c4, c5 = st.columns(5, gap="small")
        with c1:
            if st.button("🎯  Sniper Entry AI v2\nOrder execution with Institutional AI analysis.\n→  Launch", use_container_width=True, key="cmd_sniper"):
                launch_script("sniper_trigger.py")
        with c2:
            if st.button("🛡️  GTT Auto-Shield\nAuto-protect holdings using Journal levels.\n→  Launch", use_container_width=True, key="cmd_gtt"):
                launch_script("gtt_auto_shield.py")
        with c3:
            if st.button("📲  Telegram Sentinel\nActive market monitoring via Mobile.\n→  Launch", use_container_width=True, key="cmd_tg"):
                launch_script("telegram_sentinel.py")
        with c4:
            if st.button("🤖  Market Monitor Agent\nLive intraday scans and Telegram alerts.\n→  Launch", use_container_width=True, key="cmd_monitor"):
                launch_script("market_monitor_agent.py")
        with c5:
            if st.button("🔌  Dhan Webhook Gateway\nExpose port 8000 via ngrok for TV alerts.\n→  Launch", use_container_width=True, key="cmd_webhook"):
                launch_script("dhan_tv_webhook.py")

        # ── MISS-1: EXIT SIGNAL ENGINE ───────────────────────────────────────
        st.markdown("---")
        section("MISS-1 · Exit Signal Engine")
        st.caption(
            "Watchdog scanner for open positions. Flags SL-breach, target hit, "
            "stage decay (Stage 2 → 3/4), and RS fade (positive → negative) alerts."
        )
        _exit_csv = os.path.join(_APP_DIR, "Exit_Signals.csv")
        _ec1, _ec2 = st.columns([1, 3], gap="small")
        with _ec1:
            if st.button("🚨  Scan Exit Signals\nCheck all open positions for exit triggers.\n→  Scan Now",
                         use_container_width=True, key="cmd_exit_scan", type="primary"):
                launch_script("exit_signal_engine.py", "--silent")
        with _ec2:
            if os.path.exists(_exit_csv):
                try:
                    _df_exit = pd.read_csv(_exit_csv)
                    _action  = _df_exit[_df_exit.get("Exit_Flag", pd.Series()) == "ACTION"] if "Exit_Flag" in _df_exit.columns else pd.DataFrame()
                    if not _action.empty:
                        st.warning(f"⚠️ **{len(_action)} position(s) need attention** — last scan: "
                                   f"{pd.Timestamp(os.path.getmtime(_exit_csv), unit='s').strftime('%d %b %H:%M')}")
                        _exit_show = [c for c in ["Symbol","LTP","Weinstein_Stage","Mansfield_RS","StopLoss","Target","Exit_Reasons"] if c in _action.columns]
                        st.dataframe(_action[_exit_show], use_container_width=True, hide_index=True)
                    else:
                        st.success("✅ All positions clear — no exit signals.")
                except Exception:
                    st.info("Run Exit Scan to generate results.")

        # ── E-02: TRAILING STOP ENGINE ──────────────────────────────────────
        st.markdown("---")
        section("E-02 · Trailing Stop Engine")
        st.caption("Tracks ATR-based trailing stops vs highest-price-since-entry. SL > Entry = Locked Profit state.")

        df_active_cmd = df_active_global
        if not df_active_cmd.empty:
            trail_rows = []
            syms_cmd   = tuple(df_active_cmd['Symbol'].unique().tolist())
            live_prices_cmd = get_batch_ltps(syms_cmd)

            for _, row in df_active_cmd.iterrows():
                sym       = row['Symbol']
                bp        = float(row.get('BuyPrice', 0) or 0)
                qty       = float(row.get('Quantity', 0) or 0)
                curr_sl   = float(row.get('StopLoss', 0) or 0)
                entry_dt  = row.get('EntryDate', '')
                ltp       = live_prices_cmd.get(sym) or live_prices_cmd.get(clean_symbol(sym)) or bp
                atr_val   = get_atr(sym)
                atr_mult  = get_adaptive_atr_multiplier(sym)

                # Fetch high since entry for ATR-based trail
                high_since = ltp
                if entry_dt:
                    try:
                        start_d = pd.to_datetime(entry_dt).date()
                        import data_provider as dp
                        hist = dp.fetch_ohlcv(sym, start_date=str(start_d), interval="1d", auto_adjust=True, use_cache=True)
                        if hist is not None and not hist.empty:
                            h_col = hist['High']
                            high_since = float(h_col.max())
                    except Exception as e:
                        logger.warning(f"Trail high fetch {sym}: {e}")

                atr_trail_sl = high_since - (atr_mult * atr_val) if atr_val > 0 else curr_sl
                suggested_sl = max(atr_trail_sl, curr_sl)   # never trail backwards

                # Status — breach is always against Current SL (actual active stop),
                # NOT against suggested_sl (which is a recommendation only).
                if ltp < curr_sl:
                    status = "⚠️ SL BREACHED"
                elif suggested_sl > ltp:
                    # Price has fallen through where the ATR trail would have stopped you,
                    # but the actual SL was never moved up — warn user to update or exit.
                    status = f"📉 TRAIL LAPSED — update SL or exit"
                elif curr_sl > bp:
                    status = f"🔒 LOCKED (+₹{format_inr_int((curr_sl-bp)*qty)})"
                elif suggested_sl > curr_sl:
                    status = f"📈 TRAIL → ₹{format_inr(suggested_sl)}"
                else:
                    status = "✅ AT ENTRY SL"

                trail_rows.append({
                    'Symbol':       sym,
                    'Entry':        round(bp, 2),
                    'LTP':          round(ltp, 2),
                    'High Since Entry': round(high_since, 2),
                    'Current SL':   round(curr_sl, 2),
                    'ATR Trail SL': round(atr_trail_sl, 2),
                    'Suggested SL': round(suggested_sl, 2),
                    'ATR':          round(atr_val, 2),
                    'Status':       status
                })

            if trail_rows:
                df_trail = pd.DataFrame(trail_rows)
                st.dataframe(df_trail, use_container_width=True, hide_index=True, height=340)
                st.info("💡 Update 'Current SL' values in your Journal then re-run GTT Auto-Shield to push updated levels to Dhan.")
        else:
            st.info("No open positions found in journal.")

        st.markdown("---")
        # ── MISS-2: PORTFOLIO ROTATION GUARD UI ─────────────────────────────
        section("Portfolio Rotation Guard")
        st.caption("Grade all open positions on Weinstein structural alignment. "
                   "Surfaces deteriorating Stage 2 holdings before they become losers.")
        _rot_csv = os.path.join(_APP_DIR, "portfolio_rotation_output.csv")
        _pg1, _pg2 = st.columns([1, 3], gap="small")
        with _pg1:
            if st.button("🔄  Run Rotation Guard\nGrade all open positions.\n→  Scan Now",
                         use_container_width=True, key="cmd_rot_guard"):
                launch_script("portfolio_rotation_guard.py")
        with _pg2:
            if os.path.exists(_rot_csv):
                try:
                    _df_rot = pd.read_csv(_rot_csv)
                    if not _df_rot.empty:
                        _rot_show = [c for c in ["Symbol","Grade","Stage","Reason","Conviction"] if c in _df_rot.columns]
                        if not _rot_show:
                            _rot_show = list(_df_rot.columns[:6])
                        st.dataframe(_df_rot[_rot_show], use_container_width=True, hide_index=True)
                    else:
                        st.info("No rotation data. Run the guard first.")
                except Exception:
                    st.info("Run Rotation Guard to view portfolio grading.")

        st.markdown("---")
        section("GTT Orders — Live View")
        _gtt_c1, _gtt_c2 = st.columns([1, 5])
        with _gtt_c1:
            _gtt_refresh = st.button("🔄 Fetch GTTs", key="gtt_refresh", type="primary")
        with _gtt_c2:
            st.caption("Pulls active GTT orders from Dhan. Refreshes on click.")

        if _gtt_refresh or st.session_state.get("gtt_loaded"):
            with st.spinner("Fetching GTT orders from Dhan…"):
                try:
                    from dhan_auth import get_dhan_client as _gdc
                    _dhan_gtt  = _gdc()
                    # 10 May 2026 fix: Dhan SDK exposes GTTs under
                    # `get_forever()` (Dhan terminology = "Forever Orders").
                    # Previously called the non-existent `get_gtt_list()` →
                    # AttributeError → empty fallback → "No GTTs found"
                    # message even when many were pending.
                    _gtt_resp  = _dhan_gtt.get_forever()
                    if isinstance(_gtt_resp, dict) and _gtt_resp.get("status") == "success":
                        _gtt_data = _gtt_resp.get("data") or []
                    else:
                        _gtt_data = []
                        if isinstance(_gtt_resp, dict):
                            st.warning(f"Dhan returned non-success: "
                                        f"{_gtt_resp.get('remarks', _gtt_resp)}")
                    st.session_state["gtt_loaded"] = True
                    st.session_state["gtt_data"]   = _gtt_data
                except Exception as _gtte:
                    st.error(f"GTT fetch failed: {_gtte}")
                    _gtt_data = []

            _gtt_data = st.session_state.get("gtt_data", [])
            if _gtt_data:
                # Each row in `data` is a single leg of a Forever Order
                # (e.g. an OCO order produces 2 legs: STOP_LOSS_LEG + TARGET_LEG).
                _gtt_rows = []
                for _g in _gtt_data:
                    _ot = _g.get("orderType", "")  # SINGLE or OCO
                    _leg = _g.get("legName", "")   # STOP_LOSS_LEG / TARGET_LEG / ENTRY_LEG
                    _txn = _g.get("transactionType", "")  # BUY/SELL
                    # Type column: combine action + leg context for clarity
                    _type_label = f"{_txn} · {_ot}"
                    if _leg and _leg != "ENTRY_LEG":
                        _type_label += f" · {_leg.replace('_LEG','').replace('_',' ').title()}"
                    _gtt_rows.append({
                        "Symbol":     _g.get("tradingSymbol", ""),
                        "Type":       _type_label,
                        "Trigger ₹":  _g.get("triggerPrice", ""),
                        "Price ₹":    _g.get("price", ""),
                        "Qty":        _g.get("quantity", ""),
                        "Status":     _g.get("orderStatus", ""),
                        "Created":    str(_g.get("createTime", ""))[:10],
                        "Order ID":   _g.get("orderId", ""),
                    })
                _df_gtt = pd.DataFrame(_gtt_rows)
                # Sort: PENDING first, then by Symbol
                if "Status" in _df_gtt.columns:
                    _df_gtt["_sp"] = (_df_gtt["Status"] == "PENDING").map(
                        {True: 0, False: 1}
                    )
                    _df_gtt = _df_gtt.sort_values(["_sp", "Symbol"]).drop(columns=["_sp"])
                st.dataframe(_df_gtt, use_container_width=True, hide_index=True)
                _n_pending = int((_df_gtt["Status"] == "PENDING").sum()) \
                              if "Status" in _df_gtt.columns else len(_df_gtt)
                st.caption(f"{_n_pending} pending GTT(s) of {len(_df_gtt)} total | "
                           "To cancel, use the Dhan app or Journal GTT Shield.")
            else:
                st.info("No GTT orders returned by Dhan API. "
                        "If you have active GTTs in the Dhan app, check that "
                        "your access token isn't expired (sidebar → 🔑 Token detail).")

        st.markdown("---")
        section("External Apps")
        if st.button("📓  Open Full Journal App\nLaunch the complete trade journal interface.\n→  Open", use_container_width=True, key="cmd_journal"):
            launch_script("dhan_journal_v7.py", is_streamlit=True)

    with _cm2:
        col1, col2 = st.columns([0.7, 0.3])
        with col1:
            section("Live Trade Ledger")
        with col2:
            st.write("") # Spacer
            if st.button("🔄 Sync to TV", help="Sync Active Ledger to Pine Script Dashboard", use_container_width=True):
                with st.spinner("Syncing..."):
                    try:
                        import subprocess
                        subprocess.run([_PYTHON_EXE, "db_portfolio_sync.py"], capture_output=True, text=True, check=True)
                        st.success("✅ Synced! Copy code from `Weinstein and Swing Pro Dashboard v67.4.12.pine`")
                    except Exception as e:
                        st.error(f"❌ Sync failed: {e}")
                        
        df_j = load_journal_db()
        if not df_j.empty:
            show = [c for c in ["Symbol","Type","BuyPrice","Quantity","Status",
                                 "Sector","StopLoss","Target","PlannedRR","Timeframe"] if c in df_j.columns]
            st.dataframe(df_j[show], use_container_width=True, height=500, hide_index=True)
        else:
            st.info("No open trades found in the system.")

    with _cm3:
        # ── PRICE ALERTS ─────────────────────────────────────────────────────
        section("🔔 Price Alert Manager")
        st.caption(
            "Set threshold alerts for any ticker. "
            "The scheduler checks every 15 min during market hours (9:00–15:45 IST) "
            "and sends a Telegram notification when the condition fires."
        )
        try:
            from alert_engine import add_alert, remove_alert, toggle_alert, list_alerts, get_current_price
            _ae_ok = True
        except ImportError:
            _ae_ok = False
            st.error("alert_engine.py not found. Ensure it is in the same folder as this app.")

        if _ae_ok:
            # ── Add new alert ──────────────────────────────────────────────────
            with st.expander("➕ Add New Alert", expanded=True):
                _al_c1, _al_c2, _al_c3 = st.columns([2, 2, 2])
                with _al_c1:
                    _al_sym = st.text_input(
                        "Symbol", placeholder="INFY.NS / RELIANCE.NS / NIFTY=F",
                        key="alert_sym"
                    ).strip().upper()
                    if _al_sym and not any(c in _al_sym for c in [".", "=", "^"]):
                        _al_sym += ".NS"
                with _al_c2:
                    _al_cond = st.selectbox(
                        "Condition", ["above", "below", "crossing"], key="alert_cond"
                    )
                with _al_c3:
                    _al_price = st.number_input(
                        "Trigger Price ₹", min_value=0.01, step=1.0, format="%.2f",
                        key="alert_price"
                    )
                _al_note = st.text_input(
                    "Note (optional)", placeholder="e.g. Breakout level / SL hit",
                    key="alert_note"
                )
                _al_add_btn = st.button("✅ Add Alert", type="primary", key="add_alert_btn")
                if _al_add_btn:
                    if not _al_sym or _al_price <= 0:
                        st.warning("Enter a valid symbol and price.")
                    else:
                        _new_alert = add_alert(_al_sym, _al_cond, _al_price, _al_note)
                        st.success(
                            f"🔔 Alert added: **{_al_sym}** {_al_cond} ₹{_al_price:,.2f}"
                        )
                        st.rerun()

            st.markdown("---")

            # ── List existing alerts ──────────────────────────────────────────
            _all_alerts = list_alerts()
            _active_alerts = [a for a in _all_alerts if a.get("active")]
            _fired_alerts  = [a for a in _all_alerts if not a.get("active")]

            section(f"Active Alerts ({len(_active_alerts)})")
            if not _active_alerts:
                st.info("No active alerts. Add one above.")
            else:
                # Quick-check prices inline
                if st.button("⚡ Check Prices Now", key="check_alerts_btn"):
                    _cur_prices = {}
                    _prog = st.progress(0, text="Fetching prices…")
                    for _i, _al in enumerate(_active_alerts):
                        _cur_prices[_al["symbol"]] = get_current_price(_al["symbol"])
                        _prog.progress((_i + 1) / len(_active_alerts))
                    _prog.empty()
                    st.session_state["alert_prices"] = _cur_prices

                _cached_prices = st.session_state.get("alert_prices", {})

                for _al in _active_alerts:
                    _al_col1, _al_col2, _al_col3, _al_col4 = st.columns([3, 2, 2, 2])
                    _cur_p = _cached_prices.get(_al["symbol"])
                    _dist  = (
                        f"({((_cur_p / _al['price']) - 1) * 100:+.1f}% away)"
                        if _cur_p else ""
                    )
                    with _al_col1:
                        st.markdown(
                            f"**{_al['symbol']}** — {_al['condition']} ₹{_al['price']:,.2f}  "
                            f"<span style='color:#8b949e;font-size:0.8rem'>{_dist}</span>"
                            + (f"  *{_al['note']}*" if _al.get("note") else ""),
                            unsafe_allow_html=True
                        )
                        st.caption(f"Added {_al.get('created_at','')}")
                    with _al_col2:
                        if _cur_p:
                            _trig_color = "#00f260" if (
                                (_al["condition"] == "above"    and _cur_p >= _al["price"]) or
                                (_al["condition"] == "below"    and _cur_p <= _al["price"]) or
                                (_al["condition"] == "crossing" and abs(_cur_p - _al["price"]) / max(_al["price"], 1) < 0.003)
                            ) else "#8b949e"
                            st.markdown(
                                f'<div style="color:{_trig_color};font-size:0.9rem">₹{_cur_p:,.2f}</div>',
                                unsafe_allow_html=True
                            )
                    with _al_col3:
                        if st.button("🔕 Pause", key=f"pause_{_al['id'][:8]}"):
                            toggle_alert(_al["id"])
                            st.rerun()
                    with _al_col4:
                        if st.button("🗑️ Remove", key=f"del_{_al['id'][:8]}"):
                            remove_alert(_al["id"])
                            st.rerun()
                    st.markdown('<hr style="margin:4px 0;border-color:#1e3a5f">', unsafe_allow_html=True)

            # ── Fired history ─────────────────────────────────────────────────
            if _fired_alerts:
                st.markdown("---")
                section(f"Fired History ({len(_fired_alerts)})")
                _fh_rows = []
                for _al in reversed(_fired_alerts):
                    _fh_rows.append({
                        "Symbol":    _al["symbol"],
                        "Condition": f"{_al['condition']} ₹{_al['price']:,.2f}",
                        "Note":      _al.get("note", ""),
                        "Fired At":  _al.get("fired_at", ""),
                        "Added":     _al.get("created_at", ""),
                    })
                st.dataframe(pd.DataFrame(_fh_rows), use_container_width=True, hide_index=True)
                if st.button("🧹 Clear Fired History", key="clear_fired"):
                    from alert_engine import _load as _ae_load, _save as _ae_save
                    _ae_save([a for a in _ae_load() if a.get("active")])
                    st.rerun()

# ════════════════════════════════════════════════════════════════════════════
#  AI LAB
# ════════════════════════════════════════════════════════════════════════════
elif page == 'AI LAB':
    st.markdown('<div class="page-title">🧠 AI Laboratory</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Advanced Generative AI workflows and automation.</div>', unsafe_allow_html=True)
    _ai1, _ai2, _ai3, _ai4 = st.tabs(["🛫 Pre-Flight", "🤖 Generative", "⚙️ Workflows", "📆 Weekly Report"])

    with _ai1:
        section("AI-Trade Proposer — Pre-flight Check")
        p1, p2, p3 = st.columns([2,1,1], gap="small")
        with p1: prop_sym   = st.text_input("Ticker Symbol", key="prop_sym", placeholder="e.g. RELIANCE").upper()
        with p2: prop_entry = st.number_input("Entry Price", min_value=0.0, step=0.1, key="prop_entry")
        with p3: prop_risk  = st.number_input("Risk ₹", value=5000, step=500, key="prop_risk")

        if st.button("🛫  Run Analysis\nScore and size a new trade before execution.\n→  Analyse Now", type="primary", use_container_width=True, key="btn_analysis"):
            if not prop_sym:
                st.error("Enter ticker.")
            else:
                with st.spinner(f"Analyzing {prop_sym}..."):
                    try:
                        ticker_yf = yf_symbol(prop_sym)   # BUG-15: centralised mapper
                        hist = yf.Ticker(ticker_yf).history(period="1mo")
                        ltp_val = float(hist['Close'].iloc[-1]) if not hist.empty else prop_entry

                        prop_sector  = get_sector(prop_sym)   # BUG-15: top-level import
                        rating_res   = get_weinstein_score(symbol=prop_sym, sector=prop_sector,
                                                           ltp=ltp_val, buy_price=prop_entry)
                        atr_val      = get_atr(prop_sym)
                        atr_mult     = get_adaptive_atr_multiplier(prop_sym)
                        suggested_sl = prop_entry - (atr_mult * atr_val) if atr_val > 0 else 0

                        # BUG-09 FIX: for a NEW trade proposal, SL must be < entry
                        # (Trailing SL > entry is only valid for existing trades)
                        if suggested_sl >= prop_entry and prop_entry > 0:
                            suggested_sl = prop_entry * 0.95
                            st.warning("⚠️ ATR-SL would exceed entry — capped at 5% below entry as fallback.")
                        elif suggested_sl <= 0:
                            suggested_sl = prop_entry * 0.95
                            st.warning("⚠️ ATR-SL computed as zero — capped at 5% below entry as fallback.")

                        risk_per_share = prop_entry - suggested_sl
                        # FORM-03 FIX: risk % is of total_cap, not just available cash
                        qty = int(prop_risk / risk_per_share) if risk_per_share > 0 else 0

                        r1, r2, r3, r4 = st.columns(4)
                        r1.metric("Weinstein Grade", rating_res.get('rating', 'N/A'))
                        r2.metric("Quant Score",     f"{rating_res.get('quant_score', 0)}/100")
                        r3.metric("Suggested SL",    f"₹{format_inr(suggested_sl)}")
                        r4.metric("Rec. Quantity",   f"{qty} shares")
                        st.info(f"AI Rationale: {rating_res.get('reason','N/A')}")

                        breakdown = rating_res.get('breakdown', {})
                        if breakdown:
                            with st.expander("📊 Quant Scorecard Breakdown", expanded=True):
                                for factor, detail in breakdown.items():
                                    st.caption(f"**{factor}:** {detail}")

                        # MISS-8: store pre-flight results in session for atomic GTT workflow
                        st.session_state["preflight_sym"]  = prop_sym
                        st.session_state["preflight_entry"] = prop_entry
                        st.session_state["preflight_sl"]    = round(suggested_sl, 2)
                        st.session_state["preflight_qty"]   = qty
                    except Exception as e:
                        st.error(f"Analysis error: {e}")

        # MISS-8: Atomic Entry + GTT-SL workflow ─────────────────────────────
        if st.session_state.get("preflight_sym"):
            st.markdown("---")
            section("MISS-8 · Atomic Entry + GTT Stop-Loss")
            st.caption(
                "Once you are satisfied with the Pre-Flight analysis, use the buttons below "
                "to place the entry order AND set up the GTT stop-loss in one workflow. "
                "**Review all values before submitting.**"
            )
            _pf_sym   = st.session_state.get("preflight_sym", "")
            _pf_entry = st.session_state.get("preflight_entry", 0.0)
            _pf_sl    = st.session_state.get("preflight_sl", 0.0)
            _pf_qty   = st.session_state.get("preflight_qty", 0)

            _af1, _af2, _af3, _af4 = st.columns(4, gap="small")
            _af1.metric("Symbol",  _pf_sym)
            _af2.metric("Entry",   f"₹{format_inr(_pf_entry)}")
            _af3.metric("SL",      f"₹{format_inr(_pf_sl)}")
            _af4.metric("Qty",     str(_pf_qty))

            _at1, _at2 = st.columns(2, gap="small")
            with _at1:
                if st.button(
                    f"🎯  Place Entry Order — {_pf_sym}\n"
                    f"Buy {_pf_qty} shares at ₹{_pf_entry:.2f}\n→  Confirm & Place",
                    use_container_width=True, key="preflight_entry_btn", type="primary"
                ):
                    # Route to the SNIPER tab in the web interface
                    st.info(
                        f"ℹ️ Navigate to **AI LAB → Sniper Entry** tab to place order for "
                        f"{_pf_sym}. Values pre-populated: Entry={_pf_entry}, "
                        f"Qty={_pf_qty}, SL={_pf_sl}"
                    )
            with _at2:
                if st.button(
                    f"🛡️  Set GTT Stop-Loss — {_pf_sym}\n"
                    f"GTT trigger at ₹{_pf_sl:.2f}\n→  Launch GTT Shield",
                    use_container_width=True, key="preflight_gtt_btn"
                ):
                    launch_script("gtt_auto_shield.py",
                                  f"--symbol {_pf_sym} --sl {_pf_sl} --qty {_pf_qty}")

    with _ai2:
        _g1, _g2 = st.tabs(["📈 Stock Analysis", "🔬 Portfolio Review"])

        # ── Stock Analysis ────────────────────────────────────────────────────
        with _g1:
            section("Gemini AI Stock Analysis")
            _ga_c1, _ga_c2, _ga_c3 = st.columns([2, 1, 1], gap="small")
            with _ga_c1:
                _ga_sym = st.text_input("NSE Symbol", placeholder="e.g. RELIANCE, INFY",
                                        key="ga_sym").strip().upper()
            with _ga_c2:
                _ga_depth = st.selectbox("Report depth", ["Quick (100w)", "Full (250w)", "Trade Setup"],
                                         key="ga_depth")
            with _ga_c3:
                _ga_entry = st.number_input("Entry price (optional)", min_value=0.0, step=0.5,
                                            key="ga_entry", help="Leave 0 to skip trade setup calc")

            if st.button("🤖 Generate AI Analysis", key="ga_run", type="primary",
                         use_container_width=True):
                if not _ga_sym:
                    st.warning("Enter a symbol first.")
                elif not _GEMINI_OK:
                    st.error("❌ Gemini reporter module not available.")
                else:
                    with st.spinner(f"Collecting data for {_ga_sym} and generating analysis…"):
                        try:
                            _ga_yf_sym = _ga_sym if _ga_sym.endswith(".NS") else _ga_sym + ".NS"
                            _ga_tk = yf.Ticker(_ga_yf_sym)
                            _ga_hist = _ga_tk.history(period="6mo")
                            _ga_info = _ga_tk.info

                            # Technical levels
                            _ga_close = _ga_hist["Close"].dropna()
                            _ga_ltp   = float(_ga_close.iloc[-1]) if not _ga_close.empty else 0.0
                            _ga_data  = {
                                "symbol":     _ga_sym,
                                "ltp":        round(_ga_ltp, 2),
                                "entry_price": _ga_entry if _ga_entry > 0 else None,
                                "week_52_high": round(float(_ga_close.tail(252).max()), 2) if len(_ga_close) >= 20 else None,
                                "week_52_low":  round(float(_ga_close.tail(252).min()), 2) if len(_ga_close) >= 20 else None,
                                "sma_20":  round(float(_ga_close.rolling(20).mean().iloc[-1]), 2) if len(_ga_close) >= 20 else None,
                                "sma_50":  round(float(_ga_close.rolling(50).mean().iloc[-1]), 2) if len(_ga_close) >= 50 else None,
                                "sma_200": round(float(_ga_close.rolling(200).mean().iloc[-1]), 2) if len(_ga_close) >= 200 else None,
                                "above_sma50":  _ga_ltp > float(_ga_close.rolling(50).mean().iloc[-1]) if len(_ga_close) >= 50 else None,
                                "above_sma200": _ga_ltp > float(_ga_close.rolling(200).mean().iloc[-1]) if len(_ga_close) >= 200 else None,
                                # Fundamentals from yfinance
                                "sector":       _ga_info.get("sector", ""),
                                "industry":     _ga_info.get("industry", ""),
                                "market_cap_cr": round(_ga_info.get("marketCap", 0) / 1e7, 0) if _ga_info.get("marketCap") else None,
                                "pe_ratio":     _ga_info.get("trailingPE"),
                                "pb_ratio":     _ga_info.get("priceToBook"),
                                "roe_pct":      round(_ga_info.get("returnOnEquity", 0) * 100, 1) if _ga_info.get("returnOnEquity") else None,
                                "debt_equity":  _ga_info.get("debtToEquity"),
                                "revenue_growth": round(_ga_info.get("revenueGrowth", 0) * 100, 1) if _ga_info.get("revenueGrowth") else None,
                                "earnings_growth": round(_ga_info.get("earningsGrowth", 0) * 100, 1) if _ga_info.get("earningsGrowth") else None,
                                "analyst_target": _ga_info.get("targetMeanPrice"),
                                "recommendation": _ga_info.get("recommendationKey", ""),
                                # Market context
                                "breadth_regime": st.session_state.get("cached_breadth_regime", "unknown"),
                            }

                            # Recent news headlines (top 3)
                            if _NEWS_OK:
                                try:
                                    _ga_news_df = fetch_all_news(max_per_feed=5, hours_back=48)
                                    _ga_news_df = add_sentiment(_ga_news_df)
                                    _ga_sym_news = filter_by_symbol(_ga_news_df, _ga_sym)
                                    if not _ga_sym_news.empty:
                                        _ga_data["recent_news"] = _ga_sym_news[["title","sentiment"]].head(3).to_dict(orient="records")
                                except Exception:
                                    pass

                            # Adjust prompt depth
                            _depth_map = {
                                "Quick (100w)": 100, "Full (250w)": 250, "Trade Setup": 250
                            }
                            _word_limit = _depth_map.get(_ga_depth, 250)
                            if _ga_depth == "Trade Setup" and _ga_entry > 0:
                                _ga_data["analysis_focus"] = "trade_setup"
                                _ga_data["risk_reward_required"] = True

                            _ga_report = generate_stock_analysis(_ga_sym, _ga_data)
                            st.session_state["ga_last_report"] = _ga_report
                            st.session_state["ga_last_sym"]    = _ga_sym
                        except Exception as _ga_e:
                            st.error(f"Analysis failed: {_ga_e}")

            # ── Display last report ──────────────────────────────────────────
            if st.session_state.get("ga_last_report"):
                _ga_disp_sym = st.session_state.get("ga_last_sym", "")
                st.markdown("---")
                _ltp_disp = ""
                try:
                    # C1 sweep: cached latest_close
                    try:
                        import data_provider as _dp_ga
                        _ltp_v = _dp_ga.latest_close(_ga_disp_sym)
                    except Exception:
                        _ltp_v = float(yf.Ticker(_ga_disp_sym+'.NS' if not _ga_disp_sym.endswith('.NS') else _ga_disp_sym).fast_info.get('lastPrice', 0))
                    _ltp_disp = f" — ₹{_ltp_v:,.2f}"
                except Exception:
                    pass
                section(f"AI Analysis: {_ga_disp_sym}{_ltp_disp}")
                _render_ai_report(st.session_state["ga_last_report"], header_color="#58a6ff")

                # Download button
                st.download_button(
                    "📥 Download Report (.txt)",
                    data=st.session_state["ga_last_report"],
                    file_name=f"AI_Analysis_{_ga_disp_sym}_{datetime.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain", key="ga_dl",
                )

        # ── Portfolio Review ──────────────────────────────────────────────────
        with _g2:
            section("AI Portfolio Review — Closed Trades")
            if not _GEMINI_OK:
                st.error("❌ Gemini module unavailable.")
            else:
                _pr_df = load_closed_trades_db()
                if _pr_df is None or _pr_df.empty:
                    st.info("No closed trades found. Complete trades via the Journal to unlock AI review.")
                else:
                    for _c in ["ExitPrice","BuyPrice","Quantity"]:
                        _pr_df[_c] = pd.to_numeric(_pr_df.get(_c,0), errors="coerce").fillna(0)
                    _pr_df["PnL"] = (_pr_df["ExitPrice"] - _pr_df["BuyPrice"]) * _pr_df["Quantity"]
                    _pr_analytics = compute_portfolio_analytics(_pr_df, total_cap)
                    st.caption(f"{len(_pr_df)} closed trades loaded  |  "
                               f"Win rate {_pr_analytics.get('win_rate',0)}%  |  "
                               f"Profit Factor {_pr_analytics.get('profit_factor',0)}")
                    if st.button("🔬 Generate AI Portfolio Review", key="pr_run", type="primary",
                                 use_container_width=True):
                        with st.spinner("Generating Gemini portfolio review…"):
                            try:
                                _pr_report = generate_portfolio_review(_pr_df, _pr_analytics)
                                st.session_state["pr_last_report"] = _pr_report
                            except Exception as _pre:
                                st.error(f"Review failed: {_pre}")

                    if st.session_state.get("pr_last_report"):
                        st.markdown("---")
                        _render_ai_report(st.session_state["pr_last_report"], header_color="#e3b341")
                        st.download_button(
                            "📥 Download Review (.txt)",
                            data=st.session_state["pr_last_report"],
                            file_name=f"Portfolio_Review_{datetime.now().strftime('%Y%m%d')}.txt",
                            mime="text/plain", key="pr_dl",
                        )

        # ── Cache management ─────────────────────────────────────────────────
        st.markdown("---")
        _cache_col1, _cache_col2 = st.columns(2, gap="small")
        with _cache_col1:
            if st.button("🗑️ Clear AI Cache", use_container_width=True, key="ai_cache"):
                _ai_cache_path = os.path.join(_APP_DIR, "ai_cache.json")
                if os.path.exists(_ai_cache_path):
                    os.remove(_ai_cache_path); st.success("AI Cache Cleared!")
                else:
                    st.info("Cache already empty.")
        with _cache_col2:
            if st.button("🗑️ Clear News Cache", use_container_width=True, key="ai_news_cache"):
                _nc = os.path.join(_APP_DIR, "reports", "news_cache.json")
                if os.path.exists(_nc):
                    os.remove(_nc); st.success("News Cache Cleared!")
                else:
                    st.info("News cache already empty.")

    with _ai3:
        section("Workflow Automation — Inline Pipeline")
        if st.button("🤖  Run Full Auto-Pilot\nExecute full pipeline: Scanners → Fundamentals → Golden Matching → Watchlist Sync.\n→  Initiate", type="primary", use_container_width=True, key="wf_run"):
            import time as _time
            import subprocess as _sp
            _script_dir = os.path.dirname(os.path.abspath(__file__))
            phases = [
                ("Phase 1/8: Technical Scanners — Stage 2 + Recovery (Chartink)", "chartink_scanner_pro", "run_scan"),
                ("Phase 2/8: Fetching Fundamental Data",      "screener_fetcher",     "fetch_screener_data"),
                ("Phase 3/8: Processing HTML to CSV",         "screener_processor",   "process_screener_pages"),
                ("Phase 4/8: Golden Matcher",                  "brute_force_match_pro","perform_match"),
                ("Phase 5/8: Recovery Screener (Python)",      "recovery_screener",    "main"),
                ("Phase 6/8: Generating Watchlists",           "watchlist_manager",    "generate_tradingview_files"),
                ("Phase 7/8: Syncing to Strike.Money",         "_subprocess",          "strike_automation.py --mode=watchlist"),
                ("Phase 8/8: Syncing to TradingView",          "_subprocess",          "tradingview_automation_v2.py --pipeline"),
            ]
            progress_bar = st.progress(0, text="Initializing Auto-Pilot...")
            results_log  = []
            for i, (label, module_name, func_name) in enumerate(phases):
                progress_bar.progress(i / len(phases), text=f"⏳ {label}")
                try:
                    if module_name == "_subprocess":
                        # Run platform-sync scripts the same way run_pipeline.py does
                        parts = func_name.split()
                        _sp.run([_PYTHON_EXE, parts[0]] + parts[1:],
                                check=True, cwd=_script_dir, timeout=180)
                    else:
                        # BUG-M4: importlib.reload() can silently execute stale byte-code.
                        # Use sys.modules eviction so re-import always reads .py from disk.
                        if module_name in sys.modules:
                            del sys.modules[module_name]
                        importlib.invalidate_caches()
                        mod = importlib.import_module(module_name)
                        fn = getattr(mod, func_name)
                        if module_name == "chartink_scanner_pro":
                            for scan_key in ['1','2','3','4','5','6','7']:
                                fn(scan_key); _time.sleep(0.5)
                        elif module_name == "screener_fetcher":  fn(interactive=False)
                        elif module_name == "brute_force_match_pro": fn(return_raw=True)
                        elif module_name == "watchlist_manager": fn(silent=True)
                        elif module_name == "recovery_screener":
                            fn()   # BUG-C2: recovery_screener.main() no longer calls os.chdir()
                        else: fn()
                    results_log.append(f"✅ {label}")
                except Exception as e:
                    results_log.append(f"❌ {label}: {e}")
                progress_bar.progress((i+1) / len(phases), text=f"✅ {label}")
            progress_bar.progress(1.0, text="✅ Pipeline Complete!")
            st.success("🏁 Full Auto-Pilot Complete!")
            # REC-6: wrap verbose phase logs in expander so the page stays clean
            with st.expander("📋 Phase-by-Phase Log", expanded=False):
                for log in results_log:
                    st.caption(log)

        st.markdown("---")
        section("Sniper Entry — Web Interface")
        sub_label("🎯  Advanced Position Size Calculator & Order Entry")

        if "prev_sniper_sym" not in st.session_state:
            st.session_state.prev_sniper_sym = ""

        s1, s2 = st.columns([2, 2], gap="small")
        with s1:
            sniper_sym_input = st.text_input("Stock Symbol", placeholder="e.g. CHOLAFIN").upper().strip()

        if sniper_sym_input != st.session_state.prev_sniper_sym and sniper_sym_input:
            st.session_state.prev_sniper_sym = sniper_sym_input
            try:
                atr_val = get_atr(sniper_sym_input)
                # C1 sweep: cached latest_close (5-day window)
                try:
                    import data_provider as _dp_sn
                    ltp = _dp_sn.latest_close(sniper_sym_input)
                except Exception:
                    info    = yf.Ticker(yf_symbol(sniper_sym_input)).fast_info
                    ltp     = info.get("lastPrice", 0.0)
                if ltp > 0:
                    st.session_state.sniper_entry = round(ltp, 2)
                    st.session_state.sniper_sl    = round(ltp - (2.0 * atr_val), 2)
                else:
                    st.session_state.sniper_entry = 0.0
                    st.session_state.sniper_sl    = 0.0
            except Exception: pass

        c1, c2, c3 = st.columns([1,1,1], gap="small")
        with c1: sniper_entry = st.number_input("Entry Price ₹", min_value=0.0, step=0.1, key="sniper_entry")
        with c2: sniper_sl    = st.number_input("Stop Loss ₹",   min_value=0.0, step=0.1, key="sniper_sl")
        with c3: risk_pct     = st.slider("Max Risk %", min_value=0.25, max_value=2.0, value=1.0, step=0.25, key="sniper_risk_pct")

        if sniper_sym_input and sniper_entry > 0 and sniper_sl > 0 and sniper_entry > sniper_sl:
            risk_per_share = sniper_entry - sniper_sl
            risk_pct_of_entry = (risk_per_share / sniper_entry) * 100
            # FORM-03 + BUG-04 FIX: use total_cap (full portfolio equity) for all sizing
            max_risk_rupees  = total_cap * (risk_pct / 100.0)
            sniper_qty       = math.floor(max_risk_rupees / risk_per_share) if risk_per_share > 0 else 0

            # BUG-04 FIX: 20% cap on total_cap (not just available cash)
            max_cap_allowed = total_cap * 0.20
            capped_reason   = ""
            if sniper_qty * sniper_entry > max_cap_allowed:
                sniper_qty    = math.floor(max_cap_allowed / sniper_entry)
                capped_reason = f"Capped at 20% of Total Capital: ₹{format_inr_int(max_cap_allowed)}"

            trade_value = sniper_qty * sniper_entry
            target_2r   = sniper_entry + (risk_per_share * 2)
            target_3r   = sniper_entry + (risk_per_share * 3)

            if capped_reason: st.info(f"💡 **Position Adjusted**: {capped_reason}")

            q1,q2,q3,q4 = st.columns(4)
            q1.metric("Quantity",    f"{sniper_qty} shares")
            q2.metric("Trade Value", f"₹{format_inr_int(trade_value)}")
            q3.metric("Risk/Trade",  f"₹{format_inr_int(max_risk_rupees)}")
            q4.metric("Risk %",      f"{risk_pct_of_entry:.1f}%")
            t1,t2 = st.columns(2)
            t1.metric("Target 2R", f"₹{format_inr(target_2r)}")
            t2.metric("Target 3R", f"₹{format_inr(target_3r)}")

            if st.button("🚀  Execute CNC Order via Dhan", type="primary", use_container_width=True, key="sniper_exec"):
                try:
                    from dhan_symbols import get_nse_id_map
                    id_map = get_nse_id_map()
                    sec_id = id_map.get(sniper_sym_input)
                    if not sec_id:
                        st.error(f"❌ Symbol '{sniper_sym_input}' not found in NSE master.")
                    else:
                        dhan_exec, _ = get_dhanhq_client()
                        if not dhan_exec:
                            st.error("❌ Dhan Auth Failed")
                            st.stop()
                        now        = datetime.now()
                        mkt_open   = now.replace(hour=9,  minute=15, second=0, microsecond=0)
                        mkt_close  = now.replace(hour=15, minute=30, second=0, microsecond=0)
                        # REC-7: Indian market holiday awareness
                        # NSE public holidays 2026 (update annually or fetch from API)
                        _NSE_HOLIDAYS_2026 = {
                            (2026, 1, 26),  # Republic Day
                            (2026, 3, 25),  # Holi
                            (2026, 4, 14),  # Dr. Ambedkar Jayanti / Ram Navami
                            (2026, 4, 17),  # Good Friday
                            (2026, 5, 1),   # Maharashtra Day
                            (2026, 8, 15),  # Independence Day
                            (2026, 10, 2),  # Gandhi Jayanti
                            (2026, 11, 14), # Diwali Laxmi Pujan (check BSE circular)
                            (2026, 12, 25), # Christmas
                        }
                        _today_tuple = (now.year, now.month, now.day)
                        _is_holiday  = _today_tuple in _NSE_HOLIDAYS_2026
                        is_amo = not (mkt_open <= now <= mkt_close and now.weekday() < 5 and not _is_holiday)
                        if _is_holiday:
                            st.info(f"ℹ️ Today is an NSE market holiday — order will be placed as AMO.")
                        order = dhan_exec.place_order(
                            security_id=sec_id, exchange_segment=dhan_exec.NSE,
                            transaction_type=dhan_exec.BUY, quantity=sniper_qty,
                            order_type=dhan_exec.LIMIT, product_type=dhan_exec.CNC,
                            price=sniper_entry, after_market_order=is_amo,
                            trading_symbol=sniper_sym_input
                        )
                        if order.get('status') == 'success':
                            st.success(f"✅ Order Placed! ID: {order['data']['orderId']}")
                            st.toast(f"🎯 {sniper_sym_input} order placed successfully!")
                        else:
                            st.error(f"❌ Order Failed: {order.get('remarks','Unknown error')}")
                except Exception as e:
                    st.error(f"❌ Execution Error: {e}")
        elif sniper_sym_input and sniper_entry > 0 and sniper_sl > 0:
            st.warning("⚠️ Entry Price must be higher than Stop Loss for a new Long trade.")

    with _ai4:
        # ── WEEKLY REPORT ─────────────────────────────────────────────────────
        section("📆 Weekly Market Report")
        st.caption(
            "Comprehensive Sunday evening market letter — 500-600 words covering "
            "index moves, breadth, sector rotation, FII/DII flows, and setups for next week. "
            "The scheduler auto-generates and Telegrams this report every Sunday at 7:00 PM IST. "
            "Use the button below to generate on demand at any time."
        )

        # ── Generate on demand ────────────────────────────────────────────────
        _wr_gen_col1, _wr_gen_col2 = st.columns([2, 1])
        with _wr_gen_col1:
            st.markdown(
                "**Generate a fresh report** using live data — fetches market snapshot, "
                "breadth metrics, FII/DII flows, and sector data, then calls Gemini AI."
            )
        with _wr_gen_col2:
            _wr_generate = st.button(
                "🤖 Generate Weekly Report", type="primary",
                key="gen_weekly_report", use_container_width=True
            )

        st.markdown("---")

        # ── Show cached report if available ──────────────────────────────────
        _wr_dir  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
        _wr_file = os.path.join(_wr_dir, "weekly_report.txt")
        _wr_json = os.path.join(_wr_dir, "weekly_report.json")

        _wr_cached_text = None
        _wr_cached_meta = {}
        if os.path.exists(_wr_file):
            try:
                _wr_cached_text = open(_wr_file, encoding="utf-8").read()
            except Exception:
                pass
        if os.path.exists(_wr_json):
            try:
                _wr_cached_meta = json.loads(open(_wr_json, encoding="utf-8").read())
            except Exception:
                pass

        if _wr_cached_text:
            _wr_age = ""
            _wr_ts  = _wr_cached_meta.get("generated_at", "")
            if _wr_ts:
                _wr_age = f" · Generated {_wr_ts}"
            st.info(f"📄 Cached report available{_wr_age}")
            with st.expander("📖 View Cached Report", expanded=True):
                st.text(_wr_cached_text)
            st.download_button(
                "⬇️ Download Cached Report (.txt)",
                data=_wr_cached_text,
                file_name=f"weekly_report_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain",
                key="dl_weekly_cached"
            )
            st.markdown("---")

        if _wr_generate or st.session_state.get("_wr_just_generated"):
            st.session_state["_wr_just_generated"] = False
            with st.spinner("Generating weekly report… (10–30 seconds)"):
                try:
                    from gemini_reporter import generate_weekly_market_report as _gen_weekly
                    _wr_snapshot = {}
                    if _HUB_OK:
                        try:
                            from market_data_hub import build_postmarket_snapshot as _bps
                            _wr_snapshot = _bps()
                        except Exception as _hube:
                            st.warning(f"Could not fetch live snapshot: {_hube}. Using cached breadth.")

                    # Supplement with breadth cache if available
                    _bl = os.path.join(_wr_dir, "latest_breadth.json")
                    if os.path.exists(_bl):
                        try:
                            _bdata = json.loads(open(_bl, encoding="utf-8").read())
                            _wr_snapshot["breadth"] = _bdata.get("breadth", {})
                        except Exception:
                            pass

                    _wr_snapshot["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    _fresh_report = _gen_weekly(_wr_snapshot)

                    # Save to disk
                    os.makedirs(_wr_dir, exist_ok=True)
                    open(_wr_file, "w", encoding="utf-8").write(_fresh_report)
                    open(_wr_json, "w", encoding="utf-8").write(
                        json.dumps({"generated_at": _wr_snapshot["generated_at"],
                                    "word_count": len(_fresh_report.split())}, indent=2)
                    )

                    st.success(f"✅ Report generated ({len(_fresh_report.split())} words)")
                    with st.expander("📖 Weekly Report", expanded=True):
                        st.text(_fresh_report)
                    st.download_button(
                        "⬇️ Download Report (.txt)",
                        data=_fresh_report,
                        file_name=f"weekly_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                        mime="text/plain",
                        key="dl_weekly_fresh"
                    )
                except Exception as _wre:
                    st.error(f"Weekly report generation failed: {_wre}")

# ════════════════════════════════════════════════════════════════════════════
#  E-08: MACRO RADAR
# ════════════════════════════════════════════════════════════════════════════
elif page == 'MACRO':
    st.markdown('<div class="page-title">🌐 Macro Radar</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Global Risk Environment // VIX // Currencies // Commodities</div>', unsafe_allow_html=True)
    _mc1, _mc2, _mc3, _mc4 = st.tabs(["🌍 Overview", "📊 Global Indices", "💰 FII/DII Flows", "🔄 Sector RRG"])

    with _mc1:
        with st.spinner("Loading macro data (cached 5min)..."):
            macro = fetch_macro_data_cached()

        if not macro:
            st.error("Could not fetch macro data. Check your internet connection.")
        else:
            # ── Row 1: Key metrics ──
            section("Global Macro Snapshot")
            cols = st.columns(len(macro), gap="small")
            color_map = {
                'India VIX': lambda v: "#ff4b4b" if v > 20 else "#e3b341" if v > 15 else "#00f260",
                'Nifty 50':  lambda v: "#00f260",
            }
            for col, (name, dat) in zip(cols, macro.items()):
                ltp_v = dat['LTP']
                chg   = dat['1M%']
                color = "#00f260" if chg >= 0 else "#ff4b4b"
                if name == 'India VIX':
                    color = "#ff4b4b" if ltp_v > 20 else "#e3b341" if ltp_v > 15 else "#00f260"
                pctile_str = f"Pctile: {dat['Pctile']:.0f}%"
                col.metric(name, f"{ltp_v:,.2f}", delta=f"{chg:+.1f}% (1M)",
                           help=f"1Y Range Percentile: {pctile_str} | Stage: {dat['Stage']}")

            st.markdown("---")
            # ── Regime Indicators ──
            section("Regime Indicators")
            r1, r2, r3 = st.columns(3, gap="small")

            vix_data = macro.get('India VIX', {})
            vix_val  = vix_data.get('LTP', 0)
            if vix_val > 25:     vix_regime, vix_col = "🔴 STRESSED  (>25)", "#ff4b4b"
            elif vix_val > 18:   vix_regime, vix_col = "🟡 ELEVATED (18–25)", "#e3b341"
            else:                vix_regime, vix_col = "🟢 CALM     (<18)",   "#00f260"

            with r1:
                st.markdown(f"""
                <div class="metric-card">
                  <div class="metric-label">India VIX Regime</div>
                  <div class="metric-value" style="color:{vix_col};">{vix_regime}</div>
                  <div style="font-size:0.7rem;color:#5a8a9f;margin-top:4px;">1Y Pctile: {vix_data.get('Pctile',0):.0f}%</div>
                </div>""", unsafe_allow_html=True)

            inr_data = macro.get('USD/INR', {})
            inr_ltp  = inr_data.get('LTP', 0)
            inr_sma200 = inr_data.get('SMA200', inr_ltp)
            inr_signal = "🔴 Weak INR (above 200MA)" if inr_ltp > inr_sma200 else "🟢 Strong INR (below 200MA)"
            with r2:
                st.markdown(f"""
                <div class="metric-card">
                  <div class="metric-label">USD/INR Signal</div>
                  <div class="metric-value" style="font-size:0.9rem;">{inr_signal}</div>
                  <div style="font-size:0.7rem;color:#5a8a9f;margin-top:4px;">LTP: {inr_ltp:.2f} | 200MA: {inr_sma200:.2f}</div>
                </div>""", unsafe_allow_html=True)

            crude_data  = macro.get('Brent Crude', {})
            crude_chg1m = crude_data.get('1M%', 0)
            crude_sig   = "🔴 Rising Crude (inflationary)" if crude_chg1m > 5 else "🟢 Stable / Falling Crude"
            with r3:
                st.markdown(f"""
                <div class="metric-card">
                  <div class="metric-label">Crude Oil Signal</div>
                  <div class="metric-value" style="font-size:0.9rem;">{crude_sig}</div>
                  <div style="font-size:0.7rem;color:#5a8a9f;margin-top:4px;">1M Change: {crude_chg1m:+.1f}%</div>
                </div>""", unsafe_allow_html=True)

            st.markdown("---")
            # ── Multi-line chart ──
            section("12-Month Trend — Normalised to 100")
            # P2.1 (#5) — added Nifty 500 alongside Nifty 50 so divergence between
            # large-cap and broad market is visible on the same chart.
            chart_names = ['Nifty 50','Nifty 500','India VIX','Gold','Brent Crude']
            fig_macro = go.Figure()
            for name in chart_names:
                if name in macro and macro[name].get('series') is not None:
                    series = macro[name]['series'].dropna()
                    norm   = (series / series.iloc[0]) * 100
                    fig_macro.add_trace(go.Scatter(
                        x=norm.index, y=norm.values, name=name, mode='lines',
                        line=dict(width=1.5)
                    ))
            fig_macro.update_layout(
                height=300, margin=dict(t=10,l=0,r=0,b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                legend=dict(font=dict(size=10,color="#c9d1d9"), bgcolor="rgba(0,0,0,0)"),
                xaxis=dict(gridcolor="#1e3a5f"), yaxis=dict(gridcolor="#1e3a5f"),
                font=dict(color="#c9d1d9")
            )
            st.plotly_chart(fig_macro, use_container_width=True)

    with _mc2:
        section("Global Indices — Full Board")
        st.caption("Sorted by absolute |Chg%|: biggest movers float to top. ▲ green = up, ▼ red = down.")
        if _HUB_OK:
            with st.spinner("Fetching global indices..."):
                try: _glo2 = fetch_global_overview()
                except Exception as _e: _glo2 = {}; st.error(str(_e))

            if _glo2:
                _all_items = {**_glo2.get("indices",{}), **_glo2.get("commodities",{}),
                              **_glo2.get("currencies",{}), **_glo2.get("bonds",{})}
                _rows = []
                for _n, _d in _all_items.items():
                    if _d:
                        _chg_v = float(_d.get("change_pct", 0) or 0)
                        # P2.1 (#6) — direction marker as Unicode arrow with explicit text
                        _arrow = "▲" if _chg_v >= 0 else "▼"
                        _rows.append({
                            "Name": _n,
                            "LTP": _d.get("ltp", 0),
                            "Chg%": f"{_arrow} {_chg_v:+.2f}%",
                            "_chg_sort": abs(_chg_v),   # used for sort, dropped before display
                            "52W High": _d.get("week52_high", 0),
                            "52W Low":  _d.get("week52_low", 0),
                            "vs 52W H": f"{_d.get('pct_vs_52h', 0):.1f}%",
                        })
                if _rows:
                    _df_glo = pd.DataFrame(_rows)
                    _df_glo = _df_glo.sort_values("_chg_sort", ascending=False).drop(columns=["_chg_sort"])

                    # Style with red/green colour on the Chg% column based on sign
                    def _color_chg(val):
                        if isinstance(val, str) and val.startswith("▲"):
                            return "color: #00f260; font-weight: 600;"
                        if isinstance(val, str) and val.startswith("▼"):
                            return "color: #ff4b4b; font-weight: 600;"
                        return ""
                    # 10 May 2026: round numeric columns to 2 decimals (user
                    # feedback: LTP, 52W High/Low were showing 6+ decimals).
                    _glo_num_cols = {c: "{:,.2f}" for c in
                                      ["LTP", "52W High", "52W Low"]
                                      if c in _df_glo.columns}
                    try:
                        _styled = _df_glo.style.format(_glo_num_cols)
                        _styled = (_styled.set_properties(**{'text-align': 'right', 'background-color': '#0d1b2a', 'color': '#c9d1d9', 'border-bottom': '1px solid #1e3a5f', 'padding': '8px'})
                                   .set_properties(subset=['Name'], **{'text-align': 'left'}))
                        _styled = (_styled.map(_color_chg, subset=["Chg%"]) if hasattr(_styled, "map") else _styled.applymap(_color_chg, subset=["Chg%"]))
                        _styled = (_styled.set_table_styles([
                                       {'selector': 'th', 'props': [('text-align', 'right'), ('background-color', '#112236'), ('color', '#e6edf3'), ('border-bottom', '1px solid #58a6ff'), ('padding', '8px')]},
                                       {'selector': 'th.col_heading.level0.col0', 'props': [('text-align', 'left')]},
                                       {'selector': 'table', 'props': [('width', '100%'), ('border-collapse', 'collapse')]}
                                   ])
                                   .hide(axis="index"))
                        st.markdown(f'<div style="max-height: 700px; overflow-y: auto;">{_styled.to_html(escape=False)}</div>', unsafe_allow_html=True)
                    except Exception:
                        # Pandas fallback
                        for c in ["LTP", "52W High", "52W Low"]:
                            if c in _df_glo.columns:
                                _df_glo[c] = pd.to_numeric(_df_glo[c], errors="coerce").round(2)
                        st.dataframe(_df_glo, use_container_width=True, height=min(40 + 35 * len(_df_glo), 700))
        else:
            st.warning("market_data_hub not available.")

    with _mc3:
        section("FII/DII Cumulative Flows")
        if _HUB_OK:
            with st.spinner("Fetching FII/DII flow history..."):
                try: _fii3 = fetch_fii_dii_data()
                except Exception as _e: _fii3 = pd.DataFrame(); st.error(str(_e))

            if not _fii3.empty and "fii_net" in _fii3.columns:
                _fii3["fii_cumulative"] = _fii3["fii_net"].cumsum()
                _fii3["dii_cumulative"] = _fii3["dii_net"].cumsum()

                _fig_cum = go.Figure()
                _x = _fii3["date"] if "date" in _fii3.columns else _fii3.index
                _fig_cum.add_trace(go.Scatter(x=_x, y=_fii3["fii_cumulative"],
                                              name="FII Cumulative (₹Cr)", line=dict(color="#00f260",width=2)))
                _fig_cum.add_trace(go.Scatter(x=_x, y=_fii3["dii_cumulative"],
                                              name="DII Cumulative (₹Cr)", line=dict(color="#58a6ff",width=2)))
                _fig_cum.add_hline(y=0, line_dash="dot", line_color="#3d5a6e", line_width=1)
                _fig_cum.update_layout(
                    height=340, margin=dict(t=10,l=0,r=0,b=0),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                    legend=dict(font=dict(size=10,color="#c9d1d9"),bgcolor="rgba(0,0,0,0)"),
                    xaxis=dict(gridcolor="#1e3a5f", type="date",
                               tickformat="%d %b", dtick="D1"),
                    yaxis=dict(gridcolor="#1e3a5f", title="₹ Crore"),
                    font=dict(color="#c9d1d9")
                )
                st.plotly_chart(_fig_cum, use_container_width=True)
                _df_to_show = _fii3[["date","fii_net","dii_net","fii_buy","fii_sell"]].tail(30) if "fii_buy" in _fii3.columns else _fii3.tail(30)
                _fii_num_cols = {c: "{:,.2f}" for c in _df_to_show.columns if c != "date"}
                try:
                    _styled_fii = (_df_to_show.style
                                   .format(_fii_num_cols)
                                   .set_properties(**{'text-align': 'right', 'background-color': '#0d1b2a', 'color': '#c9d1d9', 'border-bottom': '1px solid #1e3a5f', 'padding': '8px'})
                                   .set_properties(subset=['date'], **{'text-align': 'left'})
                                   .set_table_styles([
                                       {'selector': 'th', 'props': [('text-align', 'right'), ('background-color', '#112236'), ('color', '#e6edf3'), ('border-bottom', '1px solid #58a6ff'), ('padding', '8px')]},
                                       {'selector': 'th.col_heading.level0.col0', 'props': [('text-align', 'left')]},
                                       {'selector': 'table', 'props': [('width', '100%'), ('border-collapse', 'collapse')]}
                                   ])
                                   .hide(axis="index"))
                    st.markdown(f'<div style="max-height: 500px; overflow-y: auto;">{_styled_fii.to_html(escape=False)}</div>', unsafe_allow_html=True)
                except Exception:
                    st.dataframe(_df_to_show, use_container_width=True)
            else:
                st.info("FII/DII flow data unavailable.")
        else:
            st.warning("market_data_hub not available.")

    with _mc4:
        # NOTE (10 May 2026): Stock-level Recovery Signals block was previously
        # rendered here. Removed per user feedback (#7): RRG is sector-rotation
        # analytics; stock-level recovery signals belong in HUNTER → Recovery
        # Screener where you actually act on them. See HUNTER cockpit.

        section("Sector RRG — Rotation Quadrant")
        st.caption("RS-Ratio > 100 = outperforming. RS-Momentum > 100 = gaining speed. Centre = 100/100.")
        with st.spinner("Loading sector RRG data (cached 5min)..."):
            df_rrg = fetch_sector_momentum_cached()

        if not df_rrg.empty and 'RS-Ratio' in df_rrg.columns:
            fig_rrg = go.Figure()
            quad_colors = {"🟢 Leading":"#00f260","🟡 Weakening":"#e3b341",
                           "🔵 Improving":"#58a6ff","🔴 Lagging":"#ff4b4b","—":"#5a8a9f"}
            for _, row in df_rrg.iterrows():
                q     = row.get('RRG Quadrant','—')
                color = quad_colors.get(q,"#5a8a9f")
                fig_rrg.add_trace(go.Scatter(
                    x=[row['RS-Ratio']], y=[row['Acceleration']],
                    mode='markers+text', name=row['Sector'],
                    text=[row['Sector'].replace('Nifty ','')],
                    textposition="top center",
                    marker=dict(size=12, color=color, line=dict(width=1, color='#e6edf3')),
                ))
            # Quadrant lines
            fig_rrg.add_hline(y=0, line_dash="dot", line_color="#3d5a6e", line_width=1)
            fig_rrg.add_vline(x=100, line_dash="dot", line_color="#3d5a6e", line_width=1)
            fig_rrg.update_layout(
                height=420, showlegend=False,
                xaxis_title="RS-Ratio (100 = neutral)", yaxis_title="Acceleration (0 = neutral)",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                xaxis=dict(gridcolor="#1e3a5f"), yaxis=dict(gridcolor="#1e3a5f"),
                font=dict(color="#c9d1d9"), margin=dict(t=10,l=0,r=0,b=0)
            )
            st.plotly_chart(fig_rrg, use_container_width=True)
            _df_rrg_show = df_rrg[['Sector','4W %','Prior 4W %','Acceleration','RS-Ratio','RRG Quadrant','Signal']]
            _rrg_num_cols = {c: "{:,.2f}" for c in ['4W %','Prior 4W %','Acceleration','RS-Ratio'] if c in _df_rrg_show.columns}
            try:
                _styled_rrg = (_df_rrg_show.style
                               .format(_rrg_num_cols)
                               .set_properties(subset=['4W %','Prior 4W %','Acceleration','RS-Ratio'], **{'text-align': 'right', 'background-color': '#0d1b2a', 'color': '#c9d1d9', 'border-bottom': '1px solid #1e3a5f', 'padding': '8px'})
                               .set_properties(subset=['Sector','RRG Quadrant','Signal'], **{'text-align': 'left', 'background-color': '#0d1b2a', 'color': '#c9d1d9', 'border-bottom': '1px solid #1e3a5f', 'padding': '8px'})
                               .set_table_styles([
                                   {'selector': 'th', 'props': [('text-align', 'left'), ('background-color', '#112236'), ('color', '#e6edf3'), ('border-bottom', '1px solid #58a6ff'), ('padding', '8px')]},
                                   {'selector': 'th.col_heading.level0.col1', 'props': [('text-align', 'right')]},
                                   {'selector': 'th.col_heading.level0.col2', 'props': [('text-align', 'right')]},
                                   {'selector': 'th.col_heading.level0.col3', 'props': [('text-align', 'right')]},
                                   {'selector': 'th.col_heading.level0.col4', 'props': [('text-align', 'right')]},
                                   {'selector': 'table', 'props': [('width', '100%'), ('border-collapse', 'collapse')]}
                               ])
                               .hide(axis="index"))
                st.markdown(f'<div style="max-height: 500px; overflow-y: auto;">{_styled_rrg.to_html(escape=False)}</div>', unsafe_allow_html=True)
            except Exception:
                st.dataframe(_df_rrg_show, use_container_width=True)
        else:
            st.info("Sector data unavailable. Check network and retry.")

# ════════════════════════════════════════════════════════════════════════════
#  E-07: OPTIONS DESK
# ════════════════════════════════════════════════════════════════════════════
elif page == 'OPTIONS':
    st.markdown('<div class="page-title">📐 Options Desk</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Live NSE option chain — PCR · Max Pain · OI buildup</div>', unsafe_allow_html=True)

    try:
        from nse_options import get_option_chain as _get_oc
        _OC_OK = True
    except ImportError:
        _OC_OK = False

    _opt1, _opt2, _opt3 = st.tabs(["📡 Live Chain", "🔗 External Tools", "📚 Quick Reference"])

    # ════════════════════════════════════════════════════════════════════════
    with _opt1:
        # ── Controls ──────────────────────────────────────────────────────
        _oc_c1, _oc_c2, _oc_c3, _oc_c4 = st.columns([2, 2, 2, 2])
        with _oc_c1:
            _oc_sym = st.selectbox(
                "Index / Symbol",
                ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"],
                key="oc_symbol"
            )
        with _oc_c2:
            _oc_custom = st.text_input(
                "Custom symbol (equity)", placeholder="e.g. RELIANCE",
                key="oc_custom"
            ).strip().upper()
            if _oc_custom:
                _oc_sym = _oc_custom
        with _oc_c3:
            _oc_expiry_idx = st.selectbox(
                "Expiry", [0, 1, 2, 3],
                format_func=lambda i: ["Current", "Next", "+2", "+3"][i],
                key="oc_expiry_idx"
            )
        with _oc_c4:
            _oc_fetch = st.button(
                "🔄 Fetch Chain", type="primary",
                key="oc_fetch_btn", use_container_width=True
            )
            _oc_auto = st.checkbox("Auto-load on open", value=True, key="oc_auto")

        if not _OC_OK:
            st.error(
                "nse_options.py not found in the project folder. "
                "Ensure the file exists and restart the app."
            )
        elif _oc_fetch or (_oc_auto and "oc_data_" + _oc_sym not in st.session_state):
            with st.spinner(f"Warming NSE session then fetching {_oc_sym} option chain… (takes ~3 seconds)"):
                if _oc_fetch:
                    # Force-clear cached session so 3-step warmup always runs fresh
                    try:
                        import nse_options as _nse_mod
                        _nse_mod._session_obj   = None
                        _nse_mod._session_built = 0.0
                    except Exception:
                        pass
                _oc_result = _get_oc(_oc_sym, int(_oc_expiry_idx))
                st.session_state["oc_data_" + _oc_sym] = _oc_result

        _oc_data = st.session_state.get("oc_data_" + _oc_sym)

        if _oc_data:
            if _oc_data.get("error"):
                if _oc_data.get("_market_closed"):
                    st.warning(
                        "**NSE markets are closed** (weekends / outside 09:15–15:30 IST). "
                        "Option chain data is only published during live trading sessions.\n\n"
                        "Fetch the chain on a weekday during market hours — results are "
                        "cached and will show here on subsequent visits."
                    )
                else:
                    st.error(f"Could not fetch option chain: {_oc_data['error']}")
                    st.info(
                        "**NSE uses Akamai bot-protection.** If you see session errors:\n\n"
                        "```\npip install curl_cffi\n```\n"
                        "`curl_cffi` impersonates Chrome's TLS fingerprint and bypasses "
                        "Akamai reliably. After installing, click **Fetch Chain** again.\n\n"
                        "Alternative: `pip install nsepython`"
                    )
            else:
                _oc_df   = _oc_data["chain_df"]
                _oc_spot = _oc_data["spot"]
                _oc_pcr  = _oc_data["pcr"]
                _oc_mp   = _oc_data["max_pain"]
                _oc_exp  = _oc_data["expiry"]
                _oc_src  = _oc_data.get("source", "")
                _oc_ts   = _oc_data.get("timestamp", "")

                st.caption(
                    f"Expiry: **{_oc_exp}** · Spot: **{_oc_spot:,.2f}** · "
                    f"Source: {_oc_src} · As of: {_oc_ts}"
                )

                # ── Key metrics row ────────────────────────────────────────
                section("Live Snapshot")
                _km1, _km2, _km3, _km4, _km5 = st.columns(5)

                # PCR colour
                _pcr_col = (
                    "#00f260" if _oc_pcr > 1.3 else
                    "#e3b341" if _oc_pcr > 0.7 else
                    "#ff4b4b"
                )
                _pcr_label = (
                    "Contrarian Bullish" if _oc_pcr > 1.3 else
                    "Mildly Bearish"     if _oc_pcr > 1.0 else
                    "Balanced"           if _oc_pcr > 0.7 else
                    "Complacency Risk"
                )
                _km1.metric("Spot", f"{_oc_spot:,.2f}")
                _km2.metric(
                    "PCR", f"{_oc_pcr:.3f}",
                    delta=_pcr_label,
                    delta_color="normal" if _oc_pcr > 0.7 else "inverse"
                )
                _km3.metric("Max Pain", f"{_oc_mp:,.0f}",
                            delta=f"{((_oc_mp - _oc_spot) / max(_oc_spot,1))*100:+.2f}% from spot",
                            delta_color="normal" if _oc_mp >= _oc_spot else "inverse")
                _km4.metric("Total CE OI", f"{_oc_data['total_ce_oi']:,}")
                _km5.metric("Total PE OI", f"{_oc_data['total_pe_oi']:,}")

                # PCR gauge bar
                st.markdown(
                    f"""<div style="margin:8px 0 4px;font-size:0.78rem;color:#8b949e">
                    PCR gauge — 0 (bearish) → 0.7 → 1.0 → 1.3 → 2 (bullish hedge)
                    </div>""",
                    unsafe_allow_html=True
                )
                _pcr_pct = min(_oc_pcr / 2.0, 1.0) * 100
                st.progress(int(_pcr_pct), text=f"PCR {_oc_pcr:.3f} — {_pcr_label}")

                st.markdown("---")

                if not _oc_df.empty:
                    # ── Filter to ATM ± N strikes ──────────────────────────
                    _oc_n = st.slider(
                        "Strikes around ATM to display",
                        min_value=5, max_value=30, value=15, step=5,
                        key="oc_atm_range"
                    )
                    _atm_idx = (_oc_df["strike"] - _oc_spot).abs().idxmin()
                    _lo_idx  = max(0, _atm_idx - _oc_n)
                    _hi_idx  = min(len(_oc_df) - 1, _atm_idx + _oc_n)
                    _oc_view = _oc_df.iloc[_lo_idx:_hi_idx + 1].copy()

                    # ── OI bar chart (CE vs PE) ────────────────────────────
                    section("Open Interest by Strike")
                    _fig_oi = go.Figure()
                    _fig_oi.add_trace(go.Bar(
                        x=_oc_view["strike"], y=_oc_view["CE_OI"],
                        name="Call OI", marker_color="#ff4b4b",
                        opacity=0.85
                    ))
                    _fig_oi.add_trace(go.Bar(
                        x=_oc_view["strike"], y=_oc_view["PE_OI"],
                        name="Put OI", marker_color="#00f260",
                        opacity=0.85
                    ))
                    # Vertical lines for spot and max pain
                    _fig_oi.add_vline(
                        x=_oc_spot, line_dash="dash", line_color="#58a6ff",
                        annotation_text=f"Spot {_oc_spot:,.0f}",
                        annotation_font_color="#58a6ff", line_width=1.5
                    )
                    _fig_oi.add_vline(
                        x=_oc_mp, line_dash="dot", line_color="#e3b341",
                        annotation_text=f"Max Pain {_oc_mp:,.0f}",
                        annotation_font_color="#e3b341", line_width=1.5
                    )
                    _fig_oi.update_layout(
                        barmode="group", height=340,
                        margin=dict(t=10, l=0, r=0, b=0),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,10,0.5)",
                        xaxis=dict(gridcolor="#1e3a5f", title="Strike"),
                        yaxis=dict(gridcolor="#1e3a5f", title="Open Interest (contracts)"),
                        legend=dict(font=dict(size=10, color="#c9d1d9"), bgcolor="rgba(0,0,0,0)"),
                        font=dict(color="#c9d1d9"),
                    )
                    st.plotly_chart(_fig_oi, use_container_width=True)

                    # ── Change-in-OI (buildup) ─────────────────────────────
                    st.markdown("---")
                    section("Change in OI — Buildup Analysis")
                    _fig_doi = go.Figure()
                    _ce_doi_colors = [
                        "#ff4b4b" if v >= 0 else "#ff9999"
                        for v in _oc_view["CE_chgOI"]
                    ]
                    _pe_doi_colors = [
                        "#00f260" if v >= 0 else "#99ffcc"
                        for v in _oc_view["PE_chgOI"]
                    ]
                    _fig_doi.add_trace(go.Bar(
                        x=_oc_view["strike"], y=_oc_view["CE_chgOI"],
                        name="Call ΔOI", marker_color=_ce_doi_colors, opacity=0.85
                    ))
                    _fig_doi.add_trace(go.Bar(
                        x=_oc_view["strike"], y=_oc_view["PE_chgOI"],
                        name="Put ΔOI", marker_color=_pe_doi_colors, opacity=0.85
                    ))
                    _fig_doi.add_vline(x=_oc_spot, line_dash="dash",
                                       line_color="#58a6ff", line_width=1.5)
                    _fig_doi.add_hline(y=0, line_color="#3d5a6e", line_width=1)
                    _fig_doi.update_layout(
                        barmode="group", height=280,
                        margin=dict(t=10, l=0, r=0, b=0),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,10,0.5)",
                        xaxis=dict(gridcolor="#1e3a5f", title="Strike"),
                        yaxis=dict(gridcolor="#1e3a5f", title="Change in OI"),
                        legend=dict(font=dict(size=10, color="#c9d1d9"), bgcolor="rgba(0,0,0,0)"),
                        font=dict(color="#c9d1d9"),
                    )
                    st.plotly_chart(_fig_doi, use_container_width=True)

                    # ── Buildup interpretation ─────────────────────────────
                    _oc_ce_chg_tot = int(_oc_view["CE_chgOI"].sum())
                    _oc_pe_chg_tot = int(_oc_view["PE_chgOI"].sum())
                    _oc_buildup = (
                        "Bears building (Call OI rising + Put OI rising)"
                        if _oc_ce_chg_tot > 0 and _oc_pe_chg_tot > 0 else
                        "Bulls building (Call OI falling + Put OI rising — put unwinding)"
                        if _oc_ce_chg_tot <= 0 and _oc_pe_chg_tot > 0 else
                        "Bearish (Call OI rising + Put OI falling — call writing)"
                        if _oc_ce_chg_tot > 0 and _oc_pe_chg_tot <= 0 else
                        "Bulls in control (both OIs declining)"
                    )
                    _oc_bu_col = (
                        "#00f260" if "Bull" in _oc_buildup else
                        "#ff4b4b" if "Bear" in _oc_buildup else "#e3b341"
                    )
                    st.markdown(
                        f'<div class="metric-card" style="border-left:3px solid {_oc_bu_col}">'
                        f'<div class="metric-label">ΔOI Interpretation</div>'
                        f'<div class="metric-value" style="color:{_oc_bu_col};font-size:0.9rem">'
                        f'{_oc_buildup}</div>'
                        f'<div style="font-size:0.72rem;color:#8b949e;margin-top:4px">'
                        f'CE ΔOI net: {_oc_ce_chg_tot:+,}  |  PE ΔOI net: {_oc_pe_chg_tot:+,}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                    # ── IV Skew ────────────────────────────────────────────
                    st.markdown("---")
                    section("IV Skew — Implied Volatility by Strike")
                    _iv_view = _oc_view[
                        (_oc_view["CE_IV"] > 0) | (_oc_view["PE_IV"] > 0)
                    ]
                    if not _iv_view.empty:
                        _fig_iv = go.Figure()
                        _fig_iv.add_trace(go.Scatter(
                            x=_iv_view["strike"], y=_iv_view["CE_IV"],
                            name="Call IV", mode="lines+markers",
                            line=dict(color="#ff4b4b", width=1.5),
                            marker=dict(size=5)
                        ))
                        _fig_iv.add_trace(go.Scatter(
                            x=_iv_view["strike"], y=_iv_view["PE_IV"],
                            name="Put IV", mode="lines+markers",
                            line=dict(color="#00f260", width=1.5),
                            marker=dict(size=5)
                        ))
                        _fig_iv.add_vline(x=_oc_spot, line_dash="dash",
                                          line_color="#58a6ff", line_width=1.5)
                        _fig_iv.update_layout(
                            height=240, margin=dict(t=10, l=0, r=0, b=0),
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,10,0.5)",
                            xaxis=dict(gridcolor="#1e3a5f", title="Strike"),
                            yaxis=dict(gridcolor="#1e3a5f", title="IV %"),
                            legend=dict(font=dict(size=10, color="#c9d1d9"),
                                        bgcolor="rgba(0,0,0,0)"),
                            font=dict(color="#c9d1d9"),
                        )
                        st.plotly_chart(_fig_iv, use_container_width=True)

                    # ── Data table ─────────────────────────────────────────
                    st.markdown("---")
                    section("Option Chain — Near ATM Strikes")
                    _tbl_cols = ["strike",
                                 "CE_OI", "CE_chgOI", "CE_LTP", "CE_IV",
                                 "PE_OI", "PE_chgOI", "PE_LTP", "PE_IV"]
                    _tbl_cols = [c for c in _tbl_cols if c in _oc_view.columns]
                    st.dataframe(
                        _oc_view[_tbl_cols].rename(columns={
                            "strike":   "Strike",
                            "CE_OI":    "CE OI", "CE_chgOI": "CE ΔOI",
                            "CE_LTP":   "CE LTP", "CE_IV":   "CE IV%",
                            "PE_OI":    "PE OI", "PE_chgOI": "PE ΔOI",
                            "PE_LTP":   "PE LTP", "PE_IV":   "PE IV%",
                        }),
                        use_container_width=True, hide_index=True
                    )

                    # Download
                    st.download_button(
                        "⬇️ Download chain CSV",
                        data=_oc_df.to_csv(index=False),
                        file_name=f"option_chain_{_oc_sym}_{_oc_exp.replace('-','')}.csv",
                        mime="text/csv",
                        key="dl_oc_csv"
                    )

    # ════════════════════════════════════════════════════════════════════════
    with _opt2:
        section("NSE Options — Direct Links")
        _ol1, _ol2, _ol3 = st.columns(3)
        with _ol1:
            st.link_button("📊 NSE Option Chain (NIFTY)",
                           "https://www.nseindia.com/option-chain",
                           use_container_width=True)
            st.link_button("📊 NSE Option Chain (BANKNIFTY)",
                           "https://www.nseindia.com/option-chain?optionType=CE&instrumentType=OPTIDX&symbol=BANKNIFTY",
                           use_container_width=True)
            st.link_button("📊 NSE Option Chain (FINNIFTY)",
                           "https://www.nseindia.com/option-chain?optionType=CE&instrumentType=OPTIDX&symbol=FINNIFTY",
                           use_container_width=True)
        with _ol2:
            st.link_button("🧠 Sensibull — Options Analysis",
                           "https://sensibull.com/nifty-option-chain",
                           use_container_width=True)
            st.link_button("📉 Sensibull Max Pain",
                           "https://sensibull.com/max-pain",
                           use_container_width=True)
            st.link_button("📈 Sensibull PCR",
                           "https://sensibull.com/pcr",
                           use_container_width=True)
        with _ol3:
            st.link_button("🔬 Opstra — Option Chain + Greeks",
                           "https://opstra.definedge.com/",
                           use_container_width=True)
            st.link_button("📋 Opstra OI Analysis",
                           "https://opstra.definedge.com/oi-analysis",
                           use_container_width=True)
            st.link_button("🎯 Opstra Strategy Builder",
                           "https://opstra.definedge.com/strategy-builder",
                           use_container_width=True)

        st.markdown("---")
        st.info(
            "If the Live Chain tab fails with a network error, these direct links "
            "open the full NSE / Sensibull / Opstra option chain in your browser.\n\n"
            "To enable the live data tab, run: `pip install nsepython` for an "
            "alternate session handler."
        )

    # ════════════════════════════════════════════════════════════════════════
    with _opt3:
        section("Key Concepts Quick Reference")
        _qr1, _qr2, _qr3 = st.columns(3, gap="large")
        with _qr1:
            st.markdown("""
**Max Pain**
Strike price where option writers (sellers) lose the *least* money at expiry.
Price gravitates toward max pain as expiry approaches.

🟢 Spot *below* max pain → drift upward expected
🔴 Spot *above* max pain → drift downward expected
""")
        with _qr2:
            st.markdown("""
**PCR (Put-Call Ratio)**
Total Put OI ÷ Total Call OI.

| PCR | Reading |
|-----|---------|
| > 1.3 | Heavy hedging — contrarian bullish |
| 1.0–1.3 | Mildly bearish |
| 0.7–1.0 | Balanced / neutral |
| < 0.7 | Complacency — reversal risk |
""")
        with _qr3:
            st.markdown("""
**Change in OI (ΔOI)**

| Call ΔOI | Put ΔOI | Interpretation |
|----------|---------|----------------|
| ↑ | ↑ | Bears in control |
| ↑ | ↓ | Put unwinding — bullish |
| ↓ | ↑ | Call writing — bearish |
| ↓ | ↓ | Bulls in control |

Short buildup = OI↑ + price↓
Long buildup  = OI↑ + price↑
""")

# ════════════════════════════════════════════════════════════════════════════
#  E-09: TRADE AUTOPSY ENGINE
# ════════════════════════════════════════════════════════════════════════════
elif page == 'AUTOPSY':
    st.markdown('<div class="page-title">🔬 Trade Autopsy</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Post-Trade Performance Intelligence — Closed Trade Analytics</div>', unsafe_allow_html=True)
    _ap1, _ap2, _ap3, _ap4, _ap5 = st.tabs(["📊 Overview", "📅 Calendar", "🏭 Sectors", "🎯 Trade Quality", "📐 Attribution"])

    df_closed = load_closed_trades_db()
    if df_closed is None or df_closed.empty:
        st.info("No closed trades found. Complete some trades to unlock the Autopsy Engine.")
    else:
        for col in ['ExitPrice','BuyPrice','Quantity']:
            df_closed[col] = pd.to_numeric(df_closed.get(col, 0), errors='coerce').fillna(0)
        df_closed['PnL']     = (df_closed['ExitPrice'] - df_closed['BuyPrice']) * df_closed['Quantity']
        df_closed['PnL_pct'] = np.where(df_closed['BuyPrice'] > 0,
                                         (df_closed['ExitPrice'] - df_closed['BuyPrice']) / df_closed['BuyPrice'] * 100, 0)
        df_closed['ExitDate']  = pd.to_datetime(df_closed['ExitDate'],  errors='coerce')
        df_closed['EntryDate'] = pd.to_datetime(df_closed.get('EntryDate', pd.NaT), errors='coerce')
        df_closed['DaysHeld']  = (df_closed['ExitDate'] - df_closed['EntryDate']).dt.days
        df_closed = df_closed.dropna(subset=['ExitDate'])

        with _ap1:
            analytics = compute_portfolio_analytics(df_closed, total_cap)
            if analytics:
                section("Closed Trade Summary")
                o1,o2,o3 = st.columns(3, gap="small")
                o1.metric("Total Trades",    str(analytics['total_trades']))
                o2.metric("Win Rate",        f"{analytics['win_rate']}%")
                o3.metric("Total Realized",  f"₹{format_inr_int(analytics['total_realized'])}")
                o4,o5,o6 = st.columns(3, gap="small")
                o4.metric("Sharpe Ratio",    str(analytics['sharpe']))
                o5.metric("Profit Factor",   str(analytics['profit_factor']))
                o6.metric("Expectancy/Trade",f"₹{format_inr_int(analytics['expectancy'])}")
                o7,o8,o9 = st.columns(3, gap="small")
                o7.metric("Max Drawdown",    f"₹{format_inr_int(abs(analytics['max_dd']))} ({analytics['max_dd_pct']}%)")
                o8.metric("Avg Win ₹",       f"₹{format_inr_int(analytics['avg_win_rs'])}")
                o9.metric("Avg Loss ₹",      f"₹{format_inr_int(abs(analytics['avg_loss_rs']))}")

            section("Holding Period Analysis")
            if 'DaysHeld' in df_closed.columns and df_closed['DaysHeld'].notna().any():
                winners = df_closed[df_closed['PnL'] > 0]['DaysHeld'].dropna()
                losers  = df_closed[df_closed['PnL'] <= 0]['DaysHeld'].dropna()
                h1,h2,h3 = st.columns(3, gap="small")
                h1.metric("Avg Days Held (All)",     f"{df_closed['DaysHeld'].mean():.0f} days")
                h2.metric("Avg Days Held (Winners)", f"{winners.mean():.0f} days" if len(winners) else "N/A")
                h3.metric("Avg Days Held (Losers)",  f"{losers.mean():.0f} days"  if len(losers)  else "N/A")

            section("Equity Curve")
            ec = df_closed.sort_values('ExitDate').copy()
            ec['Cum PnL'] = ec['PnL'].cumsum()
            fig_ec = px.area(ec, x='ExitDate', y='Cum PnL',
                             labels={'Cum PnL':'Cumulative P&L (₹)','ExitDate':'Date'})
            fig_ec.update_traces(line_color='#00f260', fillcolor='rgba(0,242,96,0.08)')
            fig_ec.update_layout(height=280, margin=dict(t=10,l=0,r=0,b=0),
                                  paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                                  xaxis=dict(gridcolor="#1e3a5f"), yaxis=dict(gridcolor="#1e3a5f"),
                                  font=dict(color="#c9d1d9"))
            st.plotly_chart(fig_ec, use_container_width=True)

        with _ap2:
            section("Monthly P&L Calendar")
            cal = df_closed.copy()
            cal['YM'] = cal['ExitDate'].dt.to_period('M').astype(str)
            monthly   = cal.groupby('YM')['PnL'].sum().reset_index()
            monthly['Year']  = monthly['YM'].str[:4]
            monthly['Month'] = monthly['YM'].str[5:].astype(int)

            if not monthly.empty:
                pivot = monthly.pivot(index='Year', columns='Month', values='PnL').fillna(0)
                month_names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
                pivot.columns = [month_names[m-1] for m in pivot.columns]
                fig_cal = px.imshow(pivot, color_continuous_scale='RdYlGn',
                                     color_continuous_midpoint=0, aspect='auto',
                                     labels=dict(color='P&L ₹'))
                fig_cal.update_layout(height=max(200, len(pivot)*60+80),
                                       margin=dict(t=10,l=0,r=0,b=0),
                                       paper_bgcolor="rgba(0,0,0,0)",
                                       font=dict(color="#c9d1d9"))
                st.plotly_chart(fig_cal, use_container_width=True)

            section("Monthly P&L Table")
            monthly['P&L ₹'] = monthly['PnL'].apply(lambda x: f"₹{format_inr_int(x)}")
            monthly['Signal'] = monthly['PnL'].apply(lambda x: '✅ Profit' if x > 0 else '❌ Loss')
            st.dataframe(monthly[['YM','P&L ₹','Signal']].rename(columns={'YM':'Month'}),
                         use_container_width=True, hide_index=True)

        with _ap3:
            section("Sector P&L Breakdown")
            if 'Sector' in df_closed.columns:
                sec_pnl = df_closed.groupby('Sector').agg(
                    Trades   = ('PnL','count'),
                    Total_PnL= ('PnL','sum'),
                    Win_Rate = ('PnL', lambda x: (x > 0).sum() / len(x) * 100),
                    Avg_PnL  = ('PnL','mean')
                ).reset_index().sort_values('Total_PnL', ascending=False)
                sec_pnl['Total ₹']  = sec_pnl['Total_PnL'].apply(lambda x: f"₹{format_inr_int(x)}")
                sec_pnl['Avg ₹']    = sec_pnl['Avg_PnL'].apply(lambda x:  f"₹{format_inr_int(x)}")
                sec_pnl['Win Rate'] = sec_pnl['Win_Rate'].apply(lambda x:  f"{x:.0f}%")
                st.dataframe(sec_pnl[['Sector','Trades','Total ₹','Avg ₹','Win Rate']],
                             use_container_width=True, hide_index=True)
                fig_sec = px.bar(sec_pnl, x='Sector', y='Total_PnL',
                                  color='Total_PnL', color_continuous_scale='RdYlGn',
                                  color_continuous_midpoint=0,
                                  labels={'Total_PnL':'Total P&L (₹)'})
                fig_sec.update_layout(height=280, margin=dict(t=10,l=0,r=0,b=0),
                                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                                       xaxis=dict(gridcolor="#1e3a5f"), yaxis=dict(gridcolor="#1e3a5f"),
                                       font=dict(color="#c9d1d9"))
                st.plotly_chart(fig_sec, use_container_width=True)

                # ── Sector COVERAGE view (10 May 2026) ──────────────────
                # The table above only shows sectors where you have CLOSED
                # trades. User feedback: "only 12 sectors". Add a coverage
                # view showing ALL NSE sectors + which ones you've traded
                # vs not — useful for spotting concentration / blind spots.
                try:
                    from breadth_engine import NSE_SECTORS_YF as _all_nse_secs
                    _traded_secs = set(df_closed['Sector'].dropna().astype(str)
                                       .str.lower().str.strip())
                    _all_sec_names = sorted(_all_nse_secs.keys())

                    def _norm(s):
                        return str(s).lower().replace("nifty ", "").strip()
                    _traded_norm = {_norm(s) for s in _traded_secs}

                    _coverage_rows = []
                    for sec in _all_sec_names:
                        norm = _norm(sec)
                        traded = norm in _traded_norm
                        # find matching row in sec_pnl (best-effort name match)
                        match = sec_pnl[sec_pnl['Sector'].astype(str)
                                          .str.lower().str.contains(norm, na=False)]
                        if not match.empty:
                            n_t   = int(match.iloc[0]['Trades'])
                            tot   = float(match.iloc[0]['Total_PnL'])
                        else:
                            n_t, tot = 0, 0.0
                        _coverage_rows.append({
                            'Sector':  sec,
                            'Status':  '✅ Traded' if traded else '⚪ Untraded',
                            'Trades':  n_t,
                            'Total ₹': f"₹{format_inr_int(tot)}" if n_t > 0 else "—",
                        })
                    _df_cov = pd.DataFrame(_coverage_rows)
                    _df_cov['_sort'] = _df_cov['Trades']
                    _df_cov = _df_cov.sort_values('_sort', ascending=False).drop(columns=['_sort'])

                    _n_traded = (_df_cov['Status'] == '✅ Traded').sum()
                    _n_untraded = len(_df_cov) - _n_traded
                    section(f"Sector Coverage — Traded {_n_traded} of "
                            f"{len(_df_cov)} NSE sectors ({_n_untraded} untraded)")
                    st.dataframe(_df_cov, use_container_width=True, hide_index=True,
                                 height=min(40 + 35*len(_df_cov), 600))
                    if _n_untraded > 0:
                        _untraded = _df_cov[_df_cov['Status'] == '⚪ Untraded']['Sector'].tolist()
                        st.caption(f"Untraded sectors: {', '.join(_untraded)}. "
                                   "Worth exploring if your strategy is sector-agnostic.")
                except Exception as _ce:
                    st.caption(f"_Coverage view unavailable ({_ce})_")
            else:
                st.info("No Sector column found in closed trades.")

        with _ap4:
            section("Trade Quality Distribution")
            if 'Quality' in df_closed.columns:
                q_grp = df_closed.groupby('Quality').agg(
                    Count    = ('PnL','count'),
                    Total_PnL= ('PnL','sum'),
                    Avg_PnL  = ('PnL','mean'),
                    Win_Rate = ('PnL', lambda x: (x > 0).sum() / len(x) * 100)
                ).reset_index().sort_values('Avg_PnL', ascending=False)
                q_grp['Total ₹']  = q_grp['Total_PnL'].apply(lambda x: f"₹{format_inr_int(x)}")
                q_grp['Avg ₹']    = q_grp['Avg_PnL'].apply(lambda x:   f"₹{format_inr_int(x)}")
                q_grp['Win Rate'] = q_grp['Win_Rate'].apply(lambda x:   f"{x:.0f}%")
                st.dataframe(q_grp[['Quality','Count','Total ₹','Avg ₹','Win Rate']],
                             use_container_width=True, hide_index=True)
                fig_q = px.bar(q_grp, x='Quality', y='Avg_PnL', color='Avg_PnL',
                                color_continuous_scale='RdYlGn', color_continuous_midpoint=0,
                                labels={'Avg_PnL':'Average P&L per Trade (₹)'})
                fig_q.update_layout(height=260, margin=dict(t=10,l=0,r=0,b=0),
                                     paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                                     xaxis=dict(gridcolor="#1e3a5f"), yaxis=dict(gridcolor="#1e3a5f"),
                                     font=dict(color="#c9d1d9"))
                st.plotly_chart(fig_q, use_container_width=True)
            else:
                st.info("No Quality column found. Grade your trades in the Journal to unlock this view.")

            section("Win/Loss Streak Analysis")
            pnls_chron = df_closed.sort_values('ExitDate')['PnL'].values
            if len(pnls_chron) > 0:
                max_win_streak = max_loss_streak = curr_w = curr_l = 0
                for p in pnls_chron:
                    if p > 0:
                        curr_w += 1; curr_l = 0
                        max_win_streak = max(max_win_streak, curr_w)
                    else:
                        curr_l += 1; curr_w = 0
                        max_loss_streak = max(max_loss_streak, curr_l)
                s1, s2 = st.columns(2, gap="small")
                s1.metric("Max Win Streak",  f"{max_win_streak} trades")
                s2.metric("Max Loss Streak", f"{max_loss_streak} trades",
                           delta=f"{'⚠️ Review setups' if max_loss_streak >= 3 else 'Manageable'}",
                           delta_color="off" if max_loss_streak >= 3 else "normal")

        # ── Attribution tab (Phase 0 engine) ───────────────────────────────────
        with _ap5:
            section("Performance Attribution — Realized P&L Decomposition")
            try:
                import performance_attribution as _pa
                _res = _pa.run_attribution()
                _q = _res.get("quality", {})

                # Data-quality / honesty line
                _dq = []
                _dq.append(f"{_q.get('attributable', 0)} attributable / {_q.get('total_closed', 0)} closed")
                if _q.get("cash_excluded"):
                    _dq.append(f"{_q['cash_excluded']} cash-park excluded ({', '.join(_q.get('cash_excluded_symbols', []))})")
                _dropped = {k: v for k, v in _q.get("dropped", {}).items() if v}
                if _dropped:
                    _dq.append("quarantined: " + ", ".join(f"{v} {k.replace('_',' ')}" for k, v in _dropped.items()))
                if _q.get("signal_snapshot_coverage"):
                    _dq.append(_q["signal_snapshot_coverage"])
                st.caption("🧪 Data quality — " + "  •  ".join(_dq))

                if not _res.get("ok"):
                    st.info(_res.get("message", "No attributable closed trades yet."))
                else:
                    _h = _res["headline"]
                    _pf = "∞" if _h["profit_factor"] == float("inf") else f"{_h['profit_factor']:.2f}"
                    a1, a2, a3 = st.columns(3, gap="small")
                    a1.metric("Trades (alpha-only)", str(_h["n_trades"]))
                    a2.metric("Win Rate",            f"{_h['win_rate_pct']}%")
                    a3.metric("Total Realized",      f"₹{format_inr_int(_h['total_realized'])}")
                    a4, a5, a6 = st.columns(3, gap="small")
                    a4.metric("Expectancy/Trade",    f"₹{format_inr_int(_h['expectancy'])}")
                    a5.metric("Profit Factor",       _pf)
                    a6.metric("Avg ROI/Trade",       f"{_h['avg_roi_pct']}%")

                    # Per-dimension tables — lead with the entry-signal drivers.
                    _labels = dict(_pa.DIMENSIONS)
                    _order = ["setup", "stage_label", "alpha_band", "rs_band", "conv_band",
                              "sector", "trade_type", "hold_bucket", "exit_reason", "trade_quality", "system"]
                    for _col in _order:
                        _t = _res["tables"].get(_col)
                        if _t is None or _t.empty:
                            continue
                        section(f"By {_labels.get(_col, _col)}")
                        _disp = _t[["bucket", "n_trades", "win_rate_pct", "total_pnl",
                                    "expectancy", "profit_factor", "contribution_pct"]].copy()
                        _disp.columns = ["Bucket", "n", "Win %", "Total ₹", "Exp ₹", "PF", "Contrib %"]
                        _disp["Total ₹"] = _disp["Total ₹"].map(lambda v: format_inr_int(v))
                        _disp["Exp ₹"]   = _disp["Exp ₹"].map(lambda v: format_inr_int(v))
                        st.dataframe(_disp, use_container_width=True, hide_index=True)
            except Exception as _ae:
                st.error(f"Attribution failed: {_ae}")

        # ── Export ─────────────────────────────────────────────────────────────
        st.markdown("---")
        section("Export")
        _ex1, _ex2 = st.columns(2, gap="small")
        with _ex1:
            _csv_data = df_closed.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Trade Log (CSV)",
                data=_csv_data,
                file_name=f"Trade_Log_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv", use_container_width=True, key="ap_dl_csv",
            )
        with _ex2:
            if _GEMINI_OK:
                if st.button("🤖 Generate + Download AI Review", use_container_width=True, key="ap_ai_dl"):
                    with st.spinner("Generating AI portfolio review…"):
                        try:
                            _ap_analytics = compute_portfolio_analytics(df_closed, total_cap)
                            _ap_review    = generate_portfolio_review(df_closed, _ap_analytics)
                            st.session_state["ap_ai_review"] = _ap_review
                        except Exception as _are:
                            st.error(f"AI review failed: {_are}")
                if st.session_state.get("ap_ai_review"):
                    st.download_button(
                        "📥 Save AI Review (.txt)",
                        data=st.session_state["ap_ai_review"],
                        file_name=f"AI_Trade_Review_{datetime.now().strftime('%Y%m%d')}.txt",
                        mime="text/plain", use_container_width=True, key="ap_ai_dl2",
                    )

# ════════════════════════════════════════════════════════════════════════════
#  MISS-5: SIGNAL BACKTEST LAB
# ════════════════════════════════════════════════════════════════════════════
elif page == 'BACKTEST':
    st.markdown('<div class="page-title">📈 Signal Backtest Lab</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-desc">Forward-return analysis of Recovery Screener signals — '
        'measures actual price outcomes at 10/21/30/60-day horizons via yfinance</div>',
        unsafe_allow_html=True,
    )

    # ── Signal source ─────────────────────────────────────────────────────────
    _REC_CSV = os.path.join(_APP_DIR, "Recovery_Screener_Results.csv")
    section("Signal Source")
    src_mode = st.radio(
        "Source",
        ["Current Recovery_Screener_Results.csv", "Upload historical signals CSV"],
        horizontal=True, label_visibility="collapsed",
    )

    df_src = None
    if src_mode == "Current Recovery_Screener_Results.csv":
        if os.path.exists(_REC_CSV):
            try:
                df_src = pd.read_csv(_REC_CSV)
                st.caption(f"Loaded **{len(df_src)} rows** from Recovery_Screener_Results.csv")
            except Exception as e:
                st.error(f"Error reading CSV: {e}")
        else:
            st.warning(
                "⚠️  Recovery_Screener_Results.csv not found in the app directory.  "
                "Run the Recovery Screener at least once, or upload a historical CSV."
            )
    else:
        up_file = st.file_uploader(
            "Upload signal CSV (required columns: Symbol, Signal_Date — optionally Edge)",
            type="csv", key="bt_upload",
        )
        if up_file:
            try:
                df_src = pd.read_csv(up_file)
                st.caption(f"Uploaded: **{len(df_src)} rows**")
            except Exception as e:
                st.error(f"Error reading uploaded CSV: {e}")

    if df_src is not None and not df_src.empty:
        # ── Parse Signal_Date ─────────────────────────────────────────────────
        if "Signal_Date" in df_src.columns:
            df_src["Signal_Date"] = pd.to_datetime(df_src["Signal_Date"], errors="coerce")
        else:
            df_src["Signal_Date"] = pd.NaT

        df_valid = df_src.dropna(subset=["Signal_Date"]).copy()

        if df_valid.empty:
            st.info(
                "No rows with a valid Signal_Date found.  "
                "The CSV must have a Signal_Date column in YYYY-MM-DD format."
            )
        else:
            # ── Configuration ─────────────────────────────────────────────────
            section("Backtest Configuration")
            bc1, bc2, bc3 = st.columns(3, gap="small")
            hold_days = bc1.selectbox(
                "Holding Period (days)", [10, 21, 30, 45, 60], index=1,
                help="Calendar days from signal date to measure the exit return",
            )

            edge_choices = sorted(df_valid["Edge"].dropna().unique().tolist()) if "Edge" in df_valid.columns else []
            edge_filter = bc2.multiselect(
                "Edge Filter", edge_choices,
                default=[], placeholder="All edges",
            )

            earliest = (datetime.today() - timedelta(days=365)).date()
            min_date = bc3.date_input(
                "Earliest signal date",
                value=max(df_valid["Signal_Date"].min().date(), earliest),
                help="Exclude signals older than this date",
            )

            today = pd.Timestamp(datetime.today().date())
            cutoff = today - pd.Timedelta(days=hold_days)

            df_bt = df_valid[df_valid["Signal_Date"] >= pd.Timestamp(min_date)].copy()
            df_bt = df_bt[df_bt["Signal_Date"] <= cutoff].copy()
            if edge_filter:
                df_bt = df_bt[df_bt["Edge"].isin(edge_filter)]

            st.caption(
                f"**{len(df_bt)} signals** eligible for {hold_days}d backtest  "
                f"(signal date between {min_date} and "
                f"{cutoff.strftime('%Y-%m-%d')})"
            )

            if len(df_bt) == 0:
                st.warning(
                    "No eligible signals found.  "
                    "Try lowering 'Earliest signal date' or reducing the holding period."
                )
            else:
                if st.button("▶  Run Backtest", type="primary", key="run_bt"):
                    # Inline cache — 24h TTL since historical data does not change
                    @st.cache_data(ttl=86400, show_spinner=False)
                    def _fetch_bt_return(symbol: str, sig_date_str: str, hold_d: int) -> "float | None":
                        """Fetch entry price at signal date and exit price at hold_d calendar days later."""
                        try:
                            sig_dt  = pd.to_datetime(sig_date_str)
                            end_buf = min(
                                sig_dt + pd.Timedelta(days=hold_d + 20),
                                pd.Timestamp.today() + pd.Timedelta(days=1),
                            )
                            import data_provider as dp
                            df_px = dp.fetch_ohlcv(
                                symbol,
                                start_date=sig_dt.strftime("%Y-%m-%d"),
                                end_date=end_buf.strftime("%Y-%m-%d"),
                                interval="1d", auto_adjust=True, use_cache=True,
                            )
                            if df_px.empty or len(df_px) < 2:
                                return None
                            entry = float(df_px["Close"].iloc[0])
                            # Exit: closest trading session to (signal_date + hold_d calendar days)
                            exit_target = sig_dt + pd.Timedelta(days=hold_d)
                            exit_idx = df_px.index.searchsorted(exit_target)
                            exit_idx = min(exit_idx, len(df_px) - 1)
                            exit_p = float(df_px["Close"].iloc[exit_idx])
                            return round((exit_p - entry) / entry * 100, 2) if entry > 0 else None
                        except Exception:
                            return None

                    prog = st.progress(0, text="Fetching price data from yfinance ...")
                    returns = []
                    n = len(df_bt)
                    import time as _t
                    for i, (_, row) in enumerate(df_bt.iterrows()):
                        sym   = str(row.get("Symbol", "")).strip().upper()
                        sdate = row["Signal_Date"].strftime("%Y-%m-%d")
                        ret   = _fetch_bt_return(sym, sdate, hold_days)
                        returns.append(ret)
                        prog.progress((i + 1) / n, text=f"Fetching {sym}  [{i+1}/{n}]")
                        _t.sleep(0.15)
                    prog.empty()

                    df_bt_result = df_bt.copy()
                    df_bt_result["Return_%"] = returns
                    st.session_state["_bt_results"] = df_bt_result
                    st.session_state["_bt_hold"]    = hold_days
                    st.rerun()

                # ── Display results ───────────────────────────────────────────
                if (
                    "_bt_results" in st.session_state
                    and st.session_state.get("_bt_hold") == hold_days
                ):
                    df_res  = st.session_state["_bt_results"]
                    df_done = df_res.dropna(subset=["Return_%"]).copy()

                    if df_done.empty:
                        st.warning(
                            "No return data fetched.  "
                            "Check symbol names, signal dates, and internet connection."
                        )
                    else:
                        hold_used = st.session_state["_bt_hold"]
                        section(f"Results — {hold_used}-day Hold  ({len(df_done)} signals)")

                        rets = df_done["Return_%"]
                        r1, r2, r3, r4, r5 = st.columns(5, gap="small")
                        r1.metric("Win Rate",      f"{(rets > 0).mean() * 100:.0f}%")
                        r2.metric("Avg Return",    f"{rets.mean():.1f}%",
                                   delta="▲" if rets.mean() > 0 else "▼", delta_color="off")
                        r3.metric("Median Return", f"{rets.median():.1f}%")
                        r4.metric("Best Signal",   f"{rets.max():.1f}%")
                        r5.metric("Worst Signal",  f"{rets.min():.1f}%")

                        # ── By edge breakdown ─────────────────────────────────
                        if "Edge" in df_done.columns and df_done["Edge"].notna().any():
                            section("By Edge Type")
                            edge_grp = (
                                df_done.groupby("Edge")["Return_%"]
                                .agg(
                                    Count="count",
                                    Win_Rate=lambda x: f"{(x > 0).mean() * 100:.0f}%",
                                    Avg_Return=lambda x: f"{x.mean():.1f}%",
                                    Median=lambda x: f"{x.median():.1f}%",
                                    Best=lambda x: f"{x.max():.1f}%",
                                )
                                .reset_index()
                            )
                            st.dataframe(edge_grp, use_container_width=True, hide_index=True)

                        # ── Distribution histogram ────────────────────────────
                        section("Return Distribution")
                        fig_hist = px.histogram(
                            df_done, x="Return_%", nbins=30,
                            color_discrete_sequence=["#58a6ff"],
                            labels={"Return_%": f"Return % at {hold_used}d"},
                        )
                        fig_hist.add_vline(x=0, line_dash="dash", line_color="#ff4b4b", line_width=1)
                        fig_hist.add_vline(
                            x=float(rets.mean()), line_dash="dot", line_color="#00f260",
                            line_width=1,
                            annotation_text=f"Mean {rets.mean():.1f}%",
                            annotation_font_color="#00f260",
                        )
                        fig_hist.update_layout(
                            height=260, margin=dict(t=10, l=0, r=0, b=0),
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                            xaxis=dict(title=f"Return % ({hold_used}d)", gridcolor="#1e3a5f"),
                            yaxis=dict(title="Signal Count", gridcolor="#1e3a5f"),
                            font=dict(color="#c9d1d9"),
                        )
                        st.plotly_chart(fig_hist, use_container_width=True)

                        # ── Scatter: return vs signal age ─────────────────────
                        if "Age_Days" in df_done.columns and df_done["Age_Days"].notna().any():
                            section("Return vs Signal Age at Entry")
                            fig_sc = px.scatter(
                                df_done, x="Age_Days", y="Return_%",
                                color="Edge" if "Edge" in df_done.columns else None,
                                hover_data=["Symbol"],
                                labels={"Age_Days": "Signal Age (days)",
                                        "Return_%": f"Return % at {hold_used}d"},
                                color_discrete_sequence=px.colors.qualitative.Set2,
                            )
                            fig_sc.add_hline(y=0, line_dash="dash", line_color="#ff4b4b", line_width=1)
                            fig_sc.update_layout(
                                height=260, margin=dict(t=10, l=0, r=0, b=0),
                                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                                xaxis=dict(gridcolor="#1e3a5f"),
                                yaxis=dict(gridcolor="#1e3a5f"),
                                font=dict(color="#c9d1d9"),
                            )
                            st.plotly_chart(fig_sc, use_container_width=True)

                        # ── Signal equity curve (sorted by signal date) ───────
                        section("Cumulative Average Return (by Signal Date)")
                        df_ec = df_done.sort_values("Signal_Date").copy()
                        df_ec["Cum_Avg"] = df_ec["Return_%"].expanding().mean()
                        fig_ec = px.line(
                            df_ec, x="Signal_Date", y="Cum_Avg",
                            labels={"Signal_Date": "Signal Date",
                                    "Cum_Avg": "Cumulative Avg Return %"},
                            color_discrete_sequence=["#00f260"],
                        )
                        fig_ec.add_hline(y=0, line_dash="dash", line_color="#ff4b4b", line_width=1)
                        fig_ec.update_layout(
                            height=240, margin=dict(t=10, l=0, r=0, b=0),
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                            xaxis=dict(gridcolor="#1e3a5f"),
                            yaxis=dict(gridcolor="#1e3a5f"),
                            font=dict(color="#c9d1d9"),
                        )
                        st.plotly_chart(fig_ec, use_container_width=True)

                        # ── Full trade log ────────────────────────────────────
                        section("Signal Backtest Log")
                        log_cols = ["Symbol", "Signal_Date", "Return_%"]
                        if "Edge" in df_done.columns:
                            log_cols.insert(1, "Edge")
                        if "Age_Days" in df_done.columns:
                            log_cols.append("Age_Days")
                        df_log = df_done[log_cols].copy()
                        df_log["Signal_Date"] = df_log["Signal_Date"].dt.strftime("%Y-%m-%d")
                        df_log["Result"] = df_log["Return_%"].apply(
                            lambda x: f"{'▲ WIN' if x >= 0 else '▼ LOSS'}  {abs(x):.1f}%"
                        )
                        st.dataframe(
                            df_log.sort_values("Return_%", ascending=False).drop(columns=["Return_%"]),
                            use_container_width=True, hide_index=True,
                        )

                        # Download
                        csv_out = df_done.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            "⬇️  Download Backtest Results CSV",
                            data=csv_out,
                            file_name=f"Backtest_{hold_used}d_{datetime.today().strftime('%Y%m%d')}.csv",
                            mime="text/csv",
                        )


# ══════════════════════════════════════════════════════════════════════════════
#  v4.0 — PRE-MARKET INTELLIGENCE HUB
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'PRE-MARKET':
    st.markdown('<div class="page-title">🌅 Pre-Market Intelligence Hub</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Global Overnight Pulse // FII/DII // VIX // Calendar // AI Brief — 8:30 AM IST</div>', unsafe_allow_html=True)

    # ── Shared: latest report meta ──────────────────────────────────────────
    _latest_pm = {}
    if _SCHED_OK:
        try: _latest_pm = load_latest_report("premarket")
        except Exception: pass

    _last_upd = _latest_pm.get("generated_at", "Not yet generated")
    c_refresh, c_meta = st.columns([1, 5])
    with c_refresh:
        if st.button("🔄 Refresh Now", key="pm_refresh", type="primary"):
            with st.spinner("Fetching data and generating report..."):
                try:
                    if _SCHED_OK:
                        trigger_manual_report("premarket")
                        st.toast("✅ Pre-market report refreshed!", icon="🌅")
                        st.rerun()
                    else:
                        st.error("Scheduler module not available")
                except Exception as _e:
                    st.error(f"Refresh failed: {_e}")
    with c_meta:
        st.caption(f"🕐 Last updated: {_last_upd}  |  Scheduler auto-runs at 8:30 AM IST Mon–Fri")

    # GIFT Nifty pill — canonical overnight indicator for cash Nifty.
    # Sourced from investing.com (yfinance has no working GIFT/SGX symbol).
    try:
        from market_data_hub import fetch_gift_nifty as _fgn_pm
        _gn = _fgn_pm() or {}
        if _gn:
            _gn_chg = _gn.get("change_pct", 0)
            _gn_col = "#00f260" if _gn_chg >= 0 else "#ff4b4b"
            _gn_arrow = "▲" if _gn_chg >= 0 else "▼"
            st.markdown(
                f'<div style="display:flex;gap:14px;align-items:center;margin:6px 0 10px 0;'
                f'padding:8px 14px;background:rgba(20,30,48,0.6);border-left:3px solid {_gn_col};'
                f'border-radius:6px;font-family:JetBrains Mono,monospace">'
                f'<span style="color:#5a8a9f;font-size:0.7rem;letter-spacing:1px">GIFT NIFTY</span>'
                f'<span style="color:#e6edf3;font-size:1.05rem;font-weight:700">{_gn.get("close",0):,.2f}</span>'
                f'<span style="color:{_gn_col};font-size:0.85rem">{_gn_arrow} {_gn_chg:+.2f}%</span>'
                f'<span style="color:#5a8a9f;font-size:0.65rem">O {_gn.get("open",0):,.0f} · H {_gn.get("high",0):,.0f} · L {_gn.get("low",0):,.0f}</span>'
                f'<span style="color:#5a8a9f;font-size:0.62rem;margin-left:auto">as of {_gn.get("date","")}</span>'
                f'</div>', unsafe_allow_html=True
            )
    except Exception as _gn_e:
        st.caption(f"GIFT Nifty unavailable: {_gn_e}")

    # Direct links to external pre-market analysis on ET Prime + MC Pro.
    # The paid news grid is in the ET + MC Pro tab below; these are
    # one-click shortcuts to the publisher's curated pre-market sections
    # for cases when the user wants the full editorial article.
    st.markdown(
        '<div style="display:flex;gap:10px;align-items:center;margin:0 0 10px 0;'
        'padding:6px 12px;background:rgba(20,30,48,0.3);border-radius:6px;'
        'font-family:JetBrains Mono,monospace;font-size:0.7rem">'
        '<span style="color:#5a8a9f;letter-spacing:1px">EXTERNAL ANALYSIS</span>'
        '<a href="https://economictimes.indiatimes.com/markets/pre-open-market" target="_blank" '
        'style="color:#ff7b72;text-decoration:none;font-weight:600">ET · Pre-Open Market →</a>'
        '<a href="https://economictimes.indiatimes.com/prime/markets" target="_blank" '
        'style="color:#ff7b72;text-decoration:none;font-weight:600">ET Prime · Markets →</a>'
        '<a href="https://www.moneycontrol.com/markets/indian-indices/" target="_blank" '
        'style="color:#58a6ff;text-decoration:none;font-weight:600">MC · Indices →</a>'
        '<a href="https://www.moneycontrol.com/news/business/markets/" target="_blank" '
        'style="color:#58a6ff;text-decoration:none;font-weight:600">MC Pro · Markets →</a>'
        '</div>', unsafe_allow_html=True
    )

    st.markdown("---")
    _pm1, _pm2, _pm3, _pm4, _pm5 = st.tabs([
        "📋 Brief", "🌍 Global", "📅 Calendar", "📐 Options", "💎 ET + MC Pro"
    ])

    with _pm1:
        section("AI Pre-Market Brief — Full Report")
        st.caption(
            "Canonical location for the daily AI briefing (single source of truth). "
            "Generated 8:30 AM IST automatically by the scheduler, or click **Refresh Now** to force. "
            "A 300-word snippet of this report is mirrored on **📊 DASHBOARD** for quick context "
            "the moment you land there."
        )
        _brief_text = _latest_pm.get("text")
        if _brief_text:
            _render_ai_report(_brief_text, header_color="#58a6ff")
        else:
            st.info("No pre-market report yet. Click **Refresh Now** to generate one.")
            if _GEMINI_OK and _HUB_OK:
                if st.button("⚡ Generate Now", key="pm_gen_now", type="primary"):
                    with st.spinner("Generating AI pre-market brief..."):
                        try:
                            snap = build_premarket_snapshot()
                            brief = generate_premarket_brief(snap)
                            _render_ai_report(brief, header_color="#58a6ff")
                        except Exception as _e:
                            st.error(f"Generation failed: {_e}")

    with _pm2:
        section("Global Overnight Pulse")
        if not _HUB_OK:
            st.warning("⚠️ market_data_hub module not available. Please check installation.")
        else:
            with st.spinner("Fetching global market data..."):
                try:
                    _global = fetch_global_overview()
                except Exception as _e:
                    st.error(f"Data fetch error: {_e}"); _global = {}

            if _global:
                _indices  = _global.get("indices", {})
                _comms    = _global.get("commodities", {})
                _currs    = _global.get("currencies", {})
                _bonds    = _global.get("bonds", {})
                _fetched  = _global.get("fetched_at", "")

                st.caption(f"Data fetched at: {_fetched} IST")

                section("Equity Indices")
                _americas = {k:v for k,v in _indices.items() if k in ["S&P 500","NASDAQ 100","Dow Jones","US VIX"]}
                _europe   = {k:v for k,v in _indices.items() if k in ["DAX","FTSE 100"]}
                _asia     = {k:v for k,v in _indices.items() if k in ["Nifty 50","India VIX","GIFT Nifty","Nikkei 225","Hang Seng"]}

                _reg_cols = st.columns(3, gap="medium")
                for _reg_col, _reg_name, _reg_data in zip(
                    _reg_cols, ["🌎 Americas","🌍 Europe","🌏 Asia-Pacific"],
                    [_americas, _europe, _asia]
                ):
                    with _reg_col:
                        st.markdown(f'<div class="section-sub-lbl">{_reg_name}</div>', unsafe_allow_html=True)
                        for _name, _dat in _reg_data.items():
                            if not _dat: continue
                            _chg  = _dat.get("change_pct", 0) or 0
                            _ltp  = _dat.get("ltp", 0) or 0
                            _col  = "#00f260" if _chg >= 0 else "#ff4b4b"
                            _arrow= "▲" if _chg >= 0 else "▼"
                            st.markdown(f"""
                            <div style="display:flex;justify-content:space-between;align-items:center;
                                        padding:5px 0;border-bottom:1px solid #1e3a5f;">
                              <span style="font-family:'Inter',sans-serif;font-size:0.82rem;color:#c9d1d9;">{_name}</span>
                              <span style="font-family:'JetBrains Mono',monospace;font-size:0.82rem;color:{_col};">
                                {_arrow} {abs(_chg):.2f}%</span>
                            </div>""", unsafe_allow_html=True)

                st.markdown("---")
                _cc1, _cc2 = st.columns(2, gap="medium")

                with _cc1:
                    section("Commodities")
                    for _name, _dat in _comms.items():
                        if not _dat: continue
                        _chg = _dat.get("change_pct", 0) or 0
                        _ltp = _dat.get("ltp", 0) or 0
                        _col = "#00f260" if _chg >= 0 else "#ff4b4b"
                        st.markdown(f"""
                        <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1e3a5f;">
                          <span style="font-size:0.82rem;color:#c9d1d9;">{_name}</span>
                          <span style="font-family:'JetBrains Mono',monospace;font-size:0.82rem;color:{_col};">
                            {_ltp:.2f} ({'+' if _chg>=0 else ''}{_chg:.1f}%)</span>
                        </div>""", unsafe_allow_html=True)

                with _cc2:
                    section("Currencies & Bonds")
                    for _name, _dat in {**_currs, **_bonds}.items():
                        if not _dat: continue
                        _chg = _dat.get("change_pct", 0) or 0
                        _ltp = _dat.get("ltp", 0) or 0
                        _col = "#00f260" if _chg >= 0 else "#ff4b4b"
                        if _name == "USD/INR": _col = "#ff4b4b" if _chg > 0 else "#00f260"
                        st.markdown(f"""
                        <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1e3a5f;">
                          <span style="font-size:0.82rem;color:#c9d1d9;">{_name}</span>
                          <span style="font-family:'JetBrains Mono',monospace;font-size:0.82rem;color:{_col};">
                            {_ltp:.4f} ({'+' if _chg>=0 else ''}{_chg:.2f}%)</span>
                        </div>""", unsafe_allow_html=True)

    with _pm3:
        section("Economic & Events Calendar")
        if _HUB_OK:
            # Inline "Fetch Live" button — calls investing.com (country=India,
            # timezone=IST) and rewrites economic_calendar.json with current
            # events + Previous/Forecast/Actual where available. The page-level
            # "Refresh Now" button now also runs this fetcher.
            _cal_btn_col, _cal_meta_col = st.columns([1, 5])
            with _cal_btn_col:
                if st.button("🔄 Fetch Live", key="cal_fetch_live", type="primary"):
                    try:
                        from market_data_hub import refresh_calendar_from_investing
                        with st.spinner("Pulling India events from investing.com…"):
                            _r = refresh_calendar_from_investing(days_ahead=14)
                        if _r.get("error"):
                            st.error(f"Fetch failed: {_r['error']}")
                        else:
                            st.toast(f"✅ Calendar refreshed — {_r['count']} events written",
                                     icon="📅")
                            st.rerun()
                    except Exception as _ce:
                        st.error(f"Refresh error: {_ce}")
            with _cal_meta_col:
                st.caption("Source: investing.com/economic-calendar · country=India · timezone=IST")

            try:
                # B13: surface staleness so users know the file is user-maintained
                try:
                    from market_data_hub import get_economic_calendar_status
                    _cal_status = get_economic_calendar_status()
                except Exception:
                    _cal_status = {"exists": False, "stale": True}
                if not _cal_status.get("exists"):
                    st.warning(
                        "📅 No `economic_calendar.json` found — the calendar is now "
                        "user-maintained (B13). Run "
                        "`python -c \"import market_data_hub; market_data_hub.seed_economic_calendar()\"` "
                        "to create a starter file, then edit the events list."
                    )
                elif _cal_status.get("stale"):
                    _age = _cal_status.get("age_days")
                    st.warning(
                        f"📅 Calendar last updated **{_cal_status.get('last_updated')}** "
                        f"({_age}d ago). Dates older than 30 days may be inaccurate — "
                        f"refresh `economic_calendar.json` and bump `last_updated`."
                    )
                else:
                    st.caption(
                        f"📅 Updated {_cal_status.get('last_updated')} · "
                        f"{_cal_status.get('future_count', 0)} upcoming · "
                        f"{_cal_status.get('event_count', 0)} total events"
                    )
                _cal = fetch_economic_calendar()
                if _cal:
                    _df_cal = pd.DataFrame(_cal)
                    _df_cal["date"] = pd.to_datetime(_df_cal["date"])
                    _df_cal = _df_cal.sort_values("date")

                    def _imp_color(imp):
                        return "#ff4b4b" if imp=="HIGH" else "#e3b341" if imp=="MEDIUM" else "#5a8a9f"

                    _cal_cols = st.columns([1,3,1,1,1,1], gap="small")
                    for _h, _c in zip(["Date","Event","Importance","Previous","Forecast","Actual"], _cal_cols):
                        _c.markdown(f'<div style="font-family:JetBrains Mono,monospace;font-size:0.58rem;color:#5a8a9f;letter-spacing:2px;text-transform:uppercase;">{_h}</div>', unsafe_allow_html=True)
                    st.markdown('<div style="border-bottom:1px solid #1e3a5f;margin:4px 0 8px 0;"></div>', unsafe_allow_html=True)

                    for _, _row in _df_cal.iterrows():
                        _c1,_c2,_c3,_c4,_c5,_c6 = st.columns([1,3,1,1,1,1], gap="small")
                        _c1.markdown(f'<div style="font-size:0.78rem;color:#8b949e;">{_row["date"].strftime("%d %b")}</div>', unsafe_allow_html=True)
                        _c2.markdown(f'<div style="font-size:0.82rem;color:#e6edf3;">{_row.get("event","")}</div>', unsafe_allow_html=True)
                        _imp = _row.get("importance","")
                        _c3.markdown(f'<div style="font-size:0.78rem;font-weight:600;color:{_imp_color(_imp)};">{_imp}</div>', unsafe_allow_html=True)
                        _c4.markdown(f'<div style="font-size:0.78rem;color:#8b949e;">{_row.get("previous","–")}</div>', unsafe_allow_html=True)
                        _c5.markdown(f'<div style="font-size:0.78rem;color:#adbac7;">{_row.get("forecast","–")}</div>', unsafe_allow_html=True)
                        _act = _row.get("actual","")
                        _act_col = "#e6edf3" if _act else "#3d5a6e"
                        _c6.markdown(f'<div style="font-size:0.78rem;color:{_act_col};">{_act if _act else "Pending"}</div>', unsafe_allow_html=True)
                else:
                    st.info("No calendar events available.")
            except Exception as _e:
                st.error(f"Calendar fetch error: {_e}")
        else:
            st.warning("market_data_hub not available.")

    with _pm4:
        section("Pre-Market Options Snapshot — Nifty")
        if _HUB_OK:
            try:
                _opts = fetch_nse_options_summary("NIFTY")

                # ── Determine display state ─────────────────────────────────
                _is_closed = _opts.get("_market_closed", False)
                _src       = _opts.get("_source", "live")
                _has_data  = bool(_opts.get("spot_price"))
                _msg       = _opts.get("_message", "")

                # ── Off-hours / fallback banner ─────────────────────────────
                if _is_closed and _has_data:
                    _cached_at = _opts.get("_cached_at_utc", "")
                    try:
                        _ca = datetime.fromisoformat(_cached_at.replace("Z", "+00:00"))
                        _ca_ist = _ca + timedelta(hours=5, minutes=30)
                        _ca_str = _ca_ist.strftime("%a %d %b %H:%M IST")
                    except Exception:
                        _ca_str = "earlier session"
                    st.info(
                        f"📁 **Showing last cached snapshot from {_ca_str}.** "
                        f"NSE markets are closed (weekend / outside 09:15–15:30 IST). "
                        f"Live data resumes next trading session."
                    )
                elif _is_closed and not _has_data:
                    st.warning(
                        "🕒 **NSE markets are closed and no cached snapshot exists yet.** "
                        "Open this tab during the next trading session (09:15–15:30 IST Mon–Fri) "
                        "to fetch and cache the first snapshot. After that, off-hours visits will "
                        "show the last good snapshot here."
                    )
                elif not _has_data and _msg:
                    st.warning(f"⚠️ {_msg}")
                elif "disk-cache (live error" in _src:
                    st.warning(
                        f"📁 Live fetch failed; showing last good cached snapshot. "
                        f"({_src})"
                    )

                if _has_data:
                    _o1,_o2,_o3,_o4 = st.columns(4, gap="small")
                    _o1.metric("PCR (OI)", f'{_opts.get("pcr_oi",0):.2f}',
                                help=">1.2 Bullish | <0.7 Bearish")
                    _o2.metric("PCR (Vol)", f'{_opts.get("pcr_vol",0):.2f}')
                    _o3.metric("Max Pain", f'{_opts.get("max_pain_strike","–")}')
                    _o4.metric("ATM IV", f'{_opts.get("atm_iv","–")}%' if _opts.get("atm_iv") else "–")

                    _o5,_o6,_o7,_o8 = st.columns(4, gap="small")
                    _o5.metric("Total Call OI", f'{_opts.get("total_call_oi",0):,.0f}')
                    _o6.metric("Total Put OI",  f'{_opts.get("total_put_oi",0):,.0f}')
                    _o7.metric("Call Wall",     f'{_opts.get("strongest_call_strike","–")}')
                    _o8.metric("Put Wall",      f'{_opts.get("strongest_put_strike","–")}')

                    _pcr = _opts.get("pcr_oi", 1.0)
                    if _pcr > 1.2:   _pcr_sig, _pcr_col = "🟢 BULLISH — heavy Put writing (market supported)", "#00f260"
                    elif _pcr < 0.7: _pcr_sig, _pcr_col = "🔴 BEARISH — heavy Call writing (market capped)", "#ff4b4b"
                    else:            _pcr_sig, _pcr_col = "🟡 NEUTRAL — balanced positioning", "#e3b341"
                    st.markdown(f'<div class="metric-card" style="margin-top:12px;">'
                                f'<div class="metric-label">PCR Signal</div>'
                                f'<div class="metric-value" style="color:{_pcr_col};font-size:0.88rem;">{_pcr_sig}</div>'
                                f'<div style="font-size:0.55rem;color:#5a8a9f;margin-top:4px;">Source: {_src} · As of: {_opts.get("fetched_at","–")}</div>'
                                f'</div>', unsafe_allow_html=True)
            except Exception as _e:
                st.warning(f"Options data unavailable: {_e}")
        else:
            st.warning("market_data_hub not available.")

    with _pm5:
        section("Pre-Market — ET Prime + Moneycontrol Pro")
        # Filter to pre-market / opening / overnight / GIFT Nifty themed items.
        # Loose, case-insensitive substring match — captures ET/MC pre-market
        # columns ("Stocks to watch", "Trade Setup", "Bulls Vs Bears", "GIFT Nifty
        # signals", "Opening Bell", etc.).
        _PM_KWS = [
            "pre-market", "premarket", "pre market",
            "stocks to watch", "stocks in focus", "trade setup", "trade idea",
            "opening bell", "gift nifty", "overnight", "morning brief",
            "f&o", "pre-open", "buy or sell", "stocks to buy",
            "bulls vs bears",
        ]
        _render_paid_news_grid(
            key_prefix="pm_paid",
            keyword_filter=_PM_KWS,
            default_limit=50,
            show_recos_only=False,
            caption=("Filtered to pre-market / opening / overnight headlines from your "
                     "ET Prime + MC Pro subscriptions. Use the **Source** dropdown to "
                     "isolate one outlet. Cards link out to the full article."),
        )


# ══════════════════════════════════════════════════════════════════════════════
#  v4.0 — POST-MARKET ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'POST-MARKET':
    st.markdown('<div class="page-title">🌙 Post-Market Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">EOD Market Summary // Breadth Recap // FII/DII Provisional // Top Movers — 4:30 PM IST</div>', unsafe_allow_html=True)

    _latest_po = {}
    if _SCHED_OK:
        try: _latest_po = load_latest_report("postmarket")
        except Exception: pass

    _last_upd_po = _latest_po.get("generated_at", "Not yet generated")
    c_ref2, c_meta2 = st.columns([1, 5])
    with c_ref2:
        if st.button("🔄 Refresh Now", key="po_refresh", type="primary"):
            with st.spinner("Fetching EOD data and generating summary..."):
                try:
                    if _SCHED_OK:
                        trigger_manual_report("postmarket")
                        st.toast("✅ Post-market report refreshed!", icon="🌙")
                        st.rerun()
                    else:
                        st.error("Scheduler module not available")
                except Exception as _e:
                    st.error(f"Refresh failed: {_e}")
    with c_meta2:
        st.caption(f"🕐 Last updated: {_last_upd_po}  |  Scheduler auto-runs at 4:30 PM IST Mon–Fri")

    # GIFT Nifty pill (same as Pre-Market) — useful post-close too because it
    # ticks through overnight US/Asian sessions and frames the next open.
    try:
        from market_data_hub import fetch_gift_nifty as _fgn_po
        _gn2 = _fgn_po() or {}
        if _gn2:
            _c2 = _gn2.get("change_pct", 0)
            _col2 = "#00f260" if _c2 >= 0 else "#ff4b4b"
            _ar2 = "▲" if _c2 >= 0 else "▼"
            st.markdown(
                f'<div style="display:flex;gap:14px;align-items:center;margin:6px 0 10px 0;'
                f'padding:8px 14px;background:rgba(20,30,48,0.6);border-left:3px solid {_col2};'
                f'border-radius:6px;font-family:JetBrains Mono,monospace">'
                f'<span style="color:#5a8a9f;font-size:0.7rem;letter-spacing:1px">GIFT NIFTY</span>'
                f'<span style="color:#e6edf3;font-size:1.05rem;font-weight:700">{_gn2.get("close",0):,.2f}</span>'
                f'<span style="color:{_col2};font-size:0.85rem">{_ar2} {_c2:+.2f}%</span>'
                f'<span style="color:#5a8a9f;font-size:0.65rem">O {_gn2.get("open",0):,.0f} · H {_gn2.get("high",0):,.0f} · L {_gn2.get("low",0):,.0f}</span>'
                f'<span style="color:#5a8a9f;font-size:0.62rem;margin-left:auto">as of {_gn2.get("date","")}</span>'
                f'</div>', unsafe_allow_html=True
            )
    except Exception as _gn_e2:
        st.caption(f"GIFT Nifty unavailable: {_gn_e2}")

    # External post-market analysis shortcuts (canonical EOD wrap pages)
    st.markdown(
        '<div style="display:flex;gap:10px;align-items:center;margin:0 0 10px 0;'
        'padding:6px 12px;background:rgba(20,30,48,0.3);border-radius:6px;'
        'font-family:JetBrains Mono,monospace;font-size:0.7rem">'
        '<span style="color:#5a8a9f;letter-spacing:1px">EXTERNAL ANALYSIS</span>'
        '<a href="https://economictimes.indiatimes.com/markets/stocks/news" target="_blank" '
        'style="color:#ff7b72;text-decoration:none;font-weight:600">ET · Closing Bell →</a>'
        '<a href="https://economictimes.indiatimes.com/prime/markets" target="_blank" '
        'style="color:#ff7b72;text-decoration:none;font-weight:600">ET Prime · Markets →</a>'
        '<a href="https://www.moneycontrol.com/markets/" target="_blank" '
        'style="color:#58a6ff;text-decoration:none;font-weight:600">MC · Market Wrap →</a>'
        '<a href="https://www.moneycontrol.com/news/business/markets/" target="_blank" '
        'style="color:#58a6ff;text-decoration:none;font-weight:600">MC Pro · Markets →</a>'
        '</div>', unsafe_allow_html=True
    )

    st.markdown("---")
    # Breadth tab removed on 19 May 2026: it ran a breadth-only regime classifier
    # ("BULL HEALTHY" when >55% of stocks > SMA50) that contradicted the composite
    # Market Regime ("Bear / Cash") in the top bar — same indicator name, two
    # incompatible definitions. The composite regime + the dedicated BREADTH page
    # already cover this surface; keeping a third panel here only confused things.
    _po1, _po3, _po4, _po5 = st.tabs([
        "📝 Summary", "💰 FII/DII", "📈 Movers", "💎 ET + MC Pro"
    ])

    with _po1:
        section("AI Post-Market Summary")
        _po_text = _latest_po.get("text")
        if _po_text:
            _render_ai_report(_po_text, header_color="#e3b341")
        else:
            st.info("No post-market report yet. Click **Refresh Now** or wait for 4:30 PM auto-run.")
            if _GEMINI_OK and _HUB_OK:
                if st.button("⚡ Generate Now", key="po_gen_now", type="primary"):
                    with st.spinner("Generating AI post-market summary..."):
                        try:
                            snap = build_postmarket_snapshot()
                            if _BREADTH_OK:
                                snap["breadth"] = calculate_breadth_metrics()
                                snap["breadth_regime"] = build_breadth_regime(snap["breadth"])
                            summary = generate_postmarket_summary(snap)
                            _render_ai_report(summary, header_color="#e3b341")
                        except Exception as _e:
                            st.error(f"Generation failed: {_e}")

    with _po3:
        section("FII/DII Provisional Data")
        if _HUB_OK:
            with st.spinner("Fetching FII/DII data..."):
                try: _fii_df2 = fetch_fii_dii_data()
                except Exception as _e: _fii_df2 = pd.DataFrame(); st.error(str(_e))

            if not _fii_df2.empty:
                _latest_fii = _fii_df2.iloc[-1]
                _f1,_f2,_f3,_f4 = st.columns(4, gap="small")
                _fn = float(_latest_fii.get("fii_net",0))
                _dn = float(_latest_fii.get("dii_net",0))
                _f1.metric("FII Net (latest)", f"₹{_fn:,.0f}Cr", delta_color="normal")
                _f2.metric("DII Net (latest)", f"₹{_dn:,.0f}Cr")
                _f3.metric("FII 5D Sum",
                           f"₹{_fii_df2['fii_net'].tail(5).sum():,.0f}Cr" if "fii_net" in _fii_df2 else "–")
                _f4.metric("DII 5D Sum",
                           f"₹{_fii_df2['dii_net'].tail(5).sum():,.0f}Cr" if "dii_net" in _fii_df2 else "–")

                try:
                    _fig_fii = go.Figure()
                    if "fii_net" in _fii_df2.columns:
                        _fig_fii.add_bar(x=_fii_df2["date"] if "date" in _fii_df2.columns else _fii_df2.index,
                                         y=_fii_df2["fii_net"],
                                         name="FII Net (₹Cr)",
                                         marker_color=["#00f260" if v>=0 else "#ff4b4b" for v in _fii_df2["fii_net"]])
                    if "dii_net" in _fii_df2.columns:
                        _fig_fii.add_bar(x=_fii_df2["date"] if "date" in _fii_df2.columns else _fii_df2.index,
                                         y=_fii_df2["dii_net"],
                                         name="DII Net (₹Cr)",
                                         marker_color=["#58a6ff" if v>=0 else "#e3b341" for v in _fii_df2["dii_net"]])
                    _fig_fii.update_layout(
                        height=280, barmode="group",
                        margin=dict(t=10,l=0,r=0,b=0),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                        legend=dict(font=dict(size=10,color="#c9d1d9"),bgcolor="rgba(0,0,0,0)"),
                        xaxis=dict(gridcolor="#1e3a5f"), yaxis=dict(gridcolor="#1e3a5f",title="₹ Cr"),
                        font=dict(color="#c9d1d9")
                    )
                    st.plotly_chart(_fig_fii, use_container_width=True)
                except Exception: pass

                st.dataframe(_fii_df2.tail(30), use_container_width=True, hide_index=True)
            else:
                st.info("FII/DII data not available. NSE API may be down or data not yet released.")
        else:
            st.warning("market_data_hub not available.")

    with _po4:
        section("Today's Notable Movers")
        _mov_src = st.radio("Universe", ["📂 My Holdings", "📊 Nifty 50", "🔀 Both"],
                            horizontal=True, key="mov_src")

        # Build symbol list
        _mov_holding_syms = ([yf_symbol(s) for s in df_live_holdings["CleanSymbol"].tolist() if s]
                             if not df_live_holdings.empty else [])
        # Note: Infosys ticker is INFY.NS on Yahoo Finance, not INFOSYS.NS
        # (the latter returns 404 — was a typo that silently dropped Infy
        # from the universe and made non-N50 holdings look like leakage).
        _N50 = [
            "RELIANCE.NS","TCS.NS","HDFCBANK.NS","BHARTIARTL.NS","ICICIBANK.NS",
            "INFY.NS","SBIN.NS","HINDUNILVR.NS","ITC.NS","LT.NS",
            "KOTAKBANK.NS","AXISBANK.NS","BAJFINANCE.NS","MARUTI.NS","ASIANPAINT.NS",
            "TITAN.NS","SUNPHARMA.NS","ULTRACEMCO.NS","WIPRO.NS","ONGC.NS",
            "NESTLEIND.NS","POWERGRID.NS","NTPC.NS","HCLTECH.NS","TECHM.NS",
            "TATASTEEL.NS","JSWSTEEL.NS","TATAMOTORS.NS","M&M.NS","ADANIENT.NS",
            "ADANIPORTS.NS","COALINDIA.NS","BAJAJFINSV.NS","INDUSINDBK.NS","DRREDDY.NS",
            "CIPLA.NS","DIVISLAB.NS","EICHERMOT.NS","HEROMOTOCO.NS","APOLLOHOSP.NS",
            "BRITANNIA.NS","BPCL.NS","HINDALCO.NS","SHREECEM.NS","TATACONSUM.NS",
            "GRASIM.NS","SBILIFE.NS","HDFCLIFE.NS","PIDILITIND.NS","BAJAJ-AUTO.NS",
        ]

        if _mov_src == "📂 My Holdings":
            _mov_syms = _mov_holding_syms
        elif _mov_src == "📊 Nifty 50":
            _mov_syms = _N50
        else:
            _mov_syms = list(dict.fromkeys(_mov_holding_syms + _N50))  # deduplicated

        if _mov_syms:
            with st.spinner(f"Fetching price data for {len(_mov_syms)} symbols…"):
                try:
                    # C1 sweep: cached batch via data_provider
                    _mov_close = None
                    try:
                        import data_provider as _dp_mov
                        _bd_mov = _dp_mov.fetch_batch_ohlcv(_mov_syms, period="5d", interval="1d")
                        if _bd_mov:
                            _mov_close = pd.DataFrame({
                                (k if k.startswith("^") else f"{k}.NS"): df["Close"]
                                for k, df in _bd_mov.items() if "Close" in df.columns
                            })
                    except Exception as e:
                        logger.warning(f"Movers fetch: {e}")
                        _mov_close = None

                    _N50_set = set(_N50)
                    _hold_set = set(_mov_holding_syms)
                    _mov_rows = []
                    for _sym_yf in _mov_syms:
                        try:
                            _cl = (_mov_close[_sym_yf] if _sym_yf in _mov_close.columns
                                   else None)
                            if _cl is not None and len(_cl.dropna()) >= 2:
                                _today_c = float(_cl.dropna().iloc[-1])
                                _prev_c  = float(_cl.dropna().iloc[-2])
                                _chg     = (_today_c - _prev_c) / _prev_c * 100 if _prev_c else 0
                                _in_port = _sym_yf in _hold_set
                                _in_n50  = _sym_yf in _N50_set
                                # Source label makes Universe=Both transparent:
                                # the user can see whether a row is N50, a
                                # personal holding, or both at a glance.
                                if _in_port and _in_n50:
                                    _source = "N50 + Portfolio"
                                elif _in_n50:
                                    _source = "Nifty 50"
                                else:
                                    _source = "Portfolio"
                                _mov_rows.append({
                                    "Symbol":      _sym_yf.replace(".NS",""),
                                    "Close":       round(_today_c, 2),
                                    "Chg%":        round(_chg, 2),
                                    "Source":      _source,
                                    "In Portfolio": "✅" if _in_port else "",
                                })
                        except Exception:
                            pass

                    if _mov_rows:
                        _df_mov = pd.DataFrame(_mov_rows).sort_values("Chg%", ascending=False).reset_index(drop=True)
                        _df_mov["Signal"] = _df_mov["Chg%"].apply(
                            lambda x: "🚀 Strong" if x > 3 else "📈 Up" if x > 0 else "📉 Down" if x > -3 else "🔻 Weak")

                        _TOP_N = 10
                        _COLS  = ["Symbol","Close","Chg%","Signal","Source","In Portfolio"]

                        # Split on sign so a stock can't appear in BOTH lists.
                        # If the universe is small (e.g. 3 holdings) a simple
                        # head/tail split would overlap — filter by Chg% instead.
                        _df_gainers = (_df_mov[_df_mov["Chg%"] >= 0]
                                       .head(_TOP_N)[_COLS]
                                       .reset_index(drop=True))
                        _df_losers  = (_df_mov[_df_mov["Chg%"] < 0]
                                       .iloc[::-1]          # worst-first
                                       .head(_TOP_N)[_COLS]
                                       .reset_index(drop=True))

                        _mv_col1, _mv_col2 = st.columns(2, gap="medium")
                        with _mv_col1:
                            sub_label(f"🏆 Top Gainers ({len(_df_gainers)})")
                            if _df_gainers.empty:
                                st.info("No gainers today.")
                            else:
                                st.dataframe(_df_gainers, use_container_width=True, hide_index=True)
                        with _mv_col2:
                            sub_label(f"📉 Top Losers ({len(_df_losers)})")
                            if _df_losers.empty:
                                st.info("No losers today.")
                            else:
                                st.dataframe(_df_losers, use_container_width=True, hide_index=True)
                except Exception as _e:
                    st.error(f"Mover data error: {_e}")
        else:
            st.info("No symbols to scan. Load holdings via Dhan or select Nifty 50.")

    with _po5:
        section("Post-Market — ET Prime + Moneycontrol Pro")
        # Filter to EOD / closing / market-wrap / after-hours items.
        _PO_KWS = [
            "post-market", "postmarket", "post market",
            "closing bell", "market wrap", "market close", "closing",
            "eod", "end of day", "today's market", "todays market",
            "sensex closes", "nifty closes", "settles", "settled",
            "after market", "after-hours", "session ends", "wraps up",
            "today's top", "top gainers", "top losers", "movers",
        ]
        _render_paid_news_grid(
            key_prefix="po_paid",
            keyword_filter=_PO_KWS,
            default_limit=50,
            show_recos_only=False,
            caption=("Filtered to EOD / closing-bell / market-wrap headlines from your "
                     "ET Prime + MC Pro subscriptions. Cards are colour-coded by analyst "
                     "action (Buy / Hold / Sell). Cached 1h."),
        )

# ══════════════════════════════════════════════════════════════════════════════
#  v4.0 — MARKET BREADTH ENGINE
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'BREADTH':
    st.markdown('<div class="page-title">📈 Market Breadth Engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Nifty 500 Internals // A/D Ratio // McClellan // Stage Distribution // Sector Breadth</div>', unsafe_allow_html=True)

    _br0, _br1, _br2, _br3, _br4, _br5 = st.tabs(
        ["🎯 Regime", "🌊 Overview", "📈 Broad Market", "🏭 Sectors", "〰️ McClellan", "🗺️ Stage Map"]
    )

    if not _BREADTH_OK:
        st.error("❌ breadth_engine module not available. Please check installation.")
    else:
        # ── TAB 0 — MARKET REGIME (B3 + B4 + B8 + composite score) ─────────
        with _br0:
            section("Market Regime — Composite Score")
            st.caption(
                "Combines benchmark trend, breadth, distribution-day count, "
                "follow-through, and Zweig breadth thrust. "
                "Use as a top-level filter: at score ≥ 6 swing entries are "
                "supported; ≤ 3 favors defensive posture."
            )
            try:
                import market_regime as _mr
                # Reuse the breadth metrics from elsewhere on the page if available
                with st.spinner("Computing regime (downloads benchmark + breadth)..."):
                    _bm_for_regime = None
                    _ad_for_regime = None
                    try:
                        _bm_for_regime = calculate_breadth_metrics()
                    except Exception:
                        pass
                    try:
                        from breadth_engine import load_or_bootstrap_ad_history as _load_ad
                        _ad_for_regime = _load_ad(min_rows=40)
                    except Exception:
                        _ad_for_regime = None
                    _reg = _mr.compute_regime(_bm_for_regime, _ad_for_regime)

                _verdict_color = (
                    "#00f260" if _reg["score"] >= 6 else
                    "#e3b341" if _reg["score"] >= 4 else
                    "#ff4b4b"
                )
                st.markdown(f"""
                <div style="background:rgba(0,0,0,0.3);border:1px solid {_verdict_color};
                            border-radius:8px;padding:18px 24px;margin-bottom:20px;text-align:center;">
                  <div style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;
                              color:#5a8a9f;letter-spacing:3px;text-transform:uppercase;">Regime Score</div>
                  <div style="font-family:'Rajdhani',sans-serif;font-size:2.6rem;font-weight:700;
                              color:{_verdict_color};margin:4px 0;">{_reg['score']}/10</div>
                  <div style="font-family:'Rajdhani',sans-serif;font-size:1.2rem;color:{_verdict_color};">{_reg['verdict']}</div>
                  <div style="font-size:0.68rem;color:#5a8a9f;margin-top:6px;">
                      {_reg['benchmark']} @ {_reg['close']}  ·  SMA200 {_reg.get('sma200','—')}
                      ({'rising' if _reg.get('sma200_rising') else 'flat/falling'})
                      ·  computed {_reg['computed_at'][:16]}
                  </div>
                </div>""", unsafe_allow_html=True)

                _rcols = st.columns(3, gap="small")
                _dd = _reg["distribution"]
                _ft = _reg["follow_through"]
                _bt = _reg["breadth_thrust"]
                _rcols[0].metric(
                    "Distribution Days (25d)",
                    f"{_dd['count']}",
                    delta="STRESS" if _dd.get("stress") else "ok",
                    delta_color="inverse" if _dd.get("stress") else "normal",
                    help="≥5 in 25 sessions = institutional selling; cap new entries.",
                )
                _rcols[1].metric(
                    "Follow-Through",
                    "ACTIVE" if _ft.get("active") else "—",
                    delta=_ft.get("ft_date", "no signal") if _ft.get("active") else "no signal",
                    help="Bar 4–25 of a rally attempt closing up ≥1.7% on higher volume — O'Neil canonical re-entry signal.",
                )
                _rcols[2].metric(
                    "Breadth Thrust (Zweig)",
                    "ACTIVE" if _bt.get("active") else "—",
                    delta=f"EMA10={_bt.get('current_ema10','—')}",
                    help="EMA10 of A/(A+D) crossed ≤0.40→≥0.615 within 10 bars. Rare; very bullish.",
                )

                with st.expander("📋 Component Breakdown — what each gate measures"):
                    # Per user feedback (10 May 2026): the raw key/✓ table was
                    # cryptic. This version explains each component, the current
                    # reading vs threshold, and the role each plays in the regime
                    # composite score.
                    _comp = _reg.get("components", {})
                    _bm_local = _bm_for_regime if _bm_for_regime else {}
                    _above200_pct = _bm_local.get("above_sma200_pct", 0) if isinstance(_bm_local, dict) else 0
                    _above50_pct  = _bm_local.get("above_sma50_pct",  0) if isinstance(_bm_local, dict) else 0
                    _comp_meta = {
                        "above_sma200_rising": {
                            "label":   "% above SMA200 — Rising",
                            "desc":    "Pct of Nifty 500 trading above their 200-day SMA, AND that pct is improving. Confirms broad participation in any uptrend.",
                            "value":   f"{_above200_pct:.1f}%",
                            "thresh":  "≥ 50% & rising",
                            "weight":  "🟢 Bullish gate",
                        },
                        "breadth_above_50": {
                            "label":   "% above SMA50 — Strong",
                            "desc":    "Pct of Nifty 500 trading above their 50-day SMA. Short-term breadth — confirms recent uptrend strength.",
                            "value":   f"{_above50_pct:.1f}%",
                            "thresh":  "≥ 50%",
                            "weight":  "🟢 Bullish gate",
                        },
                        "dd_low": {
                            "label":   "Distribution Days — Low",
                            "desc":    "Distribution days = down ≥0.2% on higher volume. >5 in last 25 sessions = institutional selling pressure.",
                            "value":   f"{_dd.get('count', 0)} in last {_dd.get('window', 25)} days",
                            "thresh":  "≤ 5 days",
                            "weight":  "🛑 Risk filter (low = good)",
                        },
                        "no_death_cross": {
                            "label":   "No Death Cross",
                            "desc":    "Death cross = SMA50 crossing BELOW SMA200 on the index. Long-term bear signal. We require its absence.",
                            "value":   "Active" if not _comp.get("no_death_cross", True) else "Clear",
                            "thresh":  "Must be clear",
                            "weight":  "🛑 Hard regime gate",
                        },
                        "follow_through": {
                            "label":   "Follow-Through Day",
                            "desc":    "O'Neil canonical re-entry signal: bar 4–25 of a rally attempt closing up ≥1.7% on higher volume than the day before.",
                            "value":   _ft.get("ft_date", "no signal") if _ft.get("active") else "no signal",
                            "thresh":  "Within last 10 days",
                            "weight":  "🟢 Bull confirmation",
                        },
                        "breadth_thrust": {
                            "label":   "Breadth Thrust (Zweig)",
                            "desc":    "EMA10 of A/(A+D) ratio crosses from ≤0.40 to ≥0.615 within 10 bars. Very rare; historically the strongest broad-market reversal signal.",
                            "value":   f"EMA10 = {_bt.get('current_ema10', '—')}",
                            "thresh":  "Triggered ≤ 10 days ago",
                            "weight":  "🟢 Strong bull confirmation",
                        },
                    }
                    _comp_rows = []
                    for k, active in _comp.items():
                        meta = _comp_meta.get(k, {})
                        _comp_rows.append({
                            "Status":      "✅ Active" if active else "❌ Not Met",
                            "Component":   meta.get("label", k),
                            "Current":     meta.get("value", "—"),
                            "Required":    meta.get("thresh", "—"),
                            "Role":        meta.get("weight", "—"),
                            "Description": meta.get("desc", ""),
                        })
                    st.dataframe(
                        pd.DataFrame(_comp_rows),
                        hide_index=True, use_container_width=True,
                        column_config={
                            "Description": st.column_config.TextColumn(width="large"),
                        },
                    )
                    st.caption(f"**Distribution Day details:** {_dd.get('details','')}")
                    st.caption(f"**Follow-Through details:** {_ft.get('details','')}")
                    st.caption(f"**Breadth Thrust details:** {_bt.get('details','')}")

                if _dd.get("stress"):
                    st.warning(
                        f"⚠️ **Distribution stress detected** — {_dd['count']} distribution "
                        f"day(s) in last {_dd['window']} sessions "
                        f"(dates: {', '.join(_dd['dates'][-5:])}). "
                        "Consider pausing new positional entries until count drops."
                    )
                if _ft.get("active"):
                    st.success(
                        f"✅ **Follow-through day on {_ft['ft_date']}** "
                        f"(+{_ft['ft_gain_pct']}%, {_ft['days_since_ft']}d ago). "
                        "Re-entry green light per IBD methodology."
                    )
            except Exception as _mre:
                st.error(f"market_regime unavailable: {_mre}")

        with _br1:
            section("Breadth Overview — Nifty 500 Universe")
            with st.spinner("Calculating breadth metrics (may take 30–60s first run)..."):
                try:
                    _bm = calculate_breadth_metrics()
                except Exception as _be:
                    _bm = {}; st.error(f"Breadth calculation error: {_be}")

            if _bm:
                _regime_s = build_breadth_regime(_bm)
                _r_col = "#00f260" if "BULL" in _regime_s else "#ff4b4b" if "BEAR" in _regime_s else "#e3b341"
                st.markdown(f"""
                <div style="background:rgba(0,0,0,0.3);border:1px solid {_r_col};border-radius:8px;
                            padding:16px 24px;margin-bottom:20px;text-align:center;">
                  <div style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;color:#5a8a9f;letter-spacing:3px;text-transform:uppercase;">Breadth Regime</div>
                  <div style="font-family:'Rajdhani',sans-serif;font-size:2rem;font-weight:700;color:{_r_col};margin:4px 0;">{_regime_s}</div>
                  <div style="font-size:0.68rem;color:#5a8a9f;">{_bm.get("symbols_analyzed",0)} stocks analyzed | Updated: {_bm.get("calculated_at","")}</div>
                </div>""", unsafe_allow_html=True)

                _g1,_g2,_g3,_g4 = st.columns(4, gap="small")
                _g1.metric("Above SMA 50",  f"{_bm.get('above_sma50_pct',0):.1f}%",
                           help="% of Nifty 500 stocks above their 50-day moving average")
                _g2.metric("Above SMA 150", f"{_bm.get('above_sma150_pct',0):.1f}%",
                           help="% above 150-day MA — intermediate trend health")
                _g3.metric("Above SMA 200", f"{_bm.get('above_sma200_pct',0):.1f}%",
                           help="% above 200-day MA — long-term breadth")
                _g4.metric("Stage 2",       f"{_bm.get('stage2_pct',0):.1f}%",
                           help="% in confirmed Stage 2 (price > SMA150, SMA150 sloping up [30-Week MA])")

                _g5,_g6,_g7,_g8 = st.columns(4, gap="small")
                _g5.metric("New 52W Highs", str(_bm.get("new_52w_high_count",0)))
                _g6.metric("New 52W Lows",  str(_bm.get("new_52w_low_count",0)))
                _g7.metric("A/D Ratio",     f"{_bm.get('ad_ratio',0):.2f}",
                           help=">2.0 = Bullish thrust | <0.5 = Bearish pressure")
                _g8.metric("High/Low Ratio",f"{_bm.get('high_low_ratio',0):.2f}",
                           help=">0.7 = Healthy | <0.3 = Weak")

                _sma_data = {
                    "SMA 50":  _bm.get("above_sma50_pct",0),
                    "SMA 150": _bm.get("above_sma150_pct",0),
                    "SMA 200": _bm.get("above_sma200_pct",0),
                    "Stage 2": _bm.get("stage2_pct",0),
                }
                _fig_bar = go.Figure(go.Bar(
                    x=list(_sma_data.keys()), y=list(_sma_data.values()),
                    marker_color=["#00f260" if v>50 else "#e3b341" if v>30 else "#ff4b4b"
                                  for v in _sma_data.values()],
                    text=[f"{v:.1f}%" for v in _sma_data.values()], textposition="auto"
                ))
                _fig_bar.add_hline(y=50, line_dash="dot", line_color="#5a8a9f", line_width=1,
                                   annotation_text="50% neutral line")
                _fig_bar.update_layout(
                    height=260, margin=dict(t=10,l=0,r=0,b=0),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                    xaxis=dict(gridcolor="#1e3a5f"), yaxis=dict(gridcolor="#1e3a5f",range=[0,100]),
                    font=dict(color="#c9d1d9"), title_text="% Stocks Above Key Moving Averages"
                )
                st.plotly_chart(_fig_bar, use_container_width=True)
        with _br2:
            with st.spinner("Fetching broad market data..."):
                try:
                    _bm_df = get_broad_market_breadth()
                except Exception as _e:
                    _bm_df = pd.DataFrame(); st.error(str(_e))

            if not _bm_df.empty:
                def _stage_icon(s):
                    return "🟢" if "Stage 2" in str(s) else "🔴" if "Stage 4" in str(s) else "🟡"

                _bm_disp = _bm_df.copy()
                if "Stage" in _bm_disp.columns:
                    _bm_disp[""] = _bm_disp["Stage"].apply(_stage_icon)

                _total_n  = len(_bm_disp)
                section(f"Broad Market Indices — {_total_n} indices")

                # Reorder columns: Stage icon first, then key numbers including Daily%
                _col_order = ["", "Sector", "LTP", "Daily%", "Weekly%", "Monthly%",
                               "Stage", "SMA150D_slope"]
                _col_order = [c for c in _col_order if c in _bm_disp.columns]
                st.dataframe(_bm_disp[_col_order], use_container_width=True, hide_index=True,
                             height=min(40 + 35 * _total_n, 600))

                # ── Timeframe selector ────────────────────────────────────────
                _avail_periods = [c for c in ["Daily%","Weekly%","Monthly%"]
                                  if c in _bm_disp.columns]
                _bm_c1, _bm_c2 = st.columns([1, 5])
                with _bm_c1:
                    _bm_period = st.selectbox(
                        "Chart period", _avail_periods,
                        index=len(_avail_periods) - 1,   # default Monthly%
                        key="br_bm_period",
                    )
                _y_vals = _bm_disp[_bm_period] if _bm_period in _bm_disp.columns else []
                _x_vals = (_bm_disp["Sector"] if "Sector" in _bm_disp.columns else [])
                if len(_y_vals):
                    _fig_bm = go.Figure(go.Bar(
                        x=_x_vals, y=_y_vals,
                        marker_color=["#00f260" if v >= 0 else "#ff4b4b" for v in _y_vals],
                        text=[f"{v:+.1f}%" for v in _y_vals], textposition="auto"
                    ))
                    _fig_bm.update_layout(
                        height=280, margin=dict(t=10, l=0, r=0, b=0),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                        xaxis=dict(gridcolor="#1e3a5f", tickangle=-30),
                        yaxis=dict(gridcolor="#1e3a5f"),
                    )
                    st.plotly_chart(_fig_bm, use_container_width=True)

        with _br3:
            with st.spinner("Fetching sector data..."):
                try:
                    _sec_df = get_sector_breadth()
                except Exception as _e:
                    _sec_df = pd.DataFrame(); st.error(str(_e))

            if not _sec_df.empty:
                def _stage_icon(s):
                    return "🟢" if "Stage 2" in str(s) else "🔴" if "Stage 4" in str(s) else "🟡"

                _sec_disp = _sec_df.copy()
                if "Stage" in _sec_disp.columns:
                    _sec_disp[""] = _sec_disp["Stage"].apply(_stage_icon)

                # P1.3 (10 May 2026): sort by Stage priority (2 → 1 → 4 → 3) so Stage 2
                # sectors — your hunting grounds — float to the top. Within same stage,
                # tiebreak by Monthly% descending. Per user feedback (#8): "Expand
                # Sector count and sort them with Stage 2 on top".
                if "Stage" in _sec_disp.columns:
                    def _stage_priority(s):
                        s_str = str(s)
                        if "Stage 2" in s_str: return 0
                        if "Stage 1" in s_str: return 1
                        if "Stage 4" in s_str: return 2
                        if "Stage 3" in s_str: return 3
                        return 4
                    _sec_disp["_sp"] = _sec_disp["Stage"].apply(_stage_priority)
                    _sort_cols = ["_sp"]
                    if "Monthly%" in _sec_disp.columns:
                        _sort_cols.append("Monthly%")
                    _sec_disp = _sec_disp.sort_values(_sort_cols, ascending=[True] + [False]*(len(_sort_cols)-1)).drop(columns=["_sp"])

                # Section header with counts so trader sees at a glance how many
                # sectors are in each stage — drives macro-state read in 1 second.
                _stage2_n = int((_sec_disp.get("Stage", pd.Series(dtype=str)).astype(str).str.contains("Stage 2")).sum()) if "Stage" in _sec_disp.columns else 0
                _stage1_n = int((_sec_disp.get("Stage", pd.Series(dtype=str)).astype(str).str.contains("Stage 1")).sum()) if "Stage" in _sec_disp.columns else 0
                _stage4_n = int((_sec_disp.get("Stage", pd.Series(dtype=str)).astype(str).str.contains("Stage 4")).sum()) if "Stage" in _sec_disp.columns else 0
                _stage3_n = int((_sec_disp.get("Stage", pd.Series(dtype=str)).astype(str).str.contains("Stage 3")).sum()) if "Stage" in _sec_disp.columns else 0
                _total_n  = len(_sec_disp)
                section(f"Sector Breadth — {_total_n} sectors  ·  🟢 Stage 2: {_stage2_n}  ·  🟡 Stage 1: {_stage1_n}  ·  🔴 Stage 4: {_stage4_n}  ·  🟡 Stage 3: {_stage3_n}")

                # Reorder columns: Stage icon first, then key numbers including Daily%
                _col_order = ["", "Sector", "LTP", "Daily%", "Weekly%", "Monthly%",
                               "Stage", "SMA150D_slope"]
                _col_order = [c for c in _col_order if c in _sec_disp.columns]
                st.dataframe(_sec_disp[_col_order], use_container_width=True, hide_index=True,
                             height=min(40 + 35 * _total_n, 600))

                # ── Timeframe selector ────────────────────────────────────────
                _avail_periods = [c for c in ["Daily%","Weekly%","Monthly%"]
                                  if c in _sec_disp.columns]
                _br_c1, _br_c2 = st.columns([1, 5])
                with _br_c1:
                    _sec_period = st.selectbox(
                        "Chart period", _avail_periods,
                        index=len(_avail_periods) - 1,   # default Monthly%
                        key="br_sec_period",
                    )
                _y_vals = _sec_disp[_sec_period] if _sec_period in _sec_disp.columns else []
                _x_vals = (_sec_disp["Sector"].str.replace("Nifty ", "")
                           if "Sector" in _sec_disp.columns else [])
                if len(_y_vals):
                    _fig_sec = go.Figure(go.Bar(
                        x=_x_vals, y=_y_vals,
                        marker_color=["#00f260" if v >= 0 else "#ff4b4b" for v in _y_vals],
                        text=[f"{v:+.1f}%" for v in _y_vals], textposition="auto"
                    ))
                    _fig_sec.update_layout(
                        height=280, margin=dict(t=10, l=0, r=0, b=0),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                        xaxis=dict(gridcolor="#1e3a5f", tickangle=-30),
                        yaxis=dict(gridcolor="#1e3a5f"),
                        font=dict(color="#c9d1d9"),
                        title_text=f"{_sec_period} Change by Sector",
                    )
                    st.plotly_chart(_fig_sec, use_container_width=True)
            else:
                st.info("Sector breadth data unavailable.")

        with _br4:
            section("McClellan Oscillator")
            st.caption("Bootstraps 60 days of A/D history from yfinance on first run (~60–90s). "
                       "Subsequent runs load from cache. History grows daily via the scheduler.")

            # 10 May 2026: surface the last-persisted date so the user knows
            # whether the displayed Summation Index is fresh or weeks old.
            # Previously the metric showed +3078 with no date — that value was
            # from April 17 but looked current.
            try:
                import json as _json_mc
                if os.path.exists("mcclellan_state.json"):
                    with open("mcclellan_state.json") as _mcfh:
                        _mc_state = _json_mc.load(_mcfh)
                    _last_d = _mc_state.get("last_date", "?")
                    _last_msi = _mc_state.get("msi", 0)
                    import datetime as _dt_mc
                    try:
                        _last_dt = _dt_mc.datetime.strptime(_last_d, "%Y-%m-%d")
                        _age_days = (_dt_mc.datetime.now() - _last_dt).days
                        if _age_days > 7:
                            st.warning(f"⚠ Last calculated **{_last_d}** "
                                       f"({_age_days}d ago, MSI={_last_msi:+.0f}). "
                                       f"Click below to refresh — Summation Index "
                                       f"is currently a stale snapshot.")
                        else:
                            st.caption(f"Last calculated: **{_last_d}** "
                                       f"({_age_days}d ago, MSI={_last_msi:+.0f})")
                    except Exception:
                        st.caption(f"Last persisted state: {_last_d}, MSI={_last_msi:+.0f}")
            except Exception:
                pass

            if st.button("📊 Compute McClellan Oscillator", key="br_mcl_btn", type="primary"):
                with st.spinner("Loading A/D history — first run downloads 60 days of data for Nifty 500…"):
                    try:
                        from breadth_engine import (
                            load_or_bootstrap_ad_history, calculate_mcclellan,
                            calculate_breadth_thrust,
                        )
                        # force=True bypasses the on-disk cache so a manual
                        # click always refetches today's A/D. Without this the
                        # MSI state file's last_date never advances and the
                        # "Last calculated" banner stays frozen.
                        _ad_df = load_or_bootstrap_ad_history(min_rows=40, force=True)
                    except Exception as _mcl_e:
                        _ad_df = pd.DataFrame()
                        st.error(f"A/D history load failed: {_mcl_e}")

                if _ad_df.empty or len(_ad_df) < 10:
                    st.warning("Insufficient A/D history. Need at least 10 days — "
                               "run the breadth job daily to accumulate data.")
                else:
                    _mcl  = calculate_mcclellan(_ad_df)
                    _thr  = calculate_breadth_thrust(_ad_df)
                    _osc  = _mcl.get("oscillator", 0)
                    _sum  = _mcl.get("summation", 0)
                    _sig  = _mcl.get("signal", "UNAVAILABLE")
                    _tval = _thr.get("current_value", 0)
                    _rows = len(_ad_df)

                    # Signal colours
                    _osc_col = "#00f260" if _osc > 0 else "#ff4b4b"
                    _sig_col = "#00f260" if "OVERSOLD" in _sig else "#ff4b4b" if "OVERBOUGHT" in _sig else "#e3b341"

                    mc1, mc2, mc3, mc4 = st.columns(4)
                    mc1.metric("McClellan Oscillator", f"{_osc:+.1f}",
                               help="EMA19 − EMA39 of daily net advances. >0 = breadth expanding")
                    mc2.metric("Summation Index",     f"{_sum:+.0f}",
                               help="Cumulative McClellan. >0 = long-term breadth bullish")
                    mc3.metric("Signal",              _sig,
                               help=">100 overbought | <-100 oversold")
                    mc4.metric("Breadth Thrust EMA10",f"{_tval:.3f}",
                               delta="ACTIVE" if _thr.get("thrust_active") else "No thrust",
                               delta_color="normal" if _thr.get("thrust_active") else "off",
                               help="Zweig Thrust — reading >0.615 within 10 days = rare bullish signal")

                    st.markdown("---")
                    # Oscillator history chart
                    if "net_advances" not in _ad_df.columns:
                        _ad_df = _ad_df.copy()
                        _ad_df["net_advances"] = _ad_df["advance_count"] - _ad_df["decline_count"]
                    _ad_df["ema19"] = _ad_df["net_advances"].ewm(span=19, adjust=False).mean()
                    _ad_df["ema39"] = _ad_df["net_advances"].ewm(span=39, adjust=False).mean()
                    _ad_df["mco"]   = _ad_df["ema19"] - _ad_df["ema39"]

                    _fig_mcl = go.Figure()
                    _fig_mcl.add_bar(
                        x=_ad_df["date"], y=_ad_df["mco"],
                        marker_color=[("#00f260" if v >= 0 else "#ff4b4b") for v in _ad_df["mco"]],
                        name="McClellan Oscillator",
                    )
                    _fig_mcl.add_hline(y=100,  line_dash="dot", line_color="#ff4b4b", line_width=1,
                                       annotation_text="Overbought +100")
                    _fig_mcl.add_hline(y=-100, line_dash="dot", line_color="#00f260", line_width=1,
                                       annotation_text="Oversold -100")
                    _fig_mcl.add_hline(y=0,    line_dash="solid", line_color="#5a8a9f", line_width=1)
                    _fig_mcl.update_layout(
                        height=300, margin=dict(t=10,l=0,r=0,b=0),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                        xaxis=dict(gridcolor="#1e3a5f"), yaxis=dict(gridcolor="#1e3a5f"),
                        font=dict(color="#c9d1d9"),
                        title_text=f"McClellan Oscillator — {_rows} days of A/D history",
                    )
                    st.plotly_chart(_fig_mcl, use_container_width=True)
                    st.caption(f"A/D history: {_rows} trading days | "
                               f"Data stored at reports/ad_history.json")

        with _br5:
            section("Stage Distribution — Nifty 500")
            with st.spinner("Loading stage data..."):
                try:
                    _bm2 = calculate_breadth_metrics()
                except Exception:
                    _bm2 = {}

            if _bm2:
                _total = _bm2.get("symbols_analyzed", 1)
                _s2_pct = _bm2.get("stage2_pct", 0)
                _above200 = _bm2.get("above_sma200_pct", 0)
                _below200 = 100 - _above200

                _stage_data = {
                    "Stage 2 (Advance)": _s2_pct,
                    "Stage 1/3 (Base/Top)": max(0, _above200 - _s2_pct),
                    "Stage 4 (Decline)": _below200,
                }
                # Stage Map donut — % labels in dark text for readability against
                # the bright green/yellow/red wedges (user feedback 10 May 2026:
                # white text was hard to read on the light wedge fills).
                _fig_pie = go.Figure(go.Pie(
                    labels=list(_stage_data.keys()),
                    values=list(_stage_data.values()),
                    hole=0.5,
                    marker_colors=["#00f260","#e3b341","#ff4b4b"],
                    textfont=dict(size=14, color="#0a0e14"),  # dark text on wedge
                    textposition="inside",
                    insidetextorientation="horizontal",
                    texttemplate="<b>%{percent}</b>",
                ))
                _fig_pie.update_layout(
                    height=320, margin=dict(t=10,l=0,r=0,b=0),
                    paper_bgcolor="rgba(0,0,0,0)",
                    legend=dict(font=dict(size=11,color="#c9d1d9"),bgcolor="rgba(0,0,0,0)"),
                    annotations=[dict(text=f"S2: {_s2_pct:.0f}%",
                                      x=0.5, y=0.5, font_size=20,
                                      font_color="#00f260", showarrow=False)]
                )
                st.plotly_chart(_fig_pie, use_container_width=True)
                st.caption("Stage 2 > 35% = Confirmed Bull Market. Stage 2 < 20% = Bear Market.")


# ══════════════════════════════════════════════════════════════════════════════
#  v4.0 Phase-4 — ETF TRADING SYSTEM
#  Added 11 May 2026 — consumes outputs of:
#    • etf_screener.py  (ETF_Screener_Results.csv)
#    • etf_rotation.py  (ETF_Sector_Rotation.csv, ETF_AssetClass_Regime.csv,
#                        ETF_RRG_Coordinates.csv, ETF_Top_Picks.csv)
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'ETF':
    st.markdown('<div class="page-title">🪙 ETF Trading System</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Sector Rotation // Asset-Class Regime // '
                'RRG Quadrants // Liquidity-Aware Picks — NSE ETFs only</div>',
                unsafe_allow_html=True)

    if not _ETF_OK:
        st.error("❌ ETF modules (etf_universe / etf_screener / etf_rotation) "
                  "not available. Run `pip install -r requirements.txt` and ensure "
                  "the three modules are present in the project root.")
    else:
        import os as _os_etf

        # ── File status strip ───────────────────────────────────────────────
        _ETF_FILES = {
            "Screener":  "ETF_Screener_Results.csv",
            "Sectors":   "ETF_Sector_Rotation.csv",
            "Regime":    "ETF_AssetClass_Regime.csv",
            "RRG":       "ETF_RRG_Coordinates.csv",
            "Picks":     "ETF_Top_Picks.csv",
        }
        _file_meta = {}
        for label, fname in _ETF_FILES.items():
            p = _os_etf.path.join(_os_etf.path.dirname(_os_etf.path.abspath(__file__)),
                                   fname)
            if _os_etf.path.exists(p):
                try:
                    _df_tmp = pd.read_csv(p)
                    _mtime = datetime.fromtimestamp(_os_etf.path.getmtime(p))
                    _age_h = (datetime.now() - _mtime).total_seconds() / 3600
                    _file_meta[label] = {
                        "rows":  len(_df_tmp),
                        "mtime": _mtime.strftime("%d %b %H:%M"),
                        "age_h": _age_h,
                        "exists": True,
                    }
                except Exception:
                    _file_meta[label] = {"exists": False}
            else:
                _file_meta[label] = {"exists": False}

        # Render the strip + Run-All button
        _hdr_l, _hdr_r = st.columns([5, 1])
        with _hdr_l:
            _strip_html = '<div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:10px">'
            for label, meta in _file_meta.items():
                if meta.get("exists"):
                    _age = meta["age_h"]
                    _color = ("#00f260" if _age < 24
                              else "#e3b341" if _age < 72
                              else "#ff4b4b")
                    _icon = ("🟢" if _age < 24 else "🟡" if _age < 72 else "🔴")
                    _txt = f"{label}: {meta['rows']} rows · {meta['mtime']}"
                else:
                    _color = "#ff4b4b"
                    _icon  = "🔴"
                    _txt   = f"{label}: not generated"
                _strip_html += (
                    f'<div style="font-family:JetBrains Mono,monospace;font-size:0.74rem;'
                    f'color:{_color}">{_icon} {_txt}</div>'
                )
            _strip_html += "</div>"
            st.markdown(_strip_html, unsafe_allow_html=True)
        with _hdr_r:
            if st.button("🔄 Run All", key="etf_run_all", type="primary",
                          use_container_width=True):
                with st.spinner("Running ETF screener + rotation engine "
                                "(~30-60s)..."):
                    try:
                        _df_etf = _etf_s.rank_universe()
                        if not _df_etf.empty:
                            _df_etf.to_csv(
                                _os_etf.path.join(_os_etf.path.dirname(
                                    _os_etf.path.abspath(__file__)),
                                    _ETF_FILES["Screener"]), index=False)

                        _sec = _etf_r.sector_rotation_table()
                        if not _sec.empty:
                            _sec.to_csv(
                                _os_etf.path.join(_os_etf.path.dirname(
                                    _os_etf.path.abspath(__file__)),
                                    _ETF_FILES["Sectors"]), index=False)

                        _reg = _etf_r.asset_class_regime()
                        if _reg.get("rows"):
                            _df_reg = pd.DataFrame(_reg["rows"])
                            _df_reg["regime_label"] = _reg["regime_label"]
                            _df_reg["fetched_at"]   = _reg["fetched_at"]
                            _df_reg.to_csv(
                                _os_etf.path.join(_os_etf.path.dirname(
                                    _os_etf.path.abspath(__file__)),
                                    _ETF_FILES["Regime"]), index=False)

                        _rrg = _etf_r.rrg_coordinates()
                        if not _rrg.empty:
                            _rrg.to_csv(
                                _os_etf.path.join(_os_etf.path.dirname(
                                    _os_etf.path.abspath(__file__)),
                                    _ETF_FILES["RRG"]), index=False)

                        _picks = _etf_r.top_picks_by_regime(_sec, _reg)
                        if not _picks.empty:
                            _picks.to_csv(
                                _os_etf.path.join(_os_etf.path.dirname(
                                    _os_etf.path.abspath(__file__)),
                                    _ETF_FILES["Picks"]), index=False)

                        st.success("✅ ETF system refreshed!")
                        st.rerun()
                    except Exception as _e:
                        st.error(f"Run failed: {_e}")

        # ── Tabs ────────────────────────────────────────────────────────────
        _et1, _et2, _et3, _et4 = st.tabs([
            "🎯 Top Picks", "🔄 Sector Rotation",
            "📊 Asset-Class Regime", "💧 Liquidity & Universe",
        ])

        # ─── TAB 1 — Top Picks ─────────────────────────────────────────────
        with _et1:
            section("Regime-Aware ETF Picks")
            _picks_path = _os_etf.path.join(
                _os_etf.path.dirname(_os_etf.path.abspath(__file__)),
                _ETF_FILES["Picks"])
            _scr_path   = _os_etf.path.join(
                _os_etf.path.dirname(_os_etf.path.abspath(__file__)),
                _ETF_FILES["Screener"])

            if not _file_meta["Picks"].get("exists") or _file_meta["Picks"]["rows"] == 0:
                st.info("No picks file yet. Click **🔄 Run All** above to generate.")
            else:
                _df_picks = pd.read_csv(_picks_path)
                _regime_lbl = (_df_picks["Regime"].iloc[0]
                                if "Regime" in _df_picks.columns and not _df_picks.empty
                                else "—")
                _reg_color = ("#00f260" if _regime_lbl == "RISK_ON" else
                              "#e3b341" if _regime_lbl in ("MIXED","INTL_LED") else
                              "#58a6ff" if _regime_lbl == "GOLD_LED" else
                              "#ff4b4b" if _regime_lbl == "RISK_OFF" else "#8b949e")
                st.markdown(
                    f'<div class="metric-card" style="padding:12px 16px;margin-bottom:14px">'
                    f'<div class="metric-label">Active Regime</div>'
                    f'<div class="metric-value" style="color:{_reg_color};font-size:1.2rem">'
                    f'{_regime_lbl}</div>'
                    f'<div style="font-size:0.62rem;color:#5a8a9f;margin-top:3px">'
                    f'{len(_df_picks)} picks · suggested weights sum to '
                    f'{_df_picks["Suggested_Weight_pct"].sum() if "Suggested_Weight_pct" in _df_picks.columns else 0}%</div>'
                    f'</div>', unsafe_allow_html=True
                )

                # Picks table with highlighted weight column
                _disp = _df_picks.copy()
                if "Suggested_Weight_pct" in _disp.columns:
                    _disp = _disp.sort_values("Suggested_Weight_pct", ascending=False)

                # Enrich with screener LTP / Stage / Signal where available
                if _file_meta["Screener"].get("exists"):
                    try:
                        _df_scr = pd.read_csv(_scr_path)
                        _enrich_cols = ["Symbol", "LTP", "Stage", "RRG_Quadrant",
                                        "Total_Score", "Signal"]
                        _enrich_cols = [c for c in _enrich_cols
                                        if c in _df_scr.columns]
                        _disp = _disp.merge(_df_scr[_enrich_cols], on="Symbol", how="left")
                    except Exception:
                        pass

                st.dataframe(_disp, use_container_width=True, hide_index=True)

                # Send-to-TV / copy-to-clipboard helper
                _sym_str = ",".join(f"NSE:{s}" for s in _df_picks["Symbol"].tolist())
                with st.expander("📋 Copy symbols (for TradingView watchlist)"):
                    st.code(_sym_str, language="text")
                    st.caption("Paste into TradingView → Watchlist → Add Symbols")

        # ─── TAB 2 — Sector Rotation ────────────────────────────────────────
        with _et2:
            section("Sector Rotation Table — composite RS (60% 12W + 40% 4W)")
            _sec_path = _os_etf.path.join(
                _os_etf.path.dirname(_os_etf.path.abspath(__file__)),
                _ETF_FILES["Sectors"])
            if not _file_meta["Sectors"].get("exists") or _file_meta["Sectors"]["rows"] == 0:
                st.info("No sector rotation file. Click **🔄 Run All** above.")
            else:
                _df_sec = pd.read_csv(_sec_path)

                # Tier counts strip
                _q_counts = _df_sec["Quartile"].value_counts() if "Quartile" in _df_sec.columns else {}
                _qc1, _qc2, _qc3, _qc4 = st.columns(4)
                _qc1.metric("🟢 OVERWEIGHT", int(_q_counts.get("TOP", 0)))
                _qc2.metric("🟡 NEUTRAL+",   int(_q_counts.get("2",   0)))
                _qc3.metric("🟠 NEUTRAL−",   int(_q_counts.get("3",   0)))
                _qc4.metric("🔴 UNDERWEIGHT",int(_q_counts.get("BOTTOM", 0)))

                st.markdown("---")
                _sty_cols = [c for c in ["Excess_4W_pct", "Excess_12W_pct",
                                          "Composite_Score"]
                             if c in _df_sec.columns]
                _sty = _df_sec.style.format({c: "{:+.2f}" for c in _sty_cols})
                st.dataframe(_sty, use_container_width=True, hide_index=True)

                with st.expander("ℹ️ How the composite is built"):
                    st.markdown("""
- **Excess return** = sector return − Nifty 500 return (so we measure
  *true rotation*, not absolute beta exposure)
- **Composite Score** = `0.6 × rank(12W excess) + 0.4 × rank(4W excess)`
- The 60/40 split favours the established trend (12W) but lets the 4W catch
  the early turn — so a sector flipping from LAGGING → IMPROVING shows up
  before the 12W catches up.
- **Quartile**: TOP = OVERWEIGHT, BOTTOM = UNDERWEIGHT.
                    """)

        # ─── TAB 3 — Asset-Class Regime ─────────────────────────────────────
        with _et3:
            section("Asset-Class Regime Detector")
            _reg_path = _os_etf.path.join(
                _os_etf.path.dirname(_os_etf.path.abspath(__file__)),
                _ETF_FILES["Regime"])
            if not _file_meta["Regime"].get("exists") or _file_meta["Regime"]["rows"] == 0:
                st.info("No regime file. Click **🔄 Run All** above.")
            else:
                _df_reg = pd.read_csv(_reg_path)
                _label  = _df_reg["regime_label"].iloc[0] if "regime_label" in _df_reg.columns else "—"
                _fetched= _df_reg["fetched_at"].iloc[0]   if "fetched_at"   in _df_reg.columns else "—"

                _reg_color = ("#00f260" if _label == "RISK_ON" else
                              "#e3b341" if _label in ("MIXED","INTL_LED") else
                              "#58a6ff" if _label == "GOLD_LED" else
                              "#ff4b4b" if _label == "RISK_OFF" else "#8b949e")

                _r_a, _r_b = st.columns([3, 1])
                with _r_a:
                    st.markdown(
                        f'<div class="metric-card" style="padding:14px 18px">'
                        f'<div class="metric-label">REGIME</div>'
                        f'<div class="metric-value" style="color:{_reg_color};'
                        f'font-size:1.5rem">{_label}</div>'
                        f'<div style="font-size:0.62rem;color:#5a8a9f">'
                        f'Detected at {_fetched}</div></div>',
                        unsafe_allow_html=True)
                with _r_b:
                    _eligible = int((_df_reg["status"] == "RISK_ON").sum()
                                     if "status" in _df_reg.columns else 0)
                    st.metric("Risk-On Asset Classes", _eligible)

                st.markdown("---")

                # Allocation pie + table
                _pie_l, _pie_r = st.columns([2, 3])
                with _pie_l:
                    if "suggested_tilt_pct" in _df_reg.columns:
                        _pie_df = _df_reg[_df_reg["suggested_tilt_pct"] > 0].copy()
                        if not _pie_df.empty:
                            import plotly.express as _px
                            _fig_pie = _px.pie(
                                _pie_df, names="asset_class",
                                values="suggested_tilt_pct",
                                hole=0.5,
                                color_discrete_sequence=_px.colors.sequential.Teal_r,
                            )
                            _fig_pie.update_layout(
                                height=320, margin=dict(t=10,b=10,l=10,r=10),
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)",
                                font=dict(color="#c9d1d9", size=11),
                                showlegend=True,
                            )
                            st.plotly_chart(_fig_pie, use_container_width=True)
                        else:
                            st.info("No allocation suggested in current regime.")
                with _pie_r:
                    _disp_reg = _df_reg.drop(columns=["regime_label","fetched_at"],
                                              errors="ignore")
                    if "score" in _disp_reg.columns:
                        _disp_reg = _disp_reg.sort_values("score", ascending=False)
                    _fmt_cols = {c: "{:+.2f}" for c in
                                 ["ret_4w_pct","ret_12w_pct","excess_12w_pct","score"]
                                 if c in _disp_reg.columns}
                    st.dataframe(_disp_reg.style.format(_fmt_cols),
                                  use_container_width=True, hide_index=True)

                with st.expander("ℹ️ Regime rules"):
                    st.markdown("""
| Regime | Trigger |
|---|---|
| **RISK_ON**  | ≥2 equity flagships above 200DMA + outperforming gold |
| **GOLD_LED** | Gold flagship score > best equity flagship score |
| **INTL_LED** | Indian equity off, US/Intl on |
| **RISK_OFF** | All equities below 200DMA, gold not leading |
| **MIXED**    | None of the above |

Allocation tilt template: top scorer 40% → 25% → 20% → 15% → 0%.
Gold floor 10% in RISK_OFF. Debt absorbs residual to 100%.
                    """)

        # ─── TAB 4 — Liquidity & Universe ──────────────────────────────────
        with _et4:
            section("ETF Universe — Liquidity & Per-ETF Scoring")
            _scr_path = _os_etf.path.join(
                _os_etf.path.dirname(_os_etf.path.abspath(__file__)),
                _ETF_FILES["Screener"])
            if not _file_meta["Screener"].get("exists") or _file_meta["Screener"]["rows"] == 0:
                st.info("No screener file. Click **🔄 Run All** above.")
            else:
                _df_scr = pd.read_csv(_scr_path)

                # Filter row
                _f1, _f2, _f3 = st.columns([2, 2, 3])
                _ac_opts = ["(all)"] + sorted(_df_scr["Asset_Class"].dropna().unique().tolist()
                                               if "Asset_Class" in _df_scr.columns else [])
                _ac_pick = _f1.selectbox("Asset Class", _ac_opts, key="etf_ac_filt")
                _liq_pick = _f2.selectbox("Liquidity Tier",
                                          ["(all)", "A only", "A + B", "A + B + C"],
                                          index=2, key="etf_liq_filt")
                _grade_pick = _f3.multiselect(
                    "Grade", ["⭐⭐⭐ A+","⭐⭐ A","⭐ B","C","D"],
                    default=["⭐⭐⭐ A+","⭐⭐ A","⭐ B"], key="etf_grade_filt")

                _disp = _df_scr.copy()
                if _ac_pick != "(all)" and "Asset_Class" in _disp.columns:
                    _disp = _disp[_disp["Asset_Class"] == _ac_pick]
                if _liq_pick != "(all)" and "Liquidity_Tier" in _disp.columns:
                    _allowed = {"A only": ["A"], "A + B": ["A","B"],
                                "A + B + C": ["A","B","C"]}.get(_liq_pick, ["A","B","C"])
                    _disp = _disp[_disp["Liquidity_Tier"].isin(_allowed)]
                if _grade_pick and "Grade" in _disp.columns:
                    _disp = _disp[_disp["Grade"].isin(_grade_pick)]

                st.caption(f"Showing **{len(_disp)}** of {len(_df_scr)} ETFs")

                # Top metrics
                _m_a, _m_b, _m_c, _m_d = st.columns(4)
                _m_a.metric("Universe", len(_df_scr))
                _m_b.metric("Stage 2",
                            int((_df_scr.get("Stage", pd.Series(dtype=int)) == 2).sum()))
                _m_c.metric("LEADING",
                            int((_df_scr.get("RRG_Quadrant", pd.Series(dtype=str)) == "LEADING").sum()))
                _m_d.metric("Liquid (≥₹2Cr/d)",
                            int((_df_scr.get("Liquidity_Score", pd.Series(dtype=int)) >= 6).sum()))

                st.markdown("---")

                # Best display columns
                _show_cols = [c for c in [
                    "Symbol", "Name", "Asset_Class", "Sub_Category",
                    "Total_Score", "Grade", "Stage", "RRG_Quadrant",
                    "Liquidity_Score", "Trend_Score", "RS_Score", "Rotation_Score",
                    "LTP", "Mansfield_RS", "RS_Momentum_4W",
                    "Turnover_60D_Cr", "Dist_52WH_pct", "Signal",
                ] if c in _disp.columns]

                _fmt = {c: "{:+.2f}" for c in
                        ["Mansfield_RS","RS_Momentum_4W","Dist_52WH_pct"]
                        if c in _disp.columns}
                _fmt.update({c: "{:.2f}" for c in
                             ["LTP","Turnover_60D_Cr"] if c in _disp.columns})
                st.dataframe(_disp[_show_cols].style.format(_fmt),
                              use_container_width=True, hide_index=True,
                              height=560)


# ══════════════════════════════════════════════════════════════════════════════
#  v4.0 Phase-2 — NEWS & SENTIMENT
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'NEWS':
    st.markdown('<div class="page-title">📰 Financial News & Sentiment</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Live RSS feeds from ET, Moneycontrol, Business Standard, LiveMint, NDTV Profit — keyword sentiment scoring</div>', unsafe_allow_html=True)

    if not _NEWS_OK:
        st.error("❌ news_feed module not available. Run: pip install feedparser")
    else:
        # ── Controls ─────────────────────────────────────────────────────────
        c1, c2, c3 = st.columns([1, 2, 3])
        with c1:
            _nw_refresh = st.button("🔄 Refresh", key="nw_refresh", type="primary")
        with c2:
            _nw_max = st.selectbox("Max per feed", [10, 15, 20], index=1, key="nw_max")
        with c3:
            _all_src_opts = ["Economic Times Markets","Economic Times Stocks",
                             "CNBCTV18 Markets","Business Standard",
                             "Business Standard Co.","LiveMint Markets",
                             "LiveMint Companies","NDTV Profit"]
            _nw_src = st.multiselect("Sources", _all_src_opts,
                default=["Economic Times Markets","CNBCTV18 Markets",
                         "Business Standard","LiveMint Markets"],
                key="nw_sources")

        if _nw_refresh:
            try:
                from news_feed import _cache as _nw_cache_store
                _nw_cache_store.clear()
            except Exception:
                pass

        _nw_df = pd.DataFrame()
        _nw_health = {}
        with st.spinner("Fetching live news feeds..."):
            try:
                _nw_df = fetch_all_news(max_per_feed=_nw_max)
                _nw_df = add_sentiment(_nw_df)
                if _nw_src and not _nw_df.empty:
                    _nw_df = _nw_df[_nw_df["source"].isin(_nw_src)]
                try:
                    from news_feed import get_last_feed_health as _glfh
                    _nw_health = _glfh() or {}
                except Exception:
                    _nw_health = {}
            except Exception as _ne:
                st.error(f"News fetch failed: {_ne}")

        # Per-feed status pill — replaces the old behaviour of injecting
        # "Feed unavailable" placeholder rows into the headline list.
        if _nw_health:
            _bad = {k: v for k, v in _nw_health.items() if v != "ok"}
            if _bad:
                _bad_lines = " · ".join(f"<b>{k}</b>: {v}" for k, v in _bad.items())
                st.markdown(
                    f"<div style='font-size:0.72rem;color:#e3b341;"
                    f"background:rgba(227,179,65,0.08);padding:6px 10px;"
                    f"border-left:3px solid #e3b341;border-radius:4px;margin-bottom:8px'>"
                    f"⚠ {len(_bad)}/{len(_nw_health)} feed(s) unavailable — "
                    f"others loaded normally. {_bad_lines}"
                    f"</div>", unsafe_allow_html=True)

        # ── Sentiment summary bar ─────────────────────────────────────────────
        if not _nw_df.empty and "sentiment" in _nw_df.columns:
            _bull = int((_nw_df["sentiment"].str.contains("Bullish", case=False, na=False)).sum())
            _bear = int((_nw_df["sentiment"].str.contains("Bearish", case=False, na=False)).sum())
            _neut = len(_nw_df) - _bull - _bear
            _score = round((_bull - _bear) / max(len(_nw_df), 1) * 100, 1)
            _score_lbl = "BULLISH" if _score > 10 else "BEARISH" if _score < -10 else "NEUTRAL"
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Headlines", len(_nw_df))
            m2.metric("🟢 Bullish", _bull)
            m3.metric("🔴 Bearish", _bear)
            m4.metric("⬜ Neutral", _neut)
            m5.metric("Sentiment", f"{_score:+.1f}%", delta=_score_lbl,
                      delta_color="off" if _score_lbl == "BEARISH" else "normal")

        st.markdown("---")

        # Source colour tags — matches the paid grid convention so both tabs
        # feel visually consistent.
        _RSS_SRC_COL = {
            "Economic Times Markets": "#ff7b72",
            "Economic Times Stocks":  "#ff7b72",
            "CNBCTV18 Markets":       "#58a6ff",
            "Business Standard":      "#e3b341",
            "Business Standard Co.":  "#e3b341",
            "LiveMint Markets":       "#a371f7",
            "LiveMint Companies":     "#a371f7",
            "NDTV Profit":            "#3fb950",
        }

        def _news_card_html(row) -> str:
            """Return one news card matching the paid-grid card style."""
            _sent    = str(row.get("sentiment", "🟡 Neutral"))
            _sent_c  = str(row.get("sentiment_color", "#e3b341"))
            _src     = str(row.get("source", ""))
            _src_c   = _RSS_SRC_COL.get(_src, "#8b949e")
            _ts      = str(row.get("published_ts", ""))[:16]
            _title   = str(row.get("title", "")).replace("<", "&lt;").replace(">", "&gt;")
            _link    = str(row.get("link", "#")) or "#"
            _summ    = str(row.get("summary", ""))[:160].replace("<", "&lt;").replace(">", "&gt;")
            if len(str(row.get("summary", ""))) > 160:
                _summ += "…"
            return (
                f'<div class="metric-card" style="padding:10px 12px;'
                f'margin-bottom:8px;min-height:150px;border-left:3px solid {_sent_c}">'
                f'<div style="display:flex;justify-content:space-between;'
                f'align-items:center;margin-bottom:5px">'
                f'<span style="color:{_sent_c};font-size:0.62rem;'
                f'font-weight:700;letter-spacing:0.5px">{_sent}</span>'
                f'<span style="color:{_src_c};font-size:0.6rem;'
                f'font-weight:600">{_src}</span></div>'
                f'<div style="font-size:0.78rem;color:#e6edf3;line-height:1.3">'
                f'<a href="{_link}" target="_blank" '
                f'style="color:#e6edf3;text-decoration:none">{_title}</a></div>'
                f'<div style="font-size:0.66rem;color:#8b949e;'
                f'margin-top:6px;line-height:1.35">{_summ}</div>'
                f'<div style="font-size:0.58rem;color:#5a8a9f;margin-top:6px">{_ts}</div>'
                f'</div>'
            )

        def _render_news_grid(df, n_cols: int = 4):
            """Render the news DataFrame as an n-column responsive card grid."""
            if df is None or df.empty:
                return
            _rows = list(df.to_dict("records"))
            for _i in range(0, len(_rows), n_cols):
                _chunk = _rows[_i:_i + n_cols]
                _cols = st.columns(n_cols, gap="small")
                for _col, _r in zip(_cols, _chunk):
                    with _col:
                        st.markdown(_news_card_html(_r), unsafe_allow_html=True)

        # Back-compat: keep single-row renderer in case other call sites use it.
        def _render_news_row(row):
            st.markdown(_news_card_html(row), unsafe_allow_html=True)

        # ── Inline tabs ───────────────────────────────────────────────────────
        _nw_tab1, _nw_tab3, _nw_tab2 = st.tabs([
            "📰 Market News (Free RSS)",
            "💎 ET Prime + MC Pro",
            "🔍 Stock Filter",
        ])

        with _nw_tab1:
            section("Market Headlines — Sorted by Recency")
            if _nw_df.empty:
                st.info("No news fetched. Check network or try refreshing.")
            else:
                _nw_ncols = st.select_slider(
                    "Columns", options=[1, 2, 3, 4, 5], value=4,
                    key="nw_free_cols",
                    help="Adjust grid density for the headline cards.")
                _render_news_grid(_nw_df, n_cols=int(_nw_ncols))

        with _nw_tab3:
            section("ET Prime + Moneycontrol Pro — Analyst Recos & News")
            _render_paid_news_grid(
                key_prefix="news_paid",
                keyword_filter=None,
                default_limit=40,
                show_recos_only=False,
                caption=("Live pull from your paid ET Prime + MC Pro sessions. "
                         "Cards are colour-coded by analyst action (Buy / Hold / Sell). "
                         "Cached 1h — click **Refresh** to force a re-fetch."),
            )

        with _nw_tab2:
            section("Stock-Specific News Filter")
            _sym_input = st.text_input(
                "Enter stock name or NSE symbol (e.g. RELIANCE, Infosys, HDFC)",
                key="nw_sym").strip()
            if _sym_input and not _nw_df.empty:
                try:
                    _stk_df = filter_by_symbol(_nw_df, _sym_input)
                except Exception as _fbe:
                    _stk_df = pd.DataFrame()
                    st.error(f"Filter error: {_fbe}")
                if not _stk_df.empty:
                    st.caption(f"**{len(_stk_df)}** headlines mentioning **{_sym_input}**")
                    _render_news_grid(_stk_df, n_cols=4)
                else:
                    st.info(f"No headlines found mentioning **{_sym_input}**.")
            elif not _sym_input:
                st.info("Enter a symbol or company name above to filter headlines.")


# ══════════════════════════════════════════════════════════════════════════════
#  v4.0 Phase-2 — FUNDAMENTALS HUB
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'FUNDAMENTALS':
    st.markdown('<div class="page-title">📊 Fundamentals Hub</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Valuation multiples, earnings quality, balance sheet health, screening — powered by yfinance</div>', unsafe_allow_html=True)

    if not _FUND_OK:
        st.error("❌ fundamental_hub module not available.")
    else:
        # ── Symbol input (shared across all tabs) ────────────────────────────
        _fd_col1, _fd_col2 = st.columns([2, 4])
        with _fd_col1:
            _fd_sym = st.text_input(
                "NSE Symbol", value=st.session_state.get("fd_symbol","RELIANCE.NS"),
                key="fd_sym_input", placeholder="e.g. INFY.NS, TCS.NS"
            ).strip().upper()
            if _fd_sym and not _fd_sym.endswith(".NS"):
                _fd_sym += ".NS"
            if _fd_sym:
                st.session_state["fd_symbol"] = _fd_sym

        _fd_tab1, _fd_tab2, _fd_tab3 = st.tabs(["📈 Snapshot", "🎯 Scorecard", "🔍 Screen"])

        with _fd_tab1:
            section(f"Fundamental Snapshot — {_fd_sym}")
            if not _fd_sym:
                st.info("Enter an NSE symbol above.")
            else:
                with st.spinner(f"Fetching fundamentals for {_fd_sym}..."):
                    try:
                        _fd = fetch_stock_fundamentals(_fd_sym)
                    except Exception as _fe:
                        _fd = {}; st.error(f"Fetch failed: {_fe}")

                if not _fd:
                    st.warning(f"No fundamental data returned for {_fd_sym}. Check the symbol.")
                else:
                    # Identity row
                    st.markdown(
                        f'<div class="metric-card" style="padding:12px 16px;margin-bottom:12px">'
                        f'<div style="font-size:1.05rem;font-weight:700;color:#58a6ff">{_fd.get("name","")}</div>'
                        f'<div style="font-size:0.78rem;color:#8b949e">{_fd.get("sector","")} › {_fd.get("industry","")}</div>'
                        f'</div>', unsafe_allow_html=True
                    )

                    # Price + market cap
                    r1 = st.columns(4)
                    r1[0].metric("Price", f"₹{_fd.get('price',0):,.2f}")
                    r1[1].metric("Market Cap", f"₹{_fd.get('market_cap',0):,.0f}Cr" if _fd.get('market_cap') else "N/A")
                    r1[2].metric("52W vs High", f"{_fd.get('week52_vs_high',0):+.1f}%" if _fd.get('week52_vs_high') is not None else "N/A")
                    r1[3].metric("Beta", f"{_fd.get('beta',0):.2f}" if _fd.get('beta') else "N/A")

                    st.markdown("---")
                    # Valuation
                    section("Valuation Multiples")
                    r2 = st.columns(5)
                    r2[0].metric("P/E (TTM)",     f"{_fd.get('pe_ratio',0):.1f}x"    if _fd.get('pe_ratio')    else "N/A")
                    r2[1].metric("Fwd P/E",        f"{_fd.get('forward_pe',0):.1f}x"  if _fd.get('forward_pe')  else "N/A")
                    r2[2].metric("P/B",             f"{_fd.get('pb_ratio',0):.2f}x"   if _fd.get('pb_ratio')    else "N/A")
                    r2[3].metric("EV/EBITDA",       f"{_fd.get('ev_ebitda',0):.1f}x"  if _fd.get('ev_ebitda')   else "N/A")
                    r2[4].metric("P/S",             f"{_fd.get('ps_ratio',0):.2f}x"   if _fd.get('ps_ratio')    else "N/A")

                    # Profitability
                    section("Profitability & Returns")
                    r3 = st.columns(5)
                    r3[0].metric("Net Margin",     f"{_fd.get('profit_margin',0):.1f}%"    if _fd.get('profit_margin')    else "N/A")
                    r3[1].metric("Op Margin",      f"{_fd.get('operating_margin',0):.1f}%" if _fd.get('operating_margin') else "N/A")
                    r3[2].metric("ROE",             f"{_fd.get('roe',0):.1f}%"             if _fd.get('roe')              else "N/A")
                    r3[3].metric("ROA",             f"{_fd.get('roa',0):.1f}%"             if _fd.get('roa')              else "N/A")
                    r3[4].metric("Div Yield",       f"{_fd.get('dividend_yield',0):.2f}%"  if _fd.get('dividend_yield')   else "N/A")

                    # Financials
                    section("Financials (TTM)")
                    r4 = st.columns(4)
                    r4[0].metric("Revenue",    f"₹{_fd.get('revenue_ttm',0):,.0f}Cr"    if _fd.get('revenue_ttm')    else "N/A")
                    r4[1].metric("Net Income", f"₹{_fd.get('net_income_ttm',0):,.0f}Cr" if _fd.get('net_income_ttm') else "N/A")
                    r4[2].metric("EPS (TTM)",  f"₹{_fd.get('eps_ttm',0):.2f}"           if _fd.get('eps_ttm')        else "N/A")
                    r4[3].metric("Fwd EPS",    f"₹{_fd.get('eps_forward',0):.2f}"       if _fd.get('eps_forward')    else "N/A")

                    # Balance sheet
                    section("Balance Sheet Health")
                    r5 = st.columns(3)
                    r5[0].metric("Debt/Equity",    f"{_fd.get('debt_equity',0):.2f}x"  if _fd.get('debt_equity')    else "N/A")
                    r5[1].metric("Current Ratio",  f"{_fd.get('current_ratio',0):.2f}" if _fd.get('current_ratio')  else "N/A")
                    r5[2].metric("Float Shares",   f"{_fd.get('float_shares',0):,.1f}Cr" if _fd.get('float_shares') else "N/A")

                    # AI analysis
                    if _GEMINI_OK:
                        st.markdown("---")
                        if st.button("🤖 Generate AI Analysis", key="fd_ai_btn", type="primary"):
                            with st.spinner("Generating Gemini analysis..."):
                                try:
                                    from gemini_reporter import generate_stock_analysis
                                    _ai_text = generate_stock_analysis(_fd_sym, _fd)
                                    _render_ai_report(_ai_text)
                                except Exception as _ae:
                                    st.error(f"AI analysis failed: {_ae}")

        with _fd_tab2:
            section(f"Valuation Scorecard — {_fd_sym}")
            if not _fd_sym:
                st.info("Enter an NSE symbol above.")
            else:
                with st.spinner(f"Building scorecard for {_fd_sym}..."):
                    try:
                        _fd_raw = fetch_stock_fundamentals(_fd_sym)
                        _sc = get_valuation_scorecard(_fd_raw) if _fd_raw else {}
                    except Exception as _se:
                        _sc = {}; st.error(f"Scorecard failed: {_se}")

                if not _sc:
                    st.warning("Scorecard unavailable — no fundamental data returned.")
                else:
                    _score   = _sc.get("score", 0)
                    _rating  = _sc.get("rating", "N/A")
                    _bdown   = _sc.get("breakdown", {})
                    _r_color = "#00f260" if "BUY" in str(_rating).upper() else "#ff4b4b" if "SELL" in str(_rating).upper() else "#e3b341"

                    st.markdown(
                        f'<div class="metric-card" style="padding:16px;text-align:center;margin-bottom:16px">'
                        f'<div style="font-size:2.5rem;font-weight:800;color:{_r_color}">{_rating}</div>'
                        f'<div style="font-size:1rem;color:#c9d1d9">Score: {_score} / {sum(_bdown.values()) if _bdown else "?"}</div>'
                        f'</div>', unsafe_allow_html=True
                    )

                    if _bdown:
                        section("Score Breakdown")
                        for _metric, _pts in _bdown.items():
                            _icon = "✅" if _pts > 0 else "❌"
                            _lbl  = _metric.replace("_"," ").title()
                            st.markdown(
                                f'<div style="padding:6px 0;border-bottom:1px solid #1e3a5f;display:flex;align-items:baseline;gap:8px">'
                                f'<span style="font-size:0.95rem">{_icon}</span>'
                                f'<span style="font-size:0.82rem;color:#c9d1d9;flex:1">{_lbl}</span>'
                                f'<span style="font-size:0.78rem;color:#e3b341;margin-left:8px">{_pts:+d} pts</span>'
                                f'</div>', unsafe_allow_html=True
                            )

        with _fd_tab3:
            section("Fundamental Screener")
            st.caption("Filter NSE stocks by valuation, profitability, and growth criteria")
            _sc_c1, _sc_c2, _sc_c3 = st.columns(3)
            with _sc_c1:
                _max_pe    = st.number_input("Max P/E",      min_value=0.0, max_value=200.0, value=30.0, step=1.0, key="sc_pe")
                _min_roe   = st.number_input("Min ROE (%)",  min_value=0.0, max_value=100.0, value=15.0, step=1.0, key="sc_roe")
            with _sc_c2:
                _max_de    = st.number_input("Max Debt/Eq",  min_value=0.0, max_value=10.0,  value=1.0,  step=0.1, key="sc_de")
                _min_margin= st.number_input("Min Net Margin (%)", min_value=0.0, max_value=100.0, value=10.0, step=1.0, key="sc_margin")
            with _sc_c3:
                _screen_universe = st.selectbox(
                    "Universe", ["Nifty 50", "Custom"], key="sc_uni"
                )
                _custom_syms = st.text_area("Custom symbols (one per line, with .NS)",
                    height=68, key="sc_custom",
                    placeholder="RELIANCE.NS\nINFY.NS\nHDFCBANK.NS")

            if st.button("🔍 Run Screen", key="sc_run", type="primary"):
                # Build symbol list
                if _screen_universe == "Custom" and _custom_syms.strip():
                    _syms_to_screen = [s.strip().upper() for s in _custom_syms.strip().splitlines() if s.strip()]
                else:
                    # Use a small fixed Nifty 50 subset for speed
                    _syms_to_screen = [
                        "RELIANCE.NS","TCS.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS",
                        "HINDUNILVR.NS","ITC.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
                        "LT.NS","AXISBANK.NS","ASIANPAINT.NS","MARUTI.NS","TITAN.NS",
                        "BAJFINANCE.NS","WIPRO.NS","ULTRACEMCO.NS","NESTLEIND.NS","POWERGRID.NS",
                        "NTPC.NS","ONGC.NS","JSWSTEEL.NS","TATAMOTORS.NS","ADANIPORTS.NS",
                        "CIPLA.NS","DRREDDY.NS","SUNPHARMA.NS","DIVISLAB.NS","TECHM.NS",
                    ]
                # screen_fundamentals expects criteria as {metric: (min_val, max_val)}
                criteria = {
                    "pe_ratio":        (0, _max_pe),
                    "roe":             (_min_roe, 9999),
                    "debt_equity":     (0, _max_de),
                    "profit_margin":   (_min_margin, 9999),
                }
                with st.spinner(f"Screening {len(_syms_to_screen)} stocks (may take 30–60s)..."):
                    try:
                        _df_sc = screen_fundamentals(_syms_to_screen, criteria)
                    except Exception as _scre:
                        _df_sc = pd.DataFrame(); st.error(f"Screen failed: {_scre}")

                if not _df_sc.empty:
                    st.success(f"✅ {len(_df_sc)} stocks passed all criteria")
                    _show_cols = [c for c in ["symbol","name","pe_ratio","roe","profit_margin",
                                               "debt_equity","market_cap"] if c in _df_sc.columns]
                    _df_show = _df_sc[_show_cols].rename(columns={
                        "pe_ratio":"P/E","roe":"ROE%","profit_margin":"Net Margin%",
                        "debt_equity":"D/E","market_cap":"Mkt Cap (Cr)"
                    })
                    st.dataframe(_df_show, use_container_width=True, hide_index=True)
                else:
                    st.info("No stocks passed all criteria. Try relaxing the filters.")


# ══════════════════════════════════════════════════════════════════════════════
#  v4.0 Phase-3 — PORTFOLIO ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'PORTFOLIO':
    st.markdown('<div class="page-title">🗂️ Portfolio Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Factor exposure · VaR/CVaR · Stress testing · Walk-forward backtest</div>', unsafe_allow_html=True)

    if not _PORT_OK:
        st.error("❌ portfolio_analytics module not available. Ensure portfolio_analytics.py is in the same folder.")
    else:
        # ── Holdings source ───────────────────────────────────────────────────
        _src_mode = st.radio(
            "Holdings source", ["🔄 Auto-load from Dhan", "✏️ Manual entry"],
            horizontal=True, key="port_src_mode",
            label_visibility="collapsed",
        )

        if _src_mode == "🔄 Auto-load from Dhan":
            # Build raw string from df_live_holdings (already fetched at app start)
            if df_live_holdings is not None and not df_live_holdings.empty:
                _dhan_lines = []
                for _, _dh_row in df_live_holdings.iterrows():
                    _dh_sym = str(_dh_row.get("Symbol", "")).strip()
                    if not _dh_sym:
                        continue
                    if not _dh_sym.endswith(".NS"):
                        _dh_sym += ".NS"
                    _dh_qty  = float(_dh_row.get("Quantity", 0) or 0)
                    _dh_cost = float(_dh_row.get("BuyPrice", 0) or 0)
                    if _dh_qty > 0:
                        _dhan_lines.append(f"{_dh_sym}, {_dh_qty:.0f}, {_dh_cost:.2f}")
                _holdings_raw = "\n".join(_dhan_lines)
                st.session_state.port_holdings_raw = _holdings_raw
                _n_pos = len(_dhan_lines)
                st.success(f"✅ Loaded {_n_pos} position{'s' if _n_pos != 1 else ''} from Dhan holdings")
                with st.expander("📋 View loaded holdings"):
                    st.code(_holdings_raw, language="text")
            else:
                _holdings_raw = st.session_state.port_holdings_raw
                st.warning("⚠️ Dhan holdings unavailable (check connection or token). Using last saved holdings below.")
                with st.expander("📋 Saved holdings"):
                    st.code(_holdings_raw or "(empty)", language="text")
        else:
            # Manual entry mode
            with st.expander("📋 Enter Holdings (symbol, quantity, avg_cost — one per line)", expanded=st.session_state.port_holdings_raw == ''):
                _ph_raw = st.text_area(
                    "Holdings",
                    value=st.session_state.port_holdings_raw,
                    height=140,
                    key="port_holdings_input",
                    label_visibility="collapsed",
                    placeholder="RELIANCE.NS, 100, 2500\nINFY, 50, 1800\nTCS, 20, 3600",
                )
                _pv_col1, _ = st.columns([2, 4])
                with _pv_col1:
                    _port_val_input = st.number_input(
                        "Portfolio Value Override (₹, 0 = auto)",
                        min_value=0.0, value=st.session_state.port_value,
                        step=100000.0, key="port_val_input",
                    )
                if st.button("💾 Save Holdings", key="port_save", type="primary"):
                    st.session_state.port_holdings_raw = _ph_raw
                    st.session_state.port_value = _port_val_input
                    st.success("Holdings saved.")
            _holdings_raw = st.session_state.port_holdings_raw

        _port_val = st.session_state.port_value or None

        if not _holdings_raw.strip():
            st.info("No holdings loaded. Switch to **Auto-load from Dhan** or enter positions manually.")
        else:
            _port_tab1, _port_tab2, _port_tab3, _port_tab4 = st.tabs([
                "📊 Overview", "📉 Risk & VaR", "🔥 Stress Test", "🔄 Walk-Forward"
            ])

            # ── TAB 1 — OVERVIEW ────────────────────────────────────────────
            with _port_tab1:
                section("Portfolio Overview")
                with st.spinner("Fetching current prices & sector data..."):
                    try:
                        _ov = portfolio_overview(_holdings_raw, _port_val)
                    except Exception as _ove:
                        _ov = {}; st.error(f"Overview failed: {_ove}")

                if not _ov:
                    st.warning("Could not build overview — check symbol format (e.g. RELIANCE.NS).")
                else:
                    # ── Live-price health check (10 May 2026) ────────────────
                    # Surface the case where data_provider + yfinance both
                    # failed to fetch live prices. Previously the page
                    # silently fell back to avg_cost → P&L mechanically
                    # showed 0.0% with no explanation.
                    _failed_syms = _ov.get("live_price_failures", [])
                    _ok_count    = _ov.get("live_price_ok_count", 0)
                    _total_pos   = _ov.get("num_positions", 0)
                    if _failed_syms:
                        st.warning(
                            f"⚠ **Live prices unavailable for {len(_failed_syms)}/"
                            f"{_total_pos} positions** — "
                            f"P&L on those positions reads 0% because the "
                            f"current_price fell back to avg_cost. "
                            f"Symbols: `{', '.join(_failed_syms[:8])}`"
                            + (f" + {len(_failed_syms)-8} more" if len(_failed_syms) > 8 else "")
                            + ". Likely yfinance/data_provider transient failure — try refresh "
                              "in 1-2 min, or check internet/cache."
                        )

                    # Summary metrics row
                    _ov_c = st.columns(4)
                    _ov_c[0].metric("Positions",     _ov.get("num_positions", 0))
                    _ov_c[1].metric("Portfolio Value", f"₹{_ov.get('total_value',0):,.0f}")
                    _ov_c[2].metric("Total Cost",     f"₹{_ov.get('total_cost',0):,.0f}")
                    _pnl = _ov.get("total_pnl_pct", 0)
                    # If ALL live prices failed, the P&L is mechanically 0% —
                    # show as "—" instead of misleading "+0.00%".
                    if _failed_syms and len(_failed_syms) == _total_pos:
                        _ov_c[3].metric("Unrealised P&L", "— (no live data)",
                                        help="All positions fell back to avg_cost. "
                                             "Wait for live price feed to recover.")
                    else:
                        _ov_c[3].metric("Unrealised P&L", f"{_pnl:+.2f}%",
                                        delta=f"{_pnl:+.2f}%",
                                        delta_color="normal" if _pnl >= 0 else "inverse")

                    st.markdown("---")
                    _ov_left, _ov_right = st.columns(2, gap="large")

                    with _ov_left:
                        # Holdings table
                        section("All Holdings")
                        _h_rows = []
                        for _h in _ov.get("holdings", []):
                            _h_rows.append({
                                "Symbol":    _h["symbol"].replace(".NS",""),
                                "Qty":       int(_h["quantity"]),
                                "Avg Cost":  f"₹{_h.get('avg_cost',0):,.0f}",
                                "LTP":       f"₹{_h.get('current_price',0):,.2f}",
                                "Mkt Value": f"₹{_h.get('market_value',0):,.0f}",
                                "Weight%":   f"{_h.get('weight',0)*100:.1f}%",
                                "P&L%":      f"{_h.get('pnl_pct',0):+.1f}%",
                                "Sector":    _h.get("sector","—"),
                            })
                        if _h_rows:
                            st.dataframe(pd.DataFrame(_h_rows), use_container_width=True, hide_index=True)

                        # HHI
                        _hhi = _ov.get("hhi", 0)
                        _hhi_label = "Low Concentration" if _hhi < 1000 else "Moderate" if _hhi < 2500 else "Highly Concentrated"
                        _hhi_color = "#00f260" if _hhi < 1000 else "#e3b341" if _hhi < 2500 else "#ff4b4b"
                        st.markdown(
                            f'<div class="metric-card" style="padding:10px 14px;margin-top:10px">'
                            f'<span style="color:#8b949e;font-size:0.78rem">HHI Concentration Index: </span>'
                            f'<span style="color:{_hhi_color};font-weight:700">{_hhi:.0f} — {_hhi_label}</span>'
                            f'</div>', unsafe_allow_html=True
                        )

                    with _ov_right:
                        # Top 5
                        section("Top 5 Holdings")
                        for _t5 in _ov.get("top5", []):
                            _w = _t5["weight_pct"]
                            st.markdown(
                                f'<div style="margin-bottom:6px">'
                                f'<div style="display:flex;justify-content:space-between;font-size:0.82rem;color:#c9d1d9">'
                                f'<span>{_t5["symbol"]}</span><span style="color:#58a6ff">{_w:.1f}%</span></div>'
                                f'<div style="background:#1e3a5f;border-radius:4px;height:6px;margin-top:3px">'
                                f'<div style="background:#58a6ff;width:{min(_w,100):.0f}%;height:100%;border-radius:4px"></div>'
                                f'</div></div>', unsafe_allow_html=True
                            )

                        # Sector pie chart — same dark-text fix as Stage Map donut
                        # (10 May 2026 user feedback: % labels were unreadable
                        # white-on-bright wedges).
                        section("Sector Allocation")
                        _sw = _ov.get("sector_weights", {})
                        if _sw:
                            _fig_sec = go.Figure(go.Pie(
                                labels=list(_sw.keys()),
                                values=list(_sw.values()),
                                hole=0.45,
                                textinfo="label+percent",
                                textfont=dict(size=12, color="#0a0e14"),  # dark text on wedge
                                textposition="inside",
                                insidetextorientation="horizontal",
                                marker=dict(colors=[
                                    "#58a6ff","#00f260","#e3b341","#ff4b4b","#a78bfa",
                                    "#f97316","#06b6d4","#ec4899","#84cc16","#14b8a6","#f43f5e"
                                ])
                            ))
                            _fig_sec.update_layout(
                                height=300, margin=dict(t=0,l=0,r=0,b=0),
                                paper_bgcolor="rgba(0,0,0,0)",
                                showlegend=False, font=dict(color="#c9d1d9")
                            )
                            st.plotly_chart(_fig_sec, use_container_width=True)

            # ── TAB 2 — RISK & VaR ──────────────────────────────────────────
            with _port_tab2:
                section("Risk Metrics & Factor Exposure")
                _r_c1, _r_c2 = st.columns(2)
                with _r_c1:
                    _var_conf  = st.selectbox("VaR Confidence", [0.90, 0.95, 0.99], index=1, key="var_conf",
                                               format_func=lambda x: f"{x*100:.0f}%")
                    _var_look  = st.selectbox("Lookback (days)", [126, 252, 504], index=1, key="var_look")
                with _r_c2:
                    _factor_period = st.selectbox("Factor Period", ["6mo","1y","2y"], index=1, key="factor_period")

                _r_run = st.button("⚙️ Compute Risk Metrics", key="risk_run", type="primary")
                if _r_run:
                    with st.spinner("Running risk calculations (may take ~30s)..."):
                        try:
                            _var_res = compute_var(_holdings_raw, _var_conf, _var_look, _port_val)
                        except Exception as _ve:
                            _var_res = {}; st.error(f"VaR failed: {_ve}")
                        try:
                            _fac_res = compute_factor_exposure(_holdings_raw, _factor_period)
                        except Exception as _fe:
                            _fac_res = {}; st.error(f"Factor exposure failed: {_fe}")

                    if _var_res:
                        st.markdown("---")
                        section("Value at Risk (Historical)")
                        _v1, _v2, _v3, _v4 = st.columns(4)
                        _v1.metric("1-Day VaR",       f"{_var_res['var_1d_pct']:.2f}%",    help="Historical simulation at chosen confidence")
                        _v2.metric("1-Day VaR (₹)",   f"₹{_var_res['var_1d_inr']:,.0f}")
                        _v3.metric("CVaR (ES)",        f"{_var_res['cvar_1d_pct']:.2f}%",   help="Expected loss beyond VaR threshold")
                        _v4.metric("10-Day VaR",       f"{_var_res['var_10d_pct']:.2f}%",   help="Scaled via sqrt-of-time rule")

                        _v5, _v6, _v7, _v8 = st.columns(4)
                        _v5.metric("Parametric VaR",  f"{_var_res['var_parametric_pct']:.2f}%", help="Normal distribution assumption")
                        _v6.metric("Annual Vol",       f"{_var_res['volatility_annual_pct']:.1f}%")
                        _v7.metric("Annual Return",    f"{_var_res['annualized_return_pct']:+.1f}%")
                        _v8.metric("Max Drawdown",     f"{_var_res['max_drawdown_pct']:.1f}%")

                    if _fac_res:
                        st.markdown("---")
                        section("Factor Exposure vs Nifty50")
                        _f1, _f2, _f3, _f4 = st.columns(4)
                        _beta = _fac_res.get("portfolio_beta", 0)
                        _beta_color = "#ff4b4b" if _beta > 1.3 else "#e3b341" if _beta > 1.0 else "#00f260"
                        _f1.metric("Portfolio Beta",   f"{_beta:.2f}",      help=">1 = more volatile than Nifty")
                        _f2.metric("Nifty Correlation",f"{_fac_res.get('benchmark_corr',0):.2f}")
                        _f3.metric("Tracking Error",   f"{_fac_res.get('tracking_error_annual',0):.1f}%", help="Annual active risk vs benchmark")
                        _f4.metric("Alpha (Annual)",   f"{_fac_res.get('alpha_annual',0):+.1f}%",         help="Jensen's alpha annualised")

                        _f5, _f6 = st.columns(2)
                        _f5.metric("Sharpe Ratio",     f"{_fac_res.get('sharpe',0):.2f}", help="Risk-free rate = 6.5%")
                        _f6.metric("Sortino Ratio",    f"{_fac_res.get('sortino',0):.2f}")

                        # Per-symbol beta bar chart
                        _sym_betas = _fac_res.get("symbol_betas", {})
                        if _sym_betas:
                            section("Per-Symbol Beta")
                            _sb_df = pd.DataFrame(
                                [{"Symbol": s, "Beta": b} for s, b in _sym_betas.items()]
                            ).sort_values("Beta", ascending=False)
                            _fig_beta = go.Figure(go.Bar(
                                x=_sb_df["Symbol"], y=_sb_df["Beta"],
                                marker_color=["#ff4b4b" if b > 1.2 else "#e3b341" if b > 1.0 else "#58a6ff"
                                              for b in _sb_df["Beta"]],
                                text=[f"{b:.2f}" for b in _sb_df["Beta"]], textposition="outside",
                            ))
                            _fig_beta.add_hline(y=1.0, line_dash="dash", line_color="#3d5a6e", line_width=1)
                            _fig_beta.update_layout(
                                height=280, margin=dict(t=20,l=0,r=0,b=40),
                                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                                xaxis=dict(tickfont=dict(size=9,color="#c9d1d9"), gridcolor="#1e3a5f"),
                                yaxis=dict(gridcolor="#1e3a5f", title="Beta"),
                                font=dict(color="#c9d1d9"),
                            )
                            st.plotly_chart(_fig_beta, use_container_width=True)

            # ── TAB 3 — STRESS TEST ─────────────────────────────────────────
            with _port_tab3:
                section("Historical Stress Scenarios")
                st.caption("Simulates how your current portfolio would have performed during past market events (using current weights applied to historical returns).")

                _st_run = st.button("🔥 Run Stress Test", key="stress_run", type="primary")
                if _st_run:
                    with st.spinner("Downloading historical data for all scenarios..."):
                        try:
                            _st_results = run_stress_test(_holdings_raw, _port_val)
                        except Exception as _ste:
                            _st_results = []; st.error(f"Stress test failed: {_ste}")

                    if _st_results:
                        # Summary table
                        _st_rows = []
                        for _s in _st_results:
                            _port_r = _s["portfolio_return"]
                            _bench_r= _s["benchmark_return"]
                            _exc    = _s["excess_return"]
                            _st_rows.append({
                                "Scenario":       _s["scenario"],
                                "Period":         f"{_s['start']} → {_s['end']}",
                                "Portfolio %":    f"{_port_r:+.1f}%",
                                "Nifty %":        f"{_bench_r:+.1f}%",
                                "Alpha":          f"{_exc:+.1f}%",
                                "P&L (₹)":        f"₹{_s['pnl_inr']:+,.0f}" if _s.get("pnl_inr") else "—",
                            })
                        st.dataframe(pd.DataFrame(_st_rows), use_container_width=True, hide_index=True)

                        # Bar chart — portfolio vs benchmark per scenario
                        _sc_labels = [_s["scenario"][:30] for _s in _st_results]
                        _sc_port   = [_s["portfolio_return"] for _s in _st_results]
                        _sc_bench  = [_s["benchmark_return"]  for _s in _st_results]

                        _fig_st = go.Figure()
                        _fig_st.add_trace(go.Bar(
                            name="Portfolio", x=_sc_labels, y=_sc_port,
                            marker_color=["#00f260" if v >= 0 else "#ff4b4b" for v in _sc_port],
                            text=[f"{v:+.1f}%" for v in _sc_port], textposition="outside",
                        ))
                        _fig_st.add_trace(go.Bar(
                            name="Nifty50", x=_sc_labels, y=_sc_bench,
                            marker_color="rgba(88,166,255,0.5)",
                            text=[f"{v:+.1f}%" for v in _sc_bench], textposition="outside",
                        ))
                        _fig_st.update_layout(
                            barmode="group", height=360,
                            margin=dict(t=20,l=0,r=0,b=100),
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                            xaxis=dict(tickangle=-30, tickfont=dict(size=9,color="#c9d1d9"), gridcolor="#1e3a5f"),
                            yaxis=dict(gridcolor="#1e3a5f", title="Return (%)"),
                            legend=dict(font=dict(size=10,color="#c9d1d9"), bgcolor="rgba(0,0,0,0)"),
                            font=dict(color="#c9d1d9"),
                        )
                        st.plotly_chart(_fig_st, use_container_width=True)
                    elif _st_run:
                        st.info("No scenario data returned — check holdings format or internet connection.")
                else:
                    st.info("Click **Run Stress Test** to simulate your portfolio across 6 historical market events.")

            # ── TAB 4 — WALK-FORWARD BACKTEST ───────────────────────────────
            with _port_tab4:
                section("Walk-Forward Weinstein Stage 2 Backtest")
                st.caption("Enters stocks when price > SMA50 & SMA200. Equal-weight. Rebalances on schedule.")

                _wf_c1, _wf_c2, _wf_c3 = st.columns(3)
                with _wf_c1:
                    _wf_start = st.date_input("Start Date", value=pd.Timestamp("2022-01-01"), key="wf_start")
                with _wf_c2:
                    _wf_rebal = st.selectbox("Rebalance", ["Weekly (1w)","Bi-Weekly (2w)","Monthly (4w)"],
                                              index=2, key="wf_rebal")
                    _wf_rebal_weeks = {"Weekly (1w)": 1, "Bi-Weekly (2w)": 2, "Monthly (4w)": 4}[_wf_rebal]
                with _wf_c3:
                    _wf_univ_choice = st.selectbox("Universe", ["Use my holdings","Nifty 50 subset","Custom"], key="wf_univ")

                if _wf_univ_choice == "Custom":
                    _wf_custom = st.text_area("Custom universe (one symbol per line)",
                                               height=80, key="wf_custom_syms",
                                               placeholder="RELIANCE\nINFY\nTCS")
                    _wf_universe_raw = _wf_custom
                elif _wf_univ_choice == "Use my holdings":
                    _parsed_h = parse_holdings(_holdings_raw)
                    _wf_universe_raw = "\n".join(h["symbol"] for h in _parsed_h)
                else:
                    _wf_universe_raw = "\n".join([
                        "RELIANCE","TCS","HDFCBANK","ICICIBANK","INFY",
                        "HINDUNILVR","ITC","SBIN","BHARTIARTL","KOTAKBANK",
                        "LT","AXISBANK","ASIANPAINT","MARUTI","TITAN",
                        "BAJFINANCE","WIPRO","ULTRACEMCO","POWERGRID","NTPC",
                    ])

                _wf_run = st.button("🔄 Run Backtest", key="wf_run", type="primary")

                if _wf_run:
                    with st.spinner("Running walk-forward backtest (may take 60–120s for large universes)..."):
                        try:
                            _wf_res = run_walkforward_backtest(
                                _wf_universe_raw,
                                start=str(_wf_start),
                                rebalance_weeks=_wf_rebal_weeks,
                            )
                        except Exception as _wfe:
                            _wf_res = {}; st.error(f"Backtest failed: {_wfe}")

                    if _wf_res:
                        # Stats header
                        _wf_cols = st.columns(5)
                        _wf_cols[0].metric("Strategy CAGR",  f"{_wf_res['cagr_pct']:+.1f}%")
                        _wf_cols[1].metric("Benchmark CAGR", f"{_wf_res['benchmark_cagr_pct']:+.1f}%",
                                           delta=f"{_wf_res['cagr_pct']-_wf_res['benchmark_cagr_pct']:+.1f}% vs Nifty")
                        _wf_cols[2].metric("Sharpe",         f"{_wf_res['sharpe']:.2f}")
                        _wf_cols[3].metric("Max Drawdown",   f"{_wf_res['max_drawdown_pct']:.1f}%")
                        _wf_cols[4].metric("Avg Positions",  f"{_wf_res['avg_positions']:.0f}")

                        st.markdown("---")
                        # Equity curve chart
                        _eq = pd.DataFrame(_wf_res["equity_curve"])
                        _fig_eq = go.Figure()
                        _fig_eq.add_trace(go.Scatter(
                            x=_eq["date"], y=_eq["portfolio_value"],
                            name="Strategy", line=dict(color="#00f260", width=2),
                        ))
                        _fig_eq.add_trace(go.Scatter(
                            x=_eq["date"], y=_eq["benchmark_value"],
                            name="Nifty50 (buy & hold)", line=dict(color="#58a6ff", width=1.5, dash="dot"),
                        ))
                        _fig_eq.add_hline(y=100, line_dash="dot", line_color="#3d5a6e", line_width=1)
                        _fig_eq.update_layout(
                            height=380, margin=dict(t=10,l=0,r=0,b=0),
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                            xaxis=dict(gridcolor="#1e3a5f"),
                            yaxis=dict(gridcolor="#1e3a5f", title="Indexed (Base 100)"),
                            legend=dict(font=dict(size=10,color="#c9d1d9"), bgcolor="rgba(0,0,0,0)"),
                            font=dict(color="#c9d1d9"),
                        )
                        st.plotly_chart(_fig_eq, use_container_width=True)
                        st.caption(f"Total return: Strategy {_wf_res['total_return_pct']:+.1f}% | Nifty {_wf_res['benchmark_total_return_pct']:+.1f}% | Rebalances: {_wf_res['num_rebalances']}")
                    elif _wf_run:
                        st.info("No backtest results — check universe symbols or widen the date range.")
                else:
                    st.info("Configure the parameters above and click **Run Backtest** to begin.")

        # ── Portfolio Export ─────────────────────────────────────────────────
        st.markdown("---")
        section("Export")
        _px1, _px2 = st.columns(2, gap="small")
        with _px1:
            if df_live_holdings is not None and not df_live_holdings.empty:
                st.download_button(
                    "📥 Download Holdings (CSV)",
                    data=df_live_holdings.to_csv(index=False).encode("utf-8"),
                    file_name=f"Holdings_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv", use_container_width=True, key="port_dl_csv",
                )
            else:
                st.caption("Holdings not loaded — use Auto-load from Dhan above.")
        with _px2:
            if st.session_state.get("port_holdings_raw") and _GEMINI_OK:
                if st.button("🤖 AI Portfolio Analysis Report", use_container_width=True,
                             key="port_ai_dl"):
                    with st.spinner("Generating AI analysis…"):
                        try:
                            _px_analytics = {}
                            if _PORT_OK:
                                _px_ov = portfolio_overview(
                                    st.session_state["port_holdings_raw"], _port_val)
                                _px_analytics = _px_ov if isinstance(_px_ov, dict) else {}
                            _px_report = generate_portfolio_review(
                                df_live_holdings if df_live_holdings is not None else pd.DataFrame(),
                                _px_analytics)
                            st.session_state["port_ai_report"] = _px_report
                        except Exception as _pxe:
                            st.error(f"AI report failed: {_pxe}")
                if st.session_state.get("port_ai_report"):
                    st.download_button(
                        "📥 Save AI Report (.txt)",
                        data=st.session_state["port_ai_report"],
                        file_name=f"Portfolio_AI_{datetime.now().strftime('%Y%m%d')}.txt",
                        mime="text/plain", use_container_width=True, key="port_ai_dl2",
                    )


# ══════════════════════════════════════════════════════════════════════════════
#  X-RAY — Deep Fundamental Analysis
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'X-RAY':
    st.markdown('<div class="page-title">🧬 Stock X-Ray</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Deep-dive fundamental analysis — valuation · financials · quarterly results · sector comparison · multi-stock screen <span style="color:#5a8a9f;font-size:0.7rem;">(absorbed Fundamentals 10 May 2026)</span></div>', unsafe_allow_html=True)

    def sync_tv_symbol_xray():
        import subprocess
        import csv
        import re
        from io import StringIO
        
        browsers = ['TradingView.exe', 'chrome.exe', 'msedge.exe', 'brave.exe']
        for browser in browsers:
            try:
                res = subprocess.run(['tasklist', '/fi', f'imagename eq {browser}', '/v', '/fo', 'csv'], capture_output=True, text=True, errors='ignore', timeout=2)
                reader = csv.reader(StringIO(res.stdout))
                for row in reader:
                    if len(row) > 8:
                        exe = row[0].lower()
                        title = row[8]
                        if ('tradingview.exe' in exe and title not in ('N/A', 'OleMainThreadWndName', 'Input-Sink', 'Default IME', 'INFO')) or \
                           ('TradingView' in title and '—' in title):
                            match = re.search(r'^(.*?)\s+[\d,]+\.\d{1,4}(?:\s|%|\+|-|$)', title)
                            if match:
                                sym = match.group(1).strip()
                                if sym.upper() in ["NIFTY 50", "NIFTY"]: sym = "^NSEI"
                                elif sym.upper() in ["NIFTY BANK", "BANKNIFTY"]: sym = "^NSEBANK"
                                elif sym.upper() == "NIFTY 500": sym = "^CRSLDX"
                                else:
                                    if not sym.endswith(".NS") and "^" not in sym and "=" not in sym: sym += ".NS"
                                st.session_state["xr_sym_input"] = sym
                                st.session_state["xr_symbol"] = sym
                                return
            except Exception:
                pass

    if not _FUND_OK:
        st.error("❌ fundamental_hub module not available.")
    else:
        _xr_col1, _ = st.columns([2, 4])
        with _xr_col1:
            st.button("🔄 Sync with TV", on_click=sync_tv_symbol_xray, help="Auto-read symbol from open TradingView", use_container_width=True, key="xr_sync_btn")
            
            if "xr_sym_input" not in st.session_state:
                st.session_state["xr_sym_input"] = st.session_state.get("xr_symbol", "RELIANCE.NS")
                
            _xr_sym = st.text_input(
                "NSE Symbol", 
                key="xr_sym_input", placeholder="e.g. INFY.NS, TCS.NS"
            ).strip().upper()
            if _xr_sym and not _xr_sym.endswith(".NS"):
                _xr_sym += ".NS"
            if _xr_sym:
                st.session_state["xr_symbol"] = _xr_sym

        # P2 follow-up D (10 May 2026): added "📰 News" tab so per-stock news is
        # available where the trader is doing the deep-dive — instead of having
        # to switch to the standalone NEWS page and manually filter.
        _xr_t1, _xr_t2, _xr_t3, _xr_t4, _xr_t5, _xr_t6 = st.tabs([
            "📊 Snapshot", "📋 Income Statement", "📆 Quarterly Results",
            "🎯 Scorecard", "🔍 Screen", "📰 News"
        ])

        # ── TAB 1 — SNAPSHOT ────────────────────────────────────────────────
        with _xr_t1:
            if not _xr_sym:
                st.info("Enter an NSE symbol above.")
            else:
                with st.spinner(f"Loading X-Ray for {_xr_sym}..."):
                    try:
                        _xr_fd = fetch_stock_fundamentals(_xr_sym)
                    except Exception as _xre:
                        _xr_fd = {}; st.error(f"Fetch failed: {_xre}")

                if _xr_fd:
                    st.markdown(
                        f'<div class="metric-card" style="padding:12px 16px;margin-bottom:14px">'
                        f'<div style="font-size:1.1rem;font-weight:700;color:#58a6ff">{_xr_fd.get("name","")}</div>'
                        f'<div style="font-size:0.78rem;color:#8b949e">{_xr_fd.get("sector","")} › {_xr_fd.get("industry","")}</div>'
                        f'</div>', unsafe_allow_html=True
                    )
                    # Price
                    _xr_r1 = st.columns(4)
                    _xr_r1[0].metric("Price",       f"₹{_xr_fd.get('price',0):,.2f}")
                    _xr_r1[1].metric("Market Cap",  f"₹{_xr_fd.get('market_cap',0):,.0f}Cr" if _xr_fd.get('market_cap') else "N/A")
                    _xr_r1[2].metric("52W vs High", f"{_xr_fd.get('week52_vs_high',0):+.1f}%" if _xr_fd.get('week52_vs_high') is not None else "N/A")
                    _xr_r1[3].metric("Beta",        f"{_xr_fd.get('beta',0):.2f}" if _xr_fd.get('beta') else "N/A")
                    st.markdown("---")
                    # Valuation
                    section("Valuation")
                    _xr_r2 = st.columns(5)
                    _xr_r2[0].metric("P/E",      f"{_xr_fd.get('pe_ratio',0):.1f}x"   if _xr_fd.get('pe_ratio')   else "N/A")
                    _xr_r2[1].metric("Fwd P/E",  f"{_xr_fd.get('forward_pe',0):.1f}x" if _xr_fd.get('forward_pe') else "N/A")
                    _xr_r2[2].metric("P/B",      f"{_xr_fd.get('pb_ratio',0):.2f}x"   if _xr_fd.get('pb_ratio')   else "N/A")
                    _xr_r2[3].metric("EV/EBITDA",f"{_xr_fd.get('ev_ebitda',0):.1f}x"  if _xr_fd.get('ev_ebitda')  else "N/A")
                    _xr_r2[4].metric("P/S",      f"{_xr_fd.get('ps_ratio',0):.2f}x"   if _xr_fd.get('ps_ratio')   else "N/A")
                    # Profitability
                    section("Profitability")
                    _xr_r3 = st.columns(5)
                    _xr_r3[0].metric("Net Margin",  f"{_xr_fd.get('profit_margin',0):.1f}%"    if _xr_fd.get('profit_margin')    else "N/A")
                    _xr_r3[1].metric("Op Margin",   f"{_xr_fd.get('operating_margin',0):.1f}%" if _xr_fd.get('operating_margin') else "N/A")
                    _xr_r3[2].metric("ROE",         f"{_xr_fd.get('roe',0):.1f}%"             if _xr_fd.get('roe')              else "N/A")
                    _xr_r3[3].metric("ROA",         f"{_xr_fd.get('roa',0):.1f}%"             if _xr_fd.get('roa')              else "N/A")
                    _xr_r3[4].metric("Div Yield",   f"{_xr_fd.get('dividend_yield',0):.2f}%"  if _xr_fd.get('dividend_yield')   else "N/A")
                    # Balance sheet
                    section("Balance Sheet")
                    _xr_r4 = st.columns(4)
                    _xr_r4[0].metric("Revenue (TTM)",  f"₹{_xr_fd.get('revenue_ttm',0):,.0f}Cr"    if _xr_fd.get('revenue_ttm')    else "N/A")
                    _xr_r4[1].metric("Net Income",     f"₹{_xr_fd.get('net_income_ttm',0):,.0f}Cr" if _xr_fd.get('net_income_ttm') else "N/A")
                    _xr_r4[2].metric("Debt/Equity",    f"{_xr_fd.get('debt_equity',0):.2f}x"        if _xr_fd.get('debt_equity')    else "N/A")
                    _xr_r4[3].metric("Current Ratio",  f"{_xr_fd.get('current_ratio',0):.2f}"       if _xr_fd.get('current_ratio')  else "N/A")

        # ── TAB 2 — INCOME STATEMENT ────────────────────────────────────────
        with _xr_t2:
            if not _xr_sym:
                st.info("Enter an NSE symbol above.")
            else:
                with st.spinner("Loading financial statements..."):
                    try:
                        _xr_fs = fetch_financial_statements(_xr_sym)
                    except Exception as _xrfe:
                        _xr_fs = {}; st.error(f"Failed: {_xrfe}")

                if _xr_fs:
                    for _stmt_name, _stmt_df in _xr_fs.items():
                        section(_stmt_name)
                        if isinstance(_stmt_df, pd.DataFrame) and not _stmt_df.empty:
                            st.dataframe(_stmt_df, use_container_width=True)
                        else:
                            st.caption("No data available.")
                else:
                    st.info("Financial statement data unavailable for this symbol.")

        # ── TAB 3 — QUARTERLY RESULTS ────────────────────────────────────────
        with _xr_t3:
            if not _xr_sym:
                st.info("Enter an NSE symbol above.")
            else:
                with st.spinner("Loading quarterly results..."):
                    try:
                        _xr_qr = fetch_quarterly_results(_xr_sym)
                    except Exception as _xrqe:
                        _xr_qr = pd.DataFrame(); st.error(f"Failed: {_xrqe}")

                if isinstance(_xr_qr, pd.DataFrame) and not _xr_qr.empty:
                    section("Quarterly Results")
                    st.dataframe(_xr_qr, use_container_width=True, hide_index=True)

                    # Revenue trend chart
                    _rev_cols = [c for c in _xr_qr.columns if 'revenue' in c.lower() or 'sales' in c.lower() or 'total revenue' in c.lower()]
                    _prof_cols = [c for c in _xr_qr.columns if 'net income' in c.lower() or 'profit' in c.lower()]
                    if _rev_cols or _prof_cols:
                        section("Revenue & Profit Trend")
                        # FIX (10 May 2026 — chart "shaking continuously" reported, then
                        # "whole screen shaking" after first attempt):
                        #
                        # Root cause: _xr_qr.index.astype(str) on a DatetimeIndex emitted
                        # "2025-12-31 00:00:00" which Plotly auto-parsed as dates each
                        # render → animated re-fit on every Streamlit rerun.
                        #
                        # First attempt added `responsive: False` which conflicted with
                        # `use_container_width=True` and caused horizontal layout thrash
                        # (the "whole screen shaking, more towards the right"). Removed.
                        #
                        # Final fix:
                        #   1. Stable Q-string x-labels (Q4-25, Q3-25, …) — no date re-parse
                        #   2. xaxis type="category" with pinned categoryarray — order fixed
                        #   3. transition.duration=0 — no animated re-fits
                        #   4. Stable Streamlit `key` (sanitised: dots stripped from sym)
                        #   5. NO `responsive: False` config (let Streamlit/Plotly negotiate)
                        #   6. Wrap in fixed-height st.container — prevents the chart from
                        #      pushing the page layout when its bbox is computed
                        def _fmt_quarter(idx_val):
                            try:
                                ts = pd.to_datetime(idx_val)
                                return f"Q{((ts.month - 1) // 3) + 1}-{ts.strftime('%y')}"
                            except Exception:
                                return str(idx_val)
                        _x_labels = [_fmt_quarter(i) for i in _xr_qr.index]
                        _fig_qr = go.Figure()
                        for _rc in _rev_cols[:1]:
                            _fig_qr.add_trace(go.Bar(name="Revenue", x=_x_labels,
                                                      y=_xr_qr[_rc], marker_color="#58a6ff"))
                        for _pc in _prof_cols[:1]:
                            _fig_qr.add_trace(go.Bar(name="Net Profit", x=_x_labels,
                                                      y=_xr_qr[_pc], marker_color="#00f260"))
                        _fig_qr.update_layout(
                            barmode="group", height=300, margin=dict(t=10,l=0,r=0,b=40),
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                            xaxis=dict(type="category", gridcolor="#1e3a5f", tickangle=-30,
                                       categoryorder="array", categoryarray=_x_labels),
                            yaxis=dict(gridcolor="#1e3a5f"),
                            legend=dict(font=dict(color="#c9d1d9"), bgcolor="rgba(0,0,0,0)"),
                            font=dict(color="#c9d1d9"),
                            transition=dict(duration=0),
                        )
                        _xr_sym_key = "".join(c if c.isalnum() else "_" for c in (_xr_sym or "x"))
                        with st.container(height=350):
                            st.plotly_chart(
                                _fig_qr, use_container_width=True,
                                key=f"xr_qr_chart_{_xr_sym_key}",
                            )
                else:
                    st.info("Quarterly results unavailable for this symbol.")

        # ── TAB 4 — SCORECARD ────────────────────────────────────────────────
        with _xr_t4:
            if not _xr_sym:
                st.info("Enter an NSE symbol above.")
            else:
                with st.spinner("Building Weinstein X-Ray Scorecard (Bypassing TV limitations)..."):
                    try:
                        from weinstein_xray_screener import get_xray_scorecard
                        _xr_sc = get_xray_scorecard(_xr_sym)
                    except Exception as _xrsce:
                        _xr_sc = {}; st.error(f"Scorecard failed: {_xrsce}")
                
                if _xr_sc and "error" not in _xr_sc:
                    st.markdown(
                        f'<div class="metric-card" style="padding:20px;text-align:center;margin-bottom:16px">'
                        f'<div style="font-size:2.4rem;font-weight:800;color:#58a6ff">{_xr_sc.get("Overall_Grade", "N/A")}</div>'
                        f'<div style="font-size:1rem;color:#c9d1d9;margin-top:4px">Overall Rating: {_xr_sc.get("Overall_Rating", 0)} / 17</div>'
                        f'</div>', unsafe_allow_html=True
                    )
                    
                    _col1, _col2 = st.columns(2)
                    with _col1:
                        section(f"Minervini Score: {_xr_sc.get('Minervini_Score', 0)}/8")
                        for _k, _v in _xr_sc.get("Minervini_Details", {}).items():
                            st.markdown(
                                f'<div style="padding:6px 0;border-bottom:1px solid #1e3a5f;display:flex;gap:8px;align-items:center">'
                                f'<span>{"✅" if _v == 1 else "❌"}</span>'
                                f'<span style="flex:1;font-size:0.85rem;color:#c9d1d9">{_k}</span>'
                                f'</div>', unsafe_allow_html=True
                            )
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        section("Overall Breakdown")
                        for _k, _v in _xr_sc.get("Overall_Details", {}).items():
                            st.markdown(
                                f'<div style="padding:6px 0;border-bottom:1px solid #1e3a5f;display:flex;gap:8px;align-items:center">'
                                f'<span style="flex:1;font-size:0.85rem;color:#c9d1d9">{_k}</span>'
                                f'<span style="color:#e3b341;font-weight:bold;">{_v}</span>'
                                f'</div>', unsafe_allow_html=True
                            )
                            
                    with _col2:
                        section(f"Piotroski F-Score: {_xr_sc.get('Piotroski_Score', 0)}/9")
                        for _k, _v in _xr_sc.get("Piotroski_Details", {}).items():
                            st.markdown(
                                f'<div style="padding:6px 0;border-bottom:1px solid #1e3a5f;display:flex;gap:8px;align-items:center">'
                                f'<span>{"✅" if _v == 1 else "❌"}</span>'
                                f'<span style="flex:1;font-size:0.85rem;color:#c9d1d9">{_k}</span>'
                                f'</div>', unsafe_allow_html=True
                            )
                elif "error" in _xr_sc:
                    st.warning("Insufficient financial data from yfinance to calculate X-Ray.")

        # ── TAB 5 — SCREEN (absorbed from former Fundamentals page) ─────────
        with _xr_t5:
            section("Multi-Stock Fundamental Screener")
            st.caption("Filter NSE stocks by valuation, profitability, and growth criteria. "
                       "Same engine that powered the (now-merged) Fundamentals page.")
            _xsc_c1, _xsc_c2, _xsc_c3 = st.columns(3)
            with _xsc_c1:
                _xsc_max_pe   = st.number_input("Max P/E",      min_value=0.0, max_value=200.0, value=30.0, step=1.0, key="xsc_pe")
                _xsc_min_roe  = st.number_input("Min ROE (%)",  min_value=0.0, max_value=100.0, value=15.0, step=1.0, key="xsc_roe")
            with _xsc_c2:
                _xsc_max_de   = st.number_input("Max Debt/Eq",  min_value=0.0, max_value=10.0,  value=1.0,  step=0.1, key="xsc_de")
                _xsc_min_marg = st.number_input("Min Net Margin (%)", min_value=0.0, max_value=100.0, value=10.0, step=1.0, key="xsc_margin")
            with _xsc_c3:
                _xsc_universe = st.selectbox(
                    "Universe", ["Nifty 50", "Nifty 500", "Custom"], key="xsc_uni",
                    help="Nifty 500 = backtest-aligned full universe (validation.default_universe)"
                )
                _xsc_custom = st.text_area("Custom symbols (one per line, with .NS)",
                    height=68, key="xsc_custom",
                    placeholder="RELIANCE.NS\nINFY.NS\nHDFCBANK.NS")

            if st.button("🔍 Run Screen", key="xsc_run", type="primary"):
                if _xsc_universe == "Custom" and _xsc_custom.strip():
                    _xsc_syms = [s.strip().upper() for s in _xsc_custom.strip().splitlines() if s.strip()]
                elif _xsc_universe == "Nifty 500":
                    try:
                        import validation as _val_xsc
                        _xsc_syms = [
                            s if s.endswith(".NS") else (s + ".NS")
                            for s in _val_xsc.default_universe("nifty500")
                        ]
                    except Exception as _xsc500e:
                        st.error(f"Could not load Nifty 500: {_xsc500e}")
                        _xsc_syms = []
                else:
                    _xsc_syms = [
                        "RELIANCE.NS","TCS.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS",
                        "HINDUNILVR.NS","ITC.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
                        "LT.NS","AXISBANK.NS","ASIANPAINT.NS","MARUTI.NS","TITAN.NS",
                        "BAJFINANCE.NS","WIPRO.NS","ULTRACEMCO.NS","NESTLEIND.NS","POWERGRID.NS",
                        "NTPC.NS","ONGC.NS","JSWSTEEL.NS","TATAMOTORS.NS","ADANIPORTS.NS",
                        "CIPLA.NS","DRREDDY.NS","SUNPHARMA.NS","DIVISLAB.NS","TECHM.NS",
                    ]
                _xsc_criteria = {
                    "pe_ratio":      (0, _xsc_max_pe),
                    "roe":           (_xsc_min_roe, 9999),
                    "debt_equity":   (0, _xsc_max_de),
                    "profit_margin": (_xsc_min_marg, 9999),
                }
                with st.spinner(f"Screening {len(_xsc_syms)} stocks (may take 30–60s)..."):
                    try:
                        _xsc_df = screen_fundamentals(_xsc_syms, _xsc_criteria)
                    except Exception as _xsce:
                        _xsc_df = pd.DataFrame(); st.error(f"Screen failed: {_xsce}")

                if not _xsc_df.empty:
                    st.success(f"✅ {len(_xsc_df)} stocks passed all criteria")
                    _xsc_show_cols = [c for c in ["symbol","name","pe_ratio","roe","profit_margin",
                                                   "debt_equity","market_cap"] if c in _xsc_df.columns]
                    _xsc_show = _xsc_df[_xsc_show_cols].rename(columns={
                        "pe_ratio":"P/E","roe":"ROE%","profit_margin":"Net Margin%",
                        "debt_equity":"D/E","market_cap":"Mkt Cap (Cr)"
                    })
                    st.dataframe(_xsc_show, use_container_width=True, hide_index=True)
                else:
                    st.info("No stocks passed all criteria. Try relaxing the filters.")

        # ── TAB 6 — NEWS (per-stock filtered, NEW 10 May 2026) ──────────────
        # Per user feedback (D): a news headline about Reliance is most useful
        # when you're looking at Reliance, not at the start of the day. This
        # tab pulls from the same news_fetcher the standalone NEWS page uses,
        # then filters by ticker / company-name keywords for the symbol the
        # user is currently X-Raying.
        with _xr_t6:
            section(f"News — {_xr_sym or '(no symbol)'}")
            st.caption(
                "Articles + NSE announcements mentioning this ticker or its company name "
                "(headline + summary keyword match). Cached 30 min. "
                "Full market-wide feed is on **📰 NEWS**."
            )
            if not _xr_sym:
                st.info("Enter an NSE symbol above to filter news.")
            else:
                try:
                    from news_fetcher import get_news as _xr_get_news
                    _xr_news = _xr_get_news(hours_back=72)
                except Exception as _xrne:
                    _xr_news = {"articles": [], "announcements": []}
                    st.error(f"News fetch failed: {_xrne}")

                # Build search keywords: bare ticker + variations
                _xr_clean = (_xr_sym or "").upper().replace(".NS", "").replace(".BO", "")
                _xr_keywords = {_xr_clean}
                # Try common company-name variants for top tickers
                _xr_company_map = {
                    "RELIANCE": ["reliance industries", "ril"],
                    "TCS":      ["tata consultancy"],
                    "INFY":     ["infosys"],
                    "HDFCBANK": ["hdfc bank"],
                    "ICICIBANK":["icici bank"],
                    "SBIN":     ["state bank", "sbi"],
                    "BHARTIARTL":["bharti airtel", "airtel"],
                    "KOTAKBANK":["kotak mahindra", "kotak bank"],
                    "LT":       ["larsen", "l&t"],
                    "HCLTECH":  ["hcl technologies", "hcl tech"],
                    "WIPRO":    ["wipro"],
                    "AXISBANK": ["axis bank"],
                    "MARUTI":   ["maruti suzuki"],
                    "ASIANPAINT":["asian paints"],
                    "NESTLEIND":["nestle india"],
                    "HINDUNILVR":["hindustan unilever", "hul"],
                    "ITC":      ["itc"],
                    "ONGC":     ["oil and natural gas"],
                    "NTPC":     ["ntpc"],
                    "POWERGRID":["power grid"],
                }
                for kw in _xr_company_map.get(_xr_clean, []):
                    _xr_keywords.add(kw.upper())

                def _xr_news_match(item):
                    blob = (str(item.get("title", "")) + " " + str(item.get("summary", ""))).upper()
                    return any(kw in blob for kw in _xr_keywords)

                _xr_articles = [a for a in _xr_news.get("articles", []) if _xr_news_match(a)]
                _xr_anns     = [a for a in _xr_news.get("announcements", []) if _xr_news_match(a)]

                _xr_n1, _xr_n2 = st.columns(2)
                _xr_n1.metric(f"Matching articles", len(_xr_articles))
                _xr_n2.metric(f"NSE announcements", len(_xr_anns))
                st.caption(f"Match keywords: `{', '.join(sorted(_xr_keywords))}` · "
                           f"news cache fetched {_xr_news.get('fetched_at', '—')}")

                if _xr_articles:
                    section("📰 Articles")
                    for _a in _xr_articles[:25]:
                        _t = _a.get("title", "(no title)")
                        _s = _a.get("source", "")
                        _p = _a.get("published", "")
                        _u = _a.get("link", "")
                        _sm = _a.get("summary", "")[:300]
                        st.markdown(
                            f"**[{_t}]({_u})**  ·  *{_s}*  ·  {_p}\n\n"
                            f"<div style='font-size:0.82rem;color:#9ba8b6;'>{_sm}…</div>",
                            unsafe_allow_html=True,
                        )
                        st.markdown("---")

                if _xr_anns:
                    section("📢 NSE Corporate Announcements")
                    for _ann in _xr_anns[:15]:
                        _t = _ann.get("title", "(no title)")
                        _p = _ann.get("published", "")
                        _u = _ann.get("link", "")
                        _sm = _ann.get("summary", "")[:300]
                        st.markdown(
                            f"**[{_t}]({_u})**  ·  {_p}\n\n"
                            f"<div style='font-size:0.82rem;color:#9ba8b6;'>{_sm}</div>",
                            unsafe_allow_html=True,
                        )
                        st.markdown("---")

                if not _xr_articles and not _xr_anns:
                    st.info(f"No free RSS news in the last 72h mentioning **{_xr_clean}**. "
                            f"See the paid ET + MC section below.")

                # ── Paid sources: ET + Moneycontrol via analyst_sentiment ────
                # Stage 3b (10 May 2026): augments the free RSS feed with paid
                # ET + MC analyst recos and stock news. Cookies sourced from
                # data/paid_news_cookies/ (see setup_paid_news_cookies.py).
                st.markdown("---")
                section(f"📊 Analyst Sentiment + Paid News — {_xr_clean}")
                try:
                    import analyst_sentiment as _xr_ans
                    _xr_sent = _xr_ans.get_for_symbol(_xr_clean)

                    # Consensus badge + counts
                    _xr_cons = _xr_sent["consensus"]
                    _cons_color = {
                        "STRONG_BUY":  "#39ff14",  # bright neon green — louder than BUY
                        "BUY":         "#00f260",
                        "HOLD":        "#e3b341",
                        "SELL":        "#ff4b4b",
                        "STRONG_SELL": "#ff1744",  # bright red — louder than SELL
                        "MIXED":       "#a78bfa",
                        "NONE":        "#5a8a9f",
                    }.get(_xr_cons, "#5a8a9f")
                    # Display label: pretty-print the underscored ones
                    _cons_label_display = _xr_cons.replace("_", " ")

                    _xs1, _xs2, _xs3, _xs4, _xs5, _xs6 = st.columns(6)
                    _xs1.markdown(
                        f'<div class="metric-card">'
                        f'<div class="metric-label">Consensus</div>'
                        f'<div class="metric-value" style="color:{_cons_color}">{_cons_label_display}</div>'
                        f'</div>', unsafe_allow_html=True)
                    _xs2.metric("⭐ STRONG BUY", _xr_sent.get("strong_buy", 0))
                    _xs3.metric("BUY",          _xr_sent["buy"])
                    _xs4.metric("HOLD",         _xr_sent["hold"])
                    _xs5.metric("SELL",         _xr_sent["sell"])
                    _xs6.metric("⚠ STRONG SELL", _xr_sent.get("strong_sell", 0))

                    _src_ok = _xr_sent.get("sources_ok", {})
                    st.caption(
                        f"ET session: {'✓' if _src_ok.get('et') else '✗'}  ·  "
                        f"MC session: {'✓' if _src_ok.get('mc') else '✗'}  ·  "
                        f"Fetched: {_xr_sent.get('fetched_at', '—')}  ·  "
                        f"6h cache (re-runs are instant)"
                    )

                    _xr_items = _xr_sent.get("items", [])
                    if _xr_items:
                        # Show actionable items first — STRONG_BUY at top, then BUY, etc.
                        _action_order = {
                            "STRONG_BUY":  0,
                            "BUY":         1,
                            "STRONG_SELL": 2,
                            "SELL":        3,
                            "HOLD":        4,
                            "OTHER":       5,
                        }
                        _xr_items_sorted = sorted(
                            _xr_items,
                            key=lambda x: _action_order.get(x.get("action", "OTHER"), 6)
                        )
                        for _it in _xr_items_sorted[:30]:
                            _act = _it.get("action") or "?"
                            _act_col = {
                                "STRONG_BUY":  "#39ff14",
                                "BUY":         "#00f260",
                                "HOLD":        "#e3b341",
                                "SELL":        "#ff4b4b",
                                "STRONG_SELL": "#ff1744",
                            }.get(_act, "#5a8a9f")
                            # Pretty-print underscored buckets for the badge label
                            _act_label = _act.replace("_", " ")
                            _brk = _it.get("brokerage") or ""
                            _brk_str = f" · **{_brk}**" if _brk else ""
                            _origin = _it.get("_origin", "?").upper()
                            _origin_label = {"ET": "Economic Times", "MC": "Moneycontrol"}.get(_origin, _origin)
                            st.markdown(
                                f'<div style="margin:6px 0;padding:8px;background:#0a1628;border-left:3px solid {_act_col};border-radius:4px;">'
                                f'<span style="color:{_act_col};font-weight:600;font-family:JetBrains Mono,monospace;font-size:0.7rem;">{_act_label}</span>'
                                f'  ·  <span style="color:#5a8a9f;font-size:0.72rem;">{_origin_label}</span>'
                                f'  ·  <span style="color:#8b9eb0;font-size:0.72rem;">{_brk}</span>'
                                f'<div style="margin-top:4px;">'
                                f'<a href="{_it.get("url","#")}" target="_blank" style="color:#e6edf3;font-size:0.86rem;text-decoration:none;">{_it.get("title","")}</a>'
                                f'</div></div>',
                                unsafe_allow_html=True
                            )
                    else:
                        st.info(
                            f"No paid ET / MC headlines mentioning **{_xr_clean}** "
                            f"in current cache. Either no analyst coverage today or "
                            f"the symbol's name isn't matching headlines exactly. "
                            f"Try the bare ticker (e.g. RELIANCE not RIL)."
                        )
                except FileNotFoundError as _xr_se:
                    st.warning(
                        f"Paid news cookies not configured. Run "
                        f"`python setup_paid_news_cookies.py` to enable ET + MC scraping. "
                        f"Details: {_xr_se}"
                    )
                except Exception as _xr_se:
                    st.error(f"Sentiment fetch failed: {_xr_se}")


# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
#  GOLDEN MATCHER — Single-symbol checklist
# ══════════════════════════════════════════════════════════════════════════════
# ----------------------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------------------
elif page == 'GOLDEN MATCHER':
    st.markdown('<div class="page-title">🪙 Golden Matcher</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Single-symbol checklist presentation layer</div>', unsafe_allow_html=True)

    # ── View switch: single-symbol checklist  vs  batch Trigger Board ──────────
    _gm_view = st.radio("View", ["🎯 Single Symbol", "📋 Trigger Board"],
                        horizontal=True, key="gm_view", label_visibility="collapsed")

    if _gm_view == "📋 Trigger Board":
        # Batch board — every watchlist name run through the SAME GM engine
        # (compute_workflow / compute_recovery_workflow) → zero-drift categories.
        import gm_trigger_board as _gtb
        import datetime as _gtb_dt, time as _gtb_time
        st.markdown("#### 📋 Trigger Board — watchlists × the Golden Matcher engine")
        _uni = _gtb.load_watchlist_union()
        # Instant-on: if this browser session has no board yet, load the last
        # persisted build from disk (survives Web Commander restarts / reloads) so
        # it doesn't force a full rebuild every time.
        if st.session_state.get("gm_board_df") is None:
            _cdf, _cmeta = _gtb.load_board_cache()
            if _cdf is not None:
                st.session_state["gm_board_df"] = _cdf
                st.session_state["gm_board_stamp"] = (_cmeta or {}).get("stamp") or "from cache"
                st.session_state["gm_board_tech_stamp"] = (_cmeta or {}).get("tech_stamp")
        _bc1, _bc2, _bc3 = st.columns([1.2, 1.0, 2.2])
        with _bc1:
            _build = st.button(f"🔄 Build / Refresh  ·  {len(_uni)} names",
                               type="primary", use_container_width=True, key="gm_board_build")
            _use_xray = st.checkbox("🔬 X-Ray (Piotroski · grade · P/E)", key="gm_board_xray",
                                    help="Adds the X-Ray fundamental screener fields and folds Piotroski "
                                         "into the Overall score. Heavier (statements per name), cached 24h.")
        with _bc2:
            _trig_tf = st.selectbox("⏱ Trigger TF", ["75m", "125m", "Daily"], key="gm_board_tf",
                                    help="The board's technical + PA columns (Category/Step/trigger/CMP) "
                                         "are computed on THIS timeframe. 75/125m use INTRADAY bars — which "
                                         "move through the session, so live refresh actually updates. Daily "
                                         "uses the closed daily bar (won't change intraday).")
            _live = st.selectbox("🟢 Live refresh", ["Off", "1 min", "2 min", "3 min", "5 min", "10 min", "15 min"],
                                 key="gm_board_live",
                                 help="While the board is open, re-computes ONLY the technical + PA columns "
                                      "(Category/Step/plan/CMP/RS/Alpha…) on this cadence. Fundamentals "
                                      "(BFF/RFF/Piotroski/Conviction/Sector/Delivery) stay cached — they "
                                      "change daily/quarterly, not intraday. The true floor is how long a "
                                      "~50-name technical rebuild takes; if a tick can't finish in the "
                                      "interval it just runs back-to-back. Full Build refreshes everything.")
        with _bc3:
            _stamp = st.session_state.get("gm_board_stamp")
            _tstamp = st.session_state.get("gm_board_tech_stamp")
            st.caption((f"Full build **{_stamp}**" + (f" · live tech **{_tstamp}**" if _tstamp else "")
                        + " · RRG persists") if _stamp
                       else "Not built yet — click **Build / Refresh** (full run ~2–5 min).")

        # --- build (full = fundamentals+technical; force_technical = technical/PA only;
        #     quiet = no progress bar, used on live ticks so the layout never jumps) ---
        def _board_build(force_technical=False, quiet=False):
            if force_technical:
                # Live refresh: recompute ONLY technicals + PA. Clear the technical
                # caches; the fundamental caches (BFF/RFF/X-Ray, 24h TTL) stay warm,
                # so fundamentals are REUSED, not re-fetched. Delivery% is an EOD
                # bhavcopy value → reuse the cached NSE metrics too.
                try:
                    gm_load_symbol.clear(); gm_load_intraday.clear()
                except Exception:
                    pass
                _nse_metrics = st.session_state.get("gm_board_nse") or {}
            else:
                _nse_metrics = {}
                try:
                    import nse_archive_fetcher as _naf
                    _nse_metrics = _naf.get_nse_metrics() or {}
                except Exception:
                    _nse_metrics = {}
                st.session_state["gm_board_nse"] = _nse_metrics
            _xray_fn = None
            if _use_xray:
                try:
                    from weinstein_xray_screener import get_xray_scorecard as _xray_fn
                except Exception:
                    _xray_fn = None
            _loaders = dict(load_symbol=gm_load_symbol, load_recovery=gm_load_recovery,
                            bull_wf=compute_workflow, rec_wf=compute_recovery_workflow,
                            minervini=minervini_checks, nse_metrics=_nse_metrics,
                            xray=_xray_fn, use_xray=bool(_use_xray),
                            load_intraday=gm_load_intraday,
                            trigger_tf=(_trig_tf if _trig_tf in ("75m", "125m") else None))
            _rows = []
            _items = list(_uni.items())
            _prog = None if quiet else st.progress(0.0, "Building board…")
            for _i, (_sym, _info) in enumerate(_items):
                try:
                    _r = _gtb.build_row(_sym, _info, _loaders, _g)
                    if _r:
                        _rows.append(_r)
                except Exception:
                    pass
                if _prog is not None:
                    _prog.progress((_i + 1) / max(1, len(_items)), f"{_sym}  ({_i + 1}/{len(_items)})")
            if _prog is not None:
                _prog.empty()
            _bdf_new = pd.DataFrame(_rows)
            if not _bdf_new.empty and "Overall" in _bdf_new.columns:
                _bdf_new = _bdf_new.sort_values("Overall", ascending=False, na_position="last").reset_index(drop=True)
            st.session_state["gm_board_df"] = _bdf_new
            _now_s = _gtb_dt.datetime.now().strftime("%d %b %H:%M")
            st.session_state["gm_board_tech_stamp"] = _now_s
            st.session_state["gm_board_tech_ts"] = _gtb_time.time()
            if not force_technical:
                st.session_state["gm_board_stamp"] = _now_s
            # Persist to disk so the board survives a restart / reload (instant-on).
            _gtb.save_board_cache(_bdf_new, stamp=st.session_state.get("gm_board_stamp"),
                                  tech_stamp=_now_s)

        # --- render (RRG overlay + filters + editable table); keyed widgets so
        #     filter/edit state survives the live-refresh fragment reruns ---
        def _board_render():
            _bdf = st.session_state.get("gm_board_df")
            if _bdf is None or _bdf.empty:
                st.info("Click **Build / Refresh** to populate the board (fundamentals + technical).")
                return
            _rrg = _gtb.rrg_load()
            _bdf = _bdf.copy()
            _bdf["RRG"] = _bdf["Symbol"].map(lambda s: _rrg.get(s, "—"))
            _f1, _f2, _f3, _f4 = st.columns(4)
            _cats = sorted(_bdf["Category"].dropna().unique())
            _def_cat = [c for c in _cats if c.startswith(("Buy Trigger", "Armed", "Wait for Pullback"))]
            _fcat = _f1.multiselect("Category", _cats, default=_def_cat, key="gm_bf_cat")
            _frrg = _f2.multiselect("RRG Flag", _gtb.RRG_QUADRANTS, default=[], key="gm_bf_rrg")
            _ftier = _f3.multiselect("Tier", ["Rigorous", "Discovery"], default=[], key="gm_bf_tier")
            _fpath = _f4.multiselect("Path", ["Bull", "Recovery"], default=[], key="gm_bf_path")
            _view = _bdf
            if _fcat:  _view = _view[_view["Category"].isin(_fcat)]
            if _frrg:  _view = _view[_view["RRG"].isin(_frrg)]
            if _ftier: _view = _view[_view["Tier"].isin(_ftier)]
            if _fpath: _view = _view[_view["Path"].isin(_fpath)]
            st.caption(f"Showing **{len(_view)}** of {len(_bdf)} names")
            _edited = st.data_editor(
                _view, use_container_width=True, hide_index=True, key="gm_board_editor",
                column_config={
                    "RRG": st.column_config.SelectboxColumn(
                        "RRG Flag", options=_gtb.RRG_QUADRANTS, width="small",
                        help="Set from Strike.Money — persists per symbol."),
                    "Overall": st.column_config.ProgressColumn(
                        "Overall", min_value=0, max_value=100, format="%.0f",
                        help="0-100 opportunity score — Combined/Conviction/Alpha/Fundamentals/R:R/RS/"
                             "Piotroski, reweighted for missing inputs. Independent of category & path."),
                },
                disabled=[c for c in _view.columns if c != "RRG"],
            )
            _changed = False
            for _, _row in _edited.iterrows():
                _s = _row["Symbol"]; _v = _row["RRG"]
                if _rrg.get(_s, "—") != _v:
                    _rrg[_s] = _v; _changed = True
            if _changed:
                _gtb.rrg_save(_rrg)

        # --- LIVE header: pulsing dot + last technical refresh time ---
        def _gm_live_header(live_label):
            _ts = st.session_state.get("gm_board_tech_stamp", "—")
            st.markdown(
                f'''<div style="display:flex;align-items:center;gap:8px;margin:2px 0;">
                <span style="display:inline-block;width:9px;height:9px;border-radius:50%;
                background:#26a69a;animation:gmpulse 1.4s infinite;"></span>
                <span style="color:#26a69a;font-weight:700;font-size:13px;letter-spacing:.5px;">LIVE</span>
                <span style="color:#787b86;font-size:12px;">· technicals refresh every {live_label}
                · last {_ts}</span></div>
                <style>@keyframes gmpulse{{0%{{opacity:1;}}50%{{opacity:.25;}}100%{{opacity:1;}}}}</style>''',
                unsafe_allow_html=True)

        # --- Flashing 'Changed this tick' strip (green=improved / red=worse). The
        #     data-tick attr varies each REBUILD so the CSS animation replays on a
        #     real refresh but not on mere filter interactions. ---
        def _gm_change_strip(changes):
            if not changes:
                st.caption("· no changes on the last refresh")
                return
            _tok = st.session_state.get("gm_board_tech_ts", 0)
            _chips = []
            for _c in changes[:24]:
                _sym = _c.get("symbol", "")
                if "cat_to" in _c:
                    _up = _c.get("cat_dir", 1) > 0
                    _lbl = f"{_sym}: {str(_c['cat_from']).split(' · ')[0]}→{str(_c['cat_to']).split(' · ')[0]}"
                elif "overall_to" in _c:
                    _up = _c.get("overall_dir", 1) > 0
                    _lbl = f"{_sym}: Overall {_c['overall_from']:.0f}→{_c['overall_to']:.0f}"
                elif "cmp_to" in _c:
                    _up = _c.get("cmp_dir", 1) > 0
                    _lbl = f"{_sym} {'▲' if _up else '▼'} {_c['cmp_to']:.1f}"
                else:
                    continue
                _chips.append(f'<span class="gmchip {"gmup" if _up else "gmdn"}">{_lbl}</span>')
            st.markdown(
                f'''<div class="gmstrip" data-tick="{_tok}">{"".join(_chips)}</div>
                <style>
                .gmstrip{{margin:2px 0 8px;white-space:nowrap;overflow-x:auto;padding-bottom:4px;}}
                .gmchip{{display:inline-block;padding:3px 9px;margin:2px;border-radius:4px;
                  font-size:12px;color:#e6edf3;border:1px solid #2a2e39;}}
                .gmup{{animation:gmflashup 2.6s ease-out;}}
                .gmdn{{animation:gmflashdn 2.6s ease-out;}}
                @keyframes gmflashup{{0%{{background:#1f7a6d;}}12%{{background:#26a69a;}}100%{{background:rgba(38,166,154,.10);}}}}
                @keyframes gmflashdn{{0%{{background:#a13732;}}12%{{background:#ef5350;}}100%{{background:rgba(239,83,80,.10);}}}}
                </style>''',
                unsafe_allow_html=True)

        if _build:
            _board_build(force_technical=False)          # full: fundamentals + technical

        if _live == "Off":
            _board_render()
        else:
            _iv = {"1 min": (60, "60s"), "2 min": (120, "120s"), "3 min": (180, "180s"),
                   "5 min": (300, "300s"), "10 min": (600, "600s"), "15 min": (900, "900s")}[_live]

            # SMALL isolated live area: ONLY the LIVE dot + flashing change strip
            # re-render each tick (does the quiet technical rebuild + diff + toasts).
            # The heavy grid renders OUTSIDE this fragment, so it never shakes.
            @st.fragment(run_every=_iv[1])
            def _gm_live_ticker():
                _now = _gtb_time.time()
                _last = st.session_state.get("gm_board_tech_ts", 0)
                if st.session_state.get("gm_board_df") is not None and (_now - _last) >= _iv[0]:
                    _prev = st.session_state.get("gm_board_df")
                    _prev = _prev.copy() if _prev is not None else None
                    _board_build(force_technical=True, quiet=True)
                    _chg = _gtb.diff_boards(_prev, st.session_state.get("gm_board_df"))
                    st.session_state["gm_board_changes"] = _chg
                    for _c in _chg:
                        if _c.get("to_go"):
                            st.toast(f"🟢 **{_c['symbol']}** → Buy Trigger Live", icon="🟢")
                _gm_live_header(_live)
                _gm_change_strip(st.session_state.get("gm_board_changes"))

            _gm_live_ticker()
            _board_render()          # grid OUTSIDE the fragment → no per-tick re-render / no shake
        st.stop()
    
    st.markdown('''
    <style>
      .chk{display:flex;justify-content:space-between;align-items:center;
           padding:4px 10px;border-radius:5px;margin:2px 0;font-size:14px;}
      .chk b{font-weight:600;}
      .pass{background:rgba(38,166,154,.16);border-left:3px solid #26A69A;}
      .watch{background:rgba(255,152,0,.16);border-left:3px solid #FF9800;}
      .fail{background:rgba(239,83,80,.16);border-left:3px solid #EF5350;}
      .na{background:rgba(120,123,134,.12);border-left:3px solid #787B86;}
      .sechead{font-size:13px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;
               border-bottom:2px solid currentColor;padding-bottom:3px;margin:6px 0 6px;}
      .verdict{font-size:26px;font-weight:800;}
      .plan{font-family:Consolas,monospace;font-size:14px;line-height:1.7;}
    </style>
    ''', unsafe_allow_html=True)

    @st.fragment(run_every="2s")
    def auto_sync_tv_symbol_gm():
        import subprocess
        import csv
        import re
        from io import StringIO
        
        # REVERTED 9-Jul-2026: an attempted "one unfiltered tasklist call"
        # optimization broke the sync — unfiltered `tasklist /v` enumerates
        # window titles for EVERY process (~3.6 s, over any sane timeout),
        # while the per-image `/fi` filtered call is ~0.12 s. The original
        # per-browser filtered loop below is the fast, proven path.
        browsers = ['TradingView.exe', 'chrome.exe', 'msedge.exe', 'brave.exe']
        for browser in browsers:
            try:
                res = subprocess.run(['tasklist', '/fi', f'imagename eq {browser}', '/v', '/fo', 'csv'], capture_output=True, text=True, errors='ignore', timeout=2)
                reader = csv.reader(StringIO(res.stdout))
                for row in reader:
                    if len(row) > 8:
                        exe = row[0].lower()
                        title = row[8]
                        if ('tradingview.exe' in exe and title not in ('N/A', 'OleMainThreadWndName', 'Input-Sink', 'Default IME', 'INFO')) or \
                           ('TradingView' in title and '—' in title):
                            match = re.search(r'^(.*?)\s+[\d,]+\.\d{1,4}(?:\s|%|\+|-|$)', title)
                            if match:
                                sym = match.group(1).strip()
                                if sym.upper() in ["NIFTY 50", "NIFTY"]: sym = "^NSEI"
                                elif sym.upper() in ["NIFTY BANK", "BANKNIFTY"]: sym = "^NSEBANK"
                                elif sym.upper() == "NIFTY 500": sym = "^CRSLDX"
                                else:
                                    if not sym.endswith(".NS") and "^" not in sym and "=" not in sym: sym += ".NS"

                                # TradingView uses '_' where NSE/yfinance use '-'/'&'
                                # (BAJAJ_AUTO→BAJAJ-AUTO, NAM_INDIA→NAM-INDIA, M_M→M&M).
                                # Canonicalize via the scrip master so the box AND the
                                # loaders get the resolvable ticker.
                                sym = _canon_sym(sym)

                                current_sym = st.session_state.get("gm_sym_input", "")
                                if sym != current_sym:
                                    # DEBOUNCE (2026-07-03): commit the new symbol only after it has
                                    # been STABLE for 2 consecutive polls (~4s). Without this, fast
                                    # watchlist scrolling on TV fired a full screen_one fetch chain
                                    # (daily+weekly+fundamentals) per name — a burst that trips the
                                    # Dhan throttle (the same failure mode behind the cache-poisoning
                                    # symptom). Mid-scroll names now never trigger fetches.
                                    if sym == st.session_state.get("gm_pend_sym"):
                                        st.session_state["gm_pend_count"] = st.session_state.get("gm_pend_count", 0) + 1
                                    else:
                                        st.session_state["gm_pend_sym"] = sym
                                        st.session_state["gm_pend_count"] = 1
                                    if st.session_state["gm_pend_count"] >= 2:
                                        st.session_state["gm_pend_sym"] = None
                                        st.session_state["gm_pend_count"] = 0
                                        st.session_state["gm_sym_input"] = sym
                                        st.session_state["gm_symbol"] = sym
                                        st.rerun()
                                else:
                                    st.session_state["gm_pend_sym"] = None
                                    st.session_state["gm_pend_count"] = 0
                                return
            except Exception:
                pass

    _gm_col1, _gm_col2 = st.columns([2, 4])
    with _gm_col1:
        auto_sync = st.toggle("🔄 Auto-Sync TV", value=True, key="gm_auto_sync", help="Automatically sync with active TradingView chart")
        if auto_sync:
            auto_sync_tv_symbol_gm()
        
        if "gm_sym_input" not in st.session_state:
            st.session_state["gm_sym_input"] = "NETWEB.NS"
            
        symbol = st.text_input("NSE symbol", key="gm_sym_input").strip().upper()
        # Canonicalize underscore/hyphen/ampersand variants (esp. TradingView's
        # BAJAJ_AUTO / NAM_INDIA) to the ticker the loaders can resolve. Covers
        # manual entry / paste; the TV auto-sync path canonicalizes at commit.
        symbol = _canon_sym(symbol)
        if symbol and symbol != st.session_state.get("gm_symbol"):
            st.session_state["gm_symbol"] = symbol
            
    with _gm_col2:
        if st.button("🔄 Refresh Data", use_container_width=True,
                     help="Force a fresh fetch for THIS symbol — busts the on-disk data cache "
                          "(beats the 24h daily TTL) then reloads. Other pages' caches stay warm."):
            # 9-Jul-2026: clearing the Streamlit loaders alone did NOT refresh —
            # data_provider.fetch_ohlcv(use_cache=True) re-served the same
            # on-disk frame (a 2y/1d request carries the 24h weekly TTL, and the
            # content-staleness gate only rejects bars >5 days old). Bust the
            # on-disk cache for this symbol FIRST so the reload hits the network.
            _sym_now = st.session_state.get("gm_symbol") or st.session_state.get("gm_sym_input", "")
            try:
                import data_provider as _dpref
                if _sym_now:
                    _dpref.invalidate_symbol(_sym_now)
            except Exception:
                pass
            try:
                gm_load_symbol.clear()
                gm_load_recovery.clear()
            except Exception:
                st.cache_data.clear()
            st.rerun()

    # ---- Position-sizing settings (E2) — persisted to gm_settings.json ----
    _gmset = _gm_settings()
    _szc1, _szc2, _szc3 = st.columns([1.6, 1, 3.4])
    with _szc1:
        _gm_capital = st.number_input("Capital (₹)", min_value=0.0, step=50000.0,
                                      value=float(_gmset.get("capital", 0.0)),
                                      format="%.0f", key="gm_capital",
                                      help="Trading capital used for the 0.25%-risk position sizer on Step 6.")
    with _szc2:
        _gm_riskpct = st.number_input("Risk %", min_value=0.05, max_value=2.0, step=0.05,
                                      value=float(_gmset.get("risk_pct", 0.25)),
                                      key="gm_riskpct")
    with _szc3:
        _tf_opts = ["75m", "125m", "Daily"]
        _tf_default = str(_gmset.get("trigger_tf", "75m"))
        _gm_trig_tf = st.radio(
            "Trigger TF (Step-5 PA battery + momentum board)", _tf_opts, horizontal=True,
            index=_tf_opts.index(_tf_default) if _tf_default in _tf_opts else 0,
            key="gm_trig_tf",
            help="The Step-5 PA trigger battery and the Technical-Board momentum gauges "
                 "(RSI/ADX/RelVol/Vol-dry) recompute on this timeframe. Context/Quality "
                 "(Stage · RS · Alpha · catalyst · demand-zones) stay Daily/Weekly — they're positional.")
    if (_gm_capital != _gmset.get("capital")) or (_gm_riskpct != _gmset.get("risk_pct")) \
            or (_gm_trig_tf != _gmset.get("trigger_tf")):
        _gm_settings_save(capital=_gm_capital, risk_pct=_gm_riskpct, trigger_tf=_gm_trig_tf)

    if not symbol:
        st.info("Enter an NSE symbol in the sidebar.")
        st.stop()
    
    data = gm_load_symbol(symbol)

    # ---- Auto-heal a stale served frame (9-Jul-2026) --------------------------
    # A 2y/1d request carries the 24h weekly TTL, so a daily frame written after
    # yesterday's close is re-served all of today even though a newer session has
    # closed. If the served last bar is older than the last completed trading
    # session, bust this symbol's on-disk cache ONCE and reload — the network
    # then supplies the fresh bar. Guarded per (symbol, target-session) so it can
    # never loop when the provider genuinely hasn't published the new bar yet
    # (then the STALE banner shows and manual Refresh remains available).
    try:
        _df_h = data.get("df")
        if _df_h is not None and len(_df_h):
            _lb = _df_h.index[-1].date()
            _target = _expected_last_session()   # session-aware: today after 15:30 IST close
            if _lb < _target:
                _heal_key = f"{symbol}|{_target.isoformat()}"
                if st.session_state.get("gm_autoheal") != _heal_key:
                    st.session_state["gm_autoheal"] = _heal_key
                    import data_provider as _dph
                    _dph.invalidate_symbol(symbol)
                    gm_load_symbol.clear()
                    gm_load_recovery.clear()
                    st.rerun()
    except Exception:
        pass

    # Shallow-copy rec/ctx before any patching so the intraday overrides below
    # never mutate (poison) the cached gm_load_symbol result.
    rec = dict(data.get("rec") or {})
    ctx = dict(data.get("ctx") or {})
    fun = data.get("fun") or {}
    ctx["bff"] = data.get("bff")           # Bull Fundamental Filter status (display-only)

    # ---- Intraday trigger TF (Step-5 PA battery + momentum board) ----
    # Context/Quality/Setup/Location stay Daily/Weekly (positional); only the
    # TRIGGER battery + momentum gauges recompute on the selected trading TF.
    _intra_ok = False; _intra_label = ""
    _trig_tf = st.session_state.get("gm_trig_tf", "75m")
    if _trig_tf in ("75m", "125m"):
        _mins = 75 if _trig_tf == "75m" else 125
        _intra = gm_load_intraday(symbol, _mins)
        if _intra.get("ok"):
            _intra_ok = True
            ctx["_trigger_tf"] = _trig_tf          # so the workflow text says "fired on the 75m", not "daily"
            ctx["pa_patterns"] = _intra["pa"]
            ctx["recovery_pa_patterns"] = _intra["rpa"]
            if _intra.get("adx") is not None:     ctx["adx"] = _intra["adx"]
            if _intra.get("relvol") is not None:  ctx["relvol"] = _intra["relvol"]
            if _intra.get("vol_dry") is not None: ctx["vol_dry"] = _intra["vol_dry"]
            if _intra.get("rsi") is not None:     rec["RSI"] = _intra["rsi"]
            _intra_label = f"⏱ Trigger TF **{_trig_tf}** · bar {_intra['last_ts']} · {_intra['bars']} bars"
        else:
            _intra_label = f"⏱ Trigger TF {_trig_tf} — intraday unavailable ({_intra.get('reason','?')}); showing Daily PA"

    # Recovery engine — loaded separately so it never stalls TV auto-sync.
    # Fast (cache-only) by default; a per-symbol "deep" toggle does the live
    # RFF fundamental fetch on demand.
    _deep_rec = bool(st.session_state.get(f"gm_deeprec_{symbol}", False))
    rec_r = gm_load_recovery(symbol, deep=_deep_rec) or {}
    # Recovery signal state (parallel to the bull catalyst above).
    rec_sig   = int(_g(rec_r, "Signal", default=0) or 0)
    rec_label = str(_g(rec_r, "Signal_Label", default="None"))
    rec_fired = rec_sig >= 2   # 2=REV-CB 3=REV-RS 4=REV-EARLY 5-8=WYC-*
    # SEMANTIC GUARD: the recovery engine's regime gate opens for ANY non-
    # distressed stock when the *market* is in recovery/reclaim — so REV-EARLY/
    # REV-RS can fire on a stock at its OWN highs (market-recovery play, not a
    # beaten-down recovery). On this single-symbol tool the "RECOVERY" label is
    # read literally, so only treat it as a genuine recovery when the STOCK
    # itself is meaningfully off its 52W high (engine's own min_stock_correction
    # floor, 10%). Otherwise it's a bull setup, not a recovery — don't mislabel.
    _rec_dd_floor, _ = _rec_cfg()
    _rec_corr = _g(rec_r, "Correction_52W_pct")
    rec_beaten_down = (_rec_corr is not None) and (_rec_corr >= _rec_dd_floor)
    rec_fired_real  = rec_fired and rec_beaten_down   # genuine beaten-down recovery
    rec_fired_mktpath = rec_fired and not rec_beaten_down  # market-path artifact at/near highs

    if not rec and not ctx:
        st.error(f"Could not load **{symbol}**.")
        for e in data.get("errors", []):
            st.caption(f"• {e}")
        st.stop()
    
    # ----------------------------------------------------------------------------------------
    # Header — name, CMP, change, verdict
    # ----------------------------------------------------------------------------------------
    name = _g(fun, "name", default=symbol)
    cmp_px = _g(ctx, "cmp") or _g(rec, "Entry")
    prev = _g(ctx, "prev", default=cmp_px)
    chg_pct = ((cmp_px - prev) / prev * 100) if (cmp_px and prev) else 0.0
    catalyst = _g(rec, "Catalyst", default="NONE")
    stage = str(_g(rec, "Stage", default="—"))
    alpha = _g(rec, "Alpha", default=None)
    rs_ratio = _g(rec, "JdK_RS_Ratio")
    mansfield = (rs_ratio - 100.0) if rs_ratio is not None else None
    ml_prob = _g(rec, "ML_Prob")
    
    h1, h2, h3 = st.columns([3, 1.3, 1.6])
    with h1:
        st.markdown(f"### {symbol} — {name}")
        st.caption(f"{_g(fun,'sector',default='')}  ·  {_g(fun,'industry',default='')}")
    with h2:
        st.metric("CMP", inr(cmp_px), f"{chg_pct:+.2f}%")
        # Data freshness (G1, 9-Jul-2026): show the LAST BAR DATE, not just the
        # fetch time — a stale feed (cache-poisoning / Dhan date-shift class)
        # must be visible at a glance. The expected bar is SESSION-AWARE: after
        # today's 15:30 IST close it should be TODAY, otherwise the last completed
        # trading day (see _expected_last_session). A flat 'yesterday' target used
        # to sit green on the prior day all evening — one session behind.
        _lastbar = None
        try:
            _dfh = data.get("df")
            if _dfh is not None and len(_dfh):
                _lastbar = _dfh.index[-1].date()
        except Exception:
            pass
        _asof = _g(rec, "As_Of") or (_lastbar.strftime("%Y-%m-%d") if _lastbar else None)
        if _lastbar or _asof:
            _exp_sess = _expected_last_session()
            _stale = bool(_lastbar and _lastbar < _exp_sess)
            _fresh_txt = f"bar {_lastbar.strftime('%d-%b') if _lastbar else _asof}"
            if _asof and _lastbar and _asof != _lastbar.strftime("%Y-%m-%d"):
                _fresh_txt += f" · engine as-of {_asof}"
            if _stale:
                st.caption(f"⚠️ **STALE — {_fresh_txt}** (last completed session "
                           f"{_exp_sess.strftime('%d-%b')}). Refresh; if it stays behind, the "
                           f"broker feed hasn't published today's EOD bar yet.")
            else:
                st.caption(f"🟢 {_fresh_txt}")
    with h3:
        bull_active = _cat_on(catalyst)
        is_pos = str(catalyst).upper().startswith("POS")
        # Primary verdict = bull catalyst if one fires; otherwise the recovery
        # signal if it fires; otherwise NONE. Recovery is teal to stay visually
        # distinct from the bull green/amber.
        if bull_active:
            head_label, head_color, head_tag = catalyst, ("#26A69A" if is_pos else "#FF9800"), "CATALYST"
        elif rec_fired_real:
            head_label, head_color, head_tag = rec_label, "#00838F", "RECOVERY"
        else:
            head_label, head_color, head_tag = "NONE", "#787B86", "CATALYST"
        st.markdown(f"<div style='text-align:right'><div style='font-size:12px;opacity:.7'>{head_tag}</div>"
                    f"<div class='verdict' style='color:{head_color}'>{head_label}</div></div>",
                    unsafe_allow_html=True)
        # If BOTH sides fire (and the recovery is a GENUINE beaten-down one),
        # note it under the bull verdict so neither is hidden.
        if bull_active and rec_fired_real:
            st.markdown(f"<div style='text-align:right;font-size:12px;color:#00838F'>"
                        f"＋ Recovery: {rec_label}</div>", unsafe_allow_html=True)
    
    # ----------------------------------------------------------------------------------------
    # DECISION WORKFLOWS — Bull (left) · Recovery (right), side by side.
    # Recovery names are Stage 1/4 by nature and fail the bull Stage-2 gate at
    # Step 1, so a single bull path mislabels them AVOID. Showing BOTH paths
    # lets the trader read the correct verdict for whichever engine applies.
    # ----------------------------------------------------------------------------------------
    decision = compute_decision(rec, ctx, cmp_px, mansfield)
    _bull_active = _cat_on(catalyst)
    wf_bull = compute_workflow(rec, ctx, cmp_px, mansfield)
    wf_rec = compute_recovery_workflow(rec_r, ctx, cmp_px) if rec_r else None

    # Trigger-TF banner: makes it explicit that Step-5's battery + momentum are on
    # the trading TF while Steps 1-4 remain Daily/Weekly positional context.
    if _intra_label:
        _il_col = "#00838F" if _intra_ok else "#FF9800"
        st.markdown(f"<div style='border-left:3px solid {_il_col};background:{_il_col}14;"
                    f"border-radius:4px;padding:5px 10px;margin:2px 0 8px;font-size:12.5px'>"
                    f"{_intra_label} &nbsp;·&nbsp; Steps 1-4 (Stage · RS · Alpha · catalyst · zones) stay Daily/Weekly."
                    f"</div>", unsafe_allow_html=True)

    _wcol1, _wcol2 = st.columns(2)
    with _wcol1:
        st.markdown("##### 🐂 Bull path  ·  Stage-2 leadership")
        st.markdown(render_workflow(wf_bull), unsafe_allow_html=True)
    with _wcol2:
        st.markdown("##### 🔄 Recovery path  ·  beaten-down + RFF")
        # Render the full recovery path ONLY for a GENUINE recovery (signal fired
        # AND stock beaten-down ≥10%). A market-path artifact (signal fired at/near
        # highs) or no signal both get a concise note — so two "no real recovery"
        # names never render differently (one full red path, one one-liner).
        if wf_rec is not None and rec_fired_real:
            st.markdown(render_workflow(wf_rec), unsafe_allow_html=True)
        elif rec_fired_mktpath:
            st.info(f"Recovery engine notes **{rec_label}** only via the market-recovery regime — "
                    f"but **{symbol}** is just {fnum(_rec_corr, 1, '%')} off its 52W high "
                    f"(< {_rec_dd_floor:.0f}% floor), so it is **not** a beaten-down recovery. "
                    f"Trade the bull path.")
        else:
            st.info("No recovery catalyst on this name — the recovery path does not apply.")

    # ---- Fresh Stage-transition note (reconciles a lagging chart background) ----
    # Stage is a STATEFUL weekly state machine; at a Stage 4→1 reclaim the exact
    # flip bar is knife-edge (30-WMA slope crossing the flat band), so Python
    # (Dhan feed) and a TradingView background (TV feed + its own weekly bars)
    # can differ by one stage for a week or two. When price has RECLAIMED the
    # 30-week MA but the stage still reads 1 (base), that's a fresh turn Python
    # catches first — flag it so a chart still painting Stage 4 isn't confusing.
    _ma30 = _g(ctx, "sma150")   # daily 150-SMA ≈ 30-week MA (the stage anchor)
    _stg = None
    for _sv in (str(_g(rec, "Stage", default="")), str(_g(rec_r, "Weinstein_Stage", default=""))):
        _hit = next((d for d in "1234" if d in _sv), None)
        if _hit:
            _stg = int(_hit); break
    if _ma30 and cmp_px and _stg == 1 and cmp_px > _ma30:
        _d30 = (cmp_px / _ma30 - 1) * 100
        st.caption(f"🟡 **Stage 1 · fresh reclaim** — price is **{_d30:+.1f}% above the 30-week MA** "
                   f"({inr(_ma30)}), i.e. the stock has reclaimed its Weinstein anchor. If a "
                   f"TradingView stage-background still shows **Stage 4**, it is *lagging this turn* "
                   f"on its own data feed (the 4→1 flip is a knife-edge slope crossing) — Python "
                   f"registered the reclaim first. Trust the price-vs-30WMA read: this is an early base, not a decline.")

    # The PRIMARY path drives the single next-action + guided execution below.
    # Some names fire BOTH a bull catalyst AND a genuine recovery signal — and
    # the two have DIFFERENT entries/stops/targets — so let the trader choose
    # which setup to execute rather than silently defaulting. Otherwise the one
    # applicable path leads automatically.
    _both_fire = _bull_active and rec_fired_real and wf_rec is not None
    if _both_fire:
        _pick = st.radio(
            "⚡ This name fires BOTH a bull and a recovery setup — trade which?",
            ["🐂 Bull", "🔄 Recovery"], horizontal=True, key=f"gm_path_{symbol}")
        wf = wf_rec if _pick.startswith("🔄") else wf_bull
    elif rec_fired_real and not _bull_active and wf_rec is not None:
        wf = wf_rec
    else:
        wf = wf_bull
    _pa_html = render_pa_banner(ctx)
    if _pa_html:
        st.markdown(_pa_html, unsafe_allow_html=True)

    # ---- Session shortlist capture (E3, 9-Jul-2026) — a TV scroll session
    # leaves an artifact: every actionable name (BUY / ARMED / WAIT-class) is
    # recorded in session state; a name that degrades to AVOID/WATCHLIST on a
    # later look is removed. Rendered as a table further down.
    _slk = "recovery_pa_patterns" if wf.get("recovery") else "pa_patterns"
    _sl_tier = sum(t for _, f, t, _ in (_g(ctx, _slk, default=[]) or []) if f)
    _sl_store = st.session_state.setdefault("gm_shortlist", {})
    _sl_sym = symbol.replace(".NS", "").replace(".BO", "").upper()
    if wf["actionable"]:
        _sl_store[_sl_sym] = {"Symbol": _sl_sym, "Verdict": wf["verdict"],
                              "Path": "Recovery" if wf.get("recovery") else "Bull",
                              "Σ tier": _sl_tier, "Signal": str(head_label),
                              "Seen": datetime.now().strftime("%H:%M")}
    else:
        _sl_store.pop(_sl_sym, None)

    # ---- The single next action + guided execution sequence ----
    cur_step = wf["steps"][wf["current"] - 1]
    if not wf["actionable"]:
        if "AVOID" in wf["verdict"]:
            st.error(f"**{wf['verdict']} — Step {wf['stop_at']}.** {cur_step.get('do_fail','')}  Go to the next name.")
        else:
            st.warning(f"**{wf['verdict']} — Step {wf['stop_at']}.** {cur_step.get('do_fail','')}  Track only; no action today.")
    elif wf["current"] < 5:
        st.warning(f"**→ NOW · Step {wf['current']} ({cur_step['title']}):**  {cur_step.get('do_fail','')}")
    else:
        st.success(f"**→ NOW · Step 5 (TRIGGER):**  {cur_step.get('do_now')}")

        # ---- Position sizer (E2, 9-Jul-2026) — risk% of capital made concrete ----
        _pe = wf.get("plan_entry"); _psl = wf.get("plan_sl"); _pt1 = wf.get("plan_t1")
        _qty_sized = 0
        if _pe and _psl and _pe > _psl:
            if _gm_capital > 0:
                _risk_amt = _gm_capital * _gm_riskpct / 100.0
                _qty_sized = int(_risk_amt // (_pe - _psl))
                _ct_half = bool(_g(rec, "Counter_Trend")) and not wf.get("recovery")
                if _ct_half and _qty_sized > 1:
                    _qty_sized //= 2
                _pos_val = _qty_sized * _pe
                st.markdown(
                    f"**📏 Size @ {_gm_riskpct:.2f}% risk:** {inr(_risk_amt)} ÷ "
                    f"(entry {inr(_pe)} − SL {inr(_psl)}) = **{_qty_sized} shares** · "
                    f"position {inr(_pos_val)}"
                    + (f" ({_pos_val / _gm_capital * 100:.1f}% of capital)" if _gm_capital else "")
                    + (" · ⚠ counter-trend — size halved" if _ct_half else ""))
            else:
                st.caption("📏 Set your capital above to get an auto position size at the configured risk.")

        st.markdown("##### ✅ Guided execution — tick as you go")
        # Auto support zone (OB/FVG/pivot on Daily AND Weekly) — the S4 Pine twin.
        # When a demand zone is under price, Steps 1-2 are pre-computed (the zone
        # + proximal alert level), so you verify rather than hand-draw. Prefer the
        # tightest active zone: DAILY first (precise entry), else WEEKLY (bigger
        # structural demand). No zone → fall back to the manual wording.
        _supz = _g(ctx, "support", default={}) or {}

        def _pick_zone(_z, _tf):
            """(label, lo, hi, proximal) for the tightest FRESH active zone under
            price in one TF, or None. Keys off the exact tradeable zone labels —
            'OB/FVG tested' never match, so a mitigated zone is never auto-picked."""
            if not _z:
                return None
            _lbl = str(_z.get("zone", "outside"))
            if _lbl in ("OB inside", "OB near"):
                return (f"{_tf} {_lbl}", _z.get("ob_bot"), _z.get("ob_top"), _z.get("ob_top"))
            if _lbl in ("FVG inside", "FVG near"):
                return (f"{_tf} {_lbl}", _z.get("fvg_bot"), _z.get("fvg_top"), _z.get("fvg_top"))
            if _lbl == "Pivot near":
                return (f"{_tf} Pivot near", _z.get("pivot"), _z.get("pivot"), _z.get("pivot"))
            return None

        _pick = _pick_zone(_supz.get("daily"), "Daily") or _pick_zone(_supz.get("weekly"), "Weekly")
        if _pick:
            _z_lbl, _z_lo, _z_hi, _z_prox = _pick
            _span_txt = inr(_z_lo) if _z_lo == _z_hi else f"{inr(_z_lo)}–{inr(_z_hi)}"
            _zsummary = str(_supz.get("zone", ""))
            st.caption(f"🟩 **Auto demand-zone:** {_z_lbl} at **{_span_txt}** "
                       f"· alert proximal **{inr(_z_prox)}**  ·  _{_zsummary}_ — Steps 1-2 auto-marked; verify on the chart.")
            _man = [
                ("zone",  f"1 · Auto zone confirmed: {_z_lbl} at {_span_txt} (verify it's fresh/untested)"),
                ("alert", f"2 · Set the TradingView alert at the zone proximal {inr(_z_prox)}"),
                ("close", "3 · Wait for a 75/125m bar to CLOSE in your direction at the zone"),
                ("stop",  "4 · Place a buy-STOP above that trigger bar's high (never buy the touch)"),
                ("size",  "5 · Set SL below the zone distal · size at 0.25% risk"),
                ("gtt",   "6 · Place the order + GTT the same evening · log the trade"),
            ]
        else:
            st.caption("⬜ No auto demand-zone (OB/FVG/pivot on Daily or Weekly) under price yet — hand-draw the fresh zone.")
            _man = [
                ("zone",  "1 · Mark the FRESH demand zone on Daily/Weekly (hand-drawn, untested)"),
                ("alert", "2 · Set a TradingView alert at the zone proximal"),
                ("close", "3 · Wait for a 75/125m bar to CLOSE in your direction at the zone"),
                ("stop",  "4 · Place a buy-STOP above that trigger bar's high (never buy the touch)"),
                ("size",  "5 · Set SL below the zone distal · size at 0.25% risk"),
                ("gtt",   "6 · Place the order + GTT the same evening · log the trade"),
            ]
        _key = f"chk_{symbol}"
        _done = 0; _next = None
        for _k, _label in _man:
            if st.checkbox(_label, key=f"{_key}_{_k}"):
                _done += 1
            elif _next is None:
                _next = _label
        st.progress(_done / len(_man), text=f"{_done}/{len(_man)} done")
        if _done == len(_man):
            # ---- E1 (9-Jul-2026): actually log the trade. upsert_trade()
            # auto-captures the true-entry signal snapshot on new OPEN inserts
            # (the Phase-0 hook) — so a GM-executed trade lands in the journal
            # AND the attribution pipeline with its setup label.
            st.success("✅ All steps done — log the trade to the journal below.")
            _path_lbl = "Recovery" if wf.get("recovery") else "Bull"
            _pa_key = "recovery_pa_patterns" if wf.get("recovery") else "pa_patterns"
            _sig_tier = sum(t for _, f, t, _ in (_g(ctx, _pa_key, default=[]) or []) if f)
            _rat_default = f"GM {wf['verdict']} · {_path_lbl} · {head_label} · Σ+{_sig_tier}"
            with st.expander("📓 Log to journal", expanded=True):
                with st.form(f"gm_journal_{symbol}"):
                    _jc1, _jc2, _jc3 = st.columns(3)
                    with _jc1:
                        _j_buy = st.number_input("Buy price", min_value=0.0, format="%.2f",
                                                 value=float(_pe or cmp_px or 0.0))
                        _j_qty = st.number_input("Quantity", min_value=0, step=1,
                                                 value=int(_qty_sized))
                    with _jc2:
                        _j_sl = st.number_input("Stop-loss", min_value=0.0, format="%.2f",
                                                value=float(_psl or 0.0))
                        _j_t1 = st.number_input("Target 1", min_value=0.0, format="%.2f",
                                                value=float(_pt1 or 0.0))
                    with _jc3:
                        _j_tf = st.selectbox("Timeframe", ["Positional", "Swing"],
                                             index=0 if str(head_label).upper().startswith(("POS", "REV", "WYC")) else 1)
                        _j_rat = st.text_input("Rationale", value=_rat_default)
                    if st.form_submit_button("📓 Log OPEN trade", type="primary"):
                        try:
                            import dhan_journal_v7 as _dj
                            _bare_j = symbol.replace(".NS", "").replace(".BO", "").upper()
                            _dj.upsert_trade({
                                "Symbol": _bare_j, "Type": "LONG", "Status": "OPEN",
                                "BuyPrice": float(_j_buy), "Quantity": float(_j_qty),
                                "StopLoss": float(_j_sl) or None,
                                "Target1": float(_j_t1) or None,
                                "EntryDate": datetime.now().strftime("%Y-%m-%d"),
                                "Timeframe": _j_tf, "Rationale": _j_rat,
                                "Sector": str(_g(fun, "sector", default="") or ""),
                            })
                            st.success(f"📓 {_bare_j} logged OPEN — entry snapshot captured. On to the next name.")
                        except Exception as _je:
                            st.error(f"Journal write failed (trade NOT logged): {_je}")
        elif _next:
            st.caption(f"→ Next: {_next}")

    # ---- Recovery engine callout ------------------------------------------------
    # The decision workflow above is bull-oriented; a recovery setup would
    # otherwise be buried under a bull "no action" verdict. Surface it here so
    # a REV/WYC signal on a fundamentally-strong beaten-down name is never missed.
    if rec_fired_real:
        _rev_entry = _g(rec_r, "Entry"); _rev_sl = _g(rec_r, "SL"); _rev_t1 = _g(rec_r, "T1")
        _plan = ""
        if _rev_entry and _rev_sl:
            _plan = f"  ·  Entry {inr(_rev_entry)} · SL {inr(_rev_sl)}" + (f" · T1 {inr(_rev_t1)}" if _rev_t1 else "")
        st.success(f"**🔄 RECOVERY SIGNAL — {rec_label}** (RFF {_g(rec_r,'RFF_Base',default=0)}/6, "
                   f"{_g(rec_r,'RFF_Quality',default='—')} · {fnum(_rec_corr,1,'%')} off 52WH).{_plan}  "
                   f"Fundamentally-strong beaten-down setup — validate on the chart, then trade the recovery playbook.")
    elif rec_fired_mktpath:
        # The engine fired REV/WYC via the MARKET-recovery path, but the stock
        # itself is at/near its highs — not a beaten-down recovery. Say so
        # plainly rather than mislabelling it "recovery".
        st.caption(f"ℹ️ Recovery engine notes *{rec_label}* only via the market-recovery regime — "
                   f"but **{symbol}** is just {fnum(_rec_corr,1,'%')} off its 52W high "
                   f"(< {_rec_dd_floor:.0f}% floor), so this is **not** a beaten-down recovery. "
                   f"Trade the bull catalyst above, not a recovery playbook.")
    elif rec_sig == 1 and rec_beaten_down:
        st.info(f"**🔄 Recovery: CB-Watch** — climax detected on **{symbol}**, no turn yet. "
                f"On watch; no recovery entry until the bounce confirms.")

    # On-demand LIVE fundamentals: the fast path skips the blocking Screener.in
    # scrape (so TV auto-sync stays responsive). If RFF read INSUFFICIENT only
    # because fundamentals weren't cached, let the trader pull them for THIS name.
    if not _deep_rec and str(_g(rec_r, "RFF_Quality", default="")) == "INSUFFICIENT":
        if st.button("🔬 Fetch live fundamentals for recovery RFF (this symbol)",
                     key=f"deeprec_btn_{symbol}",
                     help="Skipped during fast scrolling to keep TV auto-sync responsive. "
                          "Pulls Screener.in/yfinance fundamentals for this symbol only."):
            st.session_state[f"gm_deeprec_{symbol}"] = True
            st.rerun()

    st.divider()

    # ---- Session shortlist (E3) — the ranked artifact of this scroll session ----
    _sl_all = st.session_state.get("gm_shortlist", {})
    with st.expander(f"📋 Session shortlist ({len(_sl_all)})", expanded=False):
        if _sl_all:
            _sl_df = pd.DataFrame(list(_sl_all.values()))
            _sl_df = _sl_df.sort_values(["Σ tier", "Symbol"], ascending=[False, True])
            st.dataframe(_sl_df, use_container_width=True, hide_index=True)
            _slc1, _slc2 = st.columns(2)
            with _slc1:
                st.download_button(
                    "⬇ TV watchlist (.txt)",
                    "###GM_SHORTLIST\n" + "\n".join(f"NSE:{s}" for s in _sl_df["Symbol"]),
                    file_name=f"GM_Shortlist-{datetime.now().strftime('%d%b%y').upper()}.txt",
                    use_container_width=True)
            with _slc2:
                if st.button("🗑 Clear shortlist", use_container_width=True):
                    st.session_state["gm_shortlist"] = {}
                    st.rerun()
        else:
            st.caption("Empty — actionable names (BUY / ARMED / WAIT) collect here as you scroll TV.")

    # Full per-panel detail is one click away — but the workflow above is the decision.
    with st.expander("▸ Full metrics — all panels (optional depth)", expanded=False):
        # v2 (2026-07-03): pre-render every card so SECTION_SCORES fills, then show
        # the one-glance score strip ABOVE the panels — read the strip, open a card
        # only when its score surprises you.
        SECTION_SCORES.clear()
        _h_board  = render_technical_board(rec, ctx, cmp_px, mansfield)
        _h_pa     = section_pa_patterns(ctx)
        _h_ctx    = section_context(rec, ctx, cmp_px)
        _h_struct = section_structure(rec, ctx, cmp_px, mansfield, decision)
        _h_gates  = section_bull_gates(rec, ctx, cmp_px, mansfield)
        _h_edges  = section_edges(rec, ctx, cmp_px)
        _h_trade  = section_trade(rec, cmp_px)
        _h_levels = section_levels(rec, ctx, cmp_px)
        _h_sector = section_sector(rec, ctx, mansfield)
        _h_funda  = section_fundamentals(fun, bff=ctx.get("bff"))
        _h_recov  = section_recovery(rec_r, cmp_px)
        _mpass, _ = minervini_checks(ctx, cmp_px, mansfield)
        st.markdown(render_score_strip(_mpass), unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3, gap="medium")
        with c1:
            st.markdown(_h_board, unsafe_allow_html=True)
            st.markdown(_h_pa, unsafe_allow_html=True)
            st.markdown(_h_ctx, unsafe_allow_html=True)
        with c2:
            st.markdown(_h_struct, unsafe_allow_html=True)
            st.markdown(_h_gates, unsafe_allow_html=True)
            st.markdown(_h_edges, unsafe_allow_html=True)
            st.markdown(_h_recov, unsafe_allow_html=True)
        with c3:
            st.markdown(_h_trade, unsafe_allow_html=True)
            st.markdown(_h_levels, unsafe_allow_html=True)
            st.markdown(_h_sector, unsafe_allow_html=True)
            st.markdown(_h_funda, unsafe_allow_html=True)
    
    st.divider()
    st.caption(f"Data: Dhan feed + Screener.in via your validated modules · "
               f"fetched {data.get('fetched_at','—')} · cache 120s · "
               f"⚠ identification only — the trigger is yours on TradingView.")
    if data.get("errors"):
        with st.expander("⚠ Partial-data notes"):
            for e in data["errors"]:
                st.caption(f"• {e}")

#  TV SIDECAR — Quick-look chart companion
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'TV SIDECAR':
    st.markdown('<div class="page-title">📺 TV Sidecar</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Quick-look companion for your TradingView chart — real-time quote, technicals, key levels</div>', unsafe_allow_html=True)

    @st.fragment(run_every="2s")
    def auto_sync_tv_symbol():
        import subprocess
        import csv
        import re
        from io import StringIO
        
        browsers = ['TradingView.exe', 'chrome.exe', 'msedge.exe', 'brave.exe']
        for browser in browsers:
            try:
                res = subprocess.run(['tasklist', '/fi', f'imagename eq {browser}', '/v', '/fo', 'csv'], capture_output=True, text=True, errors='ignore', timeout=2)
                reader = csv.reader(StringIO(res.stdout))
                for row in reader:
                    if len(row) > 8:
                        exe = row[0].lower()
                        title = row[8]
                        if ('tradingview.exe' in exe and title not in ('N/A', 'OleMainThreadWndName', 'Input-Sink', 'Default IME', 'INFO')) or \
                           ('TradingView' in title and '—' in title):
                            match = re.search(r'^(.*?)\s+[\d,]+\.\d{1,4}(?:\s|%|\+|-|$)', title)
                            if match:
                                sym = match.group(1).strip()
                                if sym.upper() in ["NIFTY 50", "NIFTY"]: sym = "^NSEI"
                                elif sym.upper() in ["NIFTY BANK", "BANKNIFTY"]: sym = "^NSEBANK"
                                elif sym.upper() == "NIFTY 500": sym = "^CRSLDX"
                                else:
                                    if not sym.endswith(".NS") and "^" not in sym and "=" not in sym: sym += ".NS"
                                
                                current_sym = st.session_state.get("tv_sym_input", "")
                                if sym != current_sym:
                                    # DEBOUNCE (2026-07-03): same 2-poll stability rule as the
                                    # Golden Matcher pane — no fetch bursts while scrolling the
                                    # TV watchlist.
                                    if sym == st.session_state.get("tv_pend_sym"):
                                        st.session_state["tv_pend_count"] = st.session_state.get("tv_pend_count", 0) + 1
                                    else:
                                        st.session_state["tv_pend_sym"] = sym
                                        st.session_state["tv_pend_count"] = 1
                                    if st.session_state["tv_pend_count"] >= 2:
                                        st.session_state["tv_pend_sym"] = None
                                        st.session_state["tv_pend_count"] = 0
                                        st.session_state["tv_sym_input"] = sym
                                        st.session_state["tv_symbol"] = sym
                                        st.rerun()
                                else:
                                    st.session_state["tv_pend_sym"] = None
                                    st.session_state["tv_pend_count"] = 0
                                return
            except Exception:
                pass

    _tv_col1, _tv_col2 = st.columns([2, 4])
    with _tv_col1:
        auto_sync = st.toggle("🔄 Auto-Sync TV", value=True, key="tv_auto_sync", help="Automatically sync with active TradingView chart")
        if auto_sync:
            auto_sync_tv_symbol()
        
        if "tv_sym_input" not in st.session_state:
            st.session_state["tv_sym_input"] = st.session_state.get("tv_symbol", "RELIANCE.NS")
            
        _tv_sym = st.text_input(
            "Symbol", 
            key="tv_sym_input", placeholder="e.g. INFY.NS, NIFTY=F"
        ).strip().upper()
        if _tv_sym and not _tv_sym.endswith(".NS") and "=" not in _tv_sym and "^" not in _tv_sym:
            _tv_sym += ".NS"
        if _tv_sym:
            st.session_state["tv_symbol"] = _tv_sym
    with _tv_col2:
        _tv_tf = st.selectbox("Timeframe context", ["Daily", "Weekly", "15min", "60min"], key="tv_tf")

    if _tv_sym:
        with st.spinner(f"Fetching {_tv_sym}..."):
            try:
                import yfinance as _yf2
                _tv_ticker = _yf2.Ticker(_tv_sym)
                _tv_info   = _tv_ticker.info
                _tv_hist   = _tv_ticker.history(period="6mo", interval="1d", auto_adjust=True)
            except Exception as _tve:
                _tv_info, _tv_hist = {}, pd.DataFrame()
                st.error(f"Fetch failed: {_tve}")

        if _tv_info:
            # ── Quote strip ──────────────────────────────────────────────────
            _tv_price  = _tv_info.get("currentPrice") or _tv_info.get("regularMarketPrice") or 0
            _tv_prev   = _tv_info.get("previousClose") or 0
            _tv_chg    = ((_tv_price / _tv_prev) - 1) * 100 if _tv_prev > 0 else 0
            _tv_hi52   = _tv_info.get("fiftyTwoWeekHigh") or 0
            _tv_lo52   = _tv_info.get("fiftyTwoWeekLow") or 0
            _tv_vol    = _tv_info.get("volume") or 0
            _tv_avol   = _tv_info.get("averageVolume") or 1

            _tvc = st.columns(6)
            _tvc[0].metric("LTP",        f"₹{_tv_price:,.2f}", delta=f"{_tv_chg:+.2f}%",
                           delta_color="normal" if _tv_chg >= 0 else "inverse")
            _tvc[1].metric("Prev Close", f"₹{_tv_prev:,.2f}")
            _tvc[2].metric("52W High",   f"₹{_tv_hi52:,.2f}")
            _tvc[3].metric("52W Low",    f"₹{_tv_lo52:,.2f}")
            _tvc[4].metric("Volume",     f"{_tv_vol:,}")
            _tvc[5].metric("Vol/Avg",    f"{_tv_vol/_tv_avol:.2f}x" if _tv_avol > 0 else "N/A",
                           delta="above avg" if _tv_vol > _tv_avol else "below avg",
                           delta_color="normal" if _tv_vol > _tv_avol else "off")

        if not _tv_hist.empty:
            st.markdown("---")
            # ── Key technical levels ─────────────────────────────────────────
            section("Key Technical Levels")
            _tv_c = _tv_hist["Close"]
            _tv_sma20  = float(_tv_c.rolling(20).mean().iloc[-1])
            _tv_sma50  = float(_tv_c.rolling(50).mean().iloc[-1])
            _tv_sma200 = float(_tv_c.rolling(min(200, len(_tv_c))).mean().iloc[-1])
            _tv_hi10   = float(_tv_hist["High"].rolling(10).max().iloc[-1])
            _tv_lo10   = float(_tv_hist["Low"].rolling(10).min().iloc[-1])
            _tv_atr14  = float(
                pd.concat([
                    (_tv_hist["High"] - _tv_hist["Low"]),
                    (_tv_hist["High"] - _tv_hist["Close"].shift()).abs(),
                    (_tv_hist["Low"]  - _tv_hist["Close"].shift()).abs(),
                ], axis=1).max(axis=1).rolling(14).mean().iloc[-1]
            ) if len(_tv_hist) >= 14 else 0.0

            _lv_col1, _lv_col2 = st.columns(2)
            with _lv_col1:
                for _lbl, _val, _above in [
                    ("SMA 20",   _tv_sma20,  _tv_price > _tv_sma20),
                    ("SMA 50",   _tv_sma50,  _tv_price > _tv_sma50),
                    ("SMA 200",  _tv_sma200, _tv_price > _tv_sma200),
                ]:
                    _ic = "🟢" if _above else "🔴"
                    _di = f"{((_tv_price/_val)-1)*100:+.1f}%" if _val > 0 else ""
                    st.markdown(
                        f'<div style="padding:5px 0;border-bottom:1px solid #1e3a5f;display:flex;gap:8px;font-size:0.82rem">'
                        f'<span>{_ic}</span>'
                        f'<span style="flex:1;color:#c9d1d9">{_lbl}</span>'
                        f'<span style="color:#58a6ff">₹{_val:,.2f}</span>'
                        f'<span style="color:#8b949e;margin-left:8px">{_di}</span>'
                        f'</div>', unsafe_allow_html=True
                    )
            with _lv_col2:
                for _lbl, _val, _col in [
                    ("10D High", _tv_hi10, "#e3b341"),
                    ("10D Low",  _tv_lo10, "#e3b341"),
                    ("ATR(14)",  _tv_atr14, "#8b949e"),
                ]:
                    st.markdown(
                        f'<div style="padding:5px 0;border-bottom:1px solid #1e3a5f;display:flex;gap:8px;font-size:0.82rem">'
                        f'<span style="flex:1;color:#c9d1d9">{_lbl}</span>'
                        f'<span style="color:{_col}">₹{_val:,.2f}</span>'
                        f'</div>', unsafe_allow_html=True
                    )

            # ── Multi-panel chart: Price + Volume + RSI + MACD ───────────────
            st.markdown("---")
            section("Technical Chart")
            from plotly.subplots import make_subplots as _make_subplots

            # ── Compute RSI(14) ──────────────────────────────────────────────
            def _calc_rsi(series, period=14):
                delta = series.diff()
                gain  = delta.clip(lower=0).rolling(period).mean()
                loss  = (-delta.clip(upper=0)).rolling(period).mean()
                rs    = gain / loss.replace(0, float("nan"))
                return 100 - (100 / (1 + rs))

            # ── Compute MACD(12,26,9) ────────────────────────────────────────
            def _calc_macd(series, fast=12, slow=26, sig=9):
                ema_fast = series.ewm(span=fast, adjust=False).mean()
                ema_slow = series.ewm(span=slow, adjust=False).mean()
                macd     = ema_fast - ema_slow
                signal   = macd.ewm(span=sig, adjust=False).mean()
                hist_val = macd - signal
                return macd, signal, hist_val

            _tv_rsi          = _calc_rsi(_tv_hist["Close"])
            _tv_macd, _tv_sig, _tv_hist_macd = _calc_macd(_tv_hist["Close"])

            _fig_mp = _make_subplots(
                rows=4, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.50, 0.15, 0.18, 0.17],
                subplot_titles=("", "Volume", "RSI(14)", "MACD(12,26,9)")
            )

            # Row 1: Candlestick + SMAs
            _fig_mp.add_trace(go.Candlestick(
                x=_tv_hist.index,
                open=_tv_hist["Open"], high=_tv_hist["High"],
                low=_tv_hist["Low"],   close=_tv_hist["Close"],
                name=_tv_sym,
                increasing_line_color="#00f260", decreasing_line_color="#ff4b4b",
                increasing_fillcolor="#00f260",  decreasing_fillcolor="#ff4b4b",
            ), row=1, col=1)
            for _sl, _sv, _sc in [
                ("SMA20",  _tv_hist["Close"].rolling(20).mean(),  "#e3b341"),
                ("SMA50",  _tv_hist["Close"].rolling(50).mean(),  "#58a6ff"),
                ("SMA200", _tv_hist["Close"].rolling(200).mean(), "#a78bfa"),
            ]:
                _fig_mp.add_trace(go.Scatter(
                    x=_tv_hist.index, y=_sv, name=_sl, mode="lines",
                    line=dict(width=1.2, color=_sc)
                ), row=1, col=1)

            # Row 2: Volume bars
            _vol_colors = [
                "#00f260" if c >= o else "#ff4b4b"
                for c, o in zip(_tv_hist["Close"], _tv_hist["Open"])
            ]
            _fig_mp.add_trace(go.Bar(
                x=_tv_hist.index, y=_tv_hist["Volume"],
                name="Volume", marker_color=_vol_colors, showlegend=False
            ), row=2, col=1)

            # Row 3: RSI
            _fig_mp.add_trace(go.Scatter(
                x=_tv_hist.index, y=_tv_rsi, name="RSI(14)", mode="lines",
                line=dict(width=1.4, color="#58a6ff"), showlegend=False
            ), row=3, col=1)
            _fig_mp.add_hrect(y0=70, y1=100, row=3, col=1,
                              fillcolor="rgba(255,75,75,0.08)", line_width=0)
            _fig_mp.add_hrect(y0=0, y1=30, row=3, col=1,
                              fillcolor="rgba(0,242,96,0.08)", line_width=0)
            _fig_mp.add_hline(y=70, row=3, col=1, line_dash="dot",
                              line_color="#ff4b4b", line_width=1)
            _fig_mp.add_hline(y=30, row=3, col=1, line_dash="dot",
                              line_color="#00f260", line_width=1)

            # Row 4: MACD
            _macd_bar_colors = [
                "#00f260" if v >= 0 else "#ff4b4b" for v in _tv_hist_macd.fillna(0)
            ]
            _fig_mp.add_trace(go.Bar(
                x=_tv_hist.index, y=_tv_hist_macd,
                name="Histogram", marker_color=_macd_bar_colors, showlegend=False
            ), row=4, col=1)
            _fig_mp.add_trace(go.Scatter(
                x=_tv_hist.index, y=_tv_macd, name="MACD", mode="lines",
                line=dict(width=1.2, color="#58a6ff"), showlegend=False
            ), row=4, col=1)
            _fig_mp.add_trace(go.Scatter(
                x=_tv_hist.index, y=_tv_sig, name="Signal", mode="lines",
                line=dict(width=1.2, color="#e3b341"), showlegend=False
            ), row=4, col=1)

            _common_ax = dict(gridcolor="#1e3a5f", showgrid=True, zeroline=False)
            _fig_mp.update_layout(
                height=640, margin=dict(t=20, l=0, r=0, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,10,0.5)",
                xaxis_rangeslider_visible=False,
                legend=dict(font=dict(size=9, color="#c9d1d9"), bgcolor="rgba(0,0,0,0)",
                            orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
                font=dict(color="#c9d1d9"),
            )
            for _ax_key in ["xaxis", "xaxis2", "xaxis3", "xaxis4",
                            "yaxis",  "yaxis2",  "yaxis3",  "yaxis4"]:
                _fig_mp.update_layout(**{_ax_key: _common_ax})
            _fig_mp.update_layout(yaxis3=dict(range=[0, 100], **_common_ax))

            # Annotation: current RSI value
            _rsi_now = float(_tv_rsi.dropna().iloc[-1]) if not _tv_rsi.dropna().empty else 0
            _rsi_col = "#ff4b4b" if _rsi_now > 70 else "#00f260" if _rsi_now < 30 else "#e3b341"
            _fig_mp.add_annotation(
                x=0.01, y=0.28, xref="paper", yref="paper",
                text=f"RSI {_rsi_now:.1f}", showarrow=False,
                font=dict(size=10, color=_rsi_col), bgcolor="rgba(0,0,0,0.5)"
            )

            st.plotly_chart(_fig_mp, use_container_width=True)

            # ── Weinstein Stage Quick-Score ───────────────────────────────────
            st.markdown("---")
            section("Weinstein Stage Quick Assessment")
            _ws_above200  = _tv_price > _tv_sma200
            _ws_above50   = _tv_price > _tv_sma50
            _ws_sma200slp = float(
                (_tv_c.rolling(200).mean().diff(10) / _tv_c.rolling(200).mean().shift(10) * 100).iloc[-1]
            ) if len(_tv_c) >= 210 else 0.0
            _ws_pos52     = ((_tv_price - _tv_lo52) / max(_tv_hi52 - _tv_lo52, 1)) * 100 if _tv_hi52 > _tv_lo52 else 50
            _ws_score = (
                (25 if _ws_above200 and _ws_sma200slp > 0 else 0) +
                (20 if _ws_above200 else 0) +
                (15 if _ws_sma200slp > 0 else 0) +
                (12 if _ws_pos52 >= 75 else 6 if _ws_pos52 >= 50 else 0) +
                (8  if _ws_above50  else 0)
            )
            _ws_stage = (
                "Stage 2 — Advancing 🟢" if _ws_score >= 60 and _ws_above200 else
                "Stage 1 — Basing 🟡"    if _ws_above200 and _ws_sma200slp >= -0.5 else
                "Stage 4 — Declining 🔴" if not _ws_above200 and _ws_sma200slp < 0 else
                "Stage 3 — Topping 🟠"
            )
            _ws_c1, _ws_c2, _ws_c3, _ws_c4 = st.columns(4)
            _ws_c1.metric("Stage",          _ws_stage.split("—")[0].strip())
            _ws_c2.metric("Weinstein Score", f"{_ws_score}/80")
            _ws_c3.metric("52W Position",    f"{_ws_pos52:.0f}%")
            _ws_c4.metric("SMA200 Slope",    f"{_ws_sma200slp:+.2f}%",
                          delta="Rising" if _ws_sma200slp > 0 else "Falling",
                          delta_color="normal" if _ws_sma200slp > 0 else "inverse")

# ══════════════════════════════════════════════════════════════════════════
#  PYRAMID / TRIM — open-position ADD/TRIM/REDUCE/HOLD (inline)
# ══════════════════════════════════════════════════════════════════════════
elif page == 'PYRAMID':
    # Shared logic with pages/5_pyramid.py (pyramid_logic.render_pyramid_trim),
    # rendered INLINE in the main content area (no separate Streamlit process).
    try:
        from pyramid_logic import render_pyramid_trim
        render_pyramid_trim()
    except Exception as _pe:
        st.error(f"Pyramid / Trim Manager failed to load: {_pe}")
        import traceback as _tb
        st.code(_tb.format_exc())

# ══════════════════════════════════════════════════════════════════════════
#  RISK SHIELD — Active Exit Monitoring & Pullback Entry Tracking
# ══════════════════════════════════════════════════════════════════════════
elif page == 'RISK SHIELD':
    st.markdown('<div class="page-title">🛡️ Risk Shield — Risk Management & Entries</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-desc">Live monitoring of OCO exits, pullback entries, and unprotected holdings from Dhan GTT orders.</div>', unsafe_allow_html=True)

    # --- Portfolio Equity Curve Protection ---
    import datetime, json, os
    PORTFOLIO_FILE = "portfolio_history.json"

    # A8 FIX (2026-07-04 audit): atomic JSON writes (temp + os.replace) so a
    # crash or a second session mid-write can never truncate the history files.
    def _rs_atomic_json_write(path, obj):
        try:
            _tmp = path + ".tmp"
            with open(_tmp, "w") as f:
                json.dump(obj, f)
            os.replace(_tmp, path)
        except Exception:
            pass

    _portfolio_history = {}
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r") as f:
                _portfolio_history = json.load(f)
        except Exception:
            pass
    _today_str = datetime.date.today().isoformat()
    if 'total_cap' in globals():
        _portfolio_history[_today_str] = total_cap
        _rs_atomic_json_write(PORTFOLIO_FILE, _portfolio_history)

    _capital_protection_mode = False
    _cap_prot_msg = ""
    if len(_portfolio_history) >= 5:
        # Convert to pandas series to calculate EMA — SORTED by date key (a
        # json file with out-of-order keys would otherwise scramble the EMA).
        _s_port = pd.Series([v for _, v in sorted(_portfolio_history.items())])
        _port_ema20 = _s_port.ewm(span=20, adjust=False).mean().iloc[-1]
        _curr_port = _s_port.iloc[-1]
        if _curr_port < _port_ema20:
            _capital_protection_mode = True
            _cap_prot_msg = f"📉 CAPITAL PROTECTION MODE ACTIVE: Portfolio Equity (₹{_curr_port:,.0f}) is below 20-EMA (₹{_port_ema20:,.0f}). Mechanical stops will be tightened globally."

    # --- AI review helper (uses fast model for batch) ---
    # Prompts are framed for Jay's NSE swing/positional method: Weinstein Stage 2,
    # ATR-trailed stops, R-discipline, and "confirmation before entry" (a closed
    # trigger bar, never a blind buy-limit at the zone). Keep answers to 1 sentence.
    def get_stock_context_and_ai_review(symbol, order_type, **kwargs):
        from ai_provider_manager import ask_llm
        _tech = kwargs.get("tech")
        _tech_str = ""
        if _tech:
            _tech_str = (f"\nLIVE TECHNICALS: "
                         f"Weinstein Score: {_tech['ws_score']}/80 | "
                         f"200-SMA: ₹{_tech['sma200']} ({'Rising' if _tech['sma200_slope'] > 0 else 'Falling'}, {_tech['sma200_slope']}% slope) | "
                         f"50-SMA: ₹{_tech['sma50']} | "
                         f"Price > 200-SMA: {'Yes' if _tech['above200'] else 'No'} | "
                         f"Dist from 200-SMA: {_tech['dist_from_200']}% | "
                         f"ATR Volatility: {_tech['atr_pct']}% | "
                         f"Volume Climax: {'Yes (Spike >300%)' if _tech.get('vol_climax') else 'No'} | "
                         f"Breakout Volume: {'Yes (Base Breakout)' if _tech.get('vol_breakout') else 'No'} | "
                         f"Days to Earnings: {_tech.get('days_to_earnings') if _tech.get('days_to_earnings') is not None else 'N/A'} | "
                         f"Chandelier Exit (22D): ₹{_tech.get('chandelier_exit', 'N/A')}")

        _sys = (
            "You are an elite NSE technical analyst and risk manager evaluating an active trade. "
            "CRITICAL: Start your response with exactly '[Positional]' or '[Swing]' based on your classification. "
            "CLASSIFICATION RULES: "
            "If the stock is highly volatile (ATR > 4%), extended from its 200-SMA (Dist > 30%), or showing trend decay (Weinstein Score < 60), classify it as '[Swing]' (tighter risk, faster exits). "
            "If it is a stable Stage 2 compounder (ATR < 4%, Dist < 30%, strong score), classify it as '[Positional]' (trend following). "
            "ANALYSIS RULES: Provide a sharp, insightful 2-3 sentence technical evaluation. "
            "If 'Volume Climax' is Yes, warn about potential trend exhaustion. If 'Breakout Volume' is Yes, highlight the strong accumulation base breakout. If 'Days to Earnings' is < 5, recommend tightening risk or trimming. "
            "Do NOT just regurgitate the numbers provided in the prompt. "
            "Analyze the price action relative to the moving averages, volatility, and trend strength. Offer actionable risk management advice."
        )
        if order_type == "OCO_EXIT_COMBINED":
            orders_list = kwargs.get("orders", [])
            ltp = kwargs.get("ltp", 0)
            r_mult = kwargs.get("r_mult", "N/A")
            risk = kwargs.get("risk", 0)
            orders_desc = []
            for o_idx, o in enumerate(orders_list):
                sl = o["sl_trigger"]; target = o["target_trigger"]
                sl_qty = o.get("sl_qty") or o.get("qty") or 0
                tgt_qty = o.get("target_qty") or o.get("qty") or 0
                sl_dist = ((ltp - sl) / ltp * 100) if ltp and sl else 0.0
                tgt_dist = ((target - ltp) / ltp * 100) if ltp and target else 0.0
                orders_desc.append(f"  Leg {o_idx+1}: SL ₹{sl:,.0f} ({sl_dist:+.1f}%) | Tgt ₹{target:,.0f} (+{tgt_dist:.1f}%)")
            prompt = f"{_sys}\n{symbol} | LTP ₹{ltp:,.2f} | open R: {r_mult} | open risk ₹{risk:,.0f}{_tech_str}\n" + "\n".join(orders_desc) + "\nProvide a brief technical analysis of this stock and advise if I should hold, trail the SL up, or exit."
            return ask_llm(prompt, fallback_text="Monitor position. SL and targets active.")
        elif order_type == "GTT_ENTRY":
            trigger = kwargs.get("trigger", 0); price = kwargs.get("price", 0)
            ltp = kwargs.get("ltp", 0); dist = kwargs.get("dist", 0)
            _style = "dip buy-limit (fills on touch, NO confirmation)" if trigger < ltp else "breakout buy-stop (confirms on a close into the trigger)"
            _tech = kwargs.get("tech")
            _setup_warn = ""
            if _tech:
                if _tech.get("ws_score", 100) < 50 or _tech.get("sma200_slope", 0) < 0:
                    _setup_warn = f"\nWARNING: Setup may be invalid. WS Score is {_tech.get('ws_score')}/80 and SMA200 slope is {_tech.get('sma200_slope'):+.2f}%. Highlight these risks."
            prompt = f"{_sys}\n{symbol} | LTP ₹{ltp:,.2f} | buy trigger ₹{trigger:,.2f} ({dist:+.1f}% vs LTP) | limit ₹{price:,.2f} | type: {_style}{_tech_str}{_setup_warn}\nProvide a brief technical analysis on whether this looks like a valid Stage-2 pullback entry setup."
            return ask_llm(prompt, fallback_text="Pullback entry active. Wait for a confirmation close before entry.")
        elif order_type == "UNPROTECTED_HOLDING":
            buy_price = kwargs.get("buy_price", 0); ltp = kwargs.get("ltp", 0)
            pnl_pct = ((ltp - buy_price) / buy_price * 100) if buy_price else 0.0
            prompt = f"{_sys}\n{symbol} | LTP ₹{ltp:,.2f} | cost ₹{buy_price:,.2f} | P&L {pnl_pct:+.1f}% | NO STOP LOSS{_tech_str}\nProvide a technical view and suggest an optimal placement for a stop loss to protect this position."
            return ask_llm(prompt, fallback_text="Place a stop loss immediately (≈2 ATR below a recent swing low).")
        elif order_type == "SINGLE_EXIT":
            trigger = kwargs.get("trigger", 0); ltp = kwargs.get("ltp", 0)
            dist = kwargs.get("dist", 0); label = kwargs.get("label", "Stop Loss")
            prompt = f"{_sys}\n{symbol} | LTP ₹{ltp:,.2f} | {label}: ₹{trigger:,.2f} ({dist:+.1f}% away){_tech_str}\nShould I hold, trail, or act on this {label.lower()}?"
            return ask_llm(prompt, fallback_text=f"{label} trigger active. Monitor.")
        return "N/A"

    # --- Persistent AI Cache Logic ---
    import json
    import os
    AI_CACHE_FILE = "ai_cache.json"
    
    if "ai_cache_loaded" not in st.session_state:
        st.session_state.ai_cache_loaded = True
        if os.path.exists(AI_CACHE_FILE):
            try:
                with open(AI_CACHE_FILE, "r") as f:
                    _saved = json.load(f)
                for k, v in _saved.items():
                    if k not in st.session_state:
                        st.session_state[k] = v
            except: pass

    # Controls row
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([8, 2, 2])
    with ctrl_col3:
        if st.button("🔄 Refresh", key="es_refresh", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    with ctrl_col2:
        if st.button("🤖 Run AI Analysis", key="es_run_ai", type="secondary", use_container_width=True):
            st.session_state.force_run_ai = True
            for k in list(st.session_state.keys()):
                if any(p in k for p in ["ai_exit_review_", "ai_single_review_", "ai_entry_review_", "ai_unprotected_review_"]):
                    del st.session_state[k]
            if os.path.exists(AI_CACHE_FILE):
                os.remove(AI_CACHE_FILE)
            st.rerun()

    if not _BROKER_OK:
        st.error("❌ Dhan broker API module not available.")
    else:
        try:
            _ts = dhan_token_status()
            _tk_valid = _ts.get("valid", False)
        except Exception:
            _tk_valid = False

        if sys_status == "AUTH EXPIRED" or not _tk_valid:
            st.error("🔑 Dhan token expired. Paste a fresh access token in the sidebar.")
        else:
            with st.spinner("Fetching active orders from Dhan..."):
                try:
                    dhan, ctx = get_dhanhq_client()
                    if not dhan:
                        st.error("Dhan Auth missing")
                        st.stop()
                    resp = dhan.get_forever()
                except Exception as e:
                    resp = None
                    st.error(f"Failed to fetch orders: {e}")

            if resp and isinstance(resp, dict) and resp.get("status") == "success":
                data = resp.get("data", [])

                # --- Parse and group orders ---
                buy_gtts = []; sell_gtts = {}; single_sells = []; symbols_to_fetch = set()

                # Dhan forever-order shape (canonical — see scratch/test_parse_gtt.py
                # and dhan_journal_v7.py): an OCO carries orderType == "OCO" and emits
                # TWO rows that share the SAME orderId — one legName=STOP_LOSS_LEG, one
                # legName=TARGET_LEG. Anything else SELL is a standalone exit. Group OCO
                # legs by orderId; classify by legName, price only as a last resort.
                for g in data:
                    if g.get("orderStatus", "") != "PENDING": continue
                    symbol = clean_symbol(g.get("tradingSymbol", ""))
                    if not symbol: continue
                    symbols_to_fetch.add(symbol)
                    txn = (g.get("transactionType", "") or "").upper()
                    ot  = (g.get("orderType", "") or "").upper()
                    order_id = g.get("orderId", ""); qty = int(float(g.get("quantity", 0) or 0))
                    trigger = float(g.get("triggerPrice", 0) or 0); price = float(g.get("price", 0) or 0)
                    leg = (g.get("legName", "") or "").upper()

                    if txn == "BUY":
                        buy_gtts.append({"symbol": symbol, "qty": qty, "trigger": trigger, "price": price, "order_id": order_id})
                        continue
                    if txn != "SELL":
                        continue

                    # OCO if the broker says so OR the row is a recognised OCO leg.
                    is_oco = (ot == "OCO") or (leg in ("STOP_LOSS_LEG", "TARGET_LEG"))
                    if is_oco:
                        gid = order_id or g.get("correlationId", "")
                        if gid not in sell_gtts:
                            sell_gtts[gid] = {"symbol": symbol, "sl_trigger": None, "sl_qty": None,
                                              "target_trigger": None, "target_qty": None, "order_id": gid, "qty": qty}
                        if leg == "STOP_LOSS_LEG":
                            is_sl = True
                        elif leg == "TARGET_LEG":
                            is_sl = False
                        else:
                            # No leg label: a SELL stop sits below the target, so the
                            # lower-trigger leg is the SL. Self-heal pass below corrects ties.
                            is_sl = trigger < price if (trigger and price) else True
                        if is_sl:
                            sell_gtts[gid]["sl_trigger"] = trigger
                            sell_gtts[gid]["sl_qty"] = qty
                        else:
                            sell_gtts[gid]["target_trigger"] = trigger
                            sell_gtts[gid]["target_qty"] = qty
                    else:
                        single_sells.append({"symbol": symbol, "qty": qty, "trigger": trigger, "price": price, "order_id": order_id})

                # Self-heal: in any OCO the SL trigger must be below the target trigger.
                # If a mislabelled leg flipped them, swap (price/qty together) so downstream
                # risk + R-multiple math is correct regardless of broker leg labelling.
                for oco in sell_gtts.values():
                    _sl, _tg = oco["sl_trigger"], oco["target_trigger"]
                    if _sl is not None and _tg is not None and _sl > _tg:
                        oco["sl_trigger"], oco["target_trigger"] = _tg, _sl
                        oco["sl_qty"], oco["target_qty"] = oco["target_qty"], oco["sl_qty"]

                # Fetch LTPs
                if symbols_to_fetch:
                    ltps = get_batch_ltps(tuple(sorted(symbols_to_fetch)))
                else:
                    ltps = {}

                # Fetch overrides from global df (from SQLite)
                journal_overrides = {}
                if 'df_active_global' in globals() and not df_active_global.empty:
                    for _, r in df_active_global.iterrows():
                        sym = r.get("Symbol")
                        if pd.notna(sym):
                            journal_overrides[sym] = {
                                "manual_sl_override": float(r.get("Manual SL Override", 0)) if pd.notna(r.get("Manual SL Override")) and str(r.get("Manual SL Override")).strip() else None,
                                "custom_ce_mult": float(r.get("Custom CE Mult", 0)) if pd.notna(r.get("Custom CE Mult")) and str(r.get("Custom CE Mult")).strip() else None,
                                "pyramid_status": str(r.get("Pyramid Status", "")) if pd.notna(r.get("Pyramid Status")) else "",
                                # B1: the trade's catalyst (journal 'setup' snapshot) drives
                                # the validated trail multiplier set.
                                "setup": str(r.get("Setup", "")).strip().upper() if pd.notna(r.get("Setup")) else "",
                            }

                # B2: market regime (0-10 scorer) — degrades to per-symbol SMA200 check on failure
                _rs_regime_bear = None
                _rs_regime_chip = ""
                try:
                    from market_regime import compute_regime as _rs_creg
                    _rs_reg = _rs_creg(persist=False)
                    _rs_score9 = _rs_reg.get("score")
                    if _rs_score9 is not None:
                        _rs_regime_bear = _rs_score9 <= 5
                        _rs_regime_chip = f"{_rs_reg.get('verdict','?')} ({_rs_score9}/10)"
                except Exception:
                    pass

                # Catalyst-aware trail multipliers now live in risk_common.chandelier_exit
                # (shared single source of truth with the Pyramid/Trim page).

                # Fetch holdings for entry price & unprotected detection
                _, _, df_holdings = get_live_holdings_stats()
                holdings_map = {}
                if not df_holdings.empty:
                    for _, h in df_holdings.iterrows():
                        csym = clean_symbol(h.get("Symbol", h.get("tradingSymbol", "")))
                        if csym:
                            holdings_map[csym] = {
                                "buy_price": float(h.get("BuyPrice", h.get("avgCostPrice", 0))),
                                "qty": int(float(h.get("Quantity", h.get("totalQty", 0)))),
                                "ltp": float(h.get("LTP", h.get("lastTradedPrice", 0))),
                                "entry_date": h.get("EntryDate", "")
                            }

                # Dhan LTP is authoritative — every OCO exit sits on a stock you hold,
                # so Dhan's lastTradedPrice covers all of them and is real-time intraday.
                # Prefer it over yfinance (delayed, and flaky on some .NS tickers); fall
                # back to yfinance only for symbols Dhan has no holding for (e.g. a stale
                # OCO left after the underlying was sold). This makes the page's LTP — and
                # therefore the SL/target distance %s — fully Dhan-sourced wherever possible.
                for _csym, _h in holdings_map.items():
                    if _h.get("ltp"):
                        ltps[_csym] = _h["ltp"]

                # Detect unprotected holdings
                # A1 SAFETY FIX (2026-07-04 audit): a single sell order is only proof of
                # SL protection when a REAL LTP exists to compare against. The old
                # fallback to the order's own price made a TARGET-only order classify
                # the position as protected. No LTP -> protection state UNKNOWN,
                # surfaced loudly, never silently protected.
                all_protected_syms = set()
                protection_unknown = set()
                for oid, oco in sell_gtts.items():
                    if oco["sl_trigger"] is not None:
                        all_protected_syms.add(oco["symbol"])
                for s in single_sells:
                    _ss_ltp = ltps.get(s["symbol"])
                    if _ss_ltp and _ss_ltp > 0:
                        if s["trigger"] < _ss_ltp:
                            all_protected_syms.add(s["symbol"])
                    elif s["symbol"] in holdings_map and s["symbol"] not in all_protected_syms:
                        protection_unknown.add(s["symbol"])

                unprotected_holdings = []
                for csym, h in holdings_map.items():
                    if csym in protection_unknown:
                        continue  # rendered as UNKNOWN below, not as protected/unprotected
                    if csym not in all_protected_syms and h["qty"] > 0:
                        unprotected_holdings.append({"symbol": csym, "buy_price": h["buy_price"], "qty": h["qty"], "ltp": h["ltp"], "entry_date": h.get("entry_date", "")})
                        symbols_to_fetch.add(csym)
                if protection_unknown:
                    st.warning(f"⚠️ LTP unavailable — protection state UNKNOWN for: "
                               f"{', '.join(sorted(protection_unknown))}. Verify their stop "
                               f"orders manually on Dhan before trusting this page.")

                # Group sell_gtts by symbol
                sell_gtts_by_symbol = {}
                for oid, oco in sell_gtts.items():
                    sym = oco["symbol"]
                    if sym not in sell_gtts_by_symbol:
                        sell_gtts_by_symbol[sym] = []
                    sell_gtts_by_symbol[sym].append(oco)
                for sym, orders in sell_gtts_by_symbol.items():
                    orders.sort(key=lambda x: x["target_trigger"] if x["target_trigger"] is not None else 9999999)



                # ─────────────────────────────────────────────────────────────

                # --- Metrics ---
                # A6 FIX (2026-07-04 audit): rows without a REAL LTP are excluded from
                # the risk sums and COUNTED — headline metrics must never be quietly
                # understated by missing prices.
                total_protected = 0.0; total_risk = 0.0
                _no_ltp_rows = set()
                active_exits_count = len(sell_gtts_by_symbol)
                pending_entries_count = len(buy_gtts)
                for sym, orders in sell_gtts_by_symbol.items():
                    ltp = ltps.get(sym) or 0
                    if not ltp:
                        _no_ltp_rows.add(sym)
                    for oco in orders:
                        sl = oco["sl_trigger"]; sl_qty = oco.get("sl_qty") or oco.get("qty") or 0
                        if sl: total_protected += sl_qty * sl
                        if ltp and sl:
                            risk = sl_qty * (ltp - sl)
                            if risk > 0: total_risk += risk
                for s in single_sells:
                    trigger = s["trigger"]; qty = s["qty"]; sym = s["symbol"]
                    ltp = ltps.get(sym) or 0
                    if not ltp:
                        _no_ltp_rows.add(sym)
                    if trigger:
                        total_protected += qty * trigger
                        if ltp and ltp > trigger: total_risk += qty * (ltp - trigger)

                unprotected_count = len(unprotected_holdings)
                unprotected_color = "#ff4b4b" if unprotected_count > 0 else "#00f260"
                unprotected_label = f"{unprotected_count} Positions" if unprotected_count > 0 else "All Protected ✅"
                risk_deployed_pct = (total_risk / total_deployed_g) * 100 if total_deployed_g > 0 else 0.0

                metrics_html = (
                    f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:18px;">'
                    f'<div class="metric-card" style="padding:14px;border-top:4px solid #00f260;text-align:left;">'
                    f'<div class="metric-label">Capital Protected</div>'
                    f'<div class="metric-value" style="color:#00f260;font-size:1.5rem;">₹{format_inr_int(total_protected)}</div>'
                    f'<div style="font-size:0.68rem;color:#5a8a9f;margin-top:2px;">Active Stop Loss value</div></div>'
                    f'<div class="metric-card" style="padding:14px;border-top:4px solid #ff4b4b;text-align:left;">'
                    f'<div class="metric-label">Capital at Risk</div>'
                    f'<div class="metric-value" style="color:#ff4b4b;font-size:1.5rem;">₹{format_inr_int(total_risk)} <span style="font-size:1rem; opacity:0.8;">({risk_deployed_pct:.1f}%)</span></div>'
                    f'<div style="font-size:0.68rem;color:#5a8a9f;margin-top:2px;">Loss to SL</div></div>'
                    f'<div class="metric-card" style="padding:14px;border-top:4px solid #58a6ff;text-align:left;">'
                    f'<div class="metric-label">Active Exits</div>'
                    f'<div class="metric-value" style="color:#58a6ff;font-size:1.5rem;">{active_exits_count} Stocks</div>'
                    f'<div style="font-size:0.68rem;color:#5a8a9f;margin-top:2px;">{len(sell_gtts)} OCO · {len(single_sells)} Standalone</div></div>'
                    f'<div class="metric-card" style="padding:14px;border-top:4px solid #e3b341;text-align:left;">'
                    f'<div class="metric-label">Pullback Entries</div>'
                    f'<div class="metric-value" style="color:#e3b341;font-size:1.5rem;">{pending_entries_count} Orders</div>'
                    f'<div style="font-size:0.68rem;color:#5a8a9f;margin-top:2px;">Active GTT buy limits</div></div>'
                    f'<div class="metric-card" style="padding:14px;border-top:4px solid {unprotected_color};text-align:left;">'
                    f'<div class="metric-label">Unprotected</div>'
                    f'<div class="metric-value" style="color:{unprotected_color};font-size:1.5rem;">{unprotected_label}</div>'
                    f'<div style="font-size:0.68rem;color:#5a8a9f;margin-top:2px;">Holdings with no SL</div></div>'
                    f'</div>'
                )
                st.markdown(metrics_html, unsafe_allow_html=True)
                if _no_ltp_rows:
                    st.caption(f"⚠️ {len(_no_ltp_rows)} position(s) excluded from Capital-at-Risk "
                               f"(no live LTP): {', '.join(sorted(_no_ltp_rows))}")

                # B3: PORTFOLIO HEAT vs the capital risk budget (risk% x capital x open
                # positions). Connects Risk Shield to the capital-based risk rule —
                # 0.25% per trade during the execution freeze (1.0% standard).
                try:
                    _rb_pct = float(st.session_state.get("rs_risk_budget_pct", 0.25))
                    _cash_b = 0.0
                    try:
                        _cash_b = float(get_dhan_balance() or 0.0)
                    except Exception:
                        pass
                    _cap_base = float(total_deployed_g or 0.0) + _cash_b
                    _n_open_h = active_exits_count + len(unprotected_holdings)
                    _heat_budget = _cap_base * (_rb_pct / 100.0) * max(_n_open_h, 1)
                    if _cap_base > 0:
                        _heat_ok = total_risk <= _heat_budget
                        _hcol = "#00f260" if _heat_ok else "#ff4b4b"
                        _chip = (f" · 🌡️ Regime: <b>{_rs_regime_chip}</b>" if _rs_regime_chip else "")
                        st.markdown(
                            f"<div style='border:1.5px solid {_hcol};border-radius:8px;padding:8px 14px;"
                            f"margin:4px 0 10px;font-size:0.9rem;'>"
                            f"🔥 <b>Portfolio Heat:</b> ₹{format_inr_int(total_risk)} open risk vs budget "
                            f"₹{format_inr_int(_heat_budget)} ({_rb_pct}% × {_n_open_h} positions × "
                            f"₹{format_inr_int(_cap_base)} capital) — "
                            f"<b style='color:{_hcol}'>{'WITHIN BUDGET' if _heat_ok else 'OVER BUDGET'}</b>"
                            f"{_chip}</div>", unsafe_allow_html=True)
                except Exception:
                    pass

                # --- Fetch technicals for AI review and Risk Profile ---
                hist_data = st.session_state.get("cached_hist_data_v3", {})
                if hist_data and any(isinstance(v, dict) and ("close_5d_ago" not in v or "vol_breakout" not in v) for v in hist_data.values()):
                    hist_data = {}
                missing_syms = [s for s in symbols_to_fetch if s not in hist_data or "ema20" not in hist_data.get(s, {})]
                _tech_failed_syms = []   # A5 FIX: track symbols whose technicals could not be computed
                if missing_syms:
                    try:
                        import data_provider as dp
                        import pandas as pd
                        import numpy as np

                        _batch_data = dp.fetch_batch_ohlcv(missing_syms, period="1y", interval="1d", use_cache=True, auto_adjust=True)
                        _tech_failed_syms = [s for s in missing_syms
                                             if _batch_data.get(s) is None or getattr(_batch_data.get(s), "empty", True)]
                        # A9: capture the technicals' as-of date for the freshness strip.
                        # Stored BOTH in session_state and inside the hist cache itself, so
                        # cache-hit runs (no batch fetch) still show the real date, not "—".
                        try:
                            _asof_candidates = [df.index[-1] for df in _batch_data.values()
                                                if df is not None and not df.empty]
                            if _asof_candidates:
                                _asof_s = str(max(_asof_candidates).date())
                                st.session_state["rs_tech_asof"] = _asof_s
                                hist_data["_asof"] = _asof_s
                        except Exception:
                            pass

                        for _s in missing_syms:
                            df_sym = _batch_data.get(_s)
                            if df_sym is not None and not df_sym.empty and "Close" in df_sym.columns:
                                _c = df_sym["Close"].dropna()
                                _hi = df_sym["High"].dropna() if "High" in df_sym.columns else _c
                                _lo = df_sym["Low"].dropna() if "Low" in df_sym.columns else _c
                                
                                _ema20 = float(_c.ewm(span=20, adjust=False).mean().iloc[-1]) if len(_c) >= 20 else None
                                _close_5d_ago = float(_c.iloc[-6]) if len(_c) >= 6 else None
                                
                                _ltp = float(_c.iloc[-1])
                                _ws_score = 0
                                _ws_above200 = False
                                _sma200slp = 0.0
                                _sma200 = 0.0
                                _sma50 = 0.0
                                _atr_pct = 0.0
                                _dist_from_200 = 0.0
                                
                                if len(_c) >= 200:
                                    _sma50 = float(_c.rolling(50).mean().iloc[-1])
                                    _sma200 = float(_c.rolling(200).mean().iloc[-1])
                                    _sma200_10d_ago = float(_c.rolling(200).mean().shift(10).iloc[-1])
                                    _sma200slp = ((_sma200 - _sma200_10d_ago) / _sma200_10d_ago) * 100 if _sma200_10d_ago else 0
                                    _hi52 = float(_c.max())
                                    _lo52 = float(_c.min())
                                    
                                    # ATR Calculation (14-day)
                                    _tr1 = _hi - _lo
                                    _tr2 = (_hi - _c.shift(1)).abs()
                                    _tr3 = (_lo - _c.shift(1)).abs()
                                    _tr = pd.concat([_tr1, _tr2, _tr3], axis=1).max(axis=1)
                                    _atr = float(_tr.rolling(14).mean().iloc[-1])
                                    _atr_pct = (_atr / _ltp) * 100 if _ltp else 0.0
                                    _dist_from_200 = ((_ltp - _sma200) / _sma200) * 100 if _sma200 else 0.0
                                    
                                    _vol_climax = False
                                    _vol_breakout = False
                                    if "Volume" in df_sym.columns:
                                        _vol = df_sym["Volume"].dropna()
                                        if len(_vol) >= 50 and len(_hi) >= 45:
                                            _vol_50d_avg = float(_vol.rolling(50).mean().iloc[-1])
                                            if _vol_50d_avg > 0:
                                                _has_spike = False
                                                _has_heavy_selling = False
                                                _spike_high = 0.0
                                                for i in range(-5, 0):
                                                    if float(_vol.iloc[i]) / _vol_50d_avg >= 3.0:
                                                        _has_spike = True
                                                        _c_i = float(_c.iloc[i])
                                                        _h_i = float(_hi.iloc[i])
                                                        _l_i = float(_lo.iloc[i])
                                                        _o_i = float(df_sym["Open"].iloc[i]) if "Open" in df_sym.columns else _c_i
                                                        
                                                        _spike_high = max(_spike_high, _h_i)
                                                        
                                                        _candle_range = _h_i - _l_i
                                                        _upper_wick = _h_i - max(_c_i, _o_i)
                                                        _wick_pct = (_upper_wick / _candle_range) if _candle_range > 0 else 0.0
                                                        
                                                        if _wick_pct >= 0.35 or ((_h_i - _ltp) / _h_i) > 0.04:
                                                            _has_heavy_selling = True

                                                if _has_spike:
                                                    _prev_40d_high = float(_hi.iloc[-45:-5].max())
                                                    _dist_from_50 = ((_ltp - _sma50) / _sma50) * 100 if _sma50 else 0.0
                                                    
                                                    if _spike_high > _prev_40d_high and _dist_from_50 < 30.0 and not _has_heavy_selling:
                                                        _vol_breakout = True
                                                    else:
                                                        _vol_climax = True                                                
                                    # Chandelier trail via the SHARED risk_common helper — single
                                    # source of truth, kept in sync with the Pyramid/Trim page.
                                    _chandelier_exit = None
                                    _ce_mult = None
                                    _ce_mult_src = None
                                    _custom_mult = journal_overrides.get(_s, {}).get("custom_ce_mult") if _s in journal_overrides else None
                                    # A4 FIX (2026-07-04 audit): 0/negative custom mult is INVALID,
                                    # not "silently use system default" — flag it on the row.
                                    _invalid_ce_override = (_custom_mult is not None
                                                            and not (isinstance(_custom_mult, (int, float)) and _custom_mult > 0))
                                    if len(_c) >= 22:
                                        import risk_common as _rc
                                        _setup_s = journal_overrides.get(_s, {}).get("setup", "")
                                        _bear_s = _rs_regime_bear if _rs_regime_bear is not None else (not _ws_above200)
                                        _chandelier_exit, _ce_mult, _ce_mult_src = _rc.chandelier_exit(
                                            _hi, _lo, _c, setup=_setup_s, bear=_bear_s,
                                            cap_protect=_capital_protection_mode,
                                            custom_mult=_custom_mult, above200=_ws_above200)

                                        # Apply Manual SL Override if present.
                                        # A7 FIX: override MODE — 'Floor' (default, can only tighten)
                                        # or 'Exact' (use the manual value verbatim, both directions).
                                        _manual_sl = journal_overrides.get(_s, {}).get("manual_sl_override") if _s in journal_overrides else None
                                        if _manual_sl and _manual_sl > 0:
                                            if st.session_state.get("rs_sl_override_mode", "Floor") == "Exact":
                                                _chandelier_exit = _manual_sl
                                            else:
                                                _chandelier_exit = max(_chandelier_exit, _manual_sl)
                                        
                                    _days_to_earnings = None
                                    _edate = get_earnings_date_cached(_s)
                                    if _edate:
                                        from datetime import date
                                        _diff = (_edate - date.today()).days
                                        if 0 <= _diff <= 30:
                                            _days_to_earnings = _diff
                                    
                                    _ws_above200 = _ltp > _sma200
                                    _ws_above50 = _ltp > _sma50
                                    _ws_pos52 = ((_ltp - _lo52) / max(_hi52 - _lo52, 1)) * 100 if _hi52 > _lo52 else 50
                                    _ws_score = (
                                        (25 if _ws_above200 and _sma200slp > 0 else 0) +
                                        (20 if _ws_above200 else 0) +
                                        (15 if _sma200slp > 0 else 0) +
                                        (12 if _ws_pos52 >= 75 else 6 if _ws_pos52 >= 50 else 0) +
                                        (8  if _ws_above50  else 0)
                                    )
                                    
                                hist_data[_s] = {
                                    "ws_score": int(_ws_score),
                                    "sma200_slope": round(_sma200slp, 2),
                                    "sma200": round(_sma200, 2),
                                    "sma50": round(_sma50, 2),
                                    "ema20": round(_ema20, 2) if _ema20 else None,
                                    "above200": _ws_above200,
                                    "atr_pct": round(_atr_pct, 2),
                                    "dist_from_200": round(_dist_from_200, 2),
                                    "chandelier_exit": round(_chandelier_exit, 2) if _chandelier_exit else None,
                                    "close_5d_ago": round(_close_5d_ago, 2) if _close_5d_ago else None,
                                    "vol_breakout": _vol_breakout if '_vol_breakout' in locals() else False,
                                    "vol_climax": _vol_climax if '_vol_climax' in locals() else False,
                                    "days_to_earnings": _days_to_earnings if '_days_to_earnings' in locals() else None,
                                    "ce_mult": _ce_mult if '_ce_mult' in locals() else None,
                                    "ce_mult_src": _ce_mult_src if '_ce_mult_src' in locals() else None,
                                    "invalid_ce_override": _invalid_ce_override if '_invalid_ce_override' in locals() else False,
                                }
                    except Exception as _e:
                        # A5 FIX (2026-07-04 audit): a batch-level failure means NONE of
                        # the missing symbols got technicals — say so instead of silence.
                        _tech_failed_syms = list(missing_syms)
                        st.warning(f"⚠️ Technicals fetch failed this run ({_e}) — Chandelier/"
                                   f"flags not computed for {len(missing_syms)} symbol(s).")
                if _tech_failed_syms:
                    st.warning(f"⚠️ Technicals unavailable for: {', '.join(sorted(_tech_failed_syms))} "
                               f"— Chandelier exits, WS scores and volume flags for these are "
                               f"NOT current this run.")
                st.session_state["cached_hist_data_v3"] = hist_data

                # A9: DATA FRESHNESS STRIP — where prices came from + technicals as-of.
                try:
                    import data_provider as _dp9
                    _src_counts = {}
                    for _fs in list(symbols_to_fetch)[:100]:
                        _sname = str(_dp9.get_last_source(_fs) or "holdings")
                        _src_counts[_sname] = _src_counts.get(_sname, 0) + 1
                    _src_str = " · ".join(f"{k}:{v}" for k, v in sorted(_src_counts.items()))
                    _asof9 = st.session_state.get("rs_tech_asof") or hist_data.get("_asof") or "—"
                    _nsyms9 = sum(1 for _v9 in hist_data.values() if isinstance(_v9, dict))
                    # Split holdings vs order-only symbols (pending GTT entries / stale
                    # OCOs on sold stocks) so the count never reads as a mismatch vs
                    # the portfolio size.
                    _order_only9 = sorted(set(symbols_to_fetch) - set(holdings_map.keys()))
                    _split9 = (f" ({len(holdings_map)} holdings + {len(_order_only9)} order-only: "
                               f"{', '.join(_order_only9)})" if _order_only9 else f" ({len(holdings_map)} holdings)")
                    st.caption(f"🩺 Data: LTP sources [{_src_str}] · technicals as-of {_asof9} "
                               f"· hist cache {_nsyms9} syms{_split9}")
                except Exception:
                    pass

                _ai_tasks = []
                for _sym, _orders in sell_gtts_by_symbol.items():
                    _ai_k = f"ai_exit_review_{_sym}"
                    if _ai_k not in st.session_state:
                        if st.session_state.get("force_run_ai"):
                            _ltp = ltps.get(_sym) or 0
                            _tq = sum(o.get("sl_qty") or o.get("qty") or 0 for o in _orders)
                            _re = sum((o.get("sl_qty") or o.get("qty") or 0) * (_ltp - o["sl_trigger"]) for o in _orders if _ltp and o["sl_trigger"] is not None)
                            _h = holdings_map.get(_sym)
                            if _h:
                                _bp = _h["buy_price"]
                                _tri = sum((o.get("sl_qty") or o.get("qty") or 0) * (_bp - o["sl_trigger"]) for o in _orders if o["sl_trigger"] is not None)
                                _rm = f"{(_ltp - _bp) * _tq / _tri:+.2f}R" if _tri > 0 else "N/A"
                            else:
                                _rm = "N/A"
                            _ai_tasks.append((_ai_k, _sym, "OCO_EXIT_COMBINED", {"orders": _orders, "ltp": _ltp, "r_mult": _rm, "risk": _re, "tech": hist_data.get(_sym)}))
                        else:
                            st.session_state[_ai_k] = "AI analysis pending. Click 'Run AI Analysis' to generate."
                for _b in buy_gtts:
                    _sym = _b["symbol"]; _ai_k = f"ai_entry_review_{_sym}_{_b['order_id']}"
                    if _ai_k not in st.session_state:
                        if st.session_state.get("force_run_ai"):
                            _ltp = ltps.get(_sym) or 0
                            _dist = (_ltp - _b["trigger"]) / _ltp * 100 if _ltp else 0.0
                            _ai_tasks.append((_ai_k, _sym, "GTT_ENTRY", {"trigger": _b["trigger"], "price": _b["price"], "ltp": _ltp, "dist": _dist, "tech": hist_data.get(_sym)}))
                        else:
                            st.session_state[_ai_k] = "AI analysis pending. Click 'Run AI Analysis' to generate."
                for _h in unprotected_holdings:
                    _sym = _h["symbol"]; _ai_k = f"ai_unprotected_review_{_sym}"
                    if _ai_k not in st.session_state:
                        if st.session_state.get("force_run_ai"):
                            _ltp = ltps.get(_sym) or _h["ltp"] or 0
                            _ai_tasks.append((_ai_k, _sym, "UNPROTECTED_HOLDING", {"buy_price": _h["buy_price"], "qty": _h["qty"], "ltp": _ltp, "tech": hist_data.get(_sym)}))
                        else:
                            st.session_state[_ai_k] = "AI analysis pending. Click 'Run AI Analysis' to generate."
                for _s in single_sells:
                    _sym = _s["symbol"]; _ai_k = f"ai_single_review_{_sym}_{_s['order_id']}"
                    if _ai_k not in st.session_state:
                        if st.session_state.get("force_run_ai"):
                            _ltp = ltps.get(_sym) or _s["price"] or 0
                            _dist = (_ltp - _s["trigger"]) / _ltp * 100 if _ltp else 0.0
                            _label = "Stop Loss" if _s["trigger"] < _ltp else "Target Limit"
                            _ai_tasks.append((_ai_k, _sym, "SINGLE_EXIT", {"trigger": _s["trigger"], "ltp": _ltp, "dist": _dist, "label": _label, "tech": hist_data.get(_sym)}))
                        else:
                            st.session_state[_ai_k] = "AI analysis pending. Click 'Run AI Analysis' to generate."

                if _ai_tasks:
                    with st.spinner(f"⚡ Loading AI analysis for {len(_ai_tasks)} positions..."):
                        def _run_ai(task):
                            key, sym, otype, kw = task
                            try: return key, get_stock_context_and_ai_review(sym, otype, **kw)
                            except Exception: return key, "AI review unavailable."
                        from concurrent.futures import ThreadPoolExecutor
                        # Increased concurrency for paid API tiers
                        with ThreadPoolExecutor(max_workers=15) as executor:
                            for key, res in executor.map(_run_ai, _ai_tasks):
                                st.session_state[key] = res
                        
                        # Save back to cache
                        _new_cache = {}
                        for k, v in st.session_state.items():
                            if any(p in k for p in ["ai_exit_review_", "ai_single_review_", "ai_entry_review_", "ai_unprotected_review_", "cached_hist_data_v3"]):
                                _new_cache[k] = v
                        try:
                            with open(AI_CACHE_FILE, "w") as f:
                                json.dump(_new_cache, f)
                        except: pass
                        st.session_state.force_run_ai = False

                # =====================================================================
                # NEW ENHANCEMENTS: Actionable Alerts, Heatmap, What-If Tester, Risk Hist
                # =====================================================================
                st.markdown("<br><hr style='border-color:#30363d; margin: 10px 0;'>", unsafe_allow_html=True)
                
                portfolio_data = []
                total_portfolio_value = 0
                total_open_risk = 0
                alerts = []

                if "holdings_map" in locals() and holdings_map:
                    for sym, h in holdings_map.items():
                        qty = h.get("qty", 0)
                        bp = h.get("buy_price", 0)
                        ltp = ltps.get(sym) or h.get("ltp") or bp
                        pos_val = qty * ltp
                        total_portfolio_value += pos_val
                        
                        _tech = hist_data.get(sym, {})
                        
                        # Find closest SL
                        sl = None
                        if sym in sell_gtts_by_symbol:
                            sl_vals = [o["sl_trigger"] for o in sell_gtts_by_symbol[sym] if o.get("sl_trigger")]
                            if sl_vals:
                                sl = max(sl_vals)
                        elif sym in [s["symbol"] for s in single_sells]:
                            sl_vals = [o["trigger"] for o in single_sells if o["symbol"] == sym and o["trigger"] < ltp]
                            if sl_vals:
                                sl = max(sl_vals)
                                
                        dist_to_sl = ((ltp - sl) / ltp * 100) if sl and ltp else None
                        open_risk_rs = qty * (ltp - sl) if sl else qty * ltp
                        total_open_risk += open_risk_rs if open_risk_rs > 0 else 0
                        
                        portfolio_data.append({
                            "Symbol": sym,
                            "Sector": h.get("sector", ""),
                            "Value": pos_val,
                            "Risk %": dist_to_sl if dist_to_sl is not None else -100,
                            "LTP": ltp,
                            "SL": sl if sl else 0
                        })
                        
                        # Alerts
                        if sl is None:
                            alerts.append({"type": "NO_SL", "sym": sym, "msg": "Missing Stop Loss"})
                        if _tech.get("vol_climax"):
                            alerts.append({"type": "VOL", "sym": sym, "msg": "Volume Climax"})
                        days_to_er = _tech.get("days_to_earnings")
                        if days_to_er is not None and days_to_er <= 3:
                            alerts.append({"type": "EARNINGS", "sym": sym, "msg": f"Earnings in {days_to_er}d"})

                # B5: sector over-concentration + shadow-pair correlation alerts —
                # reuses ai_risk_manager (existing modules), refreshed at most every 15 min.
                try:
                    import time as _t5
                    _sc_cache = st.session_state.get("rs_sector_corr")
                    if not _sc_cache or (_t5.time() - _sc_cache.get("ts", 0)) > 900:
                        _sc_alerts = []
                        try:
                            from ai_risk_manager import analyze_sector_concentration as _asc
                            _scres = _asc(df_holdings) or {}
                            for _a in _scres.get("alerts", []):
                                _sc_alerts.append({"type": "SECTOR", "sym": str(_a.get("Sector", "?")),
                                                   "msg": f"Sector {_a.get('Exposure', '?')} of book (>25%)"})
                        except Exception:
                            pass
                        try:
                            from ai_risk_manager import get_portfolio_correlation_matrix as _gpc
                            _corr_df5, _shadow5, _div5 = _gpc(list(holdings_map.keys()))
                            for _pair in (_shadow5 or [])[:6]:
                                if isinstance(_pair, dict):
                                    _sc_alerts.append({"type": "CORR", "sym": str(_pair.get("Pair", "?")),
                                                       "msg": f"Shadow pair r={_pair.get('Correlation', '?')} "
                                                              f"({_pair.get('Risk', '')}) — effectively one position"})
                                else:
                                    _sc_alerts.append({"type": "CORR", "sym": "PAIR", "msg": str(_pair)[:90]})
                        except Exception:
                            pass
                        _sc_cache = {"ts": _t5.time(), "alerts": _sc_alerts}
                        st.session_state["rs_sector_corr"] = _sc_cache
                    alerts.extend(_sc_cache.get("alerts", []))
                except Exception:
                    pass

                # 1. Alerts
                if alerts:
                    st.markdown('<div class="section-sub-lbl" style="color:#ff4b4b;margin-bottom:10px;">🚨 Requires Immediate Action</div>', unsafe_allow_html=True)
                    alert_cols = st.columns(3)
                    for i, al in enumerate(alerts):
                        with alert_cols[i % 3]:
                            bg = "#ff4b4b" if al["type"] == "NO_SL" else ("#e3b341" if al["type"] == "EARNINGS" else "#bf40bf")
                            txt_c = "#fff" if al["type"] != "EARNINGS" else "#000"
                            st.markdown(f'<div style="background:{bg};color:{txt_c};padding:8px 12px;border-radius:6px;margin-bottom:10px;font-size:0.85rem;font-weight:bold;">{al["sym"]}: {al["msg"]}</div>', unsafe_allow_html=True)

                if portfolio_data:
                    # 3. What-If Tester
                    st.markdown('<div class="section-sub-lbl">🔮 What-If Scenario Tester</div>', unsafe_allow_html=True)
                    sim_drop = st.slider("Simulated NIFTY Drop (%)", min_value=0.0, max_value=15.0, value=2.0, step=0.5, format="-%f%%")
                        
                    sim_losses = 0
                    hits = 0
                    if sim_drop > 0:
                        for row in portfolio_data:
                            sim_ltp = row["LTP"] * (1 - (sim_drop/100))
                            if row["SL"] > 0 and sim_ltp <= row["SL"]:
                                loss = row["Value"] - (row["Value"] * (row["SL"] / row["LTP"]))
                                sim_losses += loss
                                hits += 1
                            elif row["SL"] == 0:
                                loss = row["Value"] * (sim_drop/100)
                                sim_losses += loss
                    
                    dd_pct = (sim_losses / total_portfolio_value * 100) if total_portfolio_value > 0 else 0
                    st.markdown(f'''
                    <div style="background:#0e2035;border:1px solid #30363d;padding:12px;border-radius:6px;margin-bottom:20px;">
                        <div style="font-size:0.85rem;color:#8b949e;">Est. Portfolio Drawdown</div>
                        <div style="font-size:1.6rem;font-weight:bold;color:#ff4b4b;">-{dd_pct:.2f}%</div>
                        <div style="font-size:0.8rem;color:#c9d1d9;margin-top:8px;">Loss: ₹{sim_losses:,.0f} | SLs Hit: {hits}</div>
                    </div>
                    ''', unsafe_allow_html=True)
                    
                    # 4. Historical Risk
                    st.markdown('<div class="section-sub-lbl">📈 Historical Risk (30 Days)</div>', unsafe_allow_html=True)
                    import os
                    import json
                    from datetime import date
                    import plotly.graph_objects as go
                    
                    RISK_FILE = "risk_history.json"
                    today_str = date.today().isoformat()
                    
                    risk_history = {}
                    if os.path.exists(RISK_FILE):
                        try:
                            with open(RISK_FILE, "r") as f:
                                risk_history = json.load(f)
                        except: pass
                        
                    risk_history[today_str] = {
                        "portfolio_value": total_portfolio_value,
                        "open_risk": total_open_risk
                    }
                    
                    _rs_atomic_json_write(RISK_FILE, risk_history)  # A8: atomic
                    
                    dates = sorted(list(risk_history.keys()))[-30:]
                    risks = [risk_history[d]["open_risk"] for d in dates]
                    
                    if len(dates) > 0:
                        fig2 = go.Figure(go.Scatter(
                            x=dates, y=risks, mode='lines+markers+text',
                            text=[f"₹{r:,.0f}" for r in risks], textposition="top center", textfont=dict(color="#58a6ff", size=10),
                            line=dict(color='#58a6ff', width=3), marker=dict(size=6, color='#58a6ff')
                        ))
                        fig2.update_layout(
                            margin=dict(t=20, l=5, r=5, b=5), height=120,
                            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                            xaxis=dict(type='category', showgrid=False, visible=True, tickfont=dict(size=9, color="#8b949e")),
                            yaxis=dict(showgrid=False, visible=False)
                        )
                        st.plotly_chart(fig2, use_container_width=True)

                st.markdown("<br>", unsafe_allow_html=True)
                # =====================================================================

                if _capital_protection_mode and _cap_prot_msg:
                    st.error(_cap_prot_msg)

                # --- TABS ---
                entry_tab0, entry_tab1, entry_tab2, entry_tab3, entry_tab4 = st.tabs([
                    "✅ Morning Approval Dashboard",
                    "🎯 Active Exits (OCO)",
                    "🛒 Pullback Entries (GTT)",
                    "📊 Risk Profile & Analytics",
                    "⚙️ Settings & Overrides"
                ])
                
                with entry_tab0:
                    st.markdown('<div class="section-sub-lbl">✅ Review & Push (Morning Gate)</div>', unsafe_allow_html=True)
                    st.markdown('<div style="font-size:0.85rem; color:#8b949e; margin-bottom:12px;">Approve automatically generated Risk Management actions before pushing to Dhan.</div>', unsafe_allow_html=True)
                    
                    proposed_actions = []
                    for sym, orders in sell_gtts_by_symbol.items():
                        _tech = hist_data.get(sym, {})
                        _ltp = ltps.get(sym) or 0
                        _c5 = _tech.get("close_5d_ago")
                        
                        cond_trim = False
                        cond_add = False
                        if _c5 and _c5 > 0 and _ltp:
                            _dist200 = _tech.get("dist_from_200", 0)
                            _days_er = _tech.get("days_to_earnings")
                            _sma200slp = _tech.get("sma200_slope", 0)
                            _above200 = _tech.get("above200", False)
                            _ema20 = _tech.get("ema20")
                            _is_breakout = _tech.get("vol_breakout", False)
                            
                            if (_days_er is not None and _days_er <= 3):
                                cond_trim = True
                            elif not _is_breakout and (_ltp > _c5 * 1.15 or _dist200 > 40.0):
                                cond_trim = True
                            if _above200 and _sma200slp > 0 and _ltp <= _c5 * 1.10 and _ema20 and _ltp > _ema20:
                                cond_add = True

                        tsl_target = _tech.get("chandelier_exit")
                        
                        # Nearest active stop
                        sl_vals = [o["sl_trigger"] for o in orders if o["sl_trigger"] is not None]
                        curr_sl = max(sl_vals) if sl_vals else None
                        
                        # 1. Update SL Action
                        has_manual_sl = (sym in journal_overrides and journal_overrides[sym].get("manual_sl_override"))
                        if tsl_target and curr_sl and tsl_target > curr_sl and not has_manual_sl:
                            proposed_actions.append({
                                "Symbol": sym,
                                "Action": "Tighten SL",
                                "Trigger Price": round(tsl_target, 2),
                                "Qty %": 100,
                                "Reason": "TSL Trailing"
                            })
                            
                        # 2. Earnings/Extension Trim
                        if cond_trim:
                            proposed_actions.append({
                                "Symbol": sym,
                                "Action": "Trim Position",
                                "Trigger Price": round(_ltp, 2),
                                "Qty %": 20,
                                "Reason": "Earnings Risk" if (_days_er is not None and _days_er <= 3) else "Over-extension"
                            })
                            
                        # 3. Pyramiding (Risk-Free)
                        pyramid_state = journal_overrides.get(sym, {}).get("pyramid_status", "")
                        if cond_add and pyramid_state != "Maxed":
                            proposed_actions.append({
                                "Symbol": sym,
                                "Action": "Pyramid (Add)",
                                "Trigger Price": round(_ema20, 2) if _ema20 else round(_ltp, 2),
                                "Qty %": 50,
                                "Reason": "Pullback & Trend OK"
                            })
                            
                    if proposed_actions:
                        df_props = pd.DataFrame(proposed_actions)
                        df_props.insert(0, "Approve", True)
                        edited_df = st.data_editor(
                            df_props,
                            column_config={
                                "Approve": st.column_config.CheckboxColumn("Approve", default=True),
                                "Symbol": st.column_config.TextColumn("Symbol", disabled=True),
                                "Action": st.column_config.TextColumn("Action", disabled=True),
                                "Reason": st.column_config.TextColumn("Reason", disabled=True),
                                "Trigger Price": st.column_config.NumberColumn("Trigger Price (₹)", format="%.2f", step=0.05),
                                "Qty %": st.column_config.NumberColumn("Qty (%)", min_value=1, max_value=100, step=1)
                            },
                            hide_index=True,
                            use_container_width=True
                        )
                        # B4 (2026-07-04, Jay: review -> modify -> execute): the old button was
                        # a MOCK ("Orders pushed successfully!") — approvals went NOWHERE.
                        # Now executes TIGHTEN-SL rows for real via dhan.modify_forever, gated
                        # by an explicit arm switch. Trim/Pyramid stay propose-only this pass
                        # (position-size changes have a bigger blast radius).
                        _rs_arm = st.checkbox("⚠️ I confirm LIVE modification of GTT stop orders on Dhan",
                                              key="rs_arm_execute")
                        if st.button("🚀 Execute Approved SL Updates on Dhan", type="primary",
                                     disabled=not _rs_arm):
                            _exec_results = []
                            for _, _pr in edited_df.iterrows():
                                if not _pr.get("Approve") or _pr.get("Action") != "Tighten SL":
                                    continue
                                _psym = str(_pr["Symbol"]); _new_sl = float(_pr["Trigger Price"])
                                try:
                                    _ocos = [o for o in sell_gtts_by_symbol.get(_psym, [])
                                             if o.get("sl_trigger") is not None]
                                    if not _ocos:
                                        _exec_results.append((_psym, False, "no OCO with SL leg found"))
                                        continue
                                    _oco0 = _ocos[0]
                                    _old_sl = _oco0["sl_trigger"]
                                    _q = int(_oco0.get("sl_qty") or _oco0.get("qty") or 0)
                                    _resp = dhan.modify_forever(
                                        order_id=str(_oco0["order_id"]),
                                        order_flag="OCO",
                                        order_type=dhan.LIMIT,
                                        leg_name="STOP_LOSS_LEG",
                                        quantity=_q,
                                        price=round(_new_sl * 0.995, 2),   # limit buffer, same convention as gtt_auto_shield
                                        trigger_price=round(_new_sl, 2),
                                        disclosed_quantity=0,
                                        validity="DAY")
                                    _ok = isinstance(_resp, dict) and _resp.get("status") == "success"
                                    _exec_results.append((_psym, _ok, str(_resp.get("remarks") or _resp.get("data") or _resp)[:160]))
                                    if _ok:
                                        # persist to journal + audit trail
                                        try:
                                            import sqlite3 as _sq4
                                            import dhan_journal_v7 as _djm4
                                            _cn4 = _sq4.connect(_djm4.DB_FILE)
                                            _cn4.execute("UPDATE journal SET manual_sl_override=? "
                                                         "WHERE symbol=? AND status='OPEN'", (_new_sl, _psym))
                                            _cn4.commit(); _cn4.close()
                                        except Exception:
                                            pass
                                        try:
                                            os.makedirs("logs", exist_ok=True)
                                            with open(os.path.join("logs", "risk_shield_actions.log"), "a", encoding="utf-8") as _alf:
                                                _alf.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} "
                                                           f"TIGHTEN_SL {_psym} {_old_sl} -> {_new_sl} "
                                                           f"order={_oco0['order_id']} resp={_resp}\n")
                                        except Exception:
                                            pass
                                except Exception as _pex:
                                    _exec_results.append((_psym, False, f"EXCEPTION: {_pex}"))
                            for _psym, _ok, _msg in _exec_results:
                                (st.success if _ok else st.error)(f"{'✅' if _ok else '❌'} {_psym}: {_msg}")
                            if not _exec_results:
                                st.info("No approved 'Tighten SL' rows to execute. "
                                        "(Trim / Pyramid actions are propose-only — execute those manually.)")
                            else:
                                st.session_state.pop("cached_hist_data_v3", None)
                        st.caption("Only 'Tighten SL' rows execute. Trim / Pyramid remain manual. "
                                   "Every execution is appended to logs/risk_shield_actions.log.")
                    else:
                        st.info("No actionable updates for today. Portfolio is optimized.")

                # ── Tab 1: Active Exits (OCO) ──
                with entry_tab1:
                    st.markdown('<div class="section-sub-lbl">🎯 Paired OCO Exits</div>', unsafe_allow_html=True)
                    if not sell_gtts_by_symbol:
                        st.info("No active OCO paired exits found.")
                    else:
                        oco_symbols = sorted(list(sell_gtts_by_symbol.keys()))
                        for idx in range(0, len(oco_symbols), 3):
                            row_items = oco_symbols[idx:idx+3]
                            cols = st.columns(3)
                            for col, sym in zip(cols, row_items):
                                with col:
                                    orders = sell_gtts_by_symbol[sym]
                                    ltp = ltps.get(sym) or 0
                                    holding = holdings_map.get(sym)
                                    buy_price = holding["buy_price"] if holding else 0

                                    # Compute aggregates
                                    total_qty = sum(o.get("sl_qty") or o.get("qty") or 0 for o in orders)
                                    risk_exposure = sum((o.get("sl_qty") or o.get("qty") or 0) * (ltp - o["sl_trigger"]) for o in orders if ltp and o["sl_trigger"] is not None)

                                    # R-Multiple
                                    if holding and buy_price:
                                        total_risk_at_entry = sum((o.get("sl_qty") or o.get("qty") or 0) * (buy_price - o["sl_trigger"]) for o in orders if o["sl_trigger"] is not None)
                                        r_multiple = (ltp - buy_price) * total_qty / total_risk_at_entry if total_risk_at_entry > 0 else 0.0
                                        r_multiple_str = f"{r_multiple:+.2f}R"
                                    else:
                                        r_multiple = 0.0; r_multiple_str = "N/A"
                                    r_color = "#00f260" if r_multiple > 0 else "#ff4b4b" if r_multiple < 0 else "#8b949e"

                                    # SL/Target distances
                                    sl_vals = [o["sl_trigger"] for o in orders if o["sl_trigger"] is not None]
                                    tgt_vals = [o["target_trigger"] for o in orders if o["target_trigger"] is not None]
                                    # Nearest stop to LTP = the HIGHEST SL (all stops sit below price),
                                    # i.e. the one most likely to fire — that drives the danger warning.
                                    near_sl = max(sl_vals) if sl_vals else None
                                    min_sl_dist = ((ltp - near_sl) / ltp * 100) if ltp and near_sl else None

                                    # Single-line layout: Combined Entry and LTP percent context
                                    sl_parts = []; tgt_parts = []
                                    for o_idx, o in enumerate(orders):
                                        sl = o["sl_trigger"]; tgt = o["target_trigger"]
                                        if sl is not None:
                                            sl_str = f"SL <span style='color:#ff4b4b'>₹{sl:,.0f}</span>"
                                            if buy_price and ltp:
                                                sl_d_e = (sl - buy_price) / buy_price * 100
                                                sl_d_l = (sl - ltp) / ltp * 100
                                                sl_str += f" (<span style='color:#8b949e'>{sl_d_e:+.1f}%</span> / <span style='color:#58a6ff'>{sl_d_l:+.1f}%</span>)"
                                            sl_parts.append(sl_str)
                                        if tgt is not None:
                                            label = f"T{o_idx+1}"
                                            tgt_str = f"<span style='color:#00f260'>{label} ₹{tgt:,.0f}</span>"
                                            if buy_price and ltp:
                                                tgt_d_e = (tgt - buy_price) / buy_price * 100
                                                tgt_d_l = (tgt - ltp) / ltp * 100
                                                tgt_str += f" (<span style='color:#8b949e'>{tgt_d_e:+.1f}%</span> / <span style='color:#58a6ff'>{tgt_d_l:+.1f}%</span>)"
                                                if sl is not None and (buy_price - sl) > 0:
                                                    r_val = (tgt - buy_price) / (buy_price - sl)
                                                    tgt_str += f" <span style='color:#e3b341;font-weight:bold;'>[{r_val:.1f}R]</span>"
                                            tgt_parts.append(tgt_str)

                                    header_entry = f"<b style='color:#8b949e;'>Entry ₹{buy_price:,.2f}</b>" if buy_price else "<b style='color:#8b949e;'>Entry: N/A</b>"
                                    header_ltp = f"<b style='color:#58a6ff;'>LTP ₹{ltp:,.2f}</b>" if ltp else "<b style='color:#58a6ff;'>LTP: N/A</b>"
                                    
                                    # Calculate ATR + is_swing first for Time Stop logic
                                    _tech = hist_data.get(sym)
                                    atr_val = 0
                                    is_swing = False
                                    
                                    if _tech and _tech.get("atr_pct"):
                                        val = _tech.get("atr_pct")
                                        if isinstance(val, (int, float)) and val == val and val > 0:
                                            atr_val = (ltp * val) / 100
                                            is_swing = _tech.get('atr_pct', 0) > 4 or _tech.get('dist_from_200', 0) > 30 or _tech.get('ws_score', 0) < 60
                                        
                                    if (not atr_val or atr_val != atr_val) and ltp:
                                        raw_atr = get_atr(sym)
                                        if raw_atr and raw_atr == raw_atr: atr_val = raw_atr
                                        ai_key = f"ai_exit_review_{sym}"
                                        if ai_key in st.session_state and "[Swing]" in st.session_state[ai_key]:
                                            is_swing = True
                                            
                                    if (not atr_val or atr_val != atr_val) and sl_vals and ltp:
                                        closest_sl = max(sl_vals)
                                        dist = ltp - closest_sl
                                        if dist > 0:
                                            if (dist / ltp) < 0.08:
                                                atr_val = dist / 1.5
                                                is_swing = True
                                            else:
                                                atr_val = dist / 3.0
                                                is_swing = False

                                    # Compute Days Held & Time Stop Hit
                                    days_held = None
                                    if holding and holding.get("entry_date"):
                                        from datetime import date
                                        try:
                                            dt_parts = holding["entry_date"].split('-')
                                            entry_d = date(int(dt_parts[0]), int(dt_parts[1]), int(dt_parts[2]))
                                            days_held = (date.today() - entry_d).days
                                        except: pass

                                    time_stop_hit = False
                                    if days_held is not None and holding and buy_price and total_risk_at_entry > 0 and total_qty > 0:
                                        limit_days = 10 if is_swing else 42
                                        if days_held >= limit_days and r_multiple < 0.5:
                                            time_stop_hit = True

                                    flags_html = ""
                                    cond_trim = False
                                    cond_add = False
                                    
                                    if _tech:
                                        _c5 = _tech.get("close_5d_ago")
                                        if _c5 and _c5 > 0 and ltp:
                                            _dist200 = _tech.get("dist_from_200", 0)
                                            _days_er = _tech.get("days_to_earnings")
                                            _sma200slp = _tech.get("sma200_slope", 0)
                                            _above200 = _tech.get("above200", False)
                                            _ema20 = _tech.get("ema20")
                                            
                                            _is_breakout = _tech.get("vol_breakout", False)
                                            if (_days_er is not None and _days_er <= 3):
                                                cond_trim = True
                                            elif not _is_breakout and (ltp > _c5 * 1.15 or _dist200 > 40.0):
                                                cond_trim = True
                                                
                                            if _above200 and _sma200slp > 0 and ltp <= _c5 * 1.10 and _ema20 and ltp > _ema20:
                                                cond_add = True

                                        _flags = []
                                        if cond_trim:
                                            _flags.append("<span style='background:#8957e5;color:#fff;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;'>✂️ TRIM</span>")
                                        elif cond_add:
                                            _flags.append("<span style='background:#238636;color:#fff;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;'>📈 ADD</span>")
                                        
                                        if time_stop_hit:
                                            _flags.append(f"<span style='background:#ff4b4b;color:#fff;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;'>⏰ TIME STOP HIT</span>")

                                        if _tech.get("vol_breakout"):
                                            _flags.append("<span style='background:#00f260;color:#000;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;font-weight:bold;'>🚀 Breakout Vol</span>")
                                        elif _tech.get("vol_climax"):
                                            _flags.append("<span style='background:#ff4b4b;color:#fff;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;'>🚨 Vol Climax</span>")
                                        if _tech.get("days_to_earnings") is not None and _tech.get("days_to_earnings") <= 5:
                                            _flags.append(f"<span style='background:#e3b341;color:#000;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;'>⚠️ ER in {_tech.get('days_to_earnings')}d</span>")
                                        if _tech.get("chandelier_exit"):
                                            # B1: show which path chose the trail multiplier
                                            _ce_lbl = f"{_tech.get('ce_mult'):.1f}×·{_tech.get('ce_mult_src')}" if _tech.get("ce_mult") else "22D"
                                            _flags.append(f"<span style='background:#2d333b;color:#c9d1d9;padding:2px 6px;border-radius:4px;font-size:0.7rem;border:1px solid #444c56;margin-right:6px;'>TSL({_ce_lbl}): ₹{_tech.get('chandelier_exit'):.0f}</span>")
                                        if _tech.get("invalid_ce_override"):
                                            _flags.append(f"<span style='background:#5a1e1e;color:#ffb3b3;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;'>⚠ invalid CE override ignored</span>")
                                        if _flags:
                                            flags_html = f"<div style='margin-bottom:6px;'>{''.join(_flags)}</div>"
                                            
                                    combined_line = f"{flags_html}<div style='margin-bottom:6px;'>{header_entry} / {header_ltp}</div><div>{', '.join(sl_parts) if sl_parts else '⚠️ No SL'} | {', '.join(tgt_parts) if tgt_parts else 'N/A'}</div>"

                                    # Qty string
                                    qty_parts = []
                                    for o_idx, o in enumerate(orders):
                                        sl_q = o.get("sl_qty") or o.get("qty") or 0
                                        tgt_q = o.get("target_qty") or o.get("qty") or 0
                                        qty_parts.append(f"SL:{int(sl_q)} Tgt:{int(tgt_q)}")
                                    qty_str = " · ".join(qty_parts)

                                    # Progress bar with ATR SL
                                    progress_bar_html = ""
                                    atr_sl = None
                                    rec_t1 = None
                                    rec_t2 = None
                                    rec_line = ""

                                    if ltp and atr_val and atr_val == atr_val and atr_val > 0:
                                        sl_mult = 1.5 if is_swing else 3.0
                                        t1_mult = 3.0 if is_swing else 5.0
                                        t2_mult = 5.0 if is_swing else 10.0
                                        atr_sl = ltp - (atr_val * sl_mult)
                                        rec_t1 = (buy_price if buy_price else ltp) + (atr_val * t1_mult)
                                        rec_t2 = (buy_price if buy_price else ltp) + (atr_val * t2_mult)
                                        
                                        if len(orders) == 1 or len(tgt_vals) <= 1 or (rec_t1 and ltp >= rec_t1):
                                            rec_t1 = None
                                            
                                        t1_str = f' | Rec T1: <span style="color:#ffb000">₹{rec_t1:,.0f}</span>' if rec_t1 else ''
                                        t2_str = f' | Rec T2: <span style="color:#ffb000">₹{rec_t2:,.0f}</span>' if rec_t2 else ''
                                        rec_line = f'<div style="font-size:0.75rem;margin-top:8px;color:#8b949e;">Rec SL: <span style="color:#bf40bf">₹{atr_sl:,.0f}</span>{t1_str}{t2_str}</div>'
                                            
                                    if ltp:
                                        ema20 = _tech.get("ema20") if _tech else None
                                        
                                        time_stop_price = None
                                        if holding and buy_price:
                                            if total_risk_at_entry > 0 and total_qty > 0:
                                                if r_multiple < 0.5:
                                                    time_stop_price = buy_price + (0.5 * total_risk_at_entry / total_qty)
                                        
                                        all_lows = []
                                        if sl_vals: all_lows.extend(sl_vals)
                                        if buy_price: all_lows.append(buy_price)
                                        if atr_sl: all_lows.append(atr_sl)
                                        if ema20: all_lows.append(ema20)
                                        chandelier = _tech.get("chandelier_exit") if _tech else None
                                        if chandelier: all_lows.append(chandelier)
                                        if time_stop_price: all_lows.append(time_stop_price)
                                        if not all_lows: all_lows.append(ltp * 0.95)
                                        bar_min = min(all_lows) * 0.98
                                        
                                        all_highs = [ltp]
                                        if tgt_vals: all_highs.extend(tgt_vals)
                                        if rec_t2: all_highs.append(rec_t2)
                                        if ema20: all_highs.append(ema20)
                                        if chandelier: all_highs.append(chandelier)
                                        if time_stop_price: all_highs.append(time_stop_price)
                                        bar_max = max(all_highs) * 1.02
                                        
                                        bar_range = bar_max - bar_min
                                        if bar_range > 0:
                                            markers_html = ""
                                            if ema20:
                                                ema_pos = (ema20 - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{ema_pos:.1f}%;top:-6px;width:3px;height:20px;background:#f97316;border-radius:1px;transform:translateX(-50%);" title="EMA20 ₹{ema20:,.2f}"></div>'
                                            if chandelier:
                                                chan_pos = (chandelier - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{chan_pos:.1f}%;top:-6px;width:3px;height:20px;background:#d2a8ff;border-radius:1px;transform:translateX(-50%);" title="TSL(22D) ₹{chandelier:,.2f}"></div>'
                                            if time_stop_price:
                                                ts_pos = (time_stop_price - bar_min) / bar_range * 100
                                                if time_stop_hit:
                                                    markers_html += f'<div style="position:absolute;left:{ts_pos:.1f}%;top:-6px;width:4px;height:20px;background:#ff4b4b;border-radius:1px;transform:translateX(-50%);box-shadow:0 0 5px #ff4b4b;" title="Time Stop HIT! Held {days_held}d (0.5R = ₹{time_stop_price:,.2f})"></div>'
                                                else:
                                                    markers_html += f'<div style="position:absolute;left:{ts_pos:.1f}%;top:-6px;width:3px;height:20px;background:#eab308;border-radius:1px;transform:translateX(-50%);" title="Time Stop (0.5R) ₹{time_stop_price:,.2f}"></div>'
                                            if atr_sl:
                                                atr_pos = (atr_sl - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{atr_pos:.1f}%;top:-2px;width:12px;height:12px;background:#bf40bf;border-radius:50%;transform:translateX(-50%);" title="AI Rec SL ₹{atr_sl:,.0f}"></div>'
                                            for sv in sl_vals:
                                                pos = (sv - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{pos:.1f}%;top:-3px;width:14px;height:14px;background:#ff4b4b;border-radius:50%;transform:translateX(-50%);" title="SL ₹{sv:,.0f}"></div>'
                                            if buy_price:
                                                entry_pos = (buy_price - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{entry_pos:.1f}%;top:-2px;width:12px;height:12px;background:#8b949e;border-radius:50%;transform:translateX(-50%);" title="Entry ₹{buy_price:,.0f}"></div>'
                                            ltp_pos = (ltp - bar_min) / bar_range * 100
                                            markers_html += f'<div style="position:absolute;left:{ltp_pos:.1f}%;top:-4px;width:16px;height:16px;background:#58a6ff;border:2px solid #0a0e14;border-radius:50%;transform:translateX(-50%);" title="LTP ₹{ltp:,.0f}"></div>'
                                            
                                            for tv in tgt_vals:
                                                pos = (tv - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{pos:.1f}%;top:-3px;width:14px;height:14px;background:#00f260;border-radius:50%;transform:translateX(-50%);" title="Actual Tgt ₹{tv:,.0f}"></div>'
                                                
                                            if rec_t1:
                                                t1_pos = (rec_t1 - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{t1_pos:.1f}%;top:-2px;width:12px;height:12px;background:#ffb000;border-radius:50%;transform:translateX(-50%);" title="Rec T1 ₹{rec_t1:,.0f}"></div>'
                                            if rec_t2:
                                                t2_pos = (rec_t2 - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{t2_pos:.1f}%;top:-2px;width:12px;height:12px;background:#ffb000;border-radius:50%;transform:translateX(-50%);" title="Rec T2 ₹{rec_t2:,.0f}"></div>'
                                                
                                            progress_bar_html = f'<div style="width:100%;background:#1e3a5f;height:8px;border-radius:4px;position:relative;margin:18px 0 14px 0;">{markers_html}</div>'

                                    # Trail SL recommendation
                                    reco_parts = []
                                    for o_idx, o in enumerate(orders):
                                        tgt = o["target_trigger"]
                                        if tgt and ltp and ltp >= tgt:
                                            reco_parts.append(f"⚠️ LTP crossed T{o_idx+1} (₹{tgt:,.0f}) — consider trailing SL to entry ₹{buy_price:,.0f}")
                                    if min_sl_dist is not None and min_sl_dist <= 3.0:
                                        reco_parts.append(f"🔴 SL only {min_sl_dist:.1f}% away — high risk zone")
                                    elif min_sl_dist is not None and min_sl_dist <= 5.0:
                                        reco_parts.append(f"🟡 SL {min_sl_dist:.1f}% away — watch closely")
                                    reco_str = " · ".join(reco_parts) if reco_parts else "✅ Position in range"

                                    status_color = "#ff4b4b" if min_sl_dist is not None and min_sl_dist <= 3.0 else "#ffb000" if min_sl_dist is not None and min_sl_dist <= 5.0 else "#00f260"
                                    reco_color = "#ff4b4b" if min_sl_dist is not None and min_sl_dist <= 3.0 else "#ffb000" if min_sl_dist is not None and min_sl_dist <= 5.0 else "#00f260"

                                    ai_key = f"ai_exit_review_{sym}"
                                    trade_style_badge = ""
                                    ai_html = ""
                                    if ai_key in st.session_state:
                                        ai_text = st.session_state[ai_key]
                                        if "[Positional]" in ai_text:
                                            trade_style_badge = '<span style="background:#238636;color:#ffffff;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-left:8px;font-weight:bold;vertical-align:middle;">POSITIONAL</span>'
                                        elif "[Swing]" in ai_text:
                                            trade_style_badge = '<span style="background:#8957e5;color:#ffffff;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-left:8px;font-weight:bold;vertical-align:middle;">SWING</span>'
                                            
                                        display_text = ai_text.replace("[Positional]", "").replace("[Swing]", "").replace("[]", "").strip()
                                        ai_html = f'<div style="background:#0e2035;border-left:3px solid #e3b341;padding:10px;border-radius:4px;margin-top:12px;font-size:0.8rem;color:#e6edf3;line-height:1.4;">🤖 <b>AI:</b> {display_text}</div>'
                                        
                                    expand_btn = '<label class=\"expand-btn\" title=\"Toggle Fullscreen\" style=\"cursor:pointer;float:right;margin-top:-5px;\">⛶<input type=\"checkbox\" class=\"expand-toggle\" style=\"display:none;\"></label>'

                                    card_html = (
                                        f'<div class="metric-card" style="padding:16px;margin-bottom:12px;border-left:4px solid {status_color};text-align:left;">'
                                        f'{expand_btn}'
                                        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                                        f'<div><span style="font-size:1.2rem;font-weight:700;color:#58a6ff;vertical-align:middle;">{sym}</span>'
                                        f'{trade_style_badge}'
                                        f'<span style="font-size:0.8rem;color:#8b949e;margin-left:8px;vertical-align:middle;">{qty_str}</span></div>'
                                        f'<div style="text-align:right;padding-right:20px;"><div style="font-size:0.75rem;color:#8b949e;">'
                                        f'R-Mult: <span style="font-family:JetBrains Mono;color:{r_color};font-weight:bold;">{r_multiple_str}</span>'
                                        f' · Risk: <span style="font-family:JetBrains Mono;color:#ff4b4b;font-weight:bold;">₹{risk_exposure:,.2f}</span></div></div></div>'
                                        f'{progress_bar_html}'
                                        f'{rec_line}'
                                        f'<div style="font-size:0.8rem;color:#c9d1d9;margin-top:5px;line-height:1.6;">'
                                        f'<div>{combined_line}</div></div>'
                                        f'<div style="margin-top:8px;font-size:0.78rem;line-height:1.35;color:{reco_color};font-weight:600;">{reco_str}</div>'
                                        f'{ai_html}</div>'
                                    )
                                    st.markdown(card_html, unsafe_allow_html=True)

                    # Standalone Exits
                    if single_sells:
                        single_sells = sorted(single_sells, key=lambda x: x["symbol"])
                        st.markdown("---")
                        st.markdown('<div class="section-sub-lbl">🛑 Standalone Exits</div>', unsafe_allow_html=True)
                        for idx in range(0, len(single_sells), 3):
                            row = single_sells[idx:idx+3]
                            cols = st.columns(3)
                            for col, s in zip(cols, row):
                                with col:
                                    sym = s["symbol"]; trigger = s["trigger"]
                                    ltp = ltps.get(sym) or s["price"] or 0
                                    dist = (ltp - trigger) / ltp * 100 if ltp else 0.0
                                    label = "Stop Loss" if trigger < ltp else "Target"
                                    color = "#ff4b4b" if trigger < ltp else "#00f260"
                                    
                                    flags_html = ""
                                    # Compute Days Held
                                    days_held = None
                                    if h.get("entry_date"):
                                        from datetime import date
                                        try:
                                            dt_parts = h["entry_date"].split('-')
                                            entry_d = date(int(dt_parts[0]), int(dt_parts[1]), int(dt_parts[2]))
                                            days_held = (date.today() - entry_d).days
                                        except: pass

                                    # A2 SAFETY FIX (2026-07-04 audit): the old dummy denominator
                                    # (10% of cost) fired time-stops on fabricated math. R is now
                                    # anchored to the ATR-based initial risk this page itself
                                    # recommends (1.5x ATR swing / 3.0x positional). No ATR ->
                                    # no time-stop verdict (n/a), never a fake one.
                                    time_stop_hit = False
                                    r_multiple_up = None
                                    if days_held is not None and bp and ltp:
                                        _atr_pct_ts = (hist_data.get(sym) or {}).get("atr_pct") or 0
                                        if _atr_pct_ts > 0:
                                            _risk_ps = (ltp * _atr_pct_ts / 100.0) * (1.5 if is_swing else 3.0)
                                            if _risk_ps > 0:
                                                r_multiple_up = (ltp - bp) / _risk_ps
                                        limit_days = 10 if is_swing else 42
                                        if r_multiple_up is not None and days_held >= limit_days and r_multiple_up < 0.5:
                                            time_stop_hit = True

                                    flags_html = ""
                                    cond_trim = False
                                    cond_add = False
                                    _tech_flag = hist_data.get(sym)
                                    if _tech_flag:
                                        _c5 = _tech_flag.get("close_5d_ago")
                                        if _c5 and _c5 > 0 and ltp:
                                            _dist200 = _tech_flag.get("dist_from_200", 0)
                                            _days_er = _tech_flag.get("days_to_earnings")
                                            _sma200slp = _tech_flag.get("sma200_slope", 0)
                                            _above200 = _tech_flag.get("above200", False)
                                            _ema20 = _tech_flag.get("ema20")
                                            
                                            _is_breakout = _tech_flag.get("vol_breakout", False)
                                            if (_days_er is not None and _days_er <= 3):
                                                cond_trim = True
                                            elif not _is_breakout and (ltp > _c5 * 1.15 or _dist200 > 40.0):
                                                cond_trim = True
                                                
                                            if _above200 and _sma200slp > 0 and ltp <= _c5 * 1.10 and _ema20 and ltp > _ema20:
                                                cond_add = True

                                        _flags = []
                                        if cond_trim:
                                            _flags.append("<span style='background:#8957e5;color:#fff;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;'>✂️ TRIM</span>")
                                        elif cond_add:
                                            _flags.append("<span style='background:#238636;color:#fff;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;'>📈 ADD</span>")
                                        
                                        if time_stop_hit:
                                            _flags.append(f"<span style='background:#ff4b4b;color:#fff;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;'>⏰ TIME STOP HIT</span>")

                                        if _tech_flag.get("vol_breakout"): _flags.append("<span style='background:#00f260;color:#000;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;font-weight:bold;'>🚀 Breakout Vol</span>")
                                        elif _tech_flag.get("vol_climax"): _flags.append("<span style='background:#ff4b4b;color:#fff;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;'>🚨 Vol Climax</span>")
                                        if _tech_flag.get("days_to_earnings") is not None and _tech_flag.get("days_to_earnings") <= 5: _flags.append(f"<span style='background:#e3b341;color:#000;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;'>⚠️ ER in {_tech_flag.get('days_to_earnings')}d</span>")
                                        if _tech_flag.get("chandelier_exit"): _flags.append(f"<span style='background:#2d333b;color:#c9d1d9;padding:2px 6px;border-radius:4px;font-size:0.7rem;border:1px solid #444c56;margin-right:6px;'>TSL(22D): ₹{_tech_flag.get('chandelier_exit'):.0f}</span>")
                                        if _flags: flags_html = f"<div style='margin-bottom:6px;'>{''.join(_flags)}</div>"
                                        
                                    expand_btn = '<label class="expand-btn" title="Toggle Fullscreen" style="cursor:pointer;float:right;margin-top:-5px;">⛶<input type="checkbox" class="expand-toggle" style="display:none;"></label>'
                                    ai_key = f"ai_single_review_{sym}_{s['order_id']}"
                                    ai_html = ""
                                    if ai_key in st.session_state:
                                        ai_html = f'<div style="background:#0e2035;border-left:3px solid #e3b341;padding:8px;border-radius:4px;margin-top:10px;font-size:0.78rem;color:#e6edf3;">🤖 {st.session_state[ai_key]}</div>'
                                        
                                    st.markdown(f'<div class="metric-card" style="padding:14px;margin-bottom:10px;border-left:3px solid {color};text-align:left;">{expand_btn}<span style="font-size:1.1rem;font-weight:700;color:#58a6ff;">{sym}</span> <span style="font-size:0.8rem;color:#8b949e;">Qty: {s["qty"]}</span><br>{flags_html}<span style="font-size:0.8rem;color:#c9d1d9;">LTP ₹{ltp:,.2f} → {label}: ₹{trigger:,.2f} ({dist:+.1f}%)</span>{ai_html}</div>', unsafe_allow_html=True)

                    # Unprotected Holdings
                    if unprotected_holdings:
                        unprotected_holdings = sorted(unprotected_holdings, key=lambda x: x["symbol"])
                        st.markdown("---")
                        st.markdown('<div class="section-sub-lbl">⚠️ Unprotected Holdings (No Stop Loss)</div>', unsafe_allow_html=True)
                        for idx in range(0, len(unprotected_holdings), 3):
                            row = unprotected_holdings[idx:idx+3]
                            cols = st.columns(3)
                            for col, h in zip(cols, row):
                                with col:
                                    sym = h["symbol"]; bp = h["buy_price"]; qty = h["qty"]
                                    ltp = ltps.get(sym) or h["ltp"] or 0
                                    pnl_pct = ((ltp - bp) / bp * 100) if bp else 0.0
                                    pnl_color = "#00f260" if pnl_pct >= 0 else "#ff4b4b"
                                    
                                    _tech = hist_data.get(sym)
                                    atr_val = 0
                                    is_swing = False
                                    
                                    if _tech:
                                        atr_val = (ltp * _tech["atr_pct"]) / 100
                                        is_swing = _tech['atr_pct'] > 4 or _tech['dist_from_200'] > 30 or _tech['ws_score'] < 60
                                    else:
                                        raw_atr = get_atr(sym)
                                        if raw_atr: atr_val = raw_atr
                                        ai_key = f"ai_unprotected_review_{sym}"
                                        if ai_key in st.session_state and "[Swing]" in st.session_state[ai_key]:
                                            is_swing = True
                                            
                                    pb_html = ""
                                    badge_html = ""
                                    rec_line = ""
                                    
                                    if atr_val > 0 and bp and ltp:
                                        trade_style = "SWING" if is_swing else "POSITIONAL"
                                        style_color = "#8957e5" if is_swing else "#238636"
                                        sl_mult = 1.5 if is_swing else 3.0
                                        t1_mult = 3.0 if is_swing else 5.0
                                        t2_mult = 5.0 if is_swing else 10.0
                                        
                                        rec_sl = ltp - (atr_val * sl_mult)
                                        rec_t1 = (bp if bp else ltp) + (atr_val * t1_mult)
                                        rec_t2 = (bp if bp else ltp) + (atr_val * t2_mult)
                                        
                                        if ltp >= rec_t1:
                                            rec_t1 = None
                                        
                                        ema20 = _tech.get("ema20") if _tech else None
                                        
                                        time_stop_price = None
                                        if bp and atr_val:
                                            time_stop_price = bp + (0.5 * atr_val * sl_mult)
                                        
                                        bar_min_vals = [rec_sl, bp, ltp] + ([ema20] if ema20 else [])
                                        bar_max_vals = [rec_t2, bp, ltp] + ([ema20] if ema20 else [])
                                        if time_stop_price:
                                            bar_min_vals.append(time_stop_price)
                                            bar_max_vals.append(time_stop_price)
                                            
                                        bar_min = min(bar_min_vals) * 0.98
                                        bar_max = max(bar_max_vals) * 1.02
                                        bar_range = bar_max - bar_min
                                        
                                        markers_html = ""
                                        chandelier = _tech.get("chandelier_exit") if _tech else None
                                        if chandelier:
                                            bar_min = min(bar_min, chandelier * 0.98)
                                            bar_max = max(bar_max, chandelier * 1.02)
                                            bar_range = bar_max - bar_min
                                            
                                        if bar_range > 0:
                                            if ema20:
                                                ema_pos = (ema20 - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{ema_pos:.1f}%;top:-6px;width:3px;height:20px;background:#f97316;border-radius:1px;transform:translateX(-50%);" title="EMA20 ₹{ema20:,.2f}"></div>'
                                            if chandelier:
                                                chan_pos = (chandelier - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{chan_pos:.1f}%;top:-6px;width:3px;height:20px;background:#d2a8ff;border-radius:1px;transform:translateX(-50%);" title="TSL(22D) ₹{chandelier:,.2f}"></div>'
                                            if time_stop_price:
                                                ts_pos = (time_stop_price - bar_min) / bar_range * 100
                                                if time_stop_hit:
                                                    markers_html += f'<div style="position:absolute;left:{ts_pos:.1f}%;top:-6px;width:4px;height:20px;background:#ff4b4b;border-radius:1px;transform:translateX(-50%);box-shadow:0 0 5px #ff4b4b;" title="Time Stop HIT! Held {days_held}d (0.5R = ₹{time_stop_price:,.2f})"></div>'
                                                else:
                                                    markers_html += f'<div style="position:absolute;left:{ts_pos:.1f}%;top:-6px;width:3px;height:20px;background:#eab308;border-radius:1px;transform:translateX(-50%);" title="Time Stop (0.5R) ₹{time_stop_price:,.2f}"></div>'
                                                    
                                            entry_pos = (bp - bar_min) / bar_range * 100
                                            markers_html += f'<div style="position:absolute;left:{entry_pos:.1f}%;top:-2px;width:12px;height:12px;background:#8b949e;border-radius:50%;transform:translateX(-50%);" title="Entry ₹{bp:,.0f}"></div>'
                                            
                                            sl_pos = (rec_sl - bar_min) / bar_range * 100
                                            markers_html += f'<div style="position:absolute;left:{sl_pos:.1f}%;top:-3px;width:14px;height:14px;background:#bf40bf;border-radius:50%;transform:translateX(-50%);" title="Rec SL ₹{rec_sl:,.0f}"></div>'
                                            
                                            ltp_pos = (ltp - bar_min) / bar_range * 100
                                            markers_html += f'<div style="position:absolute;left:{ltp_pos:.1f}%;top:-4px;width:16px;height:16px;background:#58a6ff;border:2px solid #0a0e14;border-radius:50%;transform:translateX(-50%);" title="LTP ₹{ltp:,.0f}"></div>'
                                            if rec_t1:
                                                t1_pos = (rec_t1 - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{t1_pos:.1f}%;top:-3px;width:14px;height:14px;background:#00f260;border-radius:50%;transform:translateX(-50%);" title="Rec T1 ₹{rec_t1:,.0f}"></div>'
                                            
                                            t2_pos = (rec_t2 - bar_min) / bar_range * 100
                                            markers_html += f'<div style="position:absolute;left:{t2_pos:.1f}%;top:-3px;width:14px;height:14px;background:#00f260;border-radius:50%;transform:translateX(-50%);" title="Rec T2 ₹{rec_t2:,.0f}"></div>'
                                            
                                        pb_html = f'<div style="width:100%;background:#1e3a5f;height:8px;border-radius:4px;position:relative;margin:18px 0 14px 0;">{markers_html}</div>'
                                        
                                        if _tech or trade_style: 
                                            badge_html = f'<span style="background:{style_color};color:#ffffff;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-left:8px;font-weight:bold;vertical-align:middle;">{trade_style}</span>'
                                        
                                        t1_str = f' | Rec T1: <span style="color:#00f260">₹{rec_t1:,.0f}</span>' if rec_t1 else ''
                                        rec_line = f'<div style="font-size:0.8rem;color:#c9d1d9;margin-top:5px;line-height:1.6;">Rec SL: <span style="color:#bf40bf">₹{rec_sl:,.0f}</span>{t1_str} | Rec T2: <span style="color:#00f260">₹{rec_t2:,.0f}</span></div>'
                                    elif bp and ltp:
                                        ema20 = _tech.get("ema20") if _tech else None
                                        
                                        bar_min_vals = [bp, ltp] + ([ema20] if ema20 else [])
                                        bar_max_vals = [bp, ltp] + ([ema20] if ema20 else [])
                                        bar_min = min(bar_min_vals) * 0.98
                                        bar_max = max(bar_max_vals) * 1.02
                                        bar_range = bar_max - bar_min
                                        
                                        markers_html = ""
                                        chandelier = _tech.get("chandelier_exit") if _tech else None
                                        if chandelier:
                                            bar_min = min(bar_min, chandelier * 0.98)
                                            bar_max = max(bar_max, chandelier * 1.02)
                                            bar_range = bar_max - bar_min
                                            
                                        if bar_range > 0:
                                            if ema20:
                                                ema_pos = (ema20 - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{ema_pos:.1f}%;top:-6px;width:3px;height:20px;background:#f97316;border-radius:1px;transform:translateX(-50%);" title="EMA20 ₹{ema20:,.2f}"></div>'
                                            if chandelier:
                                                chan_pos = (chandelier - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{chan_pos:.1f}%;top:-6px;width:3px;height:20px;background:#d2a8ff;border-radius:1px;transform:translateX(-50%);" title="TSL(22D) ₹{chandelier:,.2f}"></div>'
                                            entry_pos = (bp - bar_min) / bar_range * 100
                                            markers_html += f'<div style="position:absolute;left:{entry_pos:.1f}%;top:-2px;width:12px;height:12px;background:#8b949e;border-radius:50%;transform:translateX(-50%);" title="Entry ₹{bp:,.0f}"></div>'
                                            ltp_pos = (ltp - bar_min) / bar_range * 100
                                            markers_html += f'<div style="position:absolute;left:{ltp_pos:.1f}%;top:-4px;width:16px;height:16px;background:#58a6ff;border:2px solid #0a0e14;border-radius:50%;transform:translateX(-50%);" title="LTP ₹{ltp:,.0f}"></div>'
                                        pb_html = f'<div style="width:100%;background:#1e3a5f;height:8px;border-radius:4px;position:relative;margin:18px 0 14px 0;">{markers_html}</div>'
                                
                                    expand_btn = '<label class="expand-btn" title="Toggle Fullscreen" style="cursor:pointer;float:right;margin-top:-5px;">⛶<input type="checkbox" class="expand-toggle" style="display:none;"></label>'
                                    ai_key = f"ai_unprotected_review_{sym}"
                                    ai_html = ""
                                    if ai_key in st.session_state:
                                        ai_html = f'<div style="background:#0e2035;border-left:3px solid #ff4b4b;padding:8px;border-radius:4px;margin-top:10px;font-size:0.78rem;color:#e6edf3;">🤖 {st.session_state[ai_key]}</div>'
                                        
                                    flags_html = ""
                                    if _tech:
                                        _flags = []
                                        if _tech.get("vol_breakout"): _flags.append("<span style='background:#00f260;color:#000;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;font-weight:bold;'>🚀 Breakout Vol</span>")
                                        elif _tech.get("vol_climax"): _flags.append("<span style='background:#ff4b4b;color:#fff;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;'>🚨 Vol Climax</span>")
                                        if _tech.get("days_to_earnings") is not None and _tech.get("days_to_earnings") <= 5: _flags.append(f"<span style='background:#e3b341;color:#000;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-right:6px;'>⚠️ ER in {_tech.get('days_to_earnings')}d</span>")
                                        if _tech.get("chandelier_exit"): _flags.append(f"<span style='background:#2d333b;color:#c9d1d9;padding:2px 6px;border-radius:4px;font-size:0.7rem;border:1px solid #444c56;margin-right:6px;'>TSL(22D): ₹{_tech.get('chandelier_exit'):.0f}</span>")
                                        if _flags: flags_html = f"<div style='margin-bottom:6px;'>{''.join(_flags)}</div>"
                                        
                                    card_html = (
                                        f'<div class="metric-card" style="padding:14px;margin-bottom:10px;border-left:3px solid #ff4b4b;text-align:left;">'
                                        f'{expand_btn}'
                                        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                                        f'<div><span style="font-size:1.1rem;font-weight:700;color:#58a6ff;vertical-align:middle;">{sym}</span>{badge_html}'
                                        f' <span style="font-size:0.8rem;color:#ff4b4b;margin-left:8px;">⚠️ NO SL</span></div>'
                                        f'<div style="font-size:0.8rem;color:#8b949e;padding-right:20px;">Qty: {qty}</div></div>'
                                        f'{flags_html}'
                                        f'{pb_html}'
                                        f'<div style="font-size:0.8rem;color:#c9d1d9;line-height:1.6;">'
                                        f'Cost ₹{bp:,.2f} → LTP ₹{ltp:,.2f} <span style="color:{pnl_color};font-weight:bold;">({pnl_pct:+.1f}%)</span>'
                                        f'</div>'
                                        f'{rec_line}'
                                        f'{ai_html}</div>'
                                    )
                                    st.markdown(card_html, unsafe_allow_html=True)

                # ── Tab 2: Pullback Entries (GTT) ──
                with entry_tab2:
                    st.markdown('<div class="section-sub-lbl">🛒 Pending Pullback Buy Entries (GTT)</div>', unsafe_allow_html=True)
                    if not buy_gtts:
                        st.info("No pending pullback GTT buy orders found.")
                    else:
                        buy_gtts = sorted(buy_gtts, key=lambda x: x["symbol"])
                        for idx in range(0, len(buy_gtts), 3):
                            row = buy_gtts[idx:idx+3]
                            cols = st.columns(3)
                            for col, b in zip(cols, row):
                                with col:
                                    sym = b["symbol"]; trigger = b["trigger"]; price = b["price"]
                                    ltp = ltps.get(sym) or 0
                                    # Distance to the buy trigger, always expressed as |gap| from LTP.
                                    gap_pct = abs(ltp - trigger) / ltp * 100 if ltp else 0.0
                                    # Two entry styles: trigger ABOVE LTP = breakout buy-stop (waits for
                                    # price to confirm by rising into it — Jay's preferred entry); trigger
                                    # BELOW LTP = dip buy-limit (fills automatically on the touch, no
                                    # confirmation). Flag the latter so it isn't a blind zone-buy.
                                    if not ltp:
                                        kind_lbl = ""; status = "LTP: N/A"; dist_color = "#5a8a9f"; border = "#e3b341"
                                    elif trigger > ltp:
                                        kind_lbl = "Breakout buy-stop"
                                        dist_color = "#00f260" if gap_pct <= 2 else "#58a6ff"
                                        status = f"🟢 {gap_pct:.1f}% below trigger — waiting for breakout confirmation"
                                        border = "#00f260"
                                    elif gap_pct <= 0.5:
                                        kind_lbl = "Dip buy-limit"
                                        dist_color = "#ffb000"; border = "#ffb000"
                                        status = f"🟡 At trigger — fills on touch (no confirmation)"
                                    else:
                                        kind_lbl = "Dip buy-limit"
                                        dist_color = "#ffb000" if gap_pct <= 3 else "#8b949e"; border = "#e3b341"
                                        status = f"{'🟡' if gap_pct <= 3 else '⚪'} {gap_pct:.1f}% above trigger — waiting for pullback (resting limit, no confirmation)"
                                    pb_html = ""
                                    if ltp and trigger:
                                        _tech = hist_data.get(sym)
                                        ema20 = _tech.get("ema20") if _tech else None
                                        
                                        bar_min_vals = [ltp, trigger, price] + ([ema20] if ema20 else [])
                                        bar_max_vals = [ltp, trigger, price] + ([ema20] if ema20 else [])
                                        bar_min = min(bar_min_vals) * 0.99
                                        bar_max = max(bar_max_vals) * 1.01
                                        bar_range = bar_max - bar_min
                                        
                                        if bar_range > 0:
                                            markers_html = ""
                                            if ema20:
                                                ema_pos = (ema20 - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{ema_pos:.1f}%;top:-6px;width:3px;height:20px;background:#f97316;border-radius:1px;transform:translateX(-50%);" title="EMA20 ₹{ema20:,.2f}"></div>'
                                            trigger_pos = (trigger - bar_min) / bar_range * 100
                                            markers_html += f'<div style="position:absolute;left:{trigger_pos:.1f}%;top:-3px;width:14px;height:14px;background:#e3b341;border-radius:50%;transform:translateX(-50%);" title="Trigger ₹{trigger:,.2f}"></div>'
                                            
                                            if price != trigger:
                                                limit_pos = (price - bar_min) / bar_range * 100
                                                markers_html += f'<div style="position:absolute;left:{limit_pos:.1f}%;top:-2px;width:12px;height:12px;background:#8b949e;border-radius:50%;transform:translateX(-50%);" title="Limit ₹{price:,.2f}"></div>'
                                            
                                            ltp_pos = (ltp - bar_min) / bar_range * 100
                                            markers_html += f'<div style="position:absolute;left:{ltp_pos:.1f}%;top:-4px;width:16px;height:16px;background:#58a6ff;border:2px solid #0a0e14;border-radius:50%;transform:translateX(-50%);" title="LTP ₹{ltp:,.2f}"></div>'
                                            
                                            pb_html = f'<div style="width:100%;background:#1e3a5f;height:8px;border-radius:4px;position:relative;margin:18px 0 14px 0;">{markers_html}</div>'
                                
                                    kind_html = f' <span style="font-size:0.7rem;color:#8b949e;">· {kind_lbl}</span>' if kind_lbl else ""
                                    
                                    setup_warning_html = ""
                                    _tech_dict = hist_data.get(sym)
                                    if _tech_dict:
                                        if _tech_dict.get("ws_score", 100) < 50 or _tech_dict.get("sma200_slope", 0) < 0:
                                            setup_warning_html = '<div style="font-size:0.75rem;color:#ff4b4b;font-weight:bold;margin-top:4px;">🚨 INVALID SETUP WARNING (WS Score < 50 or SMA200 slope < 0)</div>'
                                            border = "#ff4b4b"
                                            
                                    entry_line = f"<b style='color:#e3b341;'>Trigger ₹{trigger:,.2f}</b> (Limit ₹{price:,.2f})"
                                    ltp_line = f"<b style='color:#58a6ff;'>LTP ₹{ltp:,.2f}</b> — <span style='color:{dist_color};font-weight:bold;'>{status}</span>" if ltp else "LTP: N/A"
                                
                                    ai_key = f"ai_entry_review_{sym}_{b['order_id']}"
                                    trade_style_badge = ""
                                    if ai_key in st.session_state:
                                        ai_text = st.session_state[ai_key]
                                        if "[Positional]" in ai_text:
                                            trade_style_badge = '<span style="background:#238636;color:#ffffff;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-left:8px;font-weight:bold;vertical-align:middle;">POSITIONAL</span>'
                                        elif "[Swing]" in ai_text:
                                            trade_style_badge = '<span style="background:#8957e5;color:#ffffff;padding:2px 6px;border-radius:4px;font-size:0.7rem;margin-left:8px;font-weight:bold;vertical-align:middle;">SWING</span>'

                                    card = (
                                        f'<div class="metric-card" style="padding:14px;margin-bottom:10px;border-left:3px solid {border};text-align:left;">'
                                        f'<span style="font-size:1.1rem;font-weight:700;color:#58a6ff;">{sym}</span>{trade_style_badge}'
                                        f' <span style="font-size:0.8rem;color:#8b949e;">Qty: {b["qty"]}</span>{kind_html}'
                                        f'{pb_html}'
                                        f'<div style="font-size:0.8rem;color:#c9d1d9;margin-top:6px;line-height:1.6;">'
                                        f'<div>{entry_line}</div><div style="margin-top:3px;">{ltp_line}</div>{setup_warning_html}</div></div>'
                                    )
                                    st.markdown(card, unsafe_allow_html=True)

                                    ai_key = f"ai_entry_review_{sym}_{b['order_id']}"
                                    if ai_key in st.session_state:
                                        st.markdown(f'<div style="background:#0e2035;border-left:3px solid #e3b341;padding:8px;border-radius:4px;margin-bottom:10px;font-size:0.78rem;color:#e6edf3;">🤖 {st.session_state[ai_key]}</div>', unsafe_allow_html=True)

                # ── Tab 3: Risk Profile ──
                with entry_tab3:
                    st.markdown('<div class="section-sub-lbl">📊 Risk Exposure & Allocation Analytics</div>', unsafe_allow_html=True)
                    # BUG FIX (2026-07-05, Jay): `balance` is available CASH, not equity —
                    # dividing open risk by idle cash produced absurd percentages (289%)
                    # and mislabeled cash as "portfolio equity". True equity = holdings
                    # market value + cash.
                    _equity_rp = float(total_portfolio_value or 0.0) + float(balance or 0.0)
                    portfolio_risk_pct = (total_risk / _equity_rp) * 100 if _equity_rp > 0 else 0.0
                    if portfolio_risk_pct <= 1.0:
                        risk_grade = "A+ (Excellent)"
                        risk_grade_color = "#00f260"
                    elif portfolio_risk_pct <= 2.0:
                        risk_grade = "A (Good)"
                        risk_grade_color = "#00f260"
                    elif portfolio_risk_pct <= 5.0:
                        risk_grade = "B (Moderate)"
                        risk_grade_color = "#e3b341"
                    else:
                        risk_grade = "C (High Risk)"
                        risk_grade_color = "#ff4b4b"

                    st.markdown(
                        f'<div class="metric-card" style="padding:20px;text-align:center;margin-bottom:15px;border-top:3px solid {risk_grade_color};">'
                        f'<div class="metric-label">Total Open Heat & Risk Grade</div>'
                        f'<div class="metric-value" style="color:{risk_grade_color};font-size:2rem;">{portfolio_risk_pct:.1f}% ({risk_grade})</div>'
                        f'<div style="font-size:0.8rem;color:#5a8a9f;margin-top:4px;">'
                        f'Total capital at risk from current LTP to Stop Loss is <b>₹{format_inr_int(total_risk)}</b> '
                        f'on total portfolio equity of <b>₹{format_inr_int(_equity_rp)}</b> '
                        f'(holdings ₹{format_inr_int(total_portfolio_value)} + cash ₹{format_inr_int(balance)}).'
                        f'</div></div>', unsafe_allow_html=True
                    )

                    # Per-stock risk breakdown
                    st.markdown('<div class="section-sub-lbl">Per-Stock Risk Breakdown</div>', unsafe_allow_html=True)
                    risk_rows = []
                    for sym, orders in sell_gtts_by_symbol.items():
                        ltp = ltps.get(sym) or 0
                        _tech = hist_data.get(sym)
                        for o in orders:
                            sl = o["sl_trigger"]; sl_qty = o.get("sl_qty") or o.get("qty") or 0
                            if ltp and sl:
                                current_risk = sl_qty * (ltp - sl)
                                if current_risk > 0:
                                    portfolio_pct = (current_risk / max(balance, 1)) * 100 if max(balance, 1) > 0 else 0.0
                                    
                                    row_data = {
                                        "Symbol": sym, 
                                        "LTP": f"₹{ltp:,.2f}", 
                                        "SL": f"₹{sl:,.2f}",
                                    }
                                    
                                    _tech = hist_data.get(sym)
                                    atr_val = 0
                                    atr_pct = 0.0
                                    is_swing = False
                                    ws_score = None
                                    
                                    if _tech:
                                        atr_val = (ltp * _tech["atr_pct"]) / 100
                                        atr_pct = _tech["atr_pct"]
                                        is_swing = _tech['atr_pct'] > 4 or _tech['dist_from_200'] > 30 or _tech['ws_score'] < 60
                                        ws_score = _tech['ws_score']
                                    elif ltp:
                                        raw_atr = get_atr(sym)
                                        if raw_atr:
                                            atr_val = raw_atr
                                            atr_pct = (raw_atr / ltp) * 100
                                        ai_key = f"ai_exit_review_{sym}"
                                        if ai_key in st.session_state and "[Swing]" in st.session_state[ai_key]:
                                            is_swing = True
                                            
                                    row_data["Style"] = "SWING" if is_swing else "POSITIONAL"
                                    
                                    # A3 FIX (2026-07-04 audit): guard the ltp division — missing
                                    # LTP rows must show "—", not crash or fake a distance.
                                    if not ltp or ltp <= 0:
                                        row_data["ATR %"] = f"{atr_pct:.2f}%" if atr_pct > 0 else "N/A"
                                        row_data["SL Dist"] = "— (no LTP)"
                                    elif atr_pct > 0:
                                        row_data["ATR %"] = f"{atr_pct:.2f}%"
                                        dist_pct = ((ltp - sl) / ltp) * 100
                                        atr_dist = dist_pct / atr_pct
                                        row_data["SL Dist"] = f"{dist_pct:.1f}% ({atr_dist:.1f} ATR)"
                                    else:
                                        row_data["ATR %"] = "N/A"
                                        row_data["SL Dist"] = f"{((ltp - sl) / ltp) * 100:.1f}%"
                                        
                                    row_data["W-Score"] = f"{ws_score}/80" if ws_score is not None else "N/A"
                                    
                                    row_data["Risk ₹"] = f"₹{current_risk:,.0f}"
                                    row_data["% Port"] = f"{portfolio_pct:.2f}%"
                                    
                                    risk_rows.append(row_data)
                    if risk_rows:
                        st.dataframe(pd.DataFrame(risk_rows), use_container_width=True, hide_index=True)
                        
                        st.markdown('<div class="section-sub-lbl" style="margin-top:20px;">Market Persona (Stage Analysis)</div>', unsafe_allow_html=True)
                        stage_counts = {"Stage 2 🟢": 0, "Stage 1/3 🟡": 0, "Stage 4 🔴": 0}
                        
                        # Count unique symbols in portfolio
                        analyzed_symbols = set()
                        for sym in sell_gtts_by_symbol.keys():
                            if sym not in analyzed_symbols:
                                _tech = hist_data.get(sym)
                                ltp = ltps.get(sym) or 0
                                if _tech and ltp:
                                    sma200 = _tech.get("sma200", 0)
                                    sma200_slope = _tech.get("sma200_slope", 0)
                                    if sma200:
                                        if ltp > sma200 and sma200_slope > 0:
                                            stage_counts["Stage 2 🟢"] += 1
                                        elif ltp < sma200 and sma200_slope < 0:
                                            stage_counts["Stage 4 🔴"] += 1
                                        else:
                                            stage_counts["Stage 1/3 🟡"] += 1
                                    analyzed_symbols.add(sym)
                                    
                        total_analyzed = sum(stage_counts.values())
                        if total_analyzed > 0:
                            sc1, sc2, sc3 = st.columns(3)
                            sc1.metric("Stage 2 (Advancing)", f"{stage_counts['Stage 2 🟢']} ({stage_counts['Stage 2 🟢']/total_analyzed*100:.0f}%)")
                            sc2.metric("Stage 1/3 (Transition)", f"{stage_counts['Stage 1/3 🟡']} ({stage_counts['Stage 1/3 🟡']/total_analyzed*100:.0f}%)")
                            sc3.metric("Stage 4 (Declining)", f"{stage_counts['Stage 4 🔴']} ({stage_counts['Stage 4 🔴']/total_analyzed*100:.0f}%)")
                    else:
                        st.info("No measurable risk from current positions (all stops are above LTP or no positions).")

                # ── Tab 4: Settings & Overrides ──
                with entry_tab4:
                    st.markdown('<div class="section-sub-lbl">⚙️ Manual SL & Multiplier Overrides</div>', unsafe_allow_html=True)
                    st.markdown('<div style="font-size:0.85rem; color:#8b949e; margin-bottom:12px;">Configure persistent manual overrides for positions. These overrides are saved to the database and will bypass the dynamic mechanical rules.</div>', unsafe_allow_html=True)

                    # A7: manual-SL override semantics (applies to all manual overrides)
                    _rs_c1, _rs_c2 = st.columns(2)
                    with _rs_c1:
                        st.radio("Manual SL mode", ["Floor", "Exact"], horizontal=True, key="rs_sl_override_mode",
                                 help="Floor (default): the Chandelier can only be TIGHTENED to your manual SL, never loosened. "
                                      "Exact: your manual SL is used verbatim, even if it sits below the computed Chandelier.")
                    with _rs_c2:
                        # B3: capital risk budget per trade (0.25% = execution freeze; 1.0% = standard)
                        st.number_input("Risk budget % per trade", min_value=0.05, max_value=2.0, step=0.05,
                                        key="rs_risk_budget_pct", value=st.session_state.get("rs_risk_budget_pct", 0.25),
                                        help="Drives the Portfolio Heat card: budget = capital × this % × open positions. "
                                             "0.25% during the execution freeze; 1.0% is the standard rule.")

                    if 'df_active_global' in globals() and not df_active_global.empty:
                        # Extract current open positions
                        override_rows = []
                        for _, r in df_active_global.iterrows():
                            sym = r.get("Symbol")
                            if pd.notna(sym):
                                override_rows.append({
                                    "Symbol": sym,
                                    "Manual SL Override": float(r.get("Manual SL Override", 0)) if pd.notna(r.get("Manual SL Override")) and str(r.get("Manual SL Override")).strip() else None,
                                    "Custom CE Mult": float(r.get("Custom CE Mult", 0)) if pd.notna(r.get("Custom CE Mult")) and str(r.get("Custom CE Mult")).strip() else None,
                                    "Pyramid Status": str(r.get("Pyramid Status", "")) if pd.notna(r.get("Pyramid Status")) else ""
                                })
                        
                        if override_rows:
                            df_overrides = pd.DataFrame(override_rows)
                            edited_overrides = st.data_editor(
                                df_overrides,
                                column_config={
                                    "Symbol": st.column_config.TextColumn("Symbol", disabled=True),
                                    "Manual SL Override": st.column_config.NumberColumn("Manual SL Override (₹)", format="%.2f", step=0.05, min_value=0.0),
                                    # A4: 0/negative multipliers are invalid — enforce at input
                                    "Custom CE Mult": st.column_config.NumberColumn("Custom CE Multiplier", format="%.1f", step=0.1, min_value=0.5, max_value=8.0,
                                                                                     help="0.5–8.0. Leave blank to use the system/catalyst multiplier."),
                                    "Pyramid Status": st.column_config.SelectboxColumn("Pyramid Status", options=["", "Initial", "Scaled", "Maxed"])
                                },
                                hide_index=True,
                                use_container_width=True
                            )
                            # A10 FIX (2026-07-04 audit): the save button was a MOCK —
                            # edits were silently discarded. Now persists to the journal DB
                            # (same columns the read path at journal_overrides consumes).
                            if st.button("💾 Save Overrides to Database", type="primary"):
                                try:
                                    import sqlite3 as _sq3
                                    import dhan_journal_v7 as _djm
                                    _conn_ov = _sq3.connect(_djm.DB_FILE)
                                    _cur_ov = _conn_ov.cursor()
                                    _nsaved = 0
                                    for _, _orow in edited_overrides.iterrows():
                                        _cur_ov.execute(
                                            "UPDATE journal SET manual_sl_override=?, custom_ce_mult=?, "
                                            "pyramid_status=? WHERE symbol=? AND status='OPEN'",
                                            (float(_orow["Manual SL Override"]) if pd.notna(_orow["Manual SL Override"]) else None,
                                             float(_orow["Custom CE Mult"]) if pd.notna(_orow["Custom CE Mult"]) else None,
                                             str(_orow["Pyramid Status"]) if pd.notna(_orow["Pyramid Status"]) else "",
                                             str(_orow["Symbol"])))
                                        _nsaved += _cur_ov.rowcount
                                    _conn_ov.commit(); _conn_ov.close()
                                    st.session_state.pop("cached_hist_data_v3", None)  # recompute Chandeliers
                                    st.success(f"✅ Overrides saved — {_nsaved} journal row(s) updated. "
                                               f"Chandeliers will recompute on next refresh.")
                                except Exception as _ove:
                                    st.error(f"❌ Override save FAILED — nothing written: {_ove}")
                        else:
                            st.info("No open positions found in the journal to override.")
                    else:
                        st.info("Journal data not loaded.")
