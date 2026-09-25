# =============================================================================
# weinstein_commander_web_v4.0.py — Weinstein Commander Web
# v4.0 — Phase 1: Pre-Market Hub | Post-Market | Breadth Engine | Macro+ | Gemini AI
# Trailing SL Note: SL > Entry is VALID for locked-profit trailing states.
#   Pre-Flight checks SL < entry (new trades). Existing positions show LOCKED badge.
# =============================================================================

import streamlit as st
import commander_theme as _theme

# ── PLOTLY DARK DEFAULT (27 Aug 2026) ────────────────────────────────────────
# Plotly does not read our CSS variables, so a chart keeps its own light template and
# paints an opaque background — which is why the sector donut appeared as a white card
# on a dark page. Setting the template ONCE here covers every figure in the app;
# per-figure overrides still win if a chart genuinely needs a different look.
try:
    import plotly.io as _pio
    import plotly.graph_objects as _pgo
    _pio.templates["commander"] = _pgo.layout.Template(
        layout=dict(
            paper_bgcolor="rgba(0,0,0,0)",   # let the card behind it show through
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=_theme.DARK["ink"], family="Inter, sans-serif"),
            xaxis=dict(gridcolor=_theme.DARK["rule"], zerolinecolor=_theme.DARK["rule"]),
            yaxis=dict(gridcolor=_theme.DARK["rule"], zerolinecolor=_theme.DARK["rule"]),
            colorway=["#56C2CC", "#45BE92", "#DCA84E", "#E9857C", "#8FA8C8",
                      "#B08FD0", "#5FBFA8", "#D09A6A"],
        )
    )
    _pio.templates.default = "plotly_dark+commander"
except Exception:
    pass   # charts still render on Plotly's own default

import streamlit.components.v1 as st_components   # for HTML that must RUN script
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
import risk_common as _rc
import house_policy as _HP   # the ONE home of risk %, capital, caps, regime (25-Sep-2026)
import journal_path as _jp  # AUD-INT-14: one owner of the journal location
# ── v4.0 Phase-1 imports ─────────────────────────────────────────────────────
try:
    from rrg_engine import (
        SECTOR_INDICES, QUADRANT_COLORS, rotation_universe,
        calculate_jdk_rrg, compute_universe_rrg, render_rrg_plotly,
        load_universe_data,          # was `from pages.6_rrg import ...` - not
                                     # importable (module name starts with a digit),
                                     # and importing that page would run its
                                     # st.set_page_config/st.title at top level.
    )
    _RRG_OK = True
except Exception:                    # ImportError was too narrow for the above
    _RRG_OK = False

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
def journal_db_path():
    """The journal DB path WITHOUT importing dhan_journal_v7.

    That module is a full Streamlit app: importing it runs st.set_page_config() and its
    top-level st.* calls, which paints the whole Journal UI into whatever page triggered
    the import. The note above says so, and three call sites imported it anyway -- all
    three only wanted this one constant. On RISK SHIELD it was the first import of the
    run, so pressing Risk Shield rendered the page header and then the entire Active
    Trade Journal underneath it (Golden Matcher was unaffected only because it imports
    the module earlier, so the second import is a cached no-op).

    Read by AST so a rename in the module is still picked up, with no execution.
    """
    import ast as _ast
    if os.environ.get("COMMANDER_JOURNAL_DB"):          # render tests point at a copy
        return os.environ["COMMANDER_JOURNAL_DB"]
    # 23-Sep: DB_FILE moved to journal_core.py in the split. This helper could now just
    # `import journal_core` — that module is UI-free and safe — but reading it without
    # executing anything is still the cheaper, stricter thing to do, so only the path moved.
    _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "journal_core.py")
    try:
        for _n in _ast.parse(open(_p, encoding="utf-8").read()).body:
            if isinstance(_n, _ast.Assign) and any(
                    getattr(t, "id", "") == "DB_FILE" for t in _n.targets):
                for _s in _ast.walk(_n.value):
                    if isinstance(_s, _ast.Constant) and isinstance(_s.value, str)                             and _s.value.endswith(".db"):
                        return os.path.join(os.path.dirname(_p), _s.value)
    except Exception:
        pass
    return _jp.JOURNAL_DB


from commander_core import (  # moved verbatim 25-Sep-2026 - see commander_core.py
    CLIENT_ID, DB_FILE, EMA20_EXT_ATR_MAX, EMA20_RECLAIM_BAND_PCT, GM_BFF_MIN,
    GM_LOC_STRICT, GM_PIVOT_NEEDS_CONFLUENCE, INHERIT_QUALIFICATION, JOURNAL_RENAME_MAP, RR_MIN_LOCATION,
    SL_BUF_PCT, SL_MULT_POS, SL_MULT_SWING, TT_SWING_ATR_PCT, TT_SWING_OFF52,
    _APP_DIR, _GM_ENTRY_SRC, _GM_SETTINGS_FILE, _SCRIPT_DIR, _canon_sym,
    _cat_on, _expected_last_session, _g, _get_dhan_client, _gm_apply_location_rule,
    _gm_bar_close_times, _gm_bff_gate, _gm_core_gate, _gm_entry_instruction, _gm_entry_method,
    _gm_last_passed_boundary, _gm_settings, _gm_settings_save, _gm_sl_basis, _gm_sync_pivot_setting,
    _gm_use_pivot_zones, _gm_zone_rungs, _grade, _house_initial_stop, _plan_structural_sl,
    _range_bar, _rec_cfg, _s4_rv, _sb_cls, _stg_digit,
    clean_symbol, compute_decision, compute_portfolio_analytics, compute_recovery_workflow, compute_workflow,
    fnum, format_inr, format_inr_int, get_dhan_balance, get_dhanhq_client,
    get_img_as_base64, get_live_holdings_stats, get_script_path, get_sector, inr,
    load_closed_trades_db, load_journal_db, logger, minervini_checks, render_pa_banner,
    yf_symbol,
)

logging.basicConfig(level=logging.WARNING)
# Suppress noisy yfinance download errors (sector indices that Yahoo doesn't serve)
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("peewee").setLevel(logging.CRITICAL)

# ── PAGE CONFIG ──────────────────────────────────────────────────────────────


_ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commander_web_icon.png")
_PAGE_ICON = _ICON_PATH if os.path.exists(_ICON_PATH) else "🦁"

st.set_page_config(
    page_title="Weinstein Commander Web",
    page_icon=_PAGE_ICON, layout="wide",
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

ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

# RS-P0 (14-Jul-2026): this map was MISSING the entry-snapshot + override columns
# that dhan_journal_v7's canonical map carries — so every read of "Setup"/"Manual SL
# Override"/"Custom CE Mult"/"Pyramid Status" on the Risk Shield page returned None.
# Consequences (all silent): manual SL overrides never applied, custom CE mult never
# applied, pyramid 'Maxed' guard dead, and the CATALYST-AWARE TRAIL never engaged
# (setup always blank → trail_mult_for never matched → heuristic 4.5/5.0 guess).
# Keep in lockstep with dhan_journal_v7.load_db's rename_map.

# ── FORMATTERS ───────────────────────────────────────────────────────────────



# THE INTERPRETER THIS APP IS RUNNING UNDER - not one discovered by scanning for a
# .venv directory. There are two virtualenvs here: an EMPTY project-local
# GeminiVSCode/.venv, and TradingData/venv which actually holds the dependencies. The
# old code preferred the project one because the path existed, so every child script
# was spawned without playwright, bs4 or anything else - and the error surfaced as
# ModuleNotFoundError, which reads as "not installed" and sends you to pip.
# sys.executable is the running environment by definition; it needs no discovery and
# cannot guess wrong. The scan survives only for the case where sys.executable is not a
# python (a packaged launcher), and even then it checks the candidate actually works.
_PYTHON_EXE = sys.executable
if not str(_PYTHON_EXE).lower().endswith(("python.exe", "pythonw.exe", "python", "python3")):
    for _cand in (os.path.join(_SCRIPT_DIR, ".venv", "Scripts", "python.exe"),
                  os.path.join(_SCRIPT_DIR, ".venv", "bin", "python")):
        if os.path.exists(_cand):
            _PYTHON_EXE = _cand
            break
_VENV_PY = _PYTHON_EXE          # back-compat: some call sites still read this name

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
    """Next earnings date. The nightly cache (earnings_calendar, auto-pilot Phase 8a)
    first - the same source the pyramid ladder reads since 22-Sep - so Risk Shield and the
    ladder cannot disagree; the live yfinance call is only the cold-cache fallback.
    None = UNKNOWN, never "no earnings soon"."""
    import yfinance as yf
    from datetime import date
    try:
        import earnings_calendar as _ec
        _nx = _ec.next_earnings(sym)
        if _nx:
            return pd.to_datetime(_nx).date()
    except Exception as e:
        logger.warning(f"earnings cache read {sym}: {e}")
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



# ── E-01: Portfolio Analytics helpers ────────────────────────────────────────


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

h_color = "var(--bull)" if is_healthy        else "var(--bear)"
# A FACT, not a regime (25-Sep-2026): the Market Regime cell beside it is the house
# regime (house_policy / regime_state.json). "BULLISH" here used to read as a second verdict.
h_text  = "Above 200-DMA" if is_healthy  else "Below 200-DMA"
w_color = "var(--bear)" if noise_count_g > 0 else "var(--bull)"
w_text  = f"⚠ {noise_count_g} AT RISK"  if noise_count_g > 0 else "✔ SECURE"
s_color = "var(--bull)" if sys_status == "SYSTEM ONLINE" else "var(--bear)"

total_deployed_g = live_dep
open_pos         = live_pos
# FORM-03 FIX: total_cap = full portfolio equity (basis for all sizing/risk)
# No invented fallback (25-Sep-2026): the old ₹50L fallback made every % below look plausible
# when Dhan was down. Fall back to the DECLARED capital, else 0 (the % cells read 0).
_live_cap = balance + total_deployed_g
_decl_cap = _HP.sizing_capital()[0]
total_cap = _live_cap if _live_cap > 0 else (_decl_cap if _decl_cap == _decl_cap else 0.0)
TOTAL_CAP_IS_LIVE = _live_cap > 0
# Split phase 1 (25-Sep-2026): pages read the shared state through ONE frozen object, so no
# page can rebind balance / total_cap / the journal frame for the pages after it.
import commander_context as _cctx
app_state = _cctx.Ctx(balance=balance, sys_status=sys_status, total_cap=total_cap,
                      total_cap_is_live=TOTAL_CAP_IS_LIVE, df_active_global=df_active_global,
                      df_live_holdings=df_live_holdings)
deployed_pct = round((total_deployed_g / total_cap) * 100, 1) if total_cap > 0 else 0.0

# Check query parameters for pop-out views (open in a new browser window/tab):
#   ?view=gm_board_maximized → GM Trigger Board only (view locked)
#   ?view=gm_window          → full Golden Matcher (Single Symbol ↔ Board switch)
#   ?view=risk_window        → Risk Shield (18-Sep, for the phone: no sidebar overlay)
# All hide the sidebar so the pop-out is a clean dedicated window while the main
# Web Commander window is used for other pages. Auto-refresh works in the pop-out
# because it's a fresh session (Live-refresh seeds to the 75m bar-close default).
_qview = st.query_params.get("view")
is_maximized_board = (_qview == "gm_board_maximized")
is_gm_window = (_qview == "gm_window")
is_risk_window = (_qview == "risk_window")
if "page" not in st.session_state and _qview is None:
    # PAGE PERSISTENCE (30-Jul, Jay: "sometimes it goes back to its default page").
    # The nav page lived ONLY in st.session_state, which dies with the websocket session
    # — tab backgrounded/slept, network blip, or a server restart — so the next run fell
    # through to the ('page','DASHBOARD') default below. The ?view= pop-outs never had
    # this problem precisely because they derive the page from the URL on every run.
    # Restore-only (guarded on a FRESH session) so it can never fight a nav click.
    _qp = st.query_params.get("p")
    if _qp:
        st.session_state["page"] = str(_qp)

# PER-WINDOW TRIGGER-TF OVERRIDE (30-Jul, Jay). The union refresh makes the board
# FRESHER but not dual-timeframe: PA still computes on the single shared Trigger-TF, so
# at a 10:30 (75m-only) close a 125m board rebuilds on the wrong clock. `?tf=75m` locks
# THIS WINDOW to a TF, so two pop-outs can monitor 75m and 125m side by side with no
# switching. Only honoured on a ?view= pop-out — the main window keeps the shared
# setting — and a locked window NEVER writes trigger_tf back to gm_settings, or the
# pop-out would hijack the TF everywhere (that unification was deliberate, 13-Jul).
TF_LOCK = None
# 18-Sep: ?mobile=1 — on a phone the ten pinned decision columns (~1,650 px) cover the
# whole viewport and the grid cannot scroll sideways at all. Mobile view leaves them
# unpinned so the grid swipes as one sheet. Desktop behaviour is unchanged.
MOBILE_VIEW = str(st.query_params.get("mobile") or "").strip() in ("1", "true", "yes")
if _qview is not None:
    _qtf = str(st.query_params.get("tf") or "").strip()
    if _qtf in ("75m", "125m", "Daily"):
        TF_LOCK = _qtf
        st.session_state["gm_trig_tf"] = _qtf

if is_maximized_board or is_gm_window or is_risk_window:
    st.session_state["page"] = "RISK SHIELD" if is_risk_window else "GOLDEN MATCHER"
    if is_maximized_board:
        st.session_state["gm_view"] = "📋 Trigger Board"   # board only; view locked
    elif is_gm_window and "gm_view" not in st.session_state:
        # 22-Sep (Jay): the GM pop-out opens on the BOARD. Seeded only on a FRESH
        # session ("not in session_state"), never on every run — the radio at :13781
        # owns this same key, so writing it unconditionally would snap the window
        # back to the board the instant he switched to Single Symbol.
        st.session_state["gm_view"] = "📋 Trigger Board"
    st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        display: none !important;
        width: 0px !important;
        min-width: 0px !important;
    }
    [data-testid="collapsedControl"] {
        display: none !important;
    }
    .statusbar {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)



def _goto_page(key: str):
    """Set the nav page AND mirror it to the URL (?p=), so a websocket reconnect or a
    server restart restores where you were instead of snapping back to DASHBOARD.
    One helper for every nav site — three call sites set the page, and they must not
    drift into some persisting and some not."""
    st.session_state["page"] = key
    try:
        st.query_params["p"] = key
    except Exception:
        pass                       # older Streamlit / read-only params — nav still works

# 18-Sep: the pop-out views (?view=gm_window / gm_board_maximized / risk_window) hide the
# sidebar, but the SIDEBAR block below forces `display: block !important` and, being
# injected LATER with equal specificity, silently won — the pop-outs had been showing the
# sidebar all along (visible on a phone, where it overlays half the page). The hide now
# lands at the END of this sheet so it is the last word.
_POPOUT_SIDEBAR_HIDE = ("""
[data-testid="stSidebar"] { display: none !important; width: 0 !important; min-width: 0 !important; }
[data-testid="collapsedControl"], [data-testid="stSidebarCollapseButton"] { display: none !important; }
""" if _qview in ("gm_window", "gm_board_maximized", "risk_window") else "")
st.markdown("<style>" + _theme.tokens_css() + f"""
*, *::before, *::after {{ box-sizing: border-box; }}
.stApp {{
    background: var(--ground) !important;
    font-family: var(--body); color: var(--ink);
}}
.block-container {{ padding: 0 !important; margin: 0 !important; max-width: 100% !important; }}
header, footer {{ visibility: hidden !important; }}
#MainMenu {{ visibility: hidden !important; }}
[data-testid="collapsedControl"] {{ display: none !important; }}
[data-testid="stSidebarCollapseButton"] {{ display: none !important; }}
button[kind="header"] {{ display: none !important; }}
section[data-testid="stSidebar"] > div:first-child > div > button {{ display: none !important; }}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {{
    background: var(--surface-3) !important;
    border-right: 2px solid var(--muted) !important;
    width: 270px !important; min-width: 270px !important; padding: 0 !important;
    transform: none !important; visibility: visible !important; display: block !important;
}}
[data-testid="stSidebar"] > div {{ padding: 0 !important; }}
[data-testid="stSidebarContent"] {{
    padding: 0 !important; overflow-y: auto !important; overflow-x: hidden !important;
    scrollbar-width: thin; scrollbar-color: var(--muted) var(--surface-3);
}}
[data-testid="stSidebarContent"]::-webkit-scrollbar {{ width: 5px; }}
[data-testid="stSidebarContent"]::-webkit-scrollbar-track {{ background: var(--surface-3); }}
[data-testid="stSidebarContent"]::-webkit-scrollbar-thumb {{ background: var(--muted); border-radius: 3px; }}

/* ── TOP STATUS BAR ── */
.statusbar {{
    display: grid; grid-template-columns: repeat(8, 1fr);
    gap: 8px; background: var(--surface-3); padding: 8px 10px; border-bottom: 2px solid var(--faint);
}}
.sb-cell {{
    background: var(--surface) !important;
    border: 1.5px solid var(--rule) !important;
    border-radius: 10px !important;
    padding: 8px 14px !important;
    display: flex !important; flex-direction: column !important; justify-content: center !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
    transition: all 0.18s ease-in-out !important;
}}
.sb-cell:hover {{
    background: var(--surface-2) !important;
    border-color: var(--acc) !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06) !important;
    transform: translateY(-1px) !important;
}}
.sb-label {{ font-family: var(--mono) !important; font-size: 0.63rem !important; color: var(--acc) !important; letter-spacing: 1.5px !important; text-transform: uppercase !important; font-weight: 800 !important; }}
.sb-value {{ font-family: var(--mono) !important; font-size: 0.95rem !important; font-weight: 900 !important; margin-top: 2px !important; letter-spacing: 0.5px !important; color: var(--ink) !important; }}

/* ── HEADERS ── */
.page-title {{
    font-family: var(--disp) !important; font-size: 1.65rem !important; font-weight: 800 !important;
    letter-spacing: 3px !important; text-transform: uppercase !important; color: var(--ink) !important;
    border-left: 4px solid var(--acc) !important; padding-left: 12px !important; margin: 14px 0 4px 0 !important;
}}
.page-desc {{ font-size: 0.75rem !important; color: var(--ink) !important; letter-spacing: 2px !important; text-transform: uppercase !important; margin: 0 0 12px 15px !important; font-family: var(--mono) !important; font-weight: 800 !important; }}
.section-hdr {{
    font-family: var(--mono) !important; font-size: 0.76rem !important; color: var(--acc) !important;
    letter-spacing: 3px !important; text-transform: uppercase !important; margin: 14px 0 8px 0 !important;
    display: flex !important; align-items: center !important; gap: 10px !important; font-weight: 800 !important;
}}
.section-hdr::after {{ content:'' !important; flex:1 !important; height:2px !important; background:var(--muted) !important; }}
.section-sub-lbl {{
    font-family: var(--disp) !important; font-size: 1.08rem !important; font-weight: 800 !important;
    color: var(--acc) !important; letter-spacing: 1.5px !important; text-transform: uppercase !important;
    padding: 6px 14px !important; background: var(--surface-2) !important;
    border-left: 4px solid var(--acc) !important; border-radius: 0 4px 4px 0 !important; margin-bottom: 8px !important;
}}

/* ── EXPANDERS ── */
[data-testid="stExpander"] {{
    background: var(--surface) !important;
    border: 1.5px solid var(--muted) !important;
    border-radius: 8px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
    margin-bottom: 12px !important;
}}
[data-testid="stExpander"] summary {{
    background: var(--surface-2) !important;
    border-bottom: 1.5px solid var(--rule) !important;
    padding: 10px 14px !important;
    border-radius: 8px 8px 0 0 !important;
}}
[data-testid="stExpander"] summary p, [data-testid="stExpander"] summary span {{
    color: var(--ink) !important;
    font-weight: 800 !important;
    font-size: 0.94rem !important;
    letter-spacing: 0.3px !important;
}}
[data-testid="stExpander"] summary svg {{
    fill: var(--ink) !important;
    color: var(--ink) !important;
}}

/* ── METRIC CARDS ── */
.metric-card {{
    background: var(--surface) !important; border: 1.5px solid var(--rule) !important; border-radius: 8px !important;
    padding: 12px 16px !important; text-align: center !important; position: relative !important;
    box-shadow: 0 2px 5px rgba(0,0,0,0.06) !important;
}}
.metric-card:has(.expand-toggle:checked) {{
    position: fixed !important;
    top: 5% !important; left: 5% !important;
    width: 90vw !important; height: 90vh !important;
    z-index: 9999999 !important;
    background: var(--surface) !important;
    border: 2px solid var(--acc) !important;
    box-shadow: 0 0 50px rgba(0,0,0,0.25) !important;
    overflow-y: auto !important;
}}
.metric-card:has(.expand-toggle:checked) .expand-btn {{
    color: var(--bear) !important;
}}
.expand-btn {{
    position: absolute !important; right: 8px !important; top: 8px !important; cursor: pointer !important; color: var(--ink) !important;
    font-size: 1.1rem !important; transition: color 0.2s !important;
}}
.expand-btn:hover {{ color: var(--ink) !important; }}
.metric-label {{ font-family: var(--mono) !important; font-size: 0.68rem !important; color: var(--ink) !important; letter-spacing: 2px !important; text-transform: uppercase !important; font-weight: 800 !important; }}
.metric-value {{ font-family: var(--mono) !important; font-size: 1.25rem !important; font-weight: 800 !important; margin-top: 3px !important; }}

/* ── ALL BUTTONS: Light background, dark text, shining border on hover/active ── */
div[data-testid="stButton"] > button:not([kind="primary"]),
button[kind="secondary"]:not([kind="primary"]) {{
    background: var(--surface) !important;
    border: 1.5px solid var(--rule) !important;
    border-radius: 8px !important;
    color: var(--acc) !important;
    font-family: var(--body) !important;
    font-size: 0.84rem !important;
    font-weight: 700 !important;
    padding: 7px 16px !important;
    width: 100% !important;
    text-align: center !important;
    box-shadow: 0 1px 4px rgba(59,130,246,0.10) !important;
    transition: all .15s ease-in-out !important;
}}
div[data-testid="stButton"] > button p,
div[data-testid="stButton"] > button span,
button[kind="secondary"] p, button[kind="secondary"] span {{
    color: var(--acc) !important;
    font-weight: 700 !important;
    font-size: 0.84rem !important;
    text-align: center !important;
    width: 100% !important;
    margin: 0 !important;
}}

/* Hover = stronger glow */
div[data-testid="stButton"] > button:not([kind="primary"]):hover,
button[kind="secondary"]:not([kind="primary"]):hover {{
    background: var(--surface-2) !important;
    border: 2px solid var(--acc) !important;
    color: var(--acc) !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08) !important;
    transform: translateY(-1px) !important;
}}

/* ── PRIMARY / ACTIVE BUTTONS — GLOWING SHINING BORDER (blue gradient + white text) ── */
button[kind="primary"],
[data-testid="stSidebar"] button[kind="primary"],
.st-key-sb_auto_pilot button,
div[data-testid="stSidebar"] .st-key-sb_auto_pilot button,
button[key="sb_auto_pilot"] {{
    background: var(--acc) !important;
    border: 2px solid var(--acc-rule) !important;
    border-radius: 8px !important;
    color: var(--ground) !important;
    font-family: var(--body) !important;
    font-size: 0.85rem !important;
    font-weight: 800 !important;
    padding: 8px 16px !important;
    box-shadow: 0 0 16px rgba(37,99,235,0.6), 0 0 4px rgba(96,165,250,0.8), 0 2px 8px rgba(0,0,0,0.15) !important;
    transition: all .15s ease-in-out !important;
    justify-content: center !important;
    text-align: center !important;
}}
/* On the ACCENT, which is a LIGHT teal in this theme, the label has to be DARK.
   --ink is the text colour for the ground, not for the accent; using it here is the
   invisible-text bug one layer up. --ground is the correct counterpart to --acc. */
button[kind="primary"] p, button[kind="primary"] span,
[data-testid="stSidebar"] button[kind="primary"] p,
.st-key-sb_auto_pilot button p, .st-key-sb_auto_pilot button span,
button[key="sb_auto_pilot"] p, button[key="sb_auto_pilot"] span {{
    color: var(--ground) !important;
    -webkit-text-fill-color: var(--ground) !important;
    font-weight: 800 !important;
    text-align: center !important;
    margin: 0 auto !important;
    width: 100% !important;
}}

/* ── SIDEBAR BUTTONS ── Light blue tint, left-aligned, shining on hover ── */
[data-testid="stSidebar"] button {{
    background: var(--surface) !important;
    border: 1.5px solid var(--rule) !important;
    border-radius: 8px !important;
    padding: 7px 12px !important;
    font-family: var(--body) !important;
    font-size: 0.82rem !important;
    font-weight: 700 !important;
    color: var(--acc) !important;
    text-align: left !important;
    width: calc(100% - 12px) !important;
    margin: 2px 6px !important;
    min-height: 0 !important;
    line-height: 1.3 !important;
    box-shadow: 0 1px 3px rgba(14,165,233,0.10) !important;
    transition: all .15s ease-in-out !important;
}}
[data-testid="stSidebar"] button:hover {{
    background: var(--surface-2) !important;
    color: var(--acc) !important;
    border: 1.5px solid var(--acc) !important;
    box-shadow: 0 0 12px rgba(59,130,246,0.45), 0 2px 4px rgba(0,0,0,0.06) !important;
    transform: translateX(2px) !important;
}}
/* Sidebar primary button (Auto-Pilot etc.) — must override sidebar base */
[data-testid="stSidebar"] button[kind="primary"],
[data-testid="stSidebar"] .st-key-sb_auto_pilot button {{
    background: var(--acc) !important;
    border: 2px solid var(--acc-rule) !important;
    color: var(--ground) !important;
    -webkit-text-fill-color: var(--ground) !important;
    font-weight: 800 !important;
    box-shadow: 0 0 16px rgba(37,99,235,0.6), 0 0 4px rgba(96,165,250,0.8) !important;
    transform: none !important;
}}
[data-testid="stSidebar"] button[kind="primary"] p,
[data-testid="stSidebar"] button[kind="primary"] span,
[data-testid="stSidebar"] .st-key-sb_auto_pilot button p,
[data-testid="stSidebar"] .st-key-sb_auto_pilot button span {{
    color: var(--ground) !important;
    -webkit-text-fill-color: var(--ground) !important;
    font-weight: 800 !important;
}}
[data-testid="stSidebar"] button p {{
    color: inherit !important;
    font-weight: inherit !important;
    text-align: left !important;
    margin: 0 !important;
}}

/* ── MAIN PAGE RADIO BUTTONS (HORIZONTAL ALIGNMENT & SHINING BORDER) ── */
[data-testid="stRadio"] {{ margin: 2px 0 !important; }}
[data-testid="stRadio"] > label {{
    font-family: var(--mono) !important;
    font-size: 0.74rem !important;
    font-weight: 800 !important;
    color: var(--ink) !important;
    letter-spacing: 1px !important;
    text-transform: uppercase !important;
    margin-bottom: 3px !important;
    display: block !important;
}}
[data-testid="stRadio"] > div[role="radiogroup"] {{
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: wrap !important;
    gap: 8px !important;
    align-items: center !important;
}}
[data-testid="stRadio"] label[data-baseweb="radio"] {{
    display: inline-flex !important;
    align-items: center !important;
    background: var(--surface) !important;
    border: 1.5px solid var(--rule) !important;
    border-radius: 8px !important;
    padding: 6px 14px !important;
    margin: 0 !important;
    width: auto !important;
    font-family: var(--body) !important;
    font-size: 0.84rem !important;
    color: var(--acc) !important;
    font-weight: 700 !important;
    cursor: pointer !important;
    transition: all 0.15s ease-in-out !important;
    box-shadow: 0 1px 3px rgba(14,165,233,0.10) !important;
}}
[data-testid="stRadio"] label[data-baseweb="radio"]:hover {{
    background: var(--surface-2) !important;
    border-color: var(--acc) !important;
    color: var(--acc) !important;
    box-shadow: 0 0 10px rgba(59,130,246,0.35) !important;
}}
/* Selected Radio Option - GLOWING SHINING BORDER */
[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked),
[data-testid="stRadio"] label[data-baseweb="radio"][data-checked="true"] {{
    background: linear-gradient(135deg, var(--surface-2) 0%, var(--surface-3) 100%) !important;
    border: 2px solid var(--acc) !important;
    color: var(--acc) !important;
    font-weight: 800 !important;
    box-shadow: 0 0 14px rgba(37,99,235,0.55), 0 0 4px rgba(96,165,250,0.9) !important;
}}
[role="radiogroup"] input {{ display: none !important; }}
[role="radiogroup"] [data-testid="stMarkdownContainer"] p {{ margin: 0 !important; font-size: 0.84rem !important; color: inherit !important; font-weight: inherit !important; }}

/* ── SIDEBAR RADIOS SPECIFIC OVERRIDE ── */
[data-testid="stSidebar"] [data-testid="stRadio"] > div[role="radiogroup"] {{
    flex-direction: column !important;
    gap: 4px !important;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"] {{
    width: calc(100% - 12px) !important;
    display: block !important;
}}

.sb-section-lbl {{
    font-family: var(--mono) !important;
    font-size: 0.70rem !important;
    font-weight: 900 !important;
    color: var(--ink) !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
    padding: 8px 12px 4px 12px !important;
    border-top: 1.5px solid var(--faint) !important;
    margin-top: 10px !important;
    margin-bottom: 2px !important;
    display: block !important;
    clear: both !important;
    width: 100% !important;
    background: transparent !important;
}}
[data-testid="stSidebarNav"] {{ display: none !important; }}
section[data-testid="stSidebar"] > div:first-child {{ padding-top: 0.5rem !important; }}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{ padding-top: 0 !important; }}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"]:first-child {{ gap: 0.3rem !important; }}
/* Sidebar nav buttons — left-aligned, NOT forced left-pad override on primary */
section[data-testid="stSidebar"] div[data-testid="stButton"] > button:not([kind="primary"]) {{
    display: block !important;
    text-align: left !important;
    padding-left: 14px !important;
    justify-content: flex-start !important;
    align-items: center !important;
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
    color: inherit !important;
}}

/* ── FORM INPUTS & METRICS ── */
[data-testid="metric-container"] {{ background: var(--surface) !important; border: 1.5px solid var(--rule) !important; border-radius: 6px !important; padding: 10px 14px !important; box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important; }}
[data-testid="metric-container"] label {{ font-family: var(--mono) !important; font-size: 0.68rem !important; color: var(--ink) !important; letter-spacing: 2px !important; text-transform: uppercase !important; font-weight: 800 !important; }}
[data-testid="metric-container"] [data-testid="stMetricValue"] {{ font-family: var(--mono) !important; font-size: 1.25rem !important; font-weight: 800 !important; color: var(--ink) !important; }}
[data-testid="stDataFrame"] {{ border: 1.5px solid var(--rule) !important; border-radius: 6px !important; }}
iframe {{ border-radius: 6px !important; }}
hr {{ border-color: var(--muted) !important; margin: 10px 0 !important; }}
[data-testid="stToast"] {{ background: var(--surface) !important; border: 2px solid var(--acc) !important; border-radius: 6px !important; color: var(--ink) !important; font-family: var(--body) !important; font-weight: 700 !important; }}
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {{
    background: var(--surface) !important; border: 1.5px solid var(--muted) !important;
    border-radius: 4px !important; color: var(--ink) !important;
    font-family: var(--mono) !important; font-size: 0.84rem !important; font-weight: 700 !important;
}}
[data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus {{ border-color: var(--acc) !important; box-shadow: 0 0 0 2px rgba(29,78,216,.25) !important; }}
label {{ color: var(--ink) !important; font-size: 0.82rem !important; font-weight: 800 !important; }}
[data-testid="stCaptionContainer"] p, caption, .stCaption {{ color: var(--ink-2) !important; font-weight: 800 !important; font-size: 0.78rem !important; }}
[data-testid="stSelectbox"] > div > div {{ background: var(--surface) !important; border: 1.5px solid var(--muted) !important; color: var(--ink) !important; border-radius: 4px !important; font-weight: 700 !important; }}

/* ── DATA SEMANTIC COLORS — Gain / Loss / Signals ── */
/* Usage: wrap any value in <span class="val-gain"> or <span class="val-loss"> */
.val-gain  {{ color: var(--bull) !important; font-weight: 800 !important; }}
.val-loss  {{ color: var(--bear) !important; font-weight: 800 !important; }}
.val-warn  {{ color: var(--warn) !important; font-weight: 700 !important; }}
.val-info  {{ color: var(--acc) !important; font-weight: 700 !important; }}
.val-neut  {{ color: var(--muted) !important; font-weight: 600 !important; }}

/* Pill / badge chips */
.pill-bull  {{ display:inline-block;padding:2px 10px;background:var(--bull-bg);color:var(--bull);border:1px solid var(--bull-rule);border-radius:20px;font-size:0.72rem;font-weight:800;letter-spacing:0.5px; }}
.pill-bear  {{ display:inline-block;padding:2px 10px;background:var(--bear-bg);color:var(--bear);border:1px solid var(--bear-rule);border-radius:20px;font-size:0.72rem;font-weight:800;letter-spacing:0.5px; }}
.pill-warn  {{ display:inline-block;padding:2px 10px;background:var(--warn-bg);color:var(--warn);border:1px solid var(--warn-rule);border-radius:20px;font-size:0.72rem;font-weight:800;letter-spacing:0.5px; }}
.pill-info  {{ display:inline-block;padding:2px 10px;background:var(--surface-2);color:var(--acc);border:1px solid var(--rule);border-radius:20px;font-size:0.72rem;font-weight:800;letter-spacing:0.5px; }}
.pill-neut  {{ display:inline-block;padding:2px 10px;background:var(--surface-2);color:var(--muted);border:1px solid var(--rule);border-radius:20px;font-size:0.72rem;font-weight:800;letter-spacing:0.5px; }}

/* ── S4-STYLE TABLE ROWS ── */
.s4-table {{ width:100%;border-collapse:collapse;font-family:var(--body);font-size:0.84rem; }}
.s4-table thead tr {{ background:var(--acc); }}
.s4-table thead th {{ color: var(--ink);font-weight:800;font-size:0.72rem;letter-spacing:1.5px;text-transform:uppercase;padding:8px 12px;text-align:left;border:none; }}
.s4-table tbody tr {{ background:var(--surface);border-bottom:1px solid var(--surface-3);transition:background .12s; }}
.s4-table tbody tr:nth-child(even) {{ background:var(--surface-2); }}
.s4-table tbody tr:hover {{ background:var(--surface) !important;border-left:3px solid var(--acc); }}
.s4-table tbody td {{ padding:7px 12px;color:var(--ink-2);font-weight:600;vertical-align:middle; }}
.s4-table tbody td.gain {{ color:var(--bull);font-weight:800; }}
.s4-table tbody td.loss {{ color:var(--bear);font-weight:800; }}
.s4-table tbody td.warn {{ color:var(--warn);font-weight:700; }}
.s4-table tbody td.info {{ color:var(--acc);font-weight:700; }}

/* ── SIGNAL STATUS INDICATORS ── */
.sig-dot-bull {{ width:8px;height:8px;border-radius:50%;background:var(--bull);display:inline-block;margin-right:5px;box-shadow:0 0 6px rgba(21,128,61,0.5); }}
.sig-dot-bear {{ width:8px;height:8px;border-radius:50%;background:var(--bear);display:inline-block;margin-right:5px;box-shadow:0 0 6px rgba(220,38,38,0.5); }}
.sig-dot-warn {{ width:8px;height:8px;border-radius:50%;background:var(--warn);display:inline-block;margin-right:5px;box-shadow:0 0 6px rgba(180,83,9,0.4); }}
.sig-dot-neut {{ width:8px;height:8px;border-radius:50%;background:var(--faint);display:inline-block;margin-right:5px; }}

/* ── CARD ACCENT BORDERS ── */
.card-bull {{ border-top:3px solid var(--bull) !important; }}
.card-bear {{ border-top:3px solid var(--bear) !important; }}
.card-warn {{ border-top:3px solid var(--warn) !important; }}
.card-info {{ border-top:3px solid var(--acc) !important; }}

/* ── STREAMLIT DATAFRAME — high-contrast table styling ── */
[data-testid="stDataFrame"] table {{ border-collapse:collapse !important; width:100% !important; }}
[data-testid="stDataFrame"] thead tr th {{
    background: var(--acc) !important; color: var(--ink) !important;
    font-family: var(--mono) !important;
    font-size: 0.70rem !important; font-weight: 800 !important;
    letter-spacing: 1px !important; text-transform: uppercase !important;
    padding: 8px 10px !important; border: none !important;
}}
[data-testid="stDataFrame"] tbody tr td {{
    color: var(--ink-2) !important; font-weight: 600 !important;
    font-family: var(--body) !important;
    font-size: 0.83rem !important; padding: 6px 10px !important;
    border-bottom: 1px solid var(--surface-3) !important;
}}
[data-testid="stDataFrame"] tbody tr:nth-child(even) td {{ background: var(--surface-2) !important; }}
[data-testid="stDataFrame"] tbody tr:hover td {{ background: var(--surface) !important; }}

/* ── SCROLL BAR ── */
::-webkit-scrollbar {{ width:6px; height:6px; }}
::-webkit-scrollbar-track {{ background:var(--surface-2); }}
::-webkit-scrollbar-thumb {{ background:var(--faint); border-radius:3px; }}
::-webkit-scrollbar-thumb:hover {{ background:var(--muted); }}

/* ── STREAMLIT WIDGETS (27 Aug 2026) ──────────────────────────────────────
   config.toml themes most of these; the rules below cover what it leaves behind
   and pin anything that still renders a white surface. `no white backgrounds`
   is the requirement, so the sweep is deliberately broad. */

/* metric values were the most visible break -- dark digits on a dark ground */
[data-testid="stMetricValue"] {{ color: var(--ink) !important;
    font-family: var(--mono) !important; font-variant-numeric: tabular-nums !important; }}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {{ color: var(--muted) !important; }}
[data-testid="stMetricDelta"] {{ font-family: var(--mono) !important; }}
[data-testid="stMetric"] {{ background: var(--surface) !important;
    border: 1px solid var(--rule) !important; border-radius: var(--radius) !important;
    padding: 10px 14px !important; }}

/* radio / checkbox / label text */
[data-testid="stRadio"] label, [data-testid="stCheckbox"] label,
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] * {{ color: var(--ink-2) !important; }}

/* tables -- st.table and st.dataframe's non-canvas chrome */
[data-testid="stTable"], [data-testid="stTable"] table {{ background: var(--surface) !important;
    color: var(--ink) !important; }}
[data-testid="stTable"] th {{ background: var(--surface-2) !important; color: var(--muted) !important;
    border-bottom: 1px solid var(--rule) !important; }}
[data-testid="stTable"] td {{ border-bottom: 1px solid var(--rule-soft) !important;
    color: var(--ink-2) !important; }}
[data-testid="stDataFrame"], [data-testid="stDataFrameResizable"] {{
    background: var(--surface) !important;
    /* NOT `border` -- see the header note. use_container_width measures the box,
       and a border that changes the box makes it measure again, forever. */
    box-shadow: inset 0 0 0 1px var(--rule) !important; }}

/* expanders, tabs, inputs, code blocks -- all default to a light surface */
[data-testid="stExpander"] {{ background: var(--surface) !important;
    border: 1px solid var(--rule) !important; }}
[data-testid="stExpander"] summary {{ color: var(--ink) !important; }}
.stTabs [data-baseweb="tab-list"] {{ background: transparent !important; }}
.stTabs [data-baseweb="tab"] {{ color: var(--muted) !important; }}
.stTabs [aria-selected="true"] {{ color: var(--acc) !important; }}
input, textarea, select {{ background: var(--surface-2) !important; color: var(--ink) !important;
    border-color: var(--rule) !important; }}
pre, code {{ background: var(--surface-2) !important; color: var(--ink) !important; }}

/* the catch-all: anything still painting itself white */
[style*="background:var(--surface)"], [style*="background: var(--surface)"],
[style*="background-color: var(--surface-3)"], [style*="background-color: var(--surface-3)"],
[style*="background:#fff"], [style*="background: #fff"] {{
    background: var(--surface) !important; }}
[style*="color:var(--ink)"], [style*="color: var(--ink)"],
[style*="color:var(--ink)"], [style*="color: var(--ink)"] {{ color: var(--ink) !important; }}

/* ── BUTTONS, ROUND 2 (27 Aug 2026) ───────────────────────────────────────
   Two gaps from the first pass.

   (a) Not every button is a div[data-testid="stButton"] > button. Form submits,
       download buttons, popovers and link buttons each get their own testid, and
       none of them were in the selector list -- so they kept a white ground.

   (b) The base rule styles the button's inner <p>/<span> explicitly. A hover rule
       that only sets the BUTTON's colour therefore loses on the child, and the
       label goes dark on a dark ground -- the disappearing text. Anything styled
       on the parent has to be re-stated for the children on hover. */
/* EXCLUDE the primary kinds. Without :not(), this broad rule set a SURFACE background
   on primary buttons while the primary TEXT rule still applied --ground to the label --
   two rules disagreeing about the same button, which renders as dark-on-dark. Streamlit
   also ships newer testids (stBaseButton-*), so match on those too. */
div[data-testid="stButton"] > button:not([kind="primary"]),
div[data-testid="stFormSubmitButton"] > button:not([kind="primary"]),
div[data-testid="stDownloadButton"] > button:not([kind="primary"]),
div[data-testid="stPopover"] > button:not([kind="primary"]),
div[data-testid="stLinkButton"] > a,
button[data-testid="stBaseButton-secondary"],
button[data-testid="stBaseButton-tertiary"],
button[kind="secondary"], button[kind="tertiary"], button[kind="secondaryFormSubmit"] {{
    background: var(--surface) !important;
    border: 1.5px solid var(--rule) !important;
    color: var(--acc) !important;
}}
/* ...and state the primary pair together, so background and label can never diverge. */
button[data-testid="stBaseButton-primary"],
button[data-testid="stBaseButton-primaryFormSubmit"],
button[kind="primary"] {{
    background: var(--acc) !important;
    border: 1.5px solid var(--acc) !important;
}}
button[data-testid="stBaseButton-primary"] p,
button[data-testid="stBaseButton-primary"] span,
button[data-testid="stBaseButton-primaryFormSubmit"] p {{
    color: var(--ground) !important;
    -webkit-text-fill-color: var(--ground) !important;
}}
div[data-testid="stButton"] > button:hover,
div[data-testid="stButton"] > button:hover p,
div[data-testid="stButton"] > button:hover span,
div[data-testid="stButton"] > button:hover div,
div[data-testid="stFormSubmitButton"] > button:hover,
div[data-testid="stFormSubmitButton"] > button:hover p,
div[data-testid="stDownloadButton"] > button:hover,
div[data-testid="stDownloadButton"] > button:hover p,
button[kind="secondary"]:hover, button[kind="secondary"]:hover p,
button[kind="secondary"]:hover span {{
    background: var(--surface-2) !important;
    color: var(--acc) !important;
    -webkit-text-fill-color: var(--acc) !important;   /* Streamlit paints some labels with this */
}}
button[kind="primary"]:hover, button[kind="primary"]:hover p,
button[kind="primary"]:hover span {{
    color: var(--ground) !important;
    -webkit-text-fill-color: var(--ground) !important;
}}
/* focus must stay visible -- hover is not the only way in */
div[data-testid="stButton"] > button:focus-visible {{
    outline: 2px solid var(--acc) !important; outline-offset: 2px !important; }}

/* ── STATUS STRIP COLOUR CODING (Jay's #2) ────────────────────────────────
   The cells already carry their state in the VALUE's colour. Promoting it to the
   cell's own tint + left border means the strip reads at a glance instead of
   needing the number parsed. Driven by a class the renderer sets, so the tint can
   never disagree with the text beside it. */
.sb-cell.is-bull {{ background: var(--bull-bg) !important;
    border-left: 3px solid var(--bull) !important; }}
.sb-cell.is-bear {{ background: var(--bear-bg) !important;
    border-left: 3px solid var(--bear) !important; }}
.sb-cell.is-warn {{ background: var(--warn-bg) !important;
    border-left: 3px solid var(--warn) !important; }}
.sb-cell.is-neut {{ border-left: 3px solid var(--rule) !important; }}
{_POPOUT_SIDEBAR_HIDE}
</style>
""", unsafe_allow_html=True)


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


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    # ── TOP UNIFIED HEADER CARD — Single button-styled container ─────────────
    try:
        _ts_top = dhan_token_status() if _BROKER_OK else {"valid": False, "expires_at": "—"}
        _tk_top_valid = _ts_top.get("valid", False)
        _tk_top_col   = "var(--bull)" if _tk_top_valid else "#F87171"
        _tk_top_label = "VALID" if _tk_top_valid else "EXPIRED"
    except Exception:
        _tk_top_valid, _tk_top_col, _tk_top_label = False, "var(--faint)", "—"

    st.markdown(f"""
    <div style="margin: 8px 8px 10px 8px; padding: 12px; background: linear-gradient(135deg, var(--surface-2) 0%, var(--surface-3) 100%); border: 1.5px solid var(--rule); border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.12); color: var(--ink);">
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom: 1px solid var(--rule); padding-bottom: 8px; margin-bottom: 8px;">
        <div>
          <div style="font-family:'Rajdhani',sans-serif; font-size:1.30rem; font-weight:800; color: var(--ink); letter-spacing:1.5px; line-height:1.1;">🦁 WEINSTEIN</div>
          <div style="font-family:'JetBrains Mono',monospace; font-size:0.62rem; color: var(--acc); letter-spacing:2px; font-weight:800; margin-top:2px;">COMMANDER WEB v4.0</div>
        </div>
      </div>
      <div style="font-family:'JetBrains Mono',monospace; font-size:0.75rem; display:flex; flex-direction:column; gap:5px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span style="font-size:0.62rem; color:var(--faint); letter-spacing:1.5px; font-weight:700;">API HEALTH</span>
          <span style="font-weight:800; color:{s_color};">{sys_status}</span>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span style="font-size:0.62rem; color:var(--faint); letter-spacing:1.5px; font-weight:700;">CAPITAL</span>
          <span style="font-weight:800; color: var(--ink-2);">₹{format_inr_int(balance)}</span>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span style="font-size:0.62rem; color:var(--faint); letter-spacing:1.5px; font-weight:700;">TOKEN</span>
          <span style="font-weight:800; color:{_tk_top_col};">{_tk_top_label}</span>
        </div>
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
            # --batch suppresses run_pipeline's "Press Enter to close window"
            # prompt. launch_script uses `start cmd /k`, so the window stays open
            # for the summary either way -- but WITHOUT this the run parks on the
            # prompt holding auto_pilot.lock, and walking away after clicking would
            # block every later run exactly as the 27-Aug run did for 24 hours.
            launch_script("run_pipeline.py", "--batch")
        except Exception as _ape:
            st.error(f"Auto-Pilot launch failed: {_ape}")
        _goto_page("WATCHLIST")
        st.session_state["wf_run_trigger"] = True   # consumed by WATCHLIST page so it scrolls to the run-status section
        st.rerun()

    # ── v4.0 Grouped Navigation ─────────────────────────────────────────────
    # 23-Sep-2026 (Jay): "Journal should be an active part of web commander." JOURNAL was
    # the last EXTERNAL page — clicking it spawned a SECOND Streamlit process, in its own
    # console, on its own port, under whatever `streamlit` resolves to on PATH (Python313,
    # not the venv). It is now an in-app page like every other, rendered by
    # journal_page.render(). dhan_journal_v7.py still runs standalone if you want it.
    EXTERNAL_PAGES: dict[str, str] = {}
    # X-RAY, TV SIDECAR, PYRAMID and now JOURNAL are inline pages (no external script)

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
            ("🎯 ACTION CENTER", "ACTION CENTER"),
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

    st.markdown("""<style>
    /* mirrors [data-testid="stSidebar"] button above, so the link reads as one more nav button */
    a.sb-navlink{display:block;box-sizing:border-box;width:calc(100% - 12px);margin:2px 6px;padding:7px 12px;
      background:var(--surface);border:1.5px solid var(--rule);border-radius:8px;
      font-family:var(--body);font-size:0.82rem;font-weight:700;line-height:1.3;color:var(--acc);
      text-align:left;text-decoration:none;box-shadow:0 1px 3px rgba(14,165,233,0.10);transition:all .15s ease-in-out}
    a.sb-navlink:hover{background:var(--surface-2);color:var(--acc);border-color:var(--acc);
      box-shadow:0 0 12px rgba(59,130,246,0.45),0 2px 4px rgba(0,0,0,0.06);transform:translateX(2px)}
    a.sb-navlink .sb-navlink-ext{opacity:.6;font-size:.8em;margin-left:.25rem}
    </style>""", unsafe_allow_html=True)
    for group_label, group_pages in NAV_GROUPS:
        st.markdown(f'<div class="sb-section-lbl">{group_label}</div>', unsafe_allow_html=True)
        for display_name, page_key in group_pages:
            if page_key == "GOLDEN MATCHER":
                # 13-Sep-2026 (Jay): the Golden Matcher opens in ITS OWN WINDOW, like a
                # second screen, so the main window stays free for Risk Shield etc.
                # st.button cannot open a tab, so this entry is an anchor styled as one;
                # ?view=gm_window is the existing pop-out route (sidebar hidden, view
                # switch intact, bar-close refresh runs there). The in-window page is
                # still reachable at /?p=GOLDEN+MATCHER for anything that links to it.
                st.markdown(
                    '<a class="sb-navlink" href="/?view=gm_window" target="_blank" '
                    'title="Opens the Golden Matcher in a new window (Single Symbol / Trigger Board / Evening run)">'
                    f'{display_name} <span class="sb-navlink-ext">↗</span></a>',
                    unsafe_allow_html=True)
                continue
            btn_type = "primary" if st.session_state.page == page_key else "secondary"
            if st.button(display_name, key=f"nav_{page_key}",
                         use_container_width=True, type=btn_type):
                if page_key in EXTERNAL_PAGES:
                    launch_script(EXTERNAL_PAGES[page_key], is_streamlit=True)
                else:
                    _goto_page(page_key)
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
        _vix_col = "var(--bear)" if _vix_val > 20 else "var(--warn)" if _vix_val > 15 else "var(--bull)"
        _vix_txt = f"{_vix_val:.1f}"
    else:
        _vix_val, _vix_col, _vix_txt = 0, "var(--ink-2)", "N/A"
except Exception:
    _vix_val, _vix_col, _vix_txt = 0, "var(--ink-2)", "N/A"

_fii_txt, _fii_col = "–", "var(--ink-2)"
if _HUB_OK:
    try:
        _fii_df = fetch_fii_dii_data()
        if not _fii_df.empty and "fii_net" in _fii_df.columns:
            _fii_net = float(_fii_df["fii_net"].iloc[-1])
            _dii_net = float(_fii_df["dii_net"].iloc[-1]) if "dii_net" in _fii_df.columns else 0.0
            # Combined display per user feedback (#4): one cell, FII / DII separated by /
            _fii_arrow = "▲" if _fii_net >= 0 else "▼"
            _dii_arrow = "▲" if _dii_net >= 0 else "▼"
            _fii_part_col = "var(--bull)" if _fii_net >= 0 else "var(--bear)"
            _dii_part_col = "var(--bull)" if _dii_net >= 0 else "var(--bear)"
            # HTML inline-coloured spans so each side colours independently
            _fii_txt = (
                f"<span style='color:{_fii_part_col};'>{_fii_arrow} ₹{abs(_fii_net):,.0f}Cr</span>"
                f"<span style='color:var(--ink-2);'> / </span>"
                f"<span style='color:{_dii_part_col};'>{_dii_arrow} ₹{abs(_dii_net):,.0f}Cr</span>"
            )
            # Net colour for the cell border-tinge: dominant flow direction
            _fii_col = "var(--bull)" if (_fii_net + _dii_net) >= 0 else "var(--bear)"
    except Exception:
        pass

# Regime text — composite verdict from market_regime.compute_regime() persisted
# in regime_state.json by the daily scheduler. Replaces the prior breadth-only
# build_breadth_regime() label which could read "BULL HEALTHY" even while the
# benchmark was below 200DMA with a death cross. The breadth-only label is
# still surfaced (correctly named) in the EOD "Breadth Regime" panel.
_regime_txt, _regime_col = "–", "var(--ink-2)"
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
                _regime_col = "var(--bull)"
            elif "BEAR" in _vu or "DEFENSIVE" in _vu:
                _regime_col = "var(--bear)"
            else:
                _regime_col = "var(--warn)"
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
                _age_col = "var(--warn)" if _stale else "var(--ink-2)"
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
        _regime_col = "var(--bull)" if "BULL" in _regime_txt else "var(--bear)" if "BEAR" in _regime_txt else "var(--warn)"
    except Exception:
        pass

h_color_cls = _sb_cls(h_color)
_regime_col_cls = _sb_cls(_regime_col)
_vix_col_cls = _sb_cls(_vix_col)
w_color_cls = _sb_cls(w_color)

st.markdown(f"""
<div class="statusbar">
  <div class="sb-cell{h_color_cls}"><div class="sb-label">Nifty 500</div><div class="sb-value" style="color:{h_color};">{h_text}</div></div>
  <div class="sb-cell{_regime_col_cls}"><div class="sb-label">Market Regime</div><div class="sb-value" style="color:{_regime_col};font-size:0.75rem;">{_regime_txt}</div>{_regime_age_html}</div>
  <div class="sb-cell{_vix_col_cls}"><div class="sb-label">India VIX</div><div class="sb-value" style="color:{_vix_col};">{_vix_txt}</div></div>
  <div class="sb-cell"><div class="sb-label">FII / DII (prev)</div><div class="sb-value" style="font-size:0.74rem;">{_fii_txt}</div></div>
  <div class="sb-cell{w_color_cls}"><div class="sb-label">Risk Watchdog</div><div class="sb-value" style="color:{w_color};">{w_text}</div></div>
  <div class="sb-cell"><div class="sb-label">Deployment</div><div class="sb-value" style="color:var(--acc);">{deployed_pct}%</div></div>
  <div class="sb-cell"><div class="sb-label">Open Positions</div><div class="sb-value" style="color:var(--ink);">{open_pos}</div></div>
  <div class="sb-cell"><div class="sb-label">Total Deployed</div><div class="sb-value" style="color:var(--warn);">₹{format_inr(total_deployed_g)}</div></div>
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
            f'<div style="font-family:JetBrains Mono,monospace;font-size:0.74rem;color:var(--ink)">'
            f'{_icon} ET cookies · {_et_meta.get("cookie_count",0)} · age {_age_s}</div>',
            unsafe_allow_html=True)
    with _csb:
        _icon = "🟢" if _mc_meta.get("fresh") else ("🟡" if _mc_meta.get("present") else "🔴")
        _age  = _mc_meta.get("age_days")
        _age_s = f"{_age:.1f}d" if _age is not None else "—"
        st.markdown(
            f'<div style="font-family:JetBrains Mono,monospace;font-size:0.74rem;color:var(--ink)">'
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
        "STRONG_BUY":  "var(--bull)",
        "BUY":         "#3fb950",
        "HOLD":        "var(--warn)",
        "SELL":        "#ff7b72",
        "STRONG_SELL": "var(--bear)",
        "OTHER":       "var(--muted)",
    }
    _ACT_LBL = {
        "STRONG_BUY":  "🟢 STRONG BUY",
        "BUY":         "🟢 BUY",
        "HOLD":        "🟡 HOLD",
        "SELL":        "🔴 SELL",
        "STRONG_SELL": "🔴 STRONG SELL",
        "OTHER":       "📰 NEWS",
    }
    _SRC_COL = {"Economic Times": "#ff7b72", "Moneycontrol": "var(--acc)"}

    # 4-column grid
    _N_COLS = 4
    for _i in range(0, len(items), _N_COLS):
        _row = items[_i:_i + _N_COLS]
        _cols = st.columns(_N_COLS, gap="small")
        for _col, _it in zip(_cols, _row):
            _act    = _it.get("action") or "OTHER"
            _act_col = _ACT_COL.get(_act, "var(--muted)")
            _act_lbl = _ACT_LBL.get(_act, _act)
            _src     = _it.get("source", "")
            _src_col = _SRC_COL.get(_src, "var(--muted)")
            _brk     = _it.get("brokerage") or ""
            _ttl     = (_it.get("title") or "").replace("<","&lt;").replace(">","&gt;")
            _url     = _it.get("url") or "#"
            _ts      = (_it.get("fetched_at") or "")[:16]
            _stocks  = _it.get("stocks_mentioned") or []
            _stk_html = ""
            if _stocks:
                _stk_pills = " ".join(
                    f'<span style="background:#1c2937;color:var(--acc);padding:1px 6px;'
                    f'border-radius:8px;font-size:0.62rem;margin-right:3px">{s}</span>'
                    for s in _stocks[:4]
                )
                _stk_html = f'<div style="margin-top:5px">{_stk_pills}</div>'
            _brk_html = (
                f'<div style="font-size:0.66rem;color:var(--faint);margin-top:4px">'
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
                    f'<div style="font-size:0.78rem;color:var(--ink);line-height:1.3">'
                    f'<a href="{_url}" target="_blank" '
                    f'style="color:var(--ink);text-decoration:none">{_ttl}</a></div>'
                    f'{_brk_html}{_stk_html}'
                    f'<div style="font-size:0.58rem;color:var(--ink);margin-top:6px">{_ts}</div>'
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
        f'ET: <b style="color:{"var(--bull)" if _et_ok else "var(--bear)"}">'
        f'{"✓ live" if _et_ok else "✗ down"}</b></div>',
        unsafe_allow_html=True)
    _hc2.markdown(
        f'<div style="font-family:JetBrains Mono,monospace;font-size:0.78rem">'
        f'MC: <b style="color:{"var(--bull)" if _mc_ok else "var(--bear)"}">'
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

def _render_ai_report(text: str, header_color: str = "var(--warn)"):
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
              <div style="font-family:'Inter',sans-serif;font-size:0.85rem;color:var(--ink);
                          line-height:1.75;">{_body_html}</div>
            </div>""", unsafe_allow_html=True)
    else:
        # Fallback: plain text (no === markers found)
        _safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        st.markdown(f'<div style="font-size:0.85rem;color:var(--ink);line-height:1.75;'
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
        <div style="background:#3d0c0c;border:2px solid var(--bear);border-radius:8px;
                    padding:14px 20px;margin-bottom:14px;">
          <div style="font-family:'Rajdhani',sans-serif;font-size:1.1rem;font-weight:700;
                      color:var(--bear);letter-spacing:1px;">
            🚨 DHAN TOKEN INVALID — AUTO-REFRESH FAILED</div>
          <div style="font-family:'Inter',sans-serif;font-size:0.85rem;color:var(--bear);
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




def row(label: str, value: str, status: str, note: str = ""):
    """Render a single colored checklist row. status in pass/watch/fail/na."""
    rhs = f"{value}" + (f"  <span style='opacity:.65'>· {note}</span>" if note else "")
    st.markdown(f"<div class='chk {status}'><b>{label}</b><span>{rhs}</span></div>",
                unsafe_allow_html=True)


















# Golden Matcher user settings (capital / risk%) — persisted across restarts.






def _cq_build_now():
    """Capital Queue build with the two live inputs it cannot fetch itself: the Dhan
    cash balance (None when the broker is not answering - shown as unknown, never 0)
    and whether EXIT/REDUCE/TRIM proceeds count as money (gm_settings, default OFF).
    Jay, 25-Sep-2026: in a deep recovery tape he is holding, not exiting."""
    import capital_queue as _cq
    _cash = None
    try:
        if sys_status == "SYSTEM ONLINE":
            _cash = float(balance)
    except Exception:
        _cash = None
    _cls = None
    try:
        _pc = st.session_state.get("pyramid_classifications")
        if _pc is not None and not _pc.empty and "classification" in _pc.columns:
            _cls = dict(zip(_pc["symbol"].astype(str).str.upper(), _pc["classification"]))
    except Exception as e:
        _gm_logger.warning(f"capital queue: live ladder classes unavailable, using 16:30 snapshot: {e}")
    return _cq.build(cash=_cash, count_exits=bool(_gm_settings().get("queue_count_exits", False)),
                     classes=_cls)


def _cq_exit_toggle(key):
    """One persisted switch for both queue surfaces (board expander, Risk Shield tab)."""
    cur = bool(_gm_settings().get("queue_count_exits", False))
    v = st.checkbox("Count EXIT / REDUCE / TRIM proceeds as available", value=cur, key=key,
                    help="OFF (default): the queue is funded from Dhan cash only; exit proceeds are "
                         "shown as 'if taken'. ON: exits first, then the REDUCE/TRIM share, then cash.")
    if v != cur:
        _gm_settings_save(queue_count_exits=v)
        st.session_state.pop("cq_res", None)








# The GM quotes entry/SL/T1 at CURRENT price (compute_workflow: entry = cmp_px). It does
# NOT latch the bar the PA trigger fired on — S4 v6.0 does (trigBar/trigCls). The old
# wording promised "the trigger bar's close" while the numbers beside it were live price,
# fix is to say where the price comes from.

def _pine_row_style(state: str) -> tuple[str, str, str, str]:
    """Mirror the exact Section4_Entry_Trigger_v5.9.pine panel table colors.
    Returns (label_bg, value_bg, text_color, border_color).
    """
    st = str(state).lower() if state else "na"
    if st in ("pass", "bull", "ok", "go", "buy", "aligned", "healthy", "leading"):
        return "#4DB6AC", "#4DB6AC", "var(--ground)", "#26A69A"  # Pine Mint Teal
    elif st in ("watch", "warn", "caution", "hold", "misaligned", "weakening", "losing steam", "easing"):
        return "var(--warn)", "var(--warn)", "var(--ground)", "#F57C00"  # Pine Warm Orange
    elif st in ("fail", "bear", "stop", "avoid", "lagging", "deepening", "block"):
        return "#E57373", "#E57373", "var(--ground)", "#D32F2F"  # Pine Salmon Red
    elif st in ("blue", "recovery", "rev", "improving", "strengthening"):
        return "#64B5F6", "#64B5F6", "var(--ground)", "#1976D2"  # Pine Soft Blue
    elif st in ("purple", "special"):
        return "#BA68C8", "#BA68C8", "var(--ground)", "#7B1FA2"  # Pine Purple
    else:
        return "#86A2B3", "#9CB5C4", "var(--ground)", "#546E7A"  # Pine Cool Slate

def _soft_style(state: str) -> tuple[str, str]:
    lbl_bg, val_bg, text_col, _ = _pine_row_style(state)
    return val_bg, text_col

def _sc(state: str) -> str:
    bg, _ = _soft_style(state)
    return bg

def _soft_badge(value: str, state: str) -> str:
    lbl_bg, val_bg, text_col, bdr_col = _pine_row_style(state)
    if state == "na" and value in ("na", "n/a", "—", ""):
        return "<span style='color:var(--ink);font-size:11px;font-weight:800;'>—</span>"
    return (f"<span style='background:{val_bg};color:{text_col};padding:2.5px 8px;"
            f"border-radius:4px;font-weight:800;font-size:11px;border:1px solid {bdr_col};"
            f"display:inline-block;letter-spacing:0.2px;'>{value}</span>")

def _gauge(label, value, vmin, vmax, gradient, state, valtxt) -> str:
    lbl_bg, val_bg, text_col, bdr_col = _pine_row_style(state)
    if value is None or (isinstance(value, float) and math.isnan(value)):
        pct = 0.0
        badge_html = "<span style='color:var(--ink);font-size:11px;font-weight:800;'>—</span>"
    else:
        pct = max(0.0, min(100.0, (float(value) - vmin) / (vmax - vmin) * 100.0))
        badge_html = (f"<span style='background:{val_bg};color:{text_col};padding:2px 8px;"
                      f"border-radius:4px;font-weight:800;font-size:11px;border:1px solid {bdr_col};'>{valtxt}</span>")

    return (f"<div style='margin:6px 0;'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;font-size:11.5px;margin-bottom:4px;'>"
            f"<span style='color:var(--ink);font-weight:800;'>{label}</span>"
            f"{badge_html}</div>"
            f"<div style='position:relative;height:9px;border-radius:6px;background:var(--rule);overflow:visible;border:1px solid var(--faint);'>"
            f"<div style='position:absolute;left:0;top:0;height:100%;width:{pct:.1f}%;border-radius:6px;"
            f"background:{gradient};opacity:0.95;'></div>"
            f"<div style='position:absolute;left:calc({pct:.1f}% - 3px);top:-3px;width:7px;height:15px;"
            f"background: var(--surface-3);box-shadow:0 1px 4px rgba(0,0,0,0.4);border-radius:3px;'></div></div></div>")

def _crit(ok: bool, label: str) -> str:
    lbl_bg, val_bg, text_col, bdr_col = _pine_row_style("pass" if ok else "fail")
    mk = "✓" if ok else "✗"
    return (f"<div style='display:flex;align-items:center;gap:6px;font-size:11.5px;margin:2.5px 0;'>"
            f"<span style='flex:0 0 16px;width:16px;height:16px;border-radius:50%;background:{val_bg};"
            f"color:{text_col};border:1px solid {bdr_col};display:inline-flex;align-items:center;justify-content:center;font-size:10px;"
            f"font-weight:900'>{mk}</span><span style='color:var(--ink);font-weight:700;'>{label}</span></div>")

def _pill(state: str, label: str, val: str) -> str:
    lbl_bg, val_bg, text_col, bdr_col = _pine_row_style(state)
    return (f"<div style='background:{val_bg};border:1px solid {bdr_col};border-left:4px solid {bdr_col};border-radius:5px;padding:5px 8px;margin-bottom:3px;box-shadow:0 1px 2px rgba(0,0,0,0.05);'>"
            f"<div style='color:var(--ink);font-size:9.5px;text-transform:uppercase;letter-spacing:.4px;font-weight:800;'>{label}</div>"
            f"<div style='color:var(--ink);font-size:11.5px;font-weight:800;'>{val}</div></div>")

def _donut(passed: int, total: int) -> str:
    r = 22.0; circ = 2 * math.pi * r
    frac = (passed / total) if total else 0
    lbl_bg, val_bg, text_col, bdr_col = _pine_row_style("pass" if frac >= 0.75 else ("watch" if frac >= 0.5 else "fail"))
    off = circ * (1 - frac)
    return (f"<svg width='54' height='54' viewBox='0 0 52 52'>"
            f"<circle cx='26' cy='26' r='{r}' fill='none' stroke='var(--rule)' stroke-width='6'/>"
            f"<circle cx='26' cy='26' r='{r}' fill='none' stroke='{bdr_col}' stroke-width='6'"
            f" stroke-dasharray='{circ:.1f}' stroke-dashoffset='{off:.1f}' stroke-linecap='round'"
            f" transform='rotate(-90 26 26)'/>"
            f"<text x='26' y='31' text-anchor='middle' font-size='13' font-weight='900' fill='var(--ink)'>{passed}/{total}</text></svg>")

# (dead first _range_bar removed 25-Sep-2026: a second definition below replaced it
#  before any call - found by the core-extraction trap check)

def card(title: str, rows, accent: str = "var(--acc)", chip_text: str = None,
         chip_color: str = None) -> str:
    """Compact table card mirroring Section4_Entry_Trigger_v5.9.pine panel table.
    Every row is a full-width colored background row with crisp 1px borders and bold dark text,
    matching the S4 Pine panel table.
    """
    body = ""
    for label, value, state in rows:
        lbl_bg, val_bg, text_col, bdr_col = _pine_row_style(state)
        val_str = str(value)
        body += (f"<div style='display:grid;grid-template-columns:38% 62%;margin-bottom:1px;border:1px solid var(--muted);font-size:11.5px;font-family:\"Inter\",sans-serif;'>"
                 f"<div style='background:{lbl_bg};color:{text_col};font-weight:700;padding:4.5px 8px;border-right:1px solid var(--muted);display:flex;align-items:center;'>{label}</div>"
                 f"<div style='background:{val_bg};color:{text_col};font-weight:800;padding:4.5px 8px;display:flex;align-items:center;justify-content:flex-start;'>{val_str}</div></div>")

    hdr_bg = "var(--acc)"
    chip = ""
    if chip_text is not None:
        chip = (f"<span style='float:right;background: var(--surface-2);color: var(--ink);padding:1.5px 9px;"
                f"border-radius:4px;font-weight:800;font-size:11px;border:1px solid var(--muted);'>{chip_text}</span>")
    else:
        evaluated = [s for _, _, s in rows if s in ("pass", "watch", "fail")]
        passed = sum(1 for s in evaluated if s == "pass")
        total = len(evaluated)
        if total:
            frac = passed / total
            badge_st = "pass" if frac >= 0.7 else ("watch" if frac >= 0.4 else "fail")
            _, val_bg, text_col, _ = _pine_row_style(badge_st)
            chip = (f"<span style='float:right;background:{val_bg};color:{text_col};padding:1.5px 9px;"
                    f"border-radius:4px;font-weight:800;font-size:11px;border:1px solid var(--muted);'>{passed}/{total}</span>")

    return (f"<div style='background:var(--surface);border:1.5px solid var(--muted);border-radius:6px;overflow:hidden;margin-bottom:12px;box-shadow:0 2px 6px rgba(0,0,0,0.08);'>"
            f"<div style='background:{hdr_bg};color: var(--ink);font-weight:800;font-size:11.5px;"
            f"letter-spacing:.5px;padding:7px 12px;border-bottom:1.5px solid var(--muted);'>{title}{chip}</div>"
            f"<div style='padding:4px;background:var(--rule);'>{body}</div></div>")




def _render_entry_method_selector(key: str):
    """Render the entry-method selector (buy-stop vs retest) on ANY GM view. The
    SETTING is global — persisted to gm_settings.json and read by _gm_entry_method()
    everywhere — so all views already FOLLOW it; this just exposes the widget on more
    surfaces (item 11). Unique `key` per view avoids a Streamlit duplicate-key clash;
    changing it anywhere writes the shared setting. Only the fill WORDING changes."""
    _opts = ["Buy-stop (confirmation)", "Retest (pullback limit)"]
    _idx = 1 if _gm_entry_method() == "retest" else 0
    _sel = st.selectbox(
        "🎯 Entry method", _opts, index=_idx, key=key,
        help="How the Plan / guided-execution tells you to ENTER once a trigger fires "
             "(mirrors the S4 indicator's v4.8 toggle). Buy-stop = above the confirmed "
             "bar's high (house doctrine, dodges the false-breakout trap). Retest = "
             "buy-limit at the trigger close on the pullback (backtest-better matched "
             "alpha, but the sim can't see false-breakout whipsaw — a live TRIAL). "
             "Only the fill instruction changes; the trigger is identical. This setting "
             "is GLOBAL — it applies to every GM view.")
    _val = "retest" if _sel == _opts[1] else "buystop"
    if _val != _gm_settings().get("entry_method", "retest"):
        _gm_settings_save(entry_method=_val)
    return _val


# ----------------------------------------------------------------------------------------
# Graphical primitives (pure HTML/SVG — no extra deps)
# ----------------------------------------------------------------------------------------
# S4 Entry Trigger v5.9 & Weinstein Dashboard Unified Palette (Financial Terminal Light)
# ----------------------------------------------------------------------------------------
C_SOFT_PASS   = "var(--bull-rule)"  # Vibrant Soft Emerald (Pass / Bull / OK / GO / Buy)
C_TEXT_PASS   = "#064E3B"  # Deep Emerald Text (Bold)
C_SOFT_WARN   = "var(--warn-rule)"  # Vibrant Soft Amber (Watch / Caution / Hold / Warning)
C_TEXT_WARN   = "#78350F"  # Deep Amber Text (Bold)
C_SOFT_FAIL   = "var(--bear-bg)"  # Vibrant Soft Rose (Fail / Bear / Stop / Avoid)
C_TEXT_FAIL   = "var(--bear)"  # Deep Rose Text (Bold)
C_SOFT_BLUE   = "var(--acc-bg)"  # Vibrant Soft Sky Blue (Recovery / Improving / Blue)
C_TEXT_BLUE   = "var(--acc)"  # Deep Blue Text (Bold)
C_SOFT_PURP   = "var(--acc-bg)"  # Vibrant Soft Purple (Special / Tier Bonus)
C_TEXT_PURP   = "var(--acc)"  # Deep Purple Text (Bold)
C_SOFT_NEUT   = "var(--surface-3)"  # Slate Container
C_SOFT_TEXT   = "var(--ink)"  # Deep Charcoal Slate Text
C_HDR_BG      = "var(--surface-3)"  # header band -- a RAISED surface, not inverted ink
C_CARD_BG     = "var(--surface)"  # Crisp White Card Container
C_CARD_BORDER = "var(--rule)"  # card border -- a RULE, not a text tone

def _crit(ok: bool, label: str) -> str:
    bg, fg = _soft_style("pass" if ok else "fail")
    mk = "✓" if ok else "✗"
    return (f"<div style='display:flex;align-items:center;gap:6px;font-size:11px;margin:2px 0;'>"
            f"<span style='flex:0 0 15px;width:15px;height:15px;border-radius:50%;background:{bg};"
            f"color:{fg};display:inline-flex;align-items:center;justify-content:center;font-size:9.5px;"
            f"font-weight:800'>{mk}</span><span style='color:var(--ink-2);font-weight:600;'>{label}</span></div>")

def _pill(state: str, label: str, val: str) -> str:
    bg, fg = _soft_style(state)
    return (f"<div style='background:{bg}80;border-left:3px solid {fg};border-radius:5px;padding:4px 8px;margin-bottom:2px;'>"
            f"<div style='color:var(--muted);font-size:9.5px;text-transform:uppercase;letter-spacing:.3px;font-weight:600;'>{label}</div>"
            f"<div style='color:{fg};font-size:11.5px;font-weight:700;'>{val}</div></div>")

def _donut(passed: int, total: int) -> str:
    r = 22.0; circ = 2 * math.pi * r
    frac = (passed / total) if total else 0
    bg, fg = _soft_style("pass" if frac >= 0.75 else ("watch" if frac >= 0.5 else "fail"))
    off = circ * (1 - frac)
    return (f"<svg width='54' height='54' viewBox='0 0 52 52'>"
            f"<circle cx='26' cy='26' r='{r}' fill='none' stroke='var(--rule)' stroke-width='6'/>"
            f"<circle cx='26' cy='26' r='{r}' fill='none' stroke='{fg}' stroke-width='6'"
            f" stroke-dasharray='{circ:.1f}' stroke-dashoffset='{off:.1f}' stroke-linecap='round'"
            f" transform='rotate(-90 26 26)'/>"
            f"<text x='26' y='31' text-anchor='middle' font-size='13' font-weight='800' fill='{fg}'>{passed}/{total}</text></svg>")







# (render_decision / render_pine_mirror removed 9-Jul-2026 — dead code, never
#  invoked; compute_decision remains live as the STRUCTURE card's gate source.)


# ----------------------------------------------------------------------------------------
# Panel-mirror cards (replace the 5 Pine panel tables)
# ----------------------------------------------------------------------------------------
# Per-section scores collected by card() on each render pass — feeds the
# score strip at the top of the Full Metrics expander (v2, 2026-07-03: every
# panel-mirror card now carries a pass-count score like the WCL FINAL SCORE).
SECTION_SCORES: dict = {}


def card(title: str, rows, accent: str = "var(--acc)", chip_text: str = None,
         chip_color: str = None) -> str:
    """Compact label:value table card mirroring Section4_Entry_Trigger_v5.9.pine panel in Light Mode.
    Every row is a full-width colored background row with crisp borders and bold dark text,
    matching the S4 Pine panel table color palette.
    """
    body = ""
    for label, value, state in rows:
        lbl_bg, val_bg, text_col, bdr_col = _pine_row_style(state)
        val_str = str(value)
        body += (f"<div style='display:flex;justify-content:space-between;align-items:center;"
                 f"background:{val_bg};color:{text_col};border:1px solid {bdr_col};border-left:4px solid {bdr_col};"
                 f"padding:5px 10px;margin-bottom:3px;border-radius:4px;font-size:11.5px;font-family:\"Inter\",sans-serif;'>"
                 f"<span style='font-weight:700;'>{label}</span>"
                 f"<span style='font-weight:800;text-align:right;'>{val_str}</span></div>")

    if chip_text is not None:
        hdr_bg = C_HDR_BG
        c_bg = chip_color or "rgba(255,255,255,0.2)"
        chip = (f"<span style='float:right;background:{c_bg};color: var(--ink);padding:1.5px 9px;"
                f"border-radius:10px;font-weight:800;font-size:10px;'>{chip_text}</span>")
        return (f"<div style='background:var(--surface);border:1.5px solid var(--faint);border-radius:8px;overflow:hidden;margin-bottom:12px;box-shadow:0 2px 6px rgba(0,0,0,0.06);'>"
                f"<div style='background:{hdr_bg};color: var(--ink);font-weight:800;font-size:11.5px;"
                f"letter-spacing:.5px;padding:7px 12px;border-bottom:1px solid var(--rule);'>{title}{chip}</div>"
                f"<div style='padding:6px;background:var(--surface-2);'>{body}</div></div>")

    evaluated = [s for _, _, s in rows if s in ("pass", "watch", "fail")]
    passed = sum(1 for s in evaluated if s == "pass")
    total = len(evaluated)
    chip = ""
    hdr_bg = C_HDR_BG
    if total:
        frac = passed / total
        scol = C_TEXT_PASS if frac >= 0.7 else (C_TEXT_WARN if frac >= 0.4 else C_TEXT_FAIL)
        short = title.split("·")[0].strip().title()
        SECTION_SCORES[short] = (passed, total, scol)
        badge_st = "pass" if frac >= 0.7 else ("watch" if frac >= 0.4 else "fail")
        c_bg, c_fg = _soft_style(badge_st)
        chip = (f"<span style='float:right;background:{c_bg};color:{c_fg};padding:1.5px 9px;"
                f"border-radius:10px;font-weight:800;font-size:10px;'>{passed}/{total}</span>")

    return (f"<div style='background:var(--surface);border:1.5px solid var(--faint);border-radius:8px;overflow:hidden;margin-bottom:12px;box-shadow:0 2px 6px rgba(0,0,0,0.06);'>"
            f"<div style='background:{hdr_bg};color: var(--ink);font-weight:800;font-size:11.5px;"
            f"letter-spacing:.5px;padding:7px 12px;border-bottom:1px solid var(--rule);'>{title}{chip}</div>"
            f"<div style='padding:6px;background:var(--surface-2);'>{body}</div></div>")


def render_score_strip(mpass: int = None) -> str:
    """One-glance chips of every section score using S4 soft palette in Light Mode."""
    chips = ""
    if mpass is not None:
        bg, fg = _soft_style("pass" if mpass >= 6 else ("watch" if mpass >= 4 else "fail"))
        chips += (f"<span style='background:{bg};color:{fg};border-radius:6px;"
                  f"padding:3.5px 11px;font-size:11.5px;font-weight:700;letter-spacing:0.2px;'>Minervini {mpass}/8</span>")
    for name, (p, t, col) in SECTION_SCORES.items():
        disp = f"{p}/{t}" if t else str(p)
        st = "pass" if col in (C_SOFT_PASS, C_TEXT_PASS, "#26A69A", "#1B7A6E") else ("watch" if col in (C_SOFT_WARN, C_TEXT_WARN, "var(--warn)", "#C77700") else "fail")
        bg, fg = _soft_style(st)
        chips += (f"<span style='background:{bg};color:{fg};border-radius:6px;"
                  f"padding:3.5px 11px;font-size:11.5px;font-weight:700;letter-spacing:0.2px;'>{name} {disp}</span>")
    return (f"<div style='display:flex;gap:8px;flex-wrap:wrap;align-items:center;"
            f"margin:4px 0 14px;background:var(--surface);padding:10px 14px;border-radius:8px;"
            f"border:1px solid var(--rule);box-shadow:0 1px 3px rgba(0,0,0,0.05);'>{chips}</div>")




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
    _scol = "#26A69A" if _frac >= 0.7 else ("var(--warn)" if _frac >= 0.4 else "#EF5350")
    _hdr = "#1B7A6E" if _frac >= 0.7 else ("#C77700" if _frac >= 0.4 else "#C62828")
    SECTION_SCORES["Bull Screener"] = (passed, total, _scol)
    return card(f"BULL SCREENER · POS-BO gates", rows, "#00695C",
                chip_text=f"{passed}/{total}", chip_color=_hdr)


def section_context(rec, ctx, cmp_px) -> str:
    """Mirror of Section 4 v5.0 & WCL v1.2 Context Layers — SMC / Wyckoff / Volume Profile / Setup Detector."""
    # 28-Jul-2026: WCL is now the REAL Pine calculation (wcl_context.py), computed once
    # in the ctx builder and read here. `_w` is None only when that failed or the frame
    # was too thin — in which case we fall back to the legacy proxies below and SAY SO,
    # rather than printing proxy numbers under a label that claims Pine parity.
    _w = _g(ctx, "wcl") if isinstance(_g(ctx, "wcl"), dict) else None
    adir = str(_g(rec, "Active_Dir", default="")).upper()
    smc = "BULLISH" if adir.startswith("UP") else "BEARISH" if adir.startswith("DOWN") else "NEUTRAL"
    if _w:
        smc = "BULLISH" if _w["smc"]["trend_up"] else "BEARISH"
    stage = str(_g(rec, "Stage", default=""))
    bfvg = _g(ctx, "bull_fvg", default=0); rfvg = _g(ctx, "bear_fvg", default=0)
    wyk = ("ACCUMULATION" if (_g(ctx, "acc_ok") and ("1" in stage or "2" in stage))
           else "DISTRIBUTION" if "3" in stage else "NEUTRAL")
    poc = _g(ctx, "poc"); vah = _g(ctx, "vah"); val = _g(ctx, "val")
    vp_pos_raw = _g(ctx, "vp_pos", default="—"); dpoc = _g(ctx, "dist_poc")
    
    # Detailed VP position matching S4 v5.0
    if vp_pos_raw == "ABOVE VAH":
        vp_pos = "✓ ABOVE VAH"
        vp_s = 3
    elif vp_pos_raw == "INSIDE VA":
        if (dpoc or 0) >= 0:
            vp_pos = "✓ IN VA (upper)"
            vp_s = 1
        else:
            vp_pos = "✗ IN VA (lower)"
            vp_s = -1
    elif vp_pos_raw == "BELOW VAL":
        vp_pos = "✗ BELOW VAL"
        vp_s = -3
    else:
        vp_pos = "—"
        vp_s = 0

    if _w:
        # Real Pine values. Wyckoff carries an EVENT and a decayed tier, so the bias
        # row can finally name what fired (SOS / Spring / SOW …) instead of inferring
        # a bias from Stage + acc_ok.
        wyk = _w["wyckoff"]["bias"]
        wyk_s = _w["wyckoff"]["score_comp"]
        smc_s = _w["smc"]["score"]
        stg_s = _w["stage_score"]
        wcl_total = _w["total_final"]
        wcl_band = _w["band"]
        choch_cnt = _w["choch_count_20"]
        struct_str, struct_status = _w["struct"], _w["struct_status"]
        setup_str = _w["setup"]
        wyk_note = f" · {_w['wyckoff']['event']} ({_w['wyckoff']['age_bars']}b)" \
            if _w["wyckoff"]["event"] != "—" else ""
    else:
        wyk_s = 3 if wyk == "ACCUMULATION" else (-3 if wyk == "DISTRIBUTION" else 0)
        smc_s = 2 if smc == "BULLISH" else (-2 if smc == "BEARISH" else 0)
        stg_s = 3 if "2" in stage else (1 if "1" in stage else (-1 if "3" in stage else -3))
        wcl_total = wyk_s + vp_s + smc_s + stg_s
        wcl_band = "STRONG BULL" if wcl_total >= 9 else ("BULL" if wcl_total >= 4 else ("NEUTRAL" if wcl_total >= -3 else ("CAUTION" if wcl_total >= -6 else "BEAR")))
        choch_cnt = 0
        struct_str, struct_status = "n/a (proxy mode)", "na"
        setup_str = "● NONE"
        wyk_note = ""
    if not _w:
        # Legacy proxy ladder — ONLY when the real engine is unavailable. Note it never
        # detected a Spring; it inferred one from Stage + acc_ok, which is why a name
        # could read "S2 — Spring/LPS Reversal" with no spring anywhere on the chart.
        if wyk == "ACCUMULATION" and "2" in stage and vp_s >= 1 and wcl_total >= 4:
            setup_str = "✓ S2 — Spring/LPS Reversal (proxy)"
        elif vp_s >= 1 and wyk == "ACCUMULATION" and wcl_total >= 2:
            setup_str = "✓ S1 — OB Retest + VP Support (proxy)"
        elif "2" in stage and vp_s == 3:
            setup_str = "✓ S5 — Stage 2 Continuation > VAH (proxy)"
        elif wyk == "DISTRIBUTION" and wcl_total <= -3:
            setup_str = "✗ S7 — Distribution Breakdown (proxy)"

    wcl_val_disp = f"{wcl_band} ({wcl_total:+d}) · {setup_str}"

    rows = [
        ("WCL Context", wcl_val_disp, "pass" if "BULL" in wcl_band else ("watch" if wcl_band == "NEUTRAL" else "fail")),
        ("Structure Health", struct_str, struct_status),
        ("Volume Profile", f"{vp_pos} (POC {inr(poc)})" if poc else vp_pos, "pass" if "✓" in vp_pos else "watch" if "upper" in vp_pos else "fail"),
        ("· components", f"Wyk:{wyk_s:+d} VP:{vp_s:+d} SMC:{smc_s:+d} Stg:{stg_s:+d}", "na"),
        ("SMC Trend", smc + (f" · {_w['smc']['last_event']} ({_w['smc']['age_bars']}b)" if (_w and _w['smc']['last_event'] != '—') else ""),
         "pass" if smc == "BULLISH" else "fail" if smc == "BEARISH" else "na"),
        ("Open FVGs", f"Bull {bfvg} · Bear {rfvg}", "pass" if bfvg >= rfvg else "watch"),
        ("Wyckoff Bias", wyk + wyk_note, "pass" if wyk == "ACCUMULATION" else "fail" if wyk == "DISTRIBUTION" else "na"),
        ("VAH / VAL", (inr(vah) + " / " + inr(val)) if (vah and val) else "—", "na"),
        ("Dist to POC", fnum(dpoc, 1, "%"), "na"),
    ]
    _wtf = (_w or {}).get("tf", "Daily")
    return card("CONTEXT LAYERS · SMC / VP / Wyckoff" + (f" ({_wtf} · S4 parity)" if _w else " (PROXY — engine unavailable)"), rows, "#6A1B9A")


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


def section_recovery(rec_r, cmp_px, canon_stage=None) -> str:
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
        # Reconciled to ONE canonical weekly stage (the shared ctx computation) so a
        # stock never shows two contradicting stages across panels (item 16). Falls
        # back to the recovery row's own stage only when no canonical is passed.
        ("Stage (weekly)", f"Stage {canon_stage if canon_stage not in (None, '', '—') else (_stg_digit(_g(rec_r, 'Weinstein_Stage', default='')) or '—')}", "na"),
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


def _recovery_plan_card(wf) -> str:
    """The disciplined recovery plan (GM Step-6: structural SL + R:R) — shown on the
    recovery path instead of the bull catalyst geometry, and instead of the raw
    recovery-screener levels (whose SL sat near the 52-week low and whose T2 could
    invert below T1). Uses the SAME plan_entry/plan_sl/plan_t1 the guided-execution
    sizer uses, so the plan card and the sizer can never disagree."""
    e = wf.get("plan_entry"); s = wf.get("plan_sl"); t1 = wf.get("plan_t1")
    if not (e and s and e > s):
        return card("TRADE GEOMETRY · recovery plan",
                    [("Status", "No disciplined level yet", "na"),
                     ("Levels", "await a trigger / location", "na")], "#00838F")
    slp = (e - s) / e * 100.0
    rr = ((t1 - e) / (e - s)) if (t1 and t1 > e) else None
    rows = [
        ("Entry", inr(e), "na"),
        ("Stop-Loss", f"{inr(s)} (-{slp:.1f}%, structural)", "fail"),
    ]
    if t1:
        rows.append(("Target 1", inr(t1) + (f" ({fnum(rr,1)}R)" if rr is not None else ""), "pass"))
    return card("TRADE GEOMETRY · recovery plan", rows, "#00838F")


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
    # /7, not /9: F6 (current ratio) and F8 (gross margin) are not derivable from
    # screener.in, so they never resolve and counting them was two free failures.
    if piot is not None: rows.append(("Piotroski", fnum(piot, 0, "/7"), "pass" if piot >= 6 else "watch" if piot >= 4 else "fail"))
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


# Step-4 LOCATION thresholds ("room" rule) — tunable. R:R is the real room; EMA20
# extension is the "not-chasing" gate. EMA20 is a DAILY anchor and acts as SUPPORT
# when price is above it, RESISTANCE when below. LOCATION is STATUS — it NEVER
# vetoes a fired Step-5 trigger; it only decides ARMED vs WAIT-FOR-PULLBACK when
# there is no trigger yet.
# Recovery "not chased" ceiling: max % above EMA20 before the bounce counts as
# extended. P0 fix (14-Jul-2026): this constant was DEAD — the live gate hardcoded
# 8.0 inline while this documented 6.0. Jay's call: keep 8% (the behavior he has
# actually been trading); the gate + its display metric now read THIS constant.
# P1 (12 Jul 2026) — INHERITED QUALIFICATION: when a name carries a source archetype
# (Chartink+Screener already qualified it), trust Context+Quality, run only a
# still-valid break-down guard, and TIME it (don't re-screen). Flag lets us A/B
# against the legacy re-qualification funnel. ON = the redesign; OFF = old behaviour.
# IZE ZONE ENGINE (18-Jul-2026) — port of the S4 Pine leg-base-leg demand/supply
# zone engine (zone_engine.py) into the GM LOCATION gate, replacing the OB/FVG/pivot
# PROXY's coarser read with the SAME zones the S4 chart draws (the documented
# "location-accuracy ceiling" fix). ON (24-Jul-2026): the location gate is driven by
# the validated S4 zone logic (zone_engine — pattern RBR/DBR/RBD/DBD + structural
# PvH/PvL + S/R levels + AVWAP, D/W/M), REPLACING the old OB/FVG/pivot proxy. Validated
# against live S4 v4.8 on MANAPPURAM + ENDURANCE (Endurance matched S4's panel exactly,
# 6 DZ / 3 SZ). The proxy call is kept for its zone/level DATA but no longer decides
# at_support. If the IZE engine errors, the proxy result stands as a safety fallback.
GM_USE_IZE_ZONES = True
# Structural-vs-catalyst-scan archetype sets — SINGLE SOURCE in gm_trigger_board
# (next to the archetype names), deliberately NO fallback literal: a silent local
# copy is exactly the rename-drift bug this import removes (P0, 14-Jul-2026).
# gm_trigger_board is import-light (os/json) and already a hard GM dependency.
from gm_trigger_board import (STRUCTURAL_BULL_ARCHETYPES,
                              STRUCTURAL_RECOVERY_ARCHETYPES)
# P1 (14-Jul-2026): shared GM logger — every previously-swallowed exception in the
# GM region now lands in logs/gm_errors.log (same safe fallbacks, but RECORDED).
from gm_log import gm_log as _gm_logger


# ----------------------------------------------------------------------------------------
# STRUCTURAL PLAN SL  (twin of the S4 Pine v3.0 Plan fix)
# ----------------------------------------------------------------------------------------
# ── STOP = S4's LADDER (24-Sep-2026, AUD-PAR-10) ─────────────────────────────────────
# The board used to stop on the OB/FVG/pivot PROXY (D+W), 1% buffer, 3xATR->2.5xATR cap,
# on the DAILY ATR -- so board and chart printed different stops, R and targets for the
# same trigger. This is S4's chain (Section 4 v10.x, the `if go_v` plan block), read on
# the TRIGGER TF exactly as S4 reads it on the chart:
#   in-zone distal (inside or reacting, best recency score, any TF incl. the chart TF)
#   -> nearest demand distal below (any kind)  -> 10-bar swing low on the chart TF
#   buffer 0.5% below the level; no level below entry -> entry - mult x ATR;
#   cap at mult x ATR, mult = 2.5 (swing) / 4.0 (positional), ATR = Wilder 14 on the
#   chart TF (S4 `chart_atr = ta.atr(14)`).
# Trade type is S4's `tt_swing`: ATR% > 4 OR > 30% off the 52W high OR below the 200-DMA.
# ATR% is the CHART-TF ATR, as S4 computes it (its tooltip says "daily"; flagged
# AUD-PINE-09) -- mirrored, not corrected, so the board shows what the chart shows.
# The put-wall and futures-basis rungs are left out: step 2 (derivatives) is frozen.










# ----------------------------------------------------------------------------------------
# DECISION WORKFLOW — the sequential path (crucial metrics only)
# ----------------------------------------------------------------------------------------
# Location must be a ZONE, not merely "near a line". See the at_support block for the
# measurement: the old six-way OR passed 97.4% of the board. Mirrors S4's `loc_strict`
# input, which defaults the same way -- if you flip one, flip the other, or the chart
# and the board will disagree about what "at location" means.
# A2: a PIVOT shelf alone is not location; it needs one more source. Mirrors
# S4's `loc_pivot_needs_confluence`. Set ZONE_USE_STRUCTURAL=0 for pattern-only.














def gm_evaluate(symbol: str, trigger_tf: str = "75m", deep_rec: bool = False) -> dict:
    """SINGLE SOURCE OF TRUTH for one symbol's GM decision. Both the Single Symbol
    page AND the Trigger Board (via loaders["evaluate"]) call THIS — so they can
    never diverge on assembly (cmp_px, intraday overlay, inherited setup) or on the
    workflow result. Assembles rec/ctx/cmp_px/mansfield + the same intraday overlay,
    inherits the source archetype, and runs BOTH workflows. The caller decides what
    to render / which path is primary; the computation is shared."""
    # CANONICALIZE to the bare union-key ticker (strip NSE:/BSE: + .NS/.BO) so BOTH
    # surfaces feed EVERY loader (gm_load_symbol/intraday/recovery) AND the resolver
    # the IDENTICAL symbol. Single Symbol passes 'ACUTAAS.NS' (TV style); the board
    # passes bare 'ACUTAAS'. gm_load_intraday resolves those differently (Dhan needs
    # bare) → different 75m PA/cmp → different trigger → categories disagree. One key.
    # Apply the pivot-zone setting BEFORE any loader runs: it changes what a zone IS,
    # and detection happens inside gm_load_symbol. Called here rather than only in the
    # board's control block so the Single Symbol view cannot run a different rule --
    # the same one-place-only defect that left the Daily tab off rule A2.
    _gm_sync_pivot_setting()
    try:
        import gm_trigger_board as _gtb0
        symbol = _gtb0._canon_key(symbol) or symbol
    except Exception as e:
        # P1: a canonicalization failure reintroduces the exact board-vs-single
        # symbol-key divergence this function exists to prevent — record it.
        _gm_logger.warning(f"{symbol}: gm_evaluate canonicalization failed: {e}")
    data = gm_load_symbol(symbol) or {}
    rec = dict(data.get("rec") or {})
    ctx = dict(data.get("ctx") or {})
    fun = data.get("fun") or {}
    bff = data.get("bff")
    ctx["bff"] = bff
    # Explicit is-None fallback (P0 fix): `or` treated a falsy-but-present cmp
    # (0.0) as missing and silently substituted the engine Entry.
    cmp_px = _g(ctx, "cmp")
    if cmp_px is None:
        cmp_px = _g(rec, "Entry")
    rs_ratio = _g(rec, "JdK_RS_Ratio")
    mansfield = (rs_ratio - 100.0) if rs_ratio is not None else None

    # Intraday trigger-TF overlay (Step-5 battery + momentum + LIVE cmp). Identical
    # to what the board used to inline — now the ONE place it lives.
    # intra_reason / intra_reason_code (17-Jul-2026): the RAW failure reason, no
    # longer only embedded in intra_label's prose. The board discarded intra_label
    # entirely, so an all-"n/a" S4-GO column gave the user no cause at all — it read
    # as a scoring problem when it is a data/feed problem. Both are None when the
    # intraday read SUCCEEDED, and — deliberately — also when it was never attempted
    # (Daily trigger-TF): "not attempted" is by design, not a failure, and must not
    # be counted as one.
    intra_ok = False; intra_label = ""; intra_reason = None; intra_reason_code = None
    if trigger_tf in ("75m", "125m"):
        _mins = 75 if trigger_tf == "75m" else 125
        _intra = gm_load_intraday(symbol, _mins) or {}
        ctx["_pa_src"] = "daily"   # overwritten below only if the intraday read succeeds
        if _intra.get("ok"):
            intra_ok = True
            ctx["_trigger_tf"] = trigger_tf
            # STAMP THE SOURCE. This overlay is conditional on _intra["ok"], and when the
            # intraday read fails the ctx keeps the DAILY battery — a silent fallback that
            # looks identical to a real trigger-TF read. On the 10-Aug 06:58 build several
            # names (SAILIFE, SOLARINDS, LAURUSLABS) reported no PA on the 75m board while
            # their 75m battery was firing; their ΣPA matched the DAILY sum exactly. A
            # feed hiccup partway through 63 symbols is survivable — a board that cannot
            # say which rows it affected is not.
            ctx["_pa_src"] = trigger_tf
            ctx["pa_patterns"] = _intra.get("pa")
            ctx["recovery_pa_patterns"] = _intra.get("rpa")
            # PA recency — the snapshot of the most recent bar that DID fire when the
            # current one is silent. Carried as its own key, never merged into
            # pa_patterns: the live battery must keep describing the live bar, or the
            # S4-GO chips end up contradicting the score above them (the v5.2 Pine bug).
            ctx["pa_recent"] = _intra.get("pa_recent")
            ctx["recovery_pa_recent"] = _intra.get("rpa_recent")
            # MARGINAL (knife-edge) patterns — those whose fired/not state flips under a
            # nudge smaller than the routine Dhan-vs-TradingView difference. This is the
            # NAM-INDIA case made visible: Σ6 here vs Σ2 on the S4 panel for the SAME
            # bar, because a 40-paise close difference straddled three thresholds. The
            # board and the chart read different feeds by design, so instead of chasing
            # agreement we mark which points are a coin-flip. Guarded — a failure costs
            # the tag, never the PA read.
            ctx["pa_marginal"] = _intra.get("pa_marginal") or []
            if _intra.get("adx") is not None:     ctx["adx"] = _intra["adx"]
            if _intra.get("relvol") is not None:  ctx["relvol"] = _intra["relvol"]
            if _intra.get("vol_dry") is not None: ctx["vol_dry"] = _intra["vol_dry"]
            if _intra.get("bar_ok") is not None:  ctx["bar_ok"] = _intra["bar_ok"]
            if _intra.get("rsi") is not None:     rec["RSI"] = _intra["rsi"]
            if _intra.get("cmp") is not None:     cmp_px = _intra["cmp"]     # LIVE intraday price
            # WCL follows the TRIGGER TF (Jay trades 75m / 125m / Daily). S4 computes
            # Wyckoff / SMC / Volume Profile on the CHART TF — only the stage flags come
            # from a daily security call — so a daily-derived WCL would not be the number
            # on the chart being read. Structure Health in particular is inert on daily
            # (CHoCH inside a trailing 20-bar daily window is rare); it only discriminates
            # intraday. Stage stays daily via the stashed _wcl_b30/_wcl_b200.
            try:
                import wcl_context as _wclm, zone_engine as _zem
                _idf = _intra.get("df")
                if _idf is not None and len(_idf) >= 60:
                    _ivp = _zem.vp_support(_idf)                  # VP on the trigger TF too
                    _ipos = str(_ivp.get("vp_pos") or "")
                    _ivps = (3 if _ipos == "ABOVE VAH" else 1 if _ipos == "IN VA (upper)"
                             else -1 if _ipos == "IN VA (lower)" else -3 if _ipos == "BELOW VAL" else 0)
                    ctx["wcl"] = _wclm.wcl_context(
                        _idf, vp_score=_ivps,
                        below_30w=ctx.get("_wcl_b30"), below_200=ctx.get("_wcl_b200"),
                        vp_above_vah=(_ipos == "ABOVE VAH"))
                    ctx["wcl"]["tf"] = trigger_tf
                    ctx["choch_count_20"] = ctx["wcl"]["choch_count_20"]
                    ctx["wcl_vp"] = _ivp
                    # Re-derive the location gate with the VP term taken from the
                    # TRIGGER TF, REPLACING (not OR-ing with) the daily VP term — Pine
                    # has exactly one VP, on the chart TF, so OR-ing both would give
                    # Python two bites and over-predict GO. The zone / S-R / AVWAP terms
                    # stay D+W by design (context is daily; only the trigger is intraday).
                    # NOTE: shallow-copy before mutating — ctx["support"] is the object
                    # inside gm_load_symbol's st.cache_data entry; writing through it
                    # would poison the cache for every later caller.
                    _s = dict(ctx.get("support") or {})
                    if _s.get("loc_source") == "IZE":
                        _s["ize_near_vp"] = bool(_ivp.get("at_vp_support"))
                        _s["vp_tf"] = trigger_tf
                        # NATIVE TRIGGER-TF ZONES + S/R (3-Aug). The comment above used to
                        # say the zone/S-R terms "stay D+W by design". That was wrong, and
                        # it was the single biggest source of board-vs-S4 disagreement:
                        # S4 on a 75/125m chart computes NATIVE chart-TF zones as well as
                        # D/W/M — on ZYDUSLIFE it reported "9 DZ / 3 SZ live · IN DEMAND"
                        # — while the board only ever looked at Daily/Weekly/Monthly and
                        # so read the same bar as "below EMA20 / below value".
                        # The gap was masked while both surfaces demanded RV >= 1.0 (a thin
                        # bar failed on BOTH, so they agreed by accident). The moment the
                        # pullback branch let S4 through on dry volume, the two answers
                        # split apart.
                        # `_idf` is already loaded for the PA battery, so this reuses the
                        # frame rather than fetching anything new.
                        _iz_tf = {"75m": "75m", "125m": "125m"}.get(str(trigger_tf), None)
                        _izI = _srI = {}
                        if _iz_tf:
                            try:
                                _pxI = float(_idf["Close"].iloc[-1])
                                _izI = _zem.zone_support(_idf, _iz_tf, _pxI) or {}
                                _srI = _zem.sr_support(_idf, _iz_tf, _pxI) or {}
                            except Exception as _ze2:
                                _gm_logger.warning(f"{symbol}: trigger-TF zones failed ({trigger_tf}): {_ze2}")
                                _izI = _srI = {}
                        # Stop ladder on the TRIGGER TF, as S4 reads it on the chart:
                        # chart-TF zones compete with D/W/M, and the swing low + ATR are
                        # the chart TF's. Only when the chart-TF read worked.
                        if _iz_tf:
                            _s["sl_basis"] = _gm_sl_basis(
                                [_izI] + list(_s.get("sl_zones_htf") or []), _idf, trigger_tf)
                        _s["tf_zone_at"] = bool(_izI.get("at_support"))
                        _s["tf_zone_pattern"] = bool(_izI.get("at_support_pattern"))
                        _s["tf_pattern_tf"] = trigger_tf if _izI.get("at_support_pattern") else None
                        _s["tf_zone_pivot"] = bool(_izI.get("at_support_pivot"))
                        _s["tf_reacting"] = bool(_izI.get("at_support_reacting"))
                        _tfa = _izI.get("approach_pct")
                        if _izI.get("approaching") and _tfa is not None and (
                                _s.get("approach_pct") is None or _tfa < _s["approach_pct"]):
                            _s["approaching"] = True
                            _s["approach_pct"], _s["approach_tf"] = _tfa, _izI.get("approach_tf")
                        # The trigger-TF zone competes with D/W/M for "nearest": on a
                        # 75m chart the zone you will actually reach first is often the
                        # intraday one. Only replaces the D/W/M answer when it is CLOSER.
                        _tfz = _izI.get("next_zone_pct")
                        if _tfz is not None and (_s.get("next_zone_pct") is None
                                                 or _tfz < _s["next_zone_pct"]):
                            _s["next_zone_pct"] = _tfz
                            _s["next_zone_tf"] = _izI.get("next_zone_tf") or _iz_tf
                        _s["tf_zone_in"] = bool(_izI.get("in_fresh_dz"))
                        _s["tf_near_sr"] = bool(_srI.get("near_sr"))
                        _s["tf_zone_tf"] = _iz_tf or ""
                        # LOCATION IS A ZONE (25-Aug-2026, rule A). This was a
                        # six-way OR and it had SATURATED: measured on the live
                        # 76-name board it passed 97.4% of the universe. A gate that
                        # passes 97% of names is not a gate -- with L a free pass the
                        # S4-GO count was really only PA + volume + bar, and because
                        # PA is STRUCTURAL (a pattern that formed still stands on any
                        # timeframe) the board showed an IDENTICAL 4/4 set on 75m,
                        # 125m and Daily. That was the reported symptom; this is the
                        # cause. The timeframes were never broken -- relvol and bar_ok
                        # varied correctly per TF; only at_support was stuck True,
                        # 18 times out of 18 on the probe.
                        #
                        # MY REGRESSION: the IZE sources were merged in July as a
                        # SUPERSET OR'd onto the existing proxy. near_ema was
                        # deliberately excluded then, on the reasoning that it "fires
                        # near the daily EMA20 most of the time and would make the
                        # board OVER-predict 4/4 GO" -- and five other sources went in
                        # anyway without the union ever being re-measured.
                        #
                        # A zone has a DISTAL EDGE, which is what makes it a location:
                        # it defines where you are wrong. An AVWAP re-anchors and an
                        # EMA slides, so a location satisfied only by those can
                        # evaporate without price going anywhere. Mirrors S4's
                        # `loc_strict` exactly, so board and chart agree by
                        # construction rather than by luck.
                        #
                        # The soft sources are NOT discarded -- they are kept on the
                        # row (and in the Loc column) as CONTEXT. They just no longer
                        # satisfy the gate alone.
                        # RULE A2 (25-Aug-2026). A PATTERN zone (leg-base-leg) stands
                        # alone; a PIVOT shelf needs one more source to agree. Mirrors
                        # S4's loc_pivot_needs_confluence exactly.
                        # Measured on the live 76-name board:
                        #   any zone 72.4% · pattern only 21.1% · A2 60.5%
                        # Of 40 pivot-only names 30 already had a second source; A2
                        # removes the 10 resting on a pivot and nothing else.
                        # JAY'S CONCERN, recorded: he does not rely on pivot zones and
                        # wants pattern-only. A2 is interim because pattern zones alone
                        # currently fire on 21% of the board. ZONE_USE_STRUCTURAL=0
                        # gives pattern-only on this surface.
                        _gm_apply_location_rule(_s, bool(_ivp.get("at_vp_support")))
                        ctx["support"] = _s
            except Exception as e:
                # Daily WCL from the ctx builder stands; it is labelled with its own tf.
                _gm_logger.warning(f"{symbol}: intraday WCL recompute failed ({trigger_tf}): {e}")
            intra_label = f"⏱ Trigger TF **{trigger_tf}** · last closed bar {_intra.get('last_ts','?')} · {_intra.get('bars','?')} bars (forming bar excluded — this is the bar time, not a refresh time)"
        else:
            intra_reason = _intra.get("reason") or "unknown"
            intra_reason_code = _intra.get("code") or "unknown"
            intra_label = f"⏱ Trigger TF {trigger_tf} — intraday unavailable ({intra_reason}); showing Daily PA"

    # The location rule must run on EVERY Trigger TF, not just the intraday ones. The
    # intraday branch above applies it with the trigger-TF terms included; this catches
    # DAILY (and any intraday tab whose fetch failed), where those terms are absent and
    # the D/W/M merge carries it alone. Idempotent -- re-running it on a dict the branch
    # already handled recomputes the same values from the same inputs.
    try:
        _sl = ctx.get("support")
        if isinstance(_sl, dict) and _sl.get("loc_source") == "IZE" and "loc_pattern" not in _sl:
            ctx["support"] = _gm_apply_location_rule(dict(_sl))
    except Exception as e:
        _gm_logger.warning(f"{symbol}: location rule (non-intraday) failed: {e}")

    rec_r = gm_load_recovery(symbol, deep=deep_rec) or {}

    # Inherited source archetype (one resolver, shared) → per-path ctx copies so a
    # bull archetype can't spoof the recovery inherited-branch and vice-versa.
    ib, ir = [], []
    inherit_error = None
    try:
        import gm_trigger_board as _gtb
        if hasattr(_gtb, "resolve_archetypes"):
            _inh = _gtb.resolve_archetypes(symbol)
            _arche = _inh.get("archetypes") or []
            ib = [a for a in _arche if a in _gtb.BULL_ARCHETYPES]
            ir = [a for a in _arche if a in _gtb.RECOVERY_ARCHETYPES]
    except Exception as e:
        # P1: a resolver failure silently DISABLED the entire inherited-
        # qualification model (name fell to legacy re-qualify with no signal to
        # the user — verdicts change). Log + surface a badge.
        inherit_error = f"{type(e).__name__}: {e}"
        _gm_logger.warning(f"{symbol}: resolve_archetypes failed — inheritance OFF: {e}")
    _cb = dict(ctx); _cr = dict(ctx)
    if ib: _cb["inherited_setup"] = ib
    if ir: _cr["inherited_setup"] = ir

    wf_bull = compute_workflow(rec, _cb, cmp_px, mansfield)
    # P0 fix (14-Jul-2026): gm_load_recovery returns {"_error": …} on total failure —
    # a TRUTHY dict. The old `if rec_r` ran the recovery workflow on the error dict,
    # producing a confident-but-wrong "NOT A RECOVERY CONTEXT" verdict. An eval
    # failure and a real no-context are decision-different — surface the error.
    rec_error = (rec_r or {}).get("_error")
    wf_rec = (compute_recovery_workflow(rec_r, _cr, cmp_px)
              if (rec_r and not rec_error) else None)
    return dict(data=data, rec=rec, ctx=ctx, fun=fun, bff=bff,
                cmp_px=cmp_px, mansfield=mansfield, rec_r=rec_r,
                wf_bull=wf_bull, wf_rec=wf_rec, rec_error=rec_error,
                inherited_bull=ib, inherited_rec=ir, inherit_error=inherit_error,
                intra_ok=intra_ok, intra_label=intra_label,
                intra_reason=intra_reason, intra_reason_code=intra_reason_code)


def render_workflow(wf: dict) -> str:
    cmap = {"pass": "pass", "fail": "fail", "wait": "watch",
            "pending": "blue", "skip": "na", "plan": "pass"}
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
            
        p_st = cmap[status]
        lbl_bg, val_bg, text_col, bdr_col = _pine_row_style(p_st)
        is_cur = (s["n"] == cur and status != "skip")
        
        chips = ""
        for lab, val, ok in s["metrics"]:
            mk = "✓" if ok else ("✗" if ok is False else "·")
            chips += (f"<span style='display:inline-block;margin-right:8px;font-size:11px;font-weight:700;color:{text_col};'>"
                      f"<span style='opacity:0.8;'>{lab}:</span> <b>{val}</b> "
                      f"<span style='font-weight:900;'>{mk}</span></span>")
        
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
            
        guide_html = f"<span style='font-size:11px;font-weight:800;margin-left:8px;'>{guide}</span>" if guide else ""
        nowbadge = ("<span style='font-size:9px;font-weight:900;color: var(--ink);background: var(--surface-3);"
                    "padding:2px 6px;border-radius:4px;margin-left:6px;'>← NOW</span>" if is_cur else "")
        
        steps_html += (
            f"<div style='display:flex;align-items:center;justify-content:space-between;gap:10px;"
            f"background:{val_bg};color:{text_col};border:1.5px solid {bdr_col};border-left:6px solid {bdr_col};"
            f"padding:7px 12px;margin-bottom:6px;border-radius:6px;font-size:12px;font-family:\"Inter\",sans-serif;'>"
            f"<div style='display:flex;align-items:center;gap:8px;flex:1;min-width:0;'>"
            f"<span style='font-weight:900;font-size:11.5px;background: var(--surface-3);color: var(--ink);padding:2px 7px;border-radius:4px;'>STEP {s['n']}</span>"
            f"<span style='font-weight:800;font-size:12px;'>{s['title']}</span>"
            f"<span style='font-size:11px;opacity:0.85;font-weight:600;'>({s['sub']})</span>{nowbadge}{guide_html}"
            f"</div>"
            f"<div style='display:flex;align-items:center;gap:12px;'>"
            f"<div>{chips}</div>"
            f"<span style='font-size:10px;font-weight:900;color: var(--ground);background:{bdr_col};"
            f"padding:3px 10px;border-radius:4px;letter-spacing:0.5px;'>{pill[status]}</span>"
            f"</div></div>"
        )
        if s.get("hard") and s["ok"] is False:
            prior_fail = True

    sub = (f"⛔ stops at Step {wf['stop_at']}" if wf["stop_at"] else f"→ you are at Step {cur}")
    hdr_st = "pass" if wf["actionable"] else ("fail" if wf.get("stop_at") else "watch")
    _, h_val_bg, h_text_col, h_bdr_col = _pine_row_style(hdr_st)
    
    return (f"<div style='background:var(--surface);border:1.5px solid var(--faint);border-radius:8px;overflow:hidden;margin-bottom:14px;box-shadow:0 2px 6px rgba(0,0,0,0.06);'>"
            f"<div style='background:{h_val_bg};color:{h_text_col};border-bottom:1.5px solid {h_bdr_col};font-weight:900;font-size:13px;"
            f"letter-spacing:.5px;padding:8px 14px;display:flex;justify-content:space-between;align-items:center;'>"
            f"<span>{wf['verdict']}</span><span style='font-size:11px;font-weight:800;'>{sub}</span></div>"
            f"<div style='padding:8px;background:var(--surface-2);'>{steps_html}</div></div>")


def render_technical_board(rec: dict, ctx: dict, cmp_px, mansfield) -> tuple[str, str, str]:
    """Build the full graphical technical board as 3 distinct card HTML strings: (momentum, minervini, pa_signals)."""
    rsi = _g(rec, "RSI"); adx = _g(ctx, "adx"); alpha = _g(rec, "Alpha"); ml = _g(rec, "ML_Prob")
    vdry = _g(ctx, "vol_dry")
    rsi_state = ("watch" if (rsi or 0) >= 70 else "pass" if (rsi or 0) >= 50 else "watch" if (rsi or 0) >= 40 else "fail")
    gauges = "".join([
        _gauge("RSI (14)", rsi, 0, 100,
               "linear-gradient(90deg,var(--bear-bg),var(--warn-bg) 30%,var(--bull-bg) 50%,var(--bull-bg) 68%,var(--warn-bg) 78%,var(--bear-bg))",
               rsi_state, fnum(rsi, 0)),
        _gauge("ADX (14)", adx, 0, 50,
               "linear-gradient(90deg,var(--surface-3),var(--warn-bg) 40%,var(--bull-bg) 50%)",
               ("pass" if (adx or 0) >= 25 else "watch" if (adx or 0) >= 20 else "fail"), fnum(adx, 0)),
        _gauge("Alpha Score", alpha, 0, 100,
               "linear-gradient(90deg,var(--bear-bg),var(--warn-bg) 50%,var(--bull-bg) 70%)",
               ("pass" if (alpha or 0) >= 70 else "watch" if (alpha or 0) >= 50 else "fail"), fnum(alpha, 0)),
        _gauge("ML Win Prob", ml, 0, 100,
               "linear-gradient(90deg,var(--bear-bg),var(--warn-bg) 55%,var(--bull-bg) 65%)",
               ("pass" if (ml or 0) >= 65 else "watch" if (ml or 0) >= 55 else "fail"), fnum(ml, 1, "%")),
        _gauge("Mansfield RS", mansfield, -50, 50,
               "linear-gradient(90deg,var(--bear-bg),var(--surface-3) 50%,var(--bull-bg))",
               ("pass" if (mansfield or 0) > 0 else "fail"), fnum(mansfield, 1)),
        _gauge("Vol Dry-up 5/20d", vdry, 0, 2,
               "linear-gradient(90deg,var(--bull-bg),var(--warn-bg) 50%,var(--bear-bg))",
               ("pass" if (vdry if vdry is not None else 9) < 0.8 else "na"), fnum(vdry, 2, "×")),
    ])

    rng = _range_bar(_g(ctx, "low52w"), _g(ctx, "high52w"), cmp_px, [
        (_g(ctx, "sma200"), "200", "#EF5350"),
        (_g(ctx, "sma50"), "50", "#2962FF"),
        (_g(ctx, "ema20"), "20e", "var(--warn)"),
    ])

    hdr_bg = C_HDR_BG

    h_momentum = (
        f"<div style='background:var(--surface);border:1.5px solid var(--faint);border-radius:8px;overflow:hidden;margin-bottom:12px;box-shadow:0 2px 6px rgba(0,0,0,0.06);'>"
        f"<div style='background:{hdr_bg};color: var(--ink);font-weight:800;font-size:11.5px;"
        f"letter-spacing:.5px;padding:7px 12px;border-bottom:1.5px solid var(--rule);'>⚡ MOMENTUM &amp; STRENGTH</div>"
        f"<div style='padding:8px 10px;background:var(--surface-2);'>"
        f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:2px 10px;'>{gauges}</div>"
        f"<div style='font-size:10.5px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;color:#0284C7;margin:8px 0 2px;'>52-Week Range (●=CMP, ticks=MAs)</div>"
        f"{rng}</div></div>"
    )

    # Minervini 8-point trend template
    e20 = _g(ctx, "ema20"); s50 = _g(ctx, "sma50"); s150 = _g(ctx, "sma150"); s200 = _g(ctx, "sma200")
    passed, c8 = minervini_checks(ctx, cmp_px, mansfield)
    dots = "".join(_crit(ok, lab) for ok, lab in c8)
    
    scol = C_TEXT_PASS if passed >= 6 else (C_TEXT_WARN if passed >= 4 else C_TEXT_FAIL)
    c_bg, c_fg = _soft_style("pass" if passed >= 6 else ("watch" if passed >= 4 else "fail"))
    chip_m = (f"<span style='float:right;background:{c_bg};color:{c_fg};padding:1.5px 9px;"
              f"border-radius:10px;font-weight:800;font-size:10px;'>{passed}/8</span>")

    h_minervini = (
        f"<div style='background:var(--surface);border:1.5px solid var(--faint);border-radius:8px;overflow:hidden;margin-bottom:12px;box-shadow:0 2px 6px rgba(0,0,0,0.06);'>"
        f"<div style='background:{hdr_bg};color: var(--ink);font-weight:800;font-size:11.5px;"
        f"letter-spacing:.5px;padding:7px 12px;border-bottom:1.5px solid var(--rule);'>🏆 MINERVINI TREND TEMPLATE{chip_m}</div>"
        f"<div style='padding:10px 12px;background:var(--surface-2);'>"
        f"<div style='display:flex;gap:12px;align-items:center;margin-bottom:4px;'>"
        f"<div>{_donut(passed, 8)}</div>"
        f"<div style='display:grid;grid-template-columns:1fr;gap:1px;flex:1'>{dots}</div></div></div></div>"
    )

    # Price-action signal pills
    stage = str(_g(rec, "Stage", default="—")); s2 = "2" in stage
    stacked = bool(e20 and s50 and cmp_px > e20 > s50 and (not s200 or s50 > s200))
    above_e20 = bool(e20 and cmp_px > e20)
    adir = _g(rec, "Active_Dir", default="—"); vacc = _g(rec, "Vel_Accel", default="")
    vcp = bool(_g(rec, "VCP_Valid")); rrg = _g(rec, "RRG_Quadrant", default="—")
    broke = bool(_g(rec, "Broke_Pivot")); rv = _g(ctx, "relvol"); d52 = _g(ctx, "dist52wh")
    s150p = _g(ctx, "sma150_prev")
    wk_up = bool(s150 and cmp_px > s150 and (s150p is None or s150 > s150p))
    d_up = str(adir).upper().startswith("UP")
    dath = _g(ctx, "dist_ath")
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

    h_pa_signals = (
        f"<div style='background:var(--surface);border:1.5px solid var(--faint);border-radius:8px;overflow:hidden;margin-bottom:12px;box-shadow:0 2px 6px rgba(0,0,0,0.06);'>"
        f"<div style='background:{hdr_bg};color: var(--ink);font-weight:800;font-size:11.5px;"
        f"letter-spacing:.5px;padding:7px 12px;border-bottom:1.5px solid var(--rule);'>📈 PRICE-ACTION SIGNALS</div>"
        f"<div style='padding:8px 10px;background:var(--surface-2);'>"
        f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:2px 8px;'>{pills}</div></div></div>"
    )

    return h_momentum, h_minervini, h_pa_signals


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


def section_pa_patterns(ctx, recovery: bool = False) -> str:
    """PA pattern batteries — split into COMMON (in both), BULL-only and RECOVERY-only
    sub-cards so the two batteries (17 bull / 10 recovery, some shared) read clearly.
    `recovery` = the ACTIVE decision path, so the Σ chip reflects the right battery
    (was always bull → a recovery stock showed the bull Σ)."""
    bull = _g(ctx, "pa_patterns", default=[]) or []
    rec = _g(ctx, "recovery_pa_patterns", default=[]) or []
    if not bull and not rec:
        return card("PA PATTERNS · v67 mirror", [("Patterns", "unavailable", "na")], "var(--ink-2)")
    _bn = {n for n, _, _, _ in bull}
    _rn = {n for n, _, _, _ in rec}
    _common = _bn & _rn                                   # exact-name matches (Wyckoff Spring, Pocket Pivot, 3-Bar…)

    def _rows(pats):
        return [(f"{name}  (+{tier})", ("FIRED — " + note) if fired else "quiet",
                 "pass" if fired else "na") for name, fired, tier, note in pats]

    def _sum(pats):
        return sum(t for _, f, t, _ in pats if f)

    def _scol(ts):
        return ("#7B1FA2" if ts >= 4 else "#26A69A" if ts >= 2
                else "var(--warn)" if ts >= 1 else "#787B86")

    common_pats = [p for p in bull if p[0] in _common]    # identical calc in both → take bull's
    bull_only = [p for p in bull if p[0] not in _common]
    rec_only = [p for p in rec if p[0] not in _common]

    # Summary chip = the ACTIVE decision-path battery's Σ (recovery when the recovery
    # path is selected, else bull). Was hardcoded to bull → the score-strip PA chip
    # showed the bull Σ on a recovery stock (the leak).
    _active_batt = (rec if recovery else bull) or bull or rec
    tier_sum = _sum(_active_batt)
    SECTION_SCORES["Pa Patterns"] = (f"Σ +{tier_sum}", None, _scol(tier_sum))

    out_bull = ""
    if common_pats:
        _ts = _sum(common_pats)
        out_bull += card("PA PATTERNS · COMMON (bull ∩ recovery)", _rows(common_pats), "var(--ink-2)",
                    chip_text=f"Σ +{_ts}", chip_color=(_scol(_ts) if _ts >= 1 else "var(--ink-2)"))
    if bull_only:
        _ts = _sum(bull_only)
        out_bull += card("PA PATTERNS · BULL", _rows(bull_only), "var(--ink-2)",
                    chip_text=f"Σ +{_ts}", chip_color=(_scol(_ts) if _ts >= 1 else "var(--ink-2)"))
    
    out_rec = ""
    if rec_only:
        _ts = _sum(rec_only)
        out_rec += card("PA PATTERNS · RECOVERY", _rows(rec_only), "var(--ink-2)",
                    chip_text=f"Σ +{_ts}", chip_color=(_scol(_ts) if _ts >= 1 else "var(--ink-2)"))
    # RETURN ONE STRING, chosen by the `recovery` flag - the signature has always said
    # `-> str` and the call site makes TWO calls (bull card in one column, recovery card
    # in another). This used to `return out_bull, out_rec`, which crashed Full Metrics
    # with "too many values to unpack" on 14-Aug; that was fixed on the CALL SITE by
    # dropping the unpack, which left the tuple intact - so st.markdown rendered its
    # repr and the panel printed raw "('<div style=..." HTML as text (18-Aug).
    # The COMMON sub-card rides with the bull return so it cannot render twice.
    return out_rec if recovery else out_bull




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

        # Trigger-bar quality on the last CLOSED daily bar — same test as the intraday
        # loader's _bar_ok, so the S4-GO "clean bar" gate means the same thing on Daily.
        _daily_bar_ok = None
        try:
            _dlb = df.iloc[-1]
            _do, _dh, _dl, _dc = float(_dlb["Open"]), float(_dlb["High"]), float(_dlb["Low"]), float(_dlb["Close"])
            _daily_bar_ok = bool((_dc >= _do) or (((_dc - _dl) / (_dh - _dl)) >= 0.5 if _dh > _dl else True))
        except Exception:
            _daily_bar_ok = None

        out["ctx"] = {
            "cmp": last,
            "prev": float(c.iloc[-2]) if len(c) > 1 else last,
            "ema20": _f(ema20), "atr": _f(atr), "sma50": _f(sma50), "sma150": _f(sma150), "sma200": _f(sma200),
            "sma200_prev": _fprev(sma200, 21), "sma150_prev": _fprev(sma150, 21),
            "sma150_prev2": _fprev(sma150, 42),
            "ath2y": float(h.max()) if len(h) else None,
            "dist_ath": (last - float(h.max())) / float(h.max()) * 100 if len(h) and float(h.max()) else None,
            "adx": _f(adx), "plus_di": _f(pdi), "minus_di": _f(mdi),
            "high52w": _f(h52), "low52w": _f(l52),
            "dist52wh": (last - _f(h52)) / _f(h52) * 100 if _f(h52) else None,
            # S4's chart_rv, exactly (24-Sep-2026, AUD-PAR-12): this bar over the mean of
            # the PRIOR 50 bars. It was over a 20-bar mean that included this bar, so the
            # board's V gate and '· no vol' were a different test from the chart's.
            "relvol": _s4_rv(v),
            "vol_dry": (vol5 / vol20) if vol20 else None,
            "bbw": bbw,
            "cpr_p": cpr_p, "cpr_tc": cpr_tc, "cpr_bc": cpr_bc,
            "mvwap": mvwap, "vwma20": vwma20, "shelf_ok": shelf_ok,
            "acc_days": acc_days, "acc_ok": acc_ok, "squeeze_on": squeeze_on,
            "stage2_weeks": stage2_weeks,
            "poc": poc, "vah": vah_hi, "val": val_lo, "dist_poc": dist_poc, "vp_pos": vp_pos,
            "bull_fvg": bull_fvg, "bear_fvg": bear_fvg,
            "turnover_cr": last * float(v.iloc[-1]) / 1e7,
            # #dailygo (30-Jul, Jay): "you're already using the last CLOSED daily candle,
            # so what's the challenge?" — correct, and this was the only genuinely missing
            # S4-GO ingredient on Daily. relvol above already exists here; bar_ok did not,
            # purely because it had only ever been written inside the intraday loader.
            # IDENTICAL formula to gm_load_intraday's (line ~4379): green close, OR a red
            # bar that still closed in the upper half of its range. Pure OHLC — nothing
            # intraday-specific about it — so the Daily read is the same test on the last
            # closed daily bar, not an approximation of it.
            "bar_ok": _daily_bar_ok,
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
        except Exception as e:
            _gm_logger.warning(f"{symbol}: 10y ATH fetch failed (52w proxy stays): {e}")
        # v67-mirror PA pattern battery (Jay: can't spot these by eye — detect them)
        try:
            if out.get("df") is not None:
                _stage0 = str((out.get("rec") or {}).get("Stage", ""))
                out["ctx"]["pa_patterns"] = _detect_pa_patterns(out["df"], _stage0)
                out["ctx"]["recovery_pa_patterns"] = _detect_recovery_pa_patterns(out["df"], _stage0)
        except Exception as e:
            # P1: a detection CRASH must not read as "no trigger" — they are
            # decision-different states. Flag it; Step-5 renders the error.
            out["ctx"]["pa_error"] = f"{type(e).__name__}: {e}"
            _gm_logger.warning(f"{symbol}: PA battery detection failed: {e}")
        # Auto support zones (OB / FVG / pivot-low) on BOTH Daily AND Weekly —
        # the Python twin of the S4 Pine v2.1 trackers (trading TF is 125/75m,
        # but the demand zones come from D+W structure). Automates Steps 1-2.
        try:
            import pa_patterns as _pap
            if out.get("df") is not None:
                out["ctx"]["support"] = _pap.detect_support_zones_dw(out["df"])
                # Stash the reference price the pivot-LEVEL test needs. The proxy
                # returns levels but not the close they were judged against, and
                # re-deriving it in the rule would risk a different bar.
                try:
                    out["ctx"]["support"]["_px"] = float(out["df"]["Close"].iloc[-1])
                except Exception:
                    pass
        except Exception as e:
            out["ctx"]["support"] = {}
            _gm_logger.warning(f"{symbol}: support-zone detection failed: {e}")
        # WCL v1.2 Wyckoff + SMC (wcl_context.py — the real Pine calculation, not the
        # old proxies). Computed ONCE here so the Single Symbol panel and the Trigger
        # Board read the SAME numbers from ctx; two independent computations is how
        # board-vs-single drift got in last time. Guarded: on failure the consumers
        # fall back to their previous proxy display rather than crashing the load.
        try:
            import wcl_context as _wcl
            if out.get("df") is not None:
                _c = out["ctx"]
                _last = _c.get("cmp")
                _s150, _s200 = _c.get("sma150"), _c.get("sma200")
                # Pine: bel30w = close < sma150, bel200 = close < sma200. None stays
                # None so stage_score() applies its fail-bearish default (never 0-as-ok).
                _b30 = (_last < _s150) if (_last is not None and _s150) else None
                _b200 = (_last < _s200) if (_last is not None and _s200) else None
                _vpp = str(_c.get("vp_pos") or "")
                _dpoc = _c.get("dist_poc")
                if _vpp == "ABOVE VAH":
                    _vps = 3
                elif _vpp == "INSIDE VA":
                    _vps = 1 if (_dpoc or 0) >= 0 else -1
                elif _vpp == "BELOW VAL":
                    _vps = -3
                else:
                    _vps = 0
                # Stash the DAILY stage flags. Pine reads bel30w/bel200 from a
                # request.security("D") call regardless of the chart TF, so when
                # gm_evaluate recomputes WCL on 75m/125m it must reuse THESE, not
                # re-derive a "150-bar SMA" from intraday bars (which would be ~3
                # weeks of tape, not 30 weeks).
                _c["_wcl_b30"], _c["_wcl_b200"] = _b30, _b200
                _c["wcl"] = _wcl.wcl_context(out["df"], vp_score=_vps,
                                             below_30w=_b30, below_200=_b200,
                                             vp_above_vah=(_vpp == "ABOVE VAH"))
                _c["wcl"]["tf"] = "Daily"
                _c["choch_count_20"] = _c["wcl"]["choch_count_20"]
        except Exception as e:
            _gm_logger.warning(f"{symbol}: WCL context (Wyckoff/SMC) failed: {e}")
        # IZE zone engine (A/B, GM_USE_IZE_ZONES): the real leg-base-leg zones S4 draws,
        # on Daily + confirmed-Weekly structure (same TF scope as the proxy). An IZE
        # demand zone containing/near price IS a location (S4 z_inDZ parity), so it
        # upgrades at_support without dropping the proxy's own hits. Fully guarded —
        # any failure leaves the proxy result untouched.
        if GM_USE_IZE_ZONES:
            try:
                import zone_engine as _ze
                _df = out.get("df")
                if _df is not None and len(_df) >= 60:
                    _sup = out["ctx"].get("support") or {}
                    _pxN = float(_df["Close"].iloc[-1])
                    _izD = _ze.zone_support(_df, "D", _pxN)
                    _wk = _pap._confirmed_weekly_ohlcv(_df)
                    _izW = _ze.zone_support(_wk, "W", _pxN) if (_wk is not None and len(_wk) >= 60) else {}
                    # Monthly too — a shelf S4 tags Weekly can land on the monthly
                    # resample here (native request.security vs pandas resample); check
                    # both so a TF-assignment difference never drops a real HTF zone.
                    # `out["df"]` is only 2y (→ ~24 monthly bars, below the 60-bar floor),
                    # so pull a 5y daily frame JUST for the monthly resample (cached 24h;
                    # monthly zones age out at 4y, so 5y is the right window). Weekly stays
                    # on the 2y df — weekly zones age out at 2y anyway, so it's fully covered.
                    try:
                        _df5 = dp.fetch_ohlcv(symbol, period="5y", interval="1d", use_cache=True, auto_adjust=True)
                    except Exception:
                        _df5 = _df
                    _mo = _pap._confirmed_month_ohlcv(_df5 if (_df5 is not None and len(_df5)) else _df)
                    _izM = _ze.zone_support(_mo, "M", _pxN) if (_mo is not None and len(_mo) >= 60) else {}
                    _ize_at = bool(_izD.get("at_support") or _izW.get("at_support") or _izM.get("at_support"))
                    _sup["ize_at_support_pattern"] = bool(
                        _izD.get("at_support_pattern") or _izW.get("at_support_pattern")
                        or _izM.get("at_support_pattern"))
                    # WHICH timeframe's pattern zone passed (25-Sep-2026): the board used to
                    # print next_zone_tf - the NEXT zone below - so a Daily-zone hit read "75m".
                    _sup["ize_pattern_tf"] = next((_t for _t, _z in (("D", _izD), ("W", _izW), ("M", _izM))
                                                   if _z and _z.get("at_support_pattern")), None)
                    _sup["ize_at_support_pivot"] = bool(
                        _izD.get("at_support_pivot") or _izW.get("at_support_pivot")
                        or _izM.get("at_support_pivot"))
                    # REACTING: tested once and turning up off the zone, still inside
                    # the engine's own travel budget. Carried separately from
                    # at_support so the board can SAY which of the two it is.
                    _sup["ize_reacting"] = bool(
                        _izD.get("at_support_reacting") or _izW.get("at_support_reacting")
                        or _izM.get("at_support_reacting"))
                    # APPROACH: watch state, never a gate pass. Closest of the three.
                    _ap = [(_z.get("approach_pct"), _z.get("approach_tf"))
                           for _z in (_izD, _izW, _izM)
                           if _z and _z.get("approaching") and _z.get("approach_pct") is not None]
                    if _ap:
                        _sup["approach_pct"], _sup["approach_tf"] = min(_ap)
                        _sup["approaching"] = True
                    _sup["ize_at_support"] = _ize_at
                    # NEAREST FRESH PATTERN ZONE BELOW PRICE, across D/W/M. The board's
                    # →Zone column is the watch list the strict gate needs: 82.9% of
                    # names HAVE a fresh pattern zone but only 3.9% have price inside
                    # one, so "am I AT one" alone turns an abundant queue into an
                    # apparent signal shortage.
                    # CLOSEST wins across the three timeframes — the question is "how
                    # far to the next place worth buying", and the nearest one answers
                    # it regardless of which timeframe drew it. The TF is carried too,
                    # because a weekly zone 3% away is a different wait from a daily
                    # zone 3% away.
                    _cands = [(_z.get("next_zone_pct"), _z.get("next_zone_tf"))
                              for _z in (_izD, _izW, _izM)
                              if _z and _z.get("next_zone_pct") is not None]
                    if _cands:
                        _best = min(_cands, key=lambda t: t[0])
                        _sup["next_zone_pct"], _sup["next_zone_tf"] = _best
                    # Stop ladder (AUD-PAR-10): Daily is the native TF for a Daily board;
                    # an intraday board re-derives it with its own zones/ATR (gm_evaluate).
                    _sup["sl_zones_htf"] = [
                        {k: _z.get(k) for k in ("zone_state", "distal", "score", "recency_score",
                                                "near_dz_proximal", "near_dz_distal")}
                        for _z in (_izD, _izW, _izM)]
                    _sup["sl_basis"] = _gm_sl_basis((_izD, _izW, _izM), _df, "Daily")
                    _sup["ize_zone"] = _izD.get("zone") or _izW.get("zone") or _izM.get("zone")
                    _sup["ize_score"] = _izD.get("score") or _izW.get("score") or _izM.get("score")
                    _sup["ize_n_dz"] = int(_izD.get("n_dz") or 0) + int(_izW.get("n_dz") or 0) + int(_izM.get("n_dz") or 0)
                    # S/R horizontal levels (phase 2 — the other half of S4's support_pass:
                    # near_sr). A non-MTTWR SUPPORT level within 1.5% below price IS a
                    # location (S4 near_sr). Daily + confirmed-Weekly, MTTWR excluded.
                    _srD = _ze.sr_support(_df, "D", _pxN)
                    _srW = _ze.sr_support(_wk, "W", _pxN) if (_wk is not None and len(_wk) >= 30) else {}
                    _near_sr = bool(_srD.get("near_sr") or _srW.get("near_sr"))
                    _sup["ize_near_sr"] = _near_sr
                    _sup["ize_sr_level"] = _srD.get("level") or _srW.get("level")
                    _sup["ize_sr_grade"] = _srD.get("grade") or _srW.get("grade")
                    # Anchored VWAPs (Low/BO/Gap): price within 1.5% above a specific AVWAP
                    # IS a location (S4 near_avwap). A precise price-memory level, not a broad
                    # MA — so it belongs in the gate (unlike near_ema, deliberately excluded).
                    _av = _ze.avwap_support(_df, _pxN)
                    _near_av = bool(_av.get("near_avwap"))
                    _sup["ize_near_avwap"] = _near_av
                    _sup["ize_avwap"] = _av.get("nearest")
                    # REPLACE the proxy (Jay, 24-Jul): the location decision is now driven
                    # ONLY by the validated S4 zone logic — IZE zones (D/W/M) + non-MTTWR S/R
                    # levels + AVWAP — overwriting the OB/FVG/pivot proxy's at_support, not
                    # OR-ing with it. The proxy's zone/level DATA is still kept in _sup for
                    # display/plan; only the at_support DECISION changes.
                    # Volume Profile VAL / POC as LOCATION — the Python twin of S4
                    # v5.1's `en_wcl_loc`. A high-volume acceptance shelf IS a location;
                    # without this the board reads "no location" on names where S4 now
                    # says GO. Same 1.5% tolerance, same one-sided VAL / two-sided POC
                    # rule as the Pine. Deliberately NOT near_ema (over-predicts).
                    _vpsup = _ze.vp_support(_df, _pxN)
                    _near_vp = bool(_vpsup.get("at_vp_support"))
                    _sup["ize_near_vp"] = _near_vp
                    _sup["ize_vp_val"] = _vpsup.get("vp_val")
                    _sup["ize_vp_poc"] = _vpsup.get("vp_poc")
                    _sup["at_support"] = bool(_ize_at or _near_sr or _near_av or _near_vp)
                    # HTF NESTING (v9.0 parity with S4's _htfNest). A zone sheltered by a
                    # HIGHER timeframe zone is the stronger proposition — and the board had
                    # no cross-TF term at all, so it systematically under-rated exactly the
                    # setups the chart rates highest. Grading only: never feeds the gate,
                    # never feeds Zone.score (so it cannot buy a nested zone a 2nd test).
                    # Raw flags only — the RANK is relative to the chart timeframe
                    # ("D" is nesting for a 75m board, native for a Daily one), and
                    # gm_load_symbol has no timeframe in scope. Resolved downstream
                    # where _trigger_tf is known.
                    _sup["htf_at"] = {"D": bool(_izD.get("at_support")),
                                      "W": bool(_izW.get("at_support")),
                                      "M": bool(_izM.get("at_support"))}
                    _sup["loc_source"] = "IZE"
                    out["ctx"]["support"] = _sup
            except Exception as e:
                # Safety net: if the validated engine errors, the proxy's at_support (set
                # above) stands rather than leaving the name with no location at all.
                _gm_logger.warning(f"{symbol}: IZE zone engine failed (proxy stands): {e}")
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
        except Exception as e:
            _gm_logger.warning(f"{symbol}: Futures-OI CSV read failed: {e}")

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
                        except Exception as e:
                            _gm_logger.warning(f"{symbol}: recovery batch mtime read failed: {e}")
                        return d
            except Exception as e:
                # P1: the AUTHORITATIVE batch row (full-RFF) failed to read —
                # falling to live cache-only recompute, which can differ (RFF
                # often INSUFFICIENT there). Decision-relevant; record it.
                _gm_logger.warning(f"{symbol}: recovery batch CSV read failed — "
                                   f"falling to live recompute: {e}")
        # 2. Live recompute (symbol not scanned in the batch, or deep forced).
        r = rs.screen_one(symbol, allow_live_fundamentals=deep) or {}
        if isinstance(r, dict):
            r["_source"] = "live (deep)" if deep else "live (cache-only)"
        return r
    except Exception as e:
        return {"_error": str(e)}


# How many closed trigger-TF bars back the PA battery is re-evaluated when the
# CURRENT bar is silent. 3 = "this candle or the two before it" — Jay's ask, and
# on 75m that is roughly the last half-session. Raising it finds more names but
# quotes older triggers; the age is always shown so a stale one can't pass as live.
_PA_LOOKBACK_BARS = 3


@st.cache_data(ttl=180, show_spinner=False)
def gm_load_intraday(symbol: str, minutes: int) -> dict:
    """Intraday (75/125-min) trigger data for the Golden Matcher's Step-5 battery
    + momentum board. Fetches Dhan 25-min bars (90d), session-anchor resamples to
    `minutes`, then recomputes the PA batteries (intraday=True → weekly patterns
    suppressed) and the momentum metrics (RSI/ADX/RelVol/Vol-dry) on that TF.

    Cached (ttl 180s) so the 2s TV auto-sync never re-hits Dhan. Returns
    {ok, pa, rpa, rsi, adx, relvol, vol_dry, last_ts, bars} — ok=False + reason
    when intraday is unavailable (page then falls back to the daily read).

    On failure BOTH a prose `reason` (per-symbol, shown on the Single Symbol
    caption) and a stable `code` are returned. The code is the bucket key the
    Trigger Board aggregates on: prose carries per-symbol specifics (bar counts,
    exception text) whose cardinality would shatter a count-by-reason into a
    hundred one-row buckets. Codes: auth · no_data · short_history ·
    no_closed_bar · error.
    """
    try:
        import dhan_ohlcv as _dh, pa_patterns as _pap, numpy as _np
        df25 = _dh.fetch_intraday(symbol,
                                  from_date=(datetime.now().date() - timedelta(days=90)).isoformat(),
                                  to_date=datetime.now().date().isoformat(), interval=25)
        if df25 is None or df25.empty:
            # Separate the FEED-WIDE auth failure from a genuinely dataless symbol.
            # They look identical here (both = empty frame) but mean opposite things:
            # auth blanks EVERY name at once and is fixable; no_data is per-symbol.
            if _dh.auth_failed():
                return {"ok": False, "code": "auth",
                        "reason": "Dhan auth failed/expired — paid feed is not being used"}
            return {"ok": False, "code": "no_data", "reason": "no intraday data from Dhan"}
        df = _pap.resample_intraday(df25, minutes, base_minutes=25)
        if df is None or len(df) < 60:
            return {"ok": False, "code": "short_history",
                    "reason": f"only {0 if df is None else len(df)} {minutes}m bars (<60)"}
        # LAST CLOSED BAR ONLY — drop the currently-forming bar so the intraday signal
        # (PA · relvol · bar_ok · cmp) never repaints mid-bar. A bar is still forming if
        # its close time (bar start + `minutes`) is after 'now'.
        try:
            _lt = df.index[-1]
            if getattr(_lt, "tzinfo", None) is not None:
                _lt = _lt.tz_localize(None)
            if (_lt.to_pydatetime() + timedelta(minutes=minutes)) > datetime.now():
                df = df.iloc[:-1]
        except Exception as _e:
            _gm_logger.warning(f"{symbol}: forming-bar drop failed: {_e}")
        if df is None or len(df) < 60:
            return {"ok": False, "code": "no_closed_bar", "reason": "no closed intraday bars yet"}
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
        except Exception as e:
            # P1: without the daily EMA anchors the intraday battery loses its
            # trend context (engulfing gates degrade) — record the degradation.
            _gm_logger.warning(f"{symbol}: daily EMA anchors for intraday PA failed: {e}")
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
        # Trigger-bar quality (twin of the S4 Pine bar_ok): the last bar closed strong —
        # green, OR a red bar that still closed in the UPPER HALF of its range. A close in
        # the lower half (sold-off / upthrust) → False. Feeds the board's S4-GO preview.
        _bar_ok = None
        try:
            _lb = df.iloc[-1]
            _bo, _bh, _bl, _bc = float(_lb["Open"]), float(_lb["High"]), float(_lb["Low"]), float(_lb["Close"])
            _bar_ok = bool((_bc >= _bo) or (((_bc - _bl) / (_bh - _bl)) >= 0.5 if _bh > _bl else True))
        except Exception:
            _bar_ok = None
        # ── PA RECENCY (Jay, 31-Jul-2026) ────────────────────────────────────
        # There are 5 x 75-min candles in an NSE session, so a pattern that fires
        # at 10:30 is gone from a last-bar-only read by 11:45 — and since the GM
        # board is where the S4-GO shortlist is FILTERED, that name simply cannot
        # be found again. Trigger-instant reads lose most of the session's signals.
        #
        # Done by re-running the SAME battery on an earlier slice (df.iloc[:-k]) —
        # not by a rolling "sticky" window. That distinction is the whole point:
        # the v5.0 Pine sticky window was reverted in v5.2 because it SUMMED
        # patterns across different bars, producing a Sigma that described no bar
        # that ever existed and a GO that contradicted its own gate chips. Here
        # each candidate bar is evaluated whole, and what is reported is a SNAPSHOT
        # of the one bar that fired: its age, its own Sigma, its own patterns.
        # Zero drift — identical function, identical flags, different last row.
        def _pa_recency(fn):
            # +1 (10-Aug-2026): `range(1, N)` stops at N-1, so a constant named
            # "_PA_LOOKBACK_BARS = 3" only ever looked back TWO bars. An NSE session is
            # 5 x 75m bars, so a third of the intended recency window was unreachable and
            # a pattern that fired 3 bars ago was simply lost from the board.
            for k in range(1, _PA_LOOKBACK_BARS + 1):
                if len(df) - k < 60:
                    break
                try:
                    _p = fn(df.iloc[:-k], "", intraday=True,
                            ema20_ref=_d_e20, ema10_ref=_d_e10)
                except Exception:
                    continue
                _s = sum(t for _n, _f, t, _x in _p if _f)
                if _s > 0:
                    return {"age": k, "sigma": _s,
                            "names": [n for n, f, _t, _x in _p if f]}
            return None

        _pa_now = _pap.detect_bull_patterns(df, "", intraday=True, ema20_ref=_d_e20, ema10_ref=_d_e10)
        _rpa_now = _pap.detect_recovery_patterns(df, "", intraday=True, ema20_ref=_d_e20, ema10_ref=_d_e10)
        return {
            "ok": True, "bars": len(df),
            "pa":  _pa_now,
            "rpa": _rpa_now,
            # Knife-edge patterns on THIS bar (see ctx["pa_marginal"]). Computed here so
            # it shares the one resampled frame — the perturbation re-runs the battery a
            # few times, which is cheap on an in-memory frame and pointless to repeat.
            "pa_marginal": sorted(_pap.marginal_patterns(
                df, intraday=True, ema20_ref=_d_e20, ema10_ref=_d_e10)),
            # Populated ONLY when the current bar is silent — a live PA needs no
            # recency, and reporting one would invite reading a stale age as fresh.
            "pa_recent":  (_pa_recency(_pap.detect_bull_patterns)
                           if not any(f for _n, f, _t, _x in _pa_now) else None),
            "rpa_recent": (_pa_recency(_pap.detect_recovery_patterns)
                           if not any(f for _n, f, _t, _x in _rpa_now) else None),
            "rsi": _f(_rsi), "adx": _f(_adx),
            "relvol": _s4_rv(v),   # S4 chart_rv: prior-50 baseline (AUD-PAR-12)
            "vol_dry": (_vol5 / _vol20) if _vol20 else None,
            "bar_ok": _bar_ok,
            "cmp": (float(df["Close"].iloc[-1]) if len(df) else None),   # live intraday last price
            "last_ts": df.index[-1].strftime("%d-%b %H:%M"),
            # The resampled trigger-TF frame itself. gm_evaluate recomputes WCL
            # (Wyckoff / SMC / Volume Profile) on THIS, because S4 computes those on
            # the chart TF — a daily-derived WCL would not be what the chart shows.
            "df": df,
        }
    except Exception as e:
        # Bucket on the exception TYPE — str(e) is per-symbol noise that would
        # give every name its own row in the board's count-by-reason.
        return {"ok": False, "code": f"error:{type(e).__name__}", "reason": str(e)}


import commander_pages   # the 22 page bodies (25-Sep-2026) - see commander_pages/__init__.py
if page == 'DASHBOARD':
    commander_pages.run("dashboard", globals())   # page body: commander_pages/dashboard.py

    # NOTE (10 May 2026): Recovery Alerts widget removed from Dashboard per user
    # feedback. Recovery signals are stock-level discovery signals; they belong in
    # HUNTER → Recovery Screener tab where you actually act on them. Dashboard is
    # for OPEN portfolio state, not for discovery-output overlay.

# ════════════════════════════════════════════════════════════════════════════
#  HUNTER
# ════════════════════════════════════════════════════════════════════════════
elif page == 'HUNTER':
    commander_pages.run("hunter", globals())   # page body: commander_pages/hunter.py


# ════════════════════════════════════════════════════════════════════════════
#  WATCHLIST
# ════════════════════════════════════════════════════════════════════════════
elif page == 'WATCHLIST':
    commander_pages.run("watchlist", globals())   # page body: commander_pages/watchlist.py

# ════════════════════════════════════════════════════════════════════════════
#  COMMAND CENTER
# ════════════════════════════════════════════════════════════════════════════
elif page == 'COMMAND':
    commander_pages.run("command", globals())   # page body: commander_pages/command.py

# ════════════════════════════════════════════════════════════════════════════
#  AI LAB
# ════════════════════════════════════════════════════════════════════════════
elif page == 'AI LAB':
    commander_pages.run("ai_lab", globals())   # page body: commander_pages/ai_lab.py

# ════════════════════════════════════════════════════════════════════════════
#  E-08: MACRO RADAR
# ════════════════════════════════════════════════════════════════════════════
elif page == 'MACRO':
    commander_pages.run("macro", globals())   # page body: commander_pages/macro.py

# ════════════════════════════════════════════════════════════════════════════
#  E-07: OPTIONS DESK
# ════════════════════════════════════════════════════════════════════════════
elif page == 'OPTIONS':
    commander_pages.run("options", globals())   # page body: commander_pages/options.py

# ════════════════════════════════════════════════════════════════════════════
#  E-09: TRADE AUTOPSY ENGINE
# ════════════════════════════════════════════════════════════════════════════
elif page == 'AUTOPSY':
    commander_pages.run("autopsy", globals())   # page body: commander_pages/autopsy.py

# ════════════════════════════════════════════════════════════════════════════
#  MISS-5: SIGNAL BACKTEST LAB
# ════════════════════════════════════════════════════════════════════════════
elif page == 'BACKTEST':
    commander_pages.run("backtest", globals())   # page body: commander_pages/backtest.py


# ══════════════════════════════════════════════════════════════════════════════
#  v4.0 — PRE-MARKET INTELLIGENCE HUB
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'PRE-MARKET':
    commander_pages.run("pre_market", globals())   # page body: commander_pages/pre_market.py


# ══════════════════════════════════════════════════════════════════════════════
#  v4.0 — POST-MARKET ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'POST-MARKET':
    commander_pages.run("post_market", globals())   # page body: commander_pages/post_market.py

# ══════════════════════════════════════════════════════════════════════════════
#  v4.0 — MARKET BREADTH ENGINE
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'BREADTH':
    commander_pages.run("breadth", globals())   # page body: commander_pages/breadth.py


# ══════════════════════════════════════════════════════════════════════════════
#  v4.0 Phase-4 — ETF TRADING SYSTEM
#  Added 11 May 2026 — consumes outputs of:
#    • etf_screener.py  (ETF_Screener_Results.csv)
#    • etf_rotation.py  (ETF_Sector_Rotation.csv, ETF_AssetClass_Regime.csv,
#                        ETF_RRG_Coordinates.csv, ETF_Top_Picks.csv)
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'ETF':
    commander_pages.run("etf", globals())   # page body: commander_pages/etf.py


# ══════════════════════════════════════════════════════════════════════════════
#  v4.0 Phase-2 — NEWS & SENTIMENT
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'NEWS':
    commander_pages.run("news", globals())   # page body: commander_pages/news.py


# ══════════════════════════════════════════════════════════════════════════════
#  v4.0 Phase-2 — FUNDAMENTALS HUB
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'FUNDAMENTALS':
    commander_pages.run("fundamentals", globals())   # page body: commander_pages/fundamentals.py


# ══════════════════════════════════════════════════════════════════════════════
#  v4.0 Phase-3 — PORTFOLIO ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'PORTFOLIO':
    commander_pages.run("portfolio", globals())   # page body: commander_pages/portfolio.py


# ══════════════════════════════════════════════════════════════════════════════
#  X-RAY — Deep Fundamental Analysis
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'X-RAY':
    commander_pages.run("x_ray", globals())   # page body: commander_pages/x_ray.py


# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
#  GOLDEN MATCHER — Single-symbol checklist
# ══════════════════════════════════════════════════════════════════════════════
# ----------------------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------------------
elif page == 'GOLDEN MATCHER':
    commander_pages.run("golden_matcher", globals())   # page body: commander_pages/golden_matcher.py

#  TV SIDECAR — Quick-look chart companion
# ══════════════════════════════════════════════════════════════════════════════
elif page == 'TV SIDECAR':
    commander_pages.run("tv_sidecar", globals())   # page body: commander_pages/tv_sidecar.py


# ══════════════════════════════════════════════════════════════════════════
#  ACTION CENTER
# ══════════════════════════════════════════════════════════════════════════
elif page == 'ACTION CENTER':
    commander_pages.run("action_center", globals())   # page body: commander_pages/action_center.py

# ══════════════════════════════════════════════════════════════════════════
#  RISK SHIELD — Active Exit Monitoring & Pullback Entry Tracking
# ══════════════════════════════════════════════════════════════════════════
elif page == 'RISK SHIELD':
    commander_pages.run("risk_shield", globals())   # page body: commander_pages/risk_shield.py


# ─────────────────────────────────────────────────────────────────────────────
# JOURNAL (23-Sep-2026) — the Trade Journal, in-app.
#
# Jay: "Journal should be an active part of web commander." It was the last
# EXTERNAL page: the nav button ran `streamlit run dhan_journal_v7.py` in a new
# console, which opened a SECOND Streamlit server on another port, under whatever
# `streamlit` resolves to on PATH — Python313's, not the venv the rest of the
# ecosystem runs on. Two servers, two browser tabs, two interpreters, one DB.
#
# dhan_journal_v7.py was split at the seam it already had (its line 510):
#   journal_core.py  the data layer, VERBATIM — one journal DB layer, not two
#   journal_page.py  the dashboard, wrapped in render()
# so this page is the same code the standalone app draws, not a reimplementation.
# That also ended the "importing it paints the whole journal into your page" bug
# class, which had cost Risk Shield and the Golden Matcher one rendering each.
#
# render(in_app=True) puts what used to be the journal's sidebar (account, open
# P&L, realised P&L, the sync buttons) into an in-page expander instead, because
# this app's sidebar is the navigation.
# ─────────────────────────────────────────────────────────────────────────────
elif page == 'JOURNAL':
    commander_pages.run("journal", globals())   # page body: commander_pages/journal.py
