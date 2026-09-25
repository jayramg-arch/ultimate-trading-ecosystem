"""commander_core.py - the Streamlit-free helpers of Web Commander, importable and testable.

MOVED VERBATIM from weinstein_commander_web_v4.0.py on 25-Sep-2026 by
tools/split_extract_core.py (docs/PLAN_web_commander_split.md, phase 2). Selection is
mechanical: no Streamlit call, directly or through a callee; no runtime-only global; no
`global` statement; and no other binding of the name anywhere in the app. The app does
`from commander_core import (...)`, so every name resolves exactly as before.

Edit HERE - the app file no longer holds these definitions.
"""
import pandas as pd
import os, sys, sqlite3, base64, math, importlib, logging, json
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
import house_policy as _HP
from gm_trigger_board import (STRUCTURAL_BULL_ARCHETYPES,
                              STRUCTURAL_RECOVERY_ARCHETYPES)
from gm_log import gm_log as _gm_logger


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

logger = logging.getLogger("__main__")   # the app's logger - same name as before the move

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

CLIENT_ID    = os.getenv("DHAN_CLIENT_ID")

_APP_DIR     = os.path.dirname(os.path.abspath(__file__))  # REC-4: absolute base dir

DB_FILE      = os.environ.get("COMMANDER_JOURNAL_DB") or os.path.join(_APP_DIR, "trade_journal_v6.db")   # env override: render tests use a copy  # BUG-H1: absolute path

JOURNAL_RENAME_MAP = {
    'symbol':'Symbol','trade_type':'Type','stoploss':'StopLoss','target':'Target',
    'rationale':'Rationale','timeframe':'Timeframe','entry_date':'EntryDate',
    'quantity':'Quantity','buy_price':'BuyPrice','exit_date':'ExitDate',
    'exit_price':'ExitPrice','exit_reason':'ExitReason','status':'Status',
    'sector':'Sector','trade_quality':'Quality','compromises':'Compromises',
    'lessons':'Lessons','screenshot_path':'Screenshot','planned_rr':'PlannedRR',
    'ai_analysis':'AI Analysis',
    'setup':'Setup','entry_stage':'EntryStage','entry_alpha':'EntryAlpha',
    'entry_rs':'EntryRS','entry_conviction':'EntryConviction',
    'snapshot_meta':'SnapshotMeta',
    'manual_sl_override':'Manual SL Override',
    'custom_ce_mult':'Custom CE Mult',
    'pyramid_status':'Pyramid Status',
}

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
        logging.getLogger("__main__").error(f"Dhan auth error: {e}")
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
            logging.getLogger("__main__").error(f"Failed to init dhanhq: {e}")
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
            logging.getLogger("__main__").info("Dhan token rejected. Forcing refresh...")
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
        daily_ret = (daily / total_cap * 100) if total_cap > 0 else daily * float("nan")  # daily return %
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

def _sb_cls(col: str) -> str:
    """Status-strip tint class, derived from the SAME colour the value text uses.

    Deriving it rather than passing a second flag is the point: a tint and a number
    that disagree is worse than no tint at all, and with one source they cannot.
    """
    c = (col or "").lower()
    if "--bull" in c:  return " is-bull"
    if "--bear" in c:  return " is-bear"
    if "--warn" in c:  return " is-warn"
    return " is-neut"

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

def _g(d: dict, *keys, default=None):
    """dict getter that treats None AND float NaN as missing (P0 fix, 14-Jul-2026).
    NaN is not None, so the old version let NaN sail into comparisons (NaN compares
    False everywhere) and into inr()/format strings — every call site needed a manual
    scrub and any missed one was a latent bug. Non-scalars (str/list/dict) pass
    through untouched; only a genuine float NaN is treated as absent."""
    for k in keys:
        if k in d and d[k] is not None:
            v = d[k]
            try:
                if isinstance(v, float) and math.isnan(v):
                    continue                    # NaN == missing → next key / default
            except Exception:
                pass                            # non-numeric oddball → return as-is
            return v
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

def _gm_bar_close_times(tf: str):
    """NSE 9:15–15:30 session bar-CLOSE clock times (h, m) for a trading TF. The
    375-min session tiles EXACTLY: 5×75m and 3×125m, so both land on 15:30."""
    _t75 = [(10, 30), (11, 45), (13, 0), (14, 15), (15, 30)]
    _t125 = [(11, 20), (13, 25), (15, 30)]
    # ── JAY'S CHECK-IN SCHEDULE (10-Aug-2026) — his desk clock, not the bar clock.
    # 10:35 · 11:50 · 13:30 · 14:20 · 15:35, with 125m joining at 11:50 / 13:30 / 15:35.
    # These are ~5 min AFTER a 75m close, which is why they work: at 10:35 the 10:30 bar
    # is closed and published. Two of them do NOT sit just after a 125m close (11:50 is
    # 30 min past the 11:20 bar; 13:30 is 5 min past 13:25) — that is HARMLESS, because a
    # rebuild always reads the last CLOSED bar, so the 11:50 125m board reads the 11:20
    # bar exactly as it should. It is a redundant rebuild, never a stale one.
    # settle is not added for these (see _gm_last_passed_boundary) — the 5-minute offset
    # he chose already is the settle.
    _c75 = [(10, 35), (11, 50), (13, 30), (14, 20), (15, 35)]
    _c125 = [(11, 50), (13, 30), (15, 35)]
    if tf == "checkin-75m":
        return _c75
    if tf == "checkin-125m":
        return _c125
    if tf == "checkin-Daily":
        return [(15, 35)]
    if tf == "checkin":                      # union, for a board showing both TFs
        return sorted(set(_c75) | set(_c125))
    if tf == "125m":
        return _t125
    # UNION (30-Jul, Jay): rebuild on EVERY 75m and 125m close — 7 distinct times, since
    # 15:30 is shared. Cadence only; the PA timeframe is still the Trigger-TF, so this
    # makes the board fresher, it does NOT add 125m signals to a 75m board.
    # A DAILY board changes ONCE — at the session close. Falling through to the 75m
    # list (the old behaviour for any unrecognised tf) rebuilt it at 10:30, 11:45,
    # 13:00 and 14:15 for an identical answer, because a Daily read takes the last
    # CLOSED daily bar and that does not move intraday. One rebuild, after the close.
    if tf == "Daily":
        return [(15, 30)]
    if tf == "75m+125m":
        return sorted(set(_t75) | set(_t125))
    return _t75                                                # 75m (default)

def _gm_last_passed_boundary(tf: str, settle_s: int = 75, now=None):
    """Most-recent 75/125m bar-CLOSE that has passed today (+settle so the broker
    has published the closed bar), as a datetime — or None (weekend / pre-first-
    close / after the last close already handled). Bar-aligned auto-refresh key:
    rebuild the board once per bar so it always reads a CLOSED 75m bar and can't
    disagree with the live Single Symbol page on a faded forming-bar trigger."""
    now = now or datetime.now()
    if now.weekday() >= 5:                      # Sat/Sun — no session
        return None
    # The check-in times already carry Jay's own ~5-minute offset from the bar close;
    # adding the 75s broker-settle on top would push 15:35 to 15:36:15 for no reason.
    if str(tf).startswith("checkin"):
        settle_s = 0
    passed = None
    for hh, mm in _gm_bar_close_times(tf):
        b = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if now >= b + timedelta(seconds=settle_s):
            passed = b                          # keep the latest one that's passed
    return passed

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
        from gm_trigger_board import atomic_write_text
        atomic_write_text(_GM_SETTINGS_FILE, json.dumps(d, indent=2))
    except Exception as e:
        # P1: a lost save silently forgets capital/risk/TF across restarts.
        _gm_logger.warning(f"gm_settings save failed (capital/risk/TF not persisted): {e}")

def _gm_use_pivot_zones() -> bool:
    """Pivot (structural) zones on/off — persisted in gm_settings.json.

    Jay does not rely on pivot shelves and wanted this switchable from settings
    rather than an env var read once at import. Default TRUE: rule A2 already makes a
    pivot earn a confirming source, and the 26-Aug A/B found no alpha difference
    between admitting pivots and refusing them -- only ~4x fewer trades. So this is a
    preference switch, not a fix; off = pattern zones only, on both surfaces.
    """
    # Default OFF since 25-Sep-2026 (Jay): pattern zones only.
    return bool(_gm_settings().get("use_pivot_zones", False))

def _gm_sync_pivot_setting() -> None:
    """Push the persisted setting into zone_engine. Called on every GM render because
    zone_engine holds it as a module global that an import-time env read would
    otherwise own for the life of the process."""
    try:
        import zone_engine as _zep
        _zep.set_use_structural(_gm_use_pivot_zones())
    except Exception as e:
        _gm_logger.warning(f"pivot-zone setting not applied (zones keep previous state): {e}")

def _gm_entry_method() -> str:
    """Entry method for the Plan/guided-exec wording — mirrors the S4 v4.8 toggle.
    'buystop' (default, house doctrine) = buy-STOP above the confirmed trigger bar's
    high (only fill on continuation, dodges the false-breakout trap). 'retest' = a
    buy-LIMIT at the trigger close on the pullback (lower entry / better R). The
    backtest (replay.py) found retest beat buy-stop on matched alpha, BUT the sim
    can't model the false-breakout whipsaw — this is a live TRIAL toggle, not a
    directive. GM only changes the fill INSTRUCTION; the trigger is unchanged."""
    return "retest" if str(_gm_settings().get("entry_method", "retest")) == "retest" else "buystop"

_GM_ENTRY_SRC = " — take that price off S4 (it latches the trigger bar); levels here are at CURRENT price"

def _gm_entry_instruction(tf_lbl="", short=False, src_note=True) -> str:
    """The order-placement phrase for the chosen entry method (see _gm_entry_method).

    src_note=True appends the provenance caveat above. Pass False only where the
    surrounding text already says the level comes from S4."""
    _note = _GM_ENTRY_SRC if src_note else ""
    if _gm_entry_method() == "retest":
        return ("buy-LIMIT @ the S4 trigger close on the pullback" if short
                else f"buy-LIMIT at the {tf_lbl + ' ' if tf_lbl else ''}trigger bar's close on the pullback (retest to value; skip a dead-volume fade){_note}")
    return ("buy-STOP above the S4 trigger bar high" if short
            else f"buy-STOP above that {tf_lbl + ' ' if tf_lbl else ''}bar's high. Never buy the touch{_note}")

def _range_bar(low, high, cmp_, marks) -> str:
    if not (low and high and high > low and cmp_):
        return "<div style='font-size:11px;color:var(--faint);'>52W range unavailable</div>"
    span = high - low
    def p(x): return max(0.0, min(100.0, (x - low) / span * 100.0))
    ticks = ""
    for x, lab, col in marks:
        if x is None:
            continue
        ticks += (f"<div style='position:absolute;left:{p(x):.1f}%;top:10px;width:1.5px;height:8px;"
                  f"background:{col};transform:translateX(-50%)'></div>"
                  f"<div style='position:absolute;left:{p(x):.1f}%;top:19px;transform:translateX(-50%);"
                  f"font-size:8.5px;font-weight:600;color:var(--muted);white-space:nowrap'>{lab}</div>")
    cp = p(cmp_)
    return (f"<div style='position:relative;margin:8px 0 32px;'>"
            f"<div style='position:relative;height:8px;border-radius:6px;"
            f"background:linear-gradient(90deg,rgba(254,226,226,0.6),rgba(254,243,199,0.6),rgba(209,250,229,0.6));'>"
            f"<div style='position:absolute;left:{cp:.1f}%;top:-6px;transform:translateX(-50%);width:0;height:0;"
            f"border-left:5px solid transparent;border-right:5px solid transparent;border-top:10px solid var(--bull);'></div>"
            f"{ticks}</div>"
            f"<div style='display:flex;justify-content:space-between;font-size:9.5px;color:var(--muted);font-weight:600;margin-top:4px'>"
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
        action = f"Confirm a CLOSED 75/125m trigger → {_gm_entry_instruction(short=True)}. Size {_g(rec,'Suggested_Size','—')}."
    elif g1 and g2 and g3:
        verdict, color = "READY · AWAIT TRIGGER", "var(--warn)"
        reason = f"All 3 gates pass · catalyst {catalyst} firing; no daily PA trigger printed yet."
        action = "Set an alert at the fresh zone; act ONLY on a fired PA pattern + closed 75/125m trigger bar."
    elif g1 and g2:
        verdict, color = "BUY ON TRIGGER", "var(--warn)"
        reason = "Context + strength pass; timing/location gate still pending."
        action = "Set an alert at the fresh zone; act ONLY on a closed 75/125m trigger bar."
    elif g1:
        verdict, color = "WATCHLIST", "var(--warn)"
        reason = "Stage-2 context OK but strength is incomplete."
        action = "Track only — needs RS / Alpha / Minervini to firm up."
    else:
        verdict, color = "NOT YET", "#787B86"
        reason = "Context gate not met (Stage 2 + above 30W MA)."
        action = "No setup. Re-check when context turns."
    if counter and verdict not in ("AVOID / EXIT", "WATCHLIST", "NOT YET"):
        reason += "  ⚠ Counter-trend (index not bull) — size halved."
    return {"verdict": verdict, "color": color, "reason": reason, "action": action, "gates": gates}

def _grade(a) -> str:
    a = a or 0
    return ("A+ Excellent" if a >= 80 else "A Strong" if a >= 70 else "B Good" if a >= 55
            else "C Fair" if a >= 40 else "D Weak")

RR_MIN_LOCATION = 2.0          # min reward:risk for "good location"

EMA20_EXT_ATR_MAX = 3.5        # bull: not extended more than this many ATR above EMA20

EMA20_RECLAIM_BAND_PCT = 8.0

INHERIT_QUALIFICATION = True

SL_BUF_PCT = 0.5          # S4 plan_slbuf_pct

SL_MULT_SWING, SL_MULT_POS = 2.5, 4.0   # S4 tt_sl_swing / tt_sl_pos

SL_MULT_SWING, SL_MULT_POS = 2.5, 4.0   # S4 tt_sl_swing / tt_sl_pos

TT_SWING_ATR_PCT, TT_SWING_OFF52 = 4.0, 30.0   # S4 swing_atr_max / swing_off52_max

TT_SWING_ATR_PCT, TT_SWING_OFF52 = 4.0, 30.0   # S4 swing_atr_max / swing_off52_max

def _gm_zone_rungs(zs_list):
    """(in-zone distal, nearest-below distal) across zone_support() results, S4 order."""
    in_best, near_best = None, None
    for z in zs_list:
        if not z:
            continue
        if z.get("zone_state") in ("inside", "reacting") and z.get("distal") is not None:
            sc = z.get("recency_score")
            sc = z.get("score") if sc is None else sc
            sc = -1.0 if sc is None else float(sc)
            if in_best is None or sc > in_best[0]:
                in_best = (sc, float(z["distal"]))
        if z.get("near_dz_proximal") is not None and z.get("near_dz_distal") is not None:
            if near_best is None or float(z["near_dz_proximal"]) > near_best[0]:
                near_best = (float(z["near_dz_proximal"]), float(z["near_dz_distal"]))
    return (in_best[1] if in_best else None), (near_best[1] if near_best else None)

def _gm_sl_basis(zs_list, df, tf):
    """Everything the stop ladder needs, on the chart TF `df`. Never raises."""
    b = {"tf": tf, "in_dist": None, "near_dist": None, "swing_lo10": None, "atr": None,
         "close": None}
    try:
        b["in_dist"], b["near_dist"] = _gm_zone_rungs(zs_list)
    except Exception as e:
        # Loud (25-Sep-2026): a silent miss here drops the zone rungs from the stop
        # ladder and the SL falls to swing-low/ATR with nothing saying why.
        _gm_logger.warning(f"stop ladder ({tf}): zone rungs unavailable, SL falls back: {e}")
    try:
        if df is not None and len(df) >= 15:
            h, l, c = df["High"], df["Low"], df["Close"]
            tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
            b["atr"] = float(tr.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1])
            b["swing_lo10"] = float(l.iloc[-10:].min())
            b["close"] = float(c.iloc[-1])
    except Exception as e:
        _gm_logger.warning(f"stop ladder ({tf}): ATR / swing-low unavailable: {e}")
    return b

def _plan_structural_sl(ctx, entry, atr, ret_src=False):
    """S4's stop ladder (see the block comment above). Returns a price (or
    (price, source) with ret_src) -- None when there is no entry. `atr` is only the
    last-resort ATR when the chart-TF basis is missing."""
    if not entry:
        return (None, "") if ret_src else None
    sup = _g(ctx, "support", default={}) or {}
    b = sup.get("sl_basis") or {}
    a = b.get("atr") or atr
    _cl = b.get("close") or entry
    atr_pct = (a / _cl * 100.0) if (a and _cl) else 0.0
    _d52 = _g(ctx, "dist52wh")                       # negative % off the 52W high
    _off52 = abs(_d52) if (_d52 is not None and _d52 < 0) else 0.0
    _s200, _cmp = _g(ctx, "sma200"), _g(ctx, "cmp") or _cl
    _bel200 = bool(_s200 and _cmp and _cmp < _s200)
    tt_swing = atr_pct > TT_SWING_ATR_PCT or _off52 > TT_SWING_OFF52 or _bel200
    mult = SL_MULT_SWING if tt_swing else SL_MULT_POS
    lvl, src = None, ""
    for key, name in (("in_dist", "zone distal (in-zone)"),
                      ("near_dist", "nearest zone distal"),
                      ("swing_lo10", "10-bar swing low")):
        v = b.get(key)
        if v is not None:
            lvl, src = float(v), name
            break
    if not a or a <= 0:
        # No ATR at all: the structural level alone, else nothing (never invent a stop).
        sl = lvl * (1 - SL_BUF_PCT / 100) if (lvl is not None and lvl < entry) else None
    elif lvl is None or lvl >= entry:
        sl, src = entry - mult * a, f"{mult:.1f}xATR (no structure below)"
    else:
        sl = lvl * (1 - SL_BUF_PCT / 100)
        if (entry - sl) > mult * a:
            sl, src = entry - mult * a, f"{src} capped at {mult:.1f}xATR"
    if sl is not None and sl >= entry:
        sl = None
    src = (src + f" · {'SWING' if tt_swing else 'POSITIONAL'} · {b.get('tf') or '?'}") if sl else ""
    return (sl, src) if ret_src else sl

def _house_initial_stop(symbol, entry):
    """The GM/S4 initial stop for a sizer that has no GM context (AUD-INT-12, Jay 25-Sep-2026).

    Same ladder as _plan_structural_sl: in-zone distal -> nearest zone distal below ->
    10-bar swing low, 0.5% buffer, capped at 2.5xATR (swing) / 4.0xATR (positional), with
    the zones built exactly as the GM Daily loader builds them (zone_engine on D / W / M).
    The AI-Trade Proposer used an ADR-bucket multiple and the AI-LAB sniper 2xATR - two
    more initial-stop rules. Returns (stop, source); (None, why) rather than an invented
    stop."""
    try:
        import data_provider as _dp_hs
        import zone_engine as _ze_hs
        import pa_patterns as _pap_hs
        df = _dp_hs.fetch_ohlcv(symbol, period="5y", interval="1d", use_cache=True, auto_adjust=True)
        if df is None or len(df) < 60:
            return None, "not enough daily history"
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        px = float(df["Close"].iloc[-1])
        zD = _ze_hs.zone_support(df, "D", px)
        wk = _pap_hs._confirmed_weekly_ohlcv(df)
        zW = _ze_hs.zone_support(wk, "W", px) if (wk is not None and len(wk) >= 60) else {}
        mo = _pap_hs._confirmed_month_ohlcv(df)
        zM = _ze_hs.zone_support(mo, "M", px) if (mo is not None and len(mo) >= 60) else {}
        basis = _gm_sl_basis((zD, zW, zM), df, "Daily")
        hi52 = float(df["High"].iloc[-252:].max())
        s200 = float(df["Close"].rolling(200).mean().iloc[-1]) if len(df) >= 200 else None
        ctx = {"support": {"sl_basis": basis}, "cmp": px, "sma200": s200,
               "dist52wh": (px / hi52 - 1.0) * 100.0 if hi52 else None}
        sl, src = _plan_structural_sl(ctx, float(entry), basis.get("atr"), ret_src=True)
        return (sl, src) if sl else (None, "no structural or ATR stop below entry")
    except Exception as e:
        _gm_logger.warning(f"house initial stop {symbol}: {e}")
        return None, f"stop computation failed: {type(e).__name__}"

GM_BFF_MIN = 4          # BFF's STRONG band; matches pullback_finder + the catalyst gate

GM_LOC_STRICT = True

GM_PIVOT_NEEDS_CONFLUENCE = True

def _gm_bff_gate(ctx):
    """True = passes, False = fails, None = unreadable (do NOT fail on None).

    Tri-state on purpose. A screener.in outage is a judgement about our data,
    not the company; failing on it would empty the board and look like a market
    with nothing in it. Same rule as pullback_finder's weak-vs-unreadable split.
    """
    try:
        from bull_fundamental_filter import bff_passes, roe_gate, de_gate
        b = _g(ctx, "bff") or {}
        # ROE and leverage are separate Tier-2 gates (docs/25 section 8.1), kept
        # out of the score so a rejection names its own leg. Either failing is a
        # fail; None (unreadable, or D/E on a lender) never rejects.
        if roe_gate(b) is False or de_gate(b) is False:
            return False
        return bff_passes(b, GM_BFF_MIN)
    except Exception:
        return None

def _gm_core_gate(symbol):
    """Size / pledge / ownership floor. None = gate unavailable, keep the name."""
    if not symbol:
        return None
    try:
        import core_universe as _cu
        elig = _cu.eligible_symbols()
        if elig is None:
            return None
        return _cu.gate(symbol, elig)
    except Exception:
        return None

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

    # FUNDAMENTALS NOW GATE (Jay, 13 Aug 2026: "Currently, in GM, BFF is not
    # gated. It should be. Have a similar approach for all other categories as
    # well. In fact, today I noticed that a Microcap has slipped into my
    # portfolio, due to these sporadic set of fundamental filters.")
    #
    # BFF was display-only here under the catalyst-gate philosophy (structure
    # fires, quality is status). That philosophy still holds for TECHNICAL
    # quality - it is why alpha stayed a status on the catalysts - but it was
    # never meant to cover the BUSINESS. Overridden on instruction.
    #
    # UNREADABLE does NOT fail: a screener.in outage is a judgement about our
    # data, not the company, and blocking on it would empty the board silently.
    # The same distinction pullback_finder draws between weak and unreadable.
    # AN ETF HAS NO FUNDAMENTALS TO GATE (24-Aug-2026). Caught live by Jay the
    # morning after the ETF source was wired: GOLDETF printed "⛔ funda" on the
    # board. Both gates return True/False/None, and None means "unknown" -- but for
    # an index fund they were returning FALSE, i.e. REJECTED. There is no BFF for a
    # basket, no promoter to pledge, no ownership concentration to check. The gate
    # was answering a question that does not apply and calling the answer a failure.
    #
    # I checked that overall_score ABSTAINS on missing fundamentals -- it does, and
    # I verified it -- and then did not check that a SECOND, separate fundamental
    # gate exists downstream. Same defect shape as gate-closed-in-three-places, in
    # the other direction.
    #
    # Short-circuited rather than post-filtered, for a second reason: _gm_bff_gate
    # pulls screener.in, so 28 ETFs was 28 pointless fetches per board build against
    # a source that already needed a circuit breaker for burst throttling.
    _is_etf = "ETF" in (_g(ctx, "inherited_setup") or [])
    if _is_etf:
        _bff_gate = None
        _core_gate = None
    else:
        _bff_gate = _gm_bff_gate(ctx)                                  # True/False/None
        _core_gate = _gm_core_gate(_g(rec, "Symbol", default=""))       # True/False/None
    if _bff_gate is False or _core_gate is False:
        g2 = False
    g3 = cat_on

    # ── P1 INHERITED QUALIFICATION ──────────────────────────────────────────────
    # When the name arrives WITH a source archetype (Chartink+Screener already
    # qualified it), the board must NOT re-screen it. Trust Context+Quality and run
    # only a lightweight "still-valid" break-down guard; fundamentals become a
    # ranking overlay (never a veto); the inherited archetype IS the setup. This is
    # what makes the rigorous watchlists — Bull AND Recovery — actionable on their
    # own trigger instead of dead-ending on a live catalyst. Flag-gated for A/B.
    inherited_setup = _g(ctx, "inherited_setup")
    inherited = bool(INHERIT_QUALIFICATION and inherited_setup)
    # Break-down guard — invalidate ONLY on positively-observed break-down (Stage 3/4
    # OR price seen below the 30WMA proxy). Missing sma150 must NOT flip a name to
    # INVALIDATED (honesty rule: no NaN→veto). Benefit of the doubt when unseen.
    _below_30wma = bool(_s150 and cmp_px and cmp_px < _s150)
    still_valid = (not s34) and (not _below_30wma)
    if inherited:
        g1 = still_valid          # CONTEXT → still-valid guard (not Stage-4, holds 30WMA)
        g2 = True                 # QUALITY → overlay (Alpha/Minervini rank, never block)
        g3 = True                 # SETUP → inherited archetype (no live catalyst required)
        # ...but FUNDAMENTALS still gate (13 Aug 2026). Inheritance exists so the
        # board stops re-running the TECHNICAL screen a rigorous watchlist already
        # passed - Alpha, Minervini, RRG stay a ranking overlay, exactly as above.
        # It was never meant to wave through the BUSINESS. Re-applied here because
        # the assignment above would otherwise silently undo the gate for the
        # majority of the board: on the 13 Aug board ALL 113 names were inherited,
        # so a gate placed before this block would have bitten on nothing.
        # None (unreadable/unavailable) still keeps the name - a data judgement.
        if _bff_gate is False or _core_gate is False:
            g2 = False
    # g4 (LOCATION) computed below — after R:R — in the "room rule" block.

    entry = _g(rec, "Entry", default=cmp_px); sl_pct = _g(rec, "SL_pct"); t1_pct = _g(rec, "T1_pct")
    # NaN → None so `if x` guards behave and formats never print "nan".
    entry, sl_pct, t1_pct = [
        (None if (v is None or (isinstance(v, float) and math.isnan(v))) else v)
        for v in (entry, sl_pct, t1_pct)]
    rr = None
    if entry and sl_pct is not None:
        sl = entry * (1 - sl_pct / 100); t1 = entry * (1 + t1_pct / 100) if t1_pct else None
        rr = (t1_pct / sl_pct) if (t1_pct and sl_pct) else None
        plan = (f"Set SL {inr(sl)} (-{sl_pct:.1f}%), size at {_HP.risk_label()} risk, place order + GTT. "
                f"Target T1 {inr(t1)} ({fnum(rr,1)}R).")
    else:
        sl = t1 = None
        plan = "No active catalyst → no plan yet. Levels are reference only."

    # ── LOCATION FALLBACK (Jay's rule): when the catalyst plan gives NO levels and
    # there's no nearby demand zone / OB / FVG, use EMA20 as the DYNAMIC support so a
    # location / R:R is ALWAYS computed. For a long above EMA20: risk = cmp − EMA20;
    # target = the 52W high (natural overhead), else a 2R default. If price is below
    # EMA20, EMA20 is resistance (not a long stop) → no fallback, location stays weak.
    _ema20 = _g(ctx, "ema20"); _atr = _g(ctx, "atr")
    _sup0 = _g(ctx, "support", default={}) or {}
    _near_zone = bool(_sup0.get("at_support"))          # a real demand zone/OB/FVG is nearby
    if rr is None and not _near_zone and _ema20 and cmp_px and cmp_px > _ema20:
        _risk = cmp_px - _ema20
        if _risk > 0:
            _d52 = _g(ctx, "dist52wh")                  # % below 52WH (negative)
            _tgt = cmp_px * (1 + abs(_d52) / 100.0) if (_d52 is not None and _d52 < 0) else None
            if not _tgt or _tgt <= cmp_px:
                _tgt = cmp_px + 2.0 * _risk             # 2R default when no overhead level
            entry, sl, t1 = cmp_px, _ema20, _tgt
            sl_pct = _risk / cmp_px * 100.0
            rr = (_tgt - cmp_px) / _risk
            plan = (f"No catalyst plan — EMA20 as dynamic support: {_gm_entry_instruction(short=True)}, "
                    f"SL {inr(sl)} (EMA20, −{sl_pct:.1f}%), target {inr(t1)} ({fnum(rr,1)}R).")

    # ── STRUCTURAL + ATR-CAPPED SL (twin of the S4 Pine v3.0 fix). Prefer the nearest
    # FRESH zone distal BELOW entry; then cap risk at 3×ATR so the stop can never be
    # absurdly far. Recompute sl_pct / rr (a tighter, correct stop also fixes the R:R).
    _ssl, _ssl_src = _plan_structural_sl(ctx, entry, _atr, ret_src=True)
    if entry and _ssl is not None:
        sl = _ssl
        sl_pct = (entry - sl) / entry * 100.0
        if t1 and t1 > entry:
            rr = (t1 - entry) / (entry - sl)
        plan = (f"Buy-STOP above the trigger bar · SL {inr(sl)} ({_ssl_src}, −{sl_pct:.1f}%)"
                + (f" · T1 {inr(t1)} ({fnum(rr,1)}R)" if (t1 and rr) else "")
                + f" · size at {_HP.risk_label()} risk.")
    elif entry and sl is not None and _atr and _atr > 0 and (entry - sl) > 3.0 * _atr:
        sl = entry - 2.5 * _atr                    # cap even the screener/EMA20 SL if it's too far
        sl_pct = (entry - sl) / entry * 100.0
        if t1 and t1 > entry:
            rr = (t1 - entry) / (entry - sl)
        plan = (f"Buy-STOP above the trigger bar · SL {inr(sl)} (ATR-capped, −{sl_pct:.1f}%)"
                + (f" · T1 {inr(t1)} ({fnum(rr,1)}R)" if (t1 and rr) else "")
                + f" · size at {_HP.risk_label()} risk.")

    # ── Step-4 "room" rule: R:R (the real reward-room off the disciplined stop) +
    # EMA20 extension/direction. EMA20 (daily) = support above / resistance below.
    ema20_dist_atr = ((cmp_px - _ema20) / _atr) if (_ema20 and _atr and _atr > 0) else None
    above_ema20 = bool(_ema20 and cmp_px >= _ema20)
    rr_ok = (rr is not None and rr >= RR_MIN_LOCATION)
    # Bull "at value": above EMA20 (support) AND not chasing (≤ N ATR above it).
    ema20_ok = bool(above_ema20 and (ema20_dist_atr is None or ema20_dist_atr <= EMA20_EXT_ATR_MAX))
    g4 = above_value and rr_ok and ema20_ok
    _loc_fail = []
    if not rr_ok:       _loc_fail.append("thin R:R" if rr is not None else "no R:R")
    if not ema20_ok:    _loc_fail.append("extended" if above_ema20 else "below EMA20")
    if not above_value: _loc_fail.append("below value")
    loc_note = " / ".join(_loc_fail)
    # No live bull_screener catalyst — but the name is pre-qualified by its source
    # watchlist (Chartink+Screener setup), so it still TRADES on its own trigger;
    # "no catalyst" is a caveat, not a block. Surfaced in the board Loc column.
    if not g3:
        loc_note = ("no catalyst / " + loc_note) if loc_note else "no catalyst"

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
    # GATED since 13 Aug 2026 — the tick now reflects the same test QUALITY applies,
    # not a looser display band, so a red BFF row explains a failed g2 instead of
    # sitting green beside it.
    _bff_ok = (_bff_gate is not False)
    _core_val = ("—" if _core_gate is None else ("PASS" if _core_gate else "below floor"))

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
                       ("Size/pledge", _core_val, _core_gate is not False),
                       ("ML Prob", fnum(ml, 0, "%"), (ml or 0) >= 60)] if is_accum else
                      [("Asset Qual", f"{alpha:.0f}/100", alpha >= 70),
                       ("Minervini", f"{mpass}/8", mpass >= 6),
                       ("RRG", rrg, rrg_ok),
                       ("BFF (funda)", _bff_val, _bff_ok),
                       ("Size/pledge", _core_val, _core_gate is not False),
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
             do_fail="No live bull_screener catalyst — but this is a pre-qualified setup (source watchlist); "
                     "a fired Step-5 trigger still BUYS. Else set a price alert at the zone and wait."),
        dict(n=4, title="LOCATION", sub="Room: R:R + EMA20", hard=False, ok=g4,
             metrics=[("R:R", (f"{rr:.1f}:1" if rr is not None else "—"), rr_ok),
                      ("vs EMA20", (f"{ema20_dist_atr:+.1f}ATR {'sup' if above_ema20 else 'res'}"
                                    if ema20_dist_atr is not None else ("above" if above_ema20 else "below")), ema20_ok),
                      ("vs CPR+VWAP", "above" if above_value else "below", above_value),
                      ("Room 52WH", fnum(d52, 1, "%"), None),      # context only — NOT a gate
                      ("Support (auto)", _sup_zone, _at_support)],
             do_pass="Good location — adequate R:R and not extended above EMA20 (support below).",
             do_fail=("Location weak (" + (loc_note or "thin R:R / extended") + ") — a fired TRIGGER still buys "
                      "(shown with the caveat); otherwise WAIT for a pullback toward EMA20 / a fresh zone.")),
        dict(n=5, title="TRIGGER", sub=(f"{_tf_lbl} PA battery" if _is_intra else "Daily PA battery + intraday confirm"),
             hard=False, ok=None, manual=True,
             metrics=[("PA trigger", (_pa_names if pa_fired else
                       ("⚠ DETECTION ERROR" if _g(ctx, "pa_error") else "none yet")), pa_fired),
                      ("Σ tier", (f"+{_pa_tier}" if _pa_tier else "0"), _pa_tier >= 2),
                      ("Confirm on", _confirm_lbl, None)],
             do_now=((f"TRIGGER LIVE — {_pa_names} (Σ+{_pa_tier}) fired on the {_fired_on}"
                      + (f" bar at the zone → {_gm_entry_instruction(_tf_lbl)}."
                         if _is_intra else
                         f". Drop to 75/125m, confirm a CLOSED bar at the zone → {_gm_entry_instruction()}."))
                     if pa_fired else
                     (f"No {_fired_on} PA trigger yet. Wait for a closed-bar pattern (VCP-BO / Pocket / 3-Bar / "
                      f"Undercut / Spring / IB-NR7 …) at the zone on the {_tf_lbl} chart, then {_gm_entry_instruction(short=True)}."))),
        dict(n=6, title="EXECUTE", sub="Plan & GTT", hard=False, ok=None, execute=True,
             metrics=[], do_now=plan),
    ]

    # ── INHERITED-MODEL DISPLAY: when the name is pre-qualified by a source
    # watchlist, the tree must SAY what the engine does — Steps 1-3 stop being
    # "re-screen & maybe SKIP" and become "confirm it hasn't broken down → then
    # time it", with quality/setup demoted to status. (The gating g1/g2/g3 was
    # already switched to this model above; here we relabel the DISPLAY to match.)
    if inherited:
        _arche_lbl = ", ".join(inherited_setup) if isinstance(inherited_setup, (list, tuple)) else str(inherited_setup)
        steps[0] = dict(n=1, title="STILL VALID?", sub="Break-down guard", hard=True, ok=g1,
             metrics=[("Stage", stage or "—", not s34),
                      ("Holds 30WMA", ("yes" if not _below_30wma else "no"), not _below_30wma),
                      ("RS vs N500", f"{(mansfield or 0):+.1f}", rs),
                      ("Regime", regime, regime == "BULL")],
             do_pass=f"Still valid — not Stage 3/4 and holding the 30WMA. Qualified by its "
                     f"{_arche_lbl} watchlist; the board is TIMING it, not re-screening.",
             do_fail="Broke down since it was watchlisted (Stage 3/4 or lost the 30WMA) → "
                     "INVALIDATED. Drop it — don't trade the setup.")
        # TECHNICAL quality stays an overlay for inherited names; FUNDAMENTALS do
        # not. This dict REPLACES steps[1] wholesale, so hard-coding hard=False /
        # ok=True here discarded the g2 gate at render time - ACE (BFF 2/5) still
        # read as passing after the engine had already failed it. Third place the
        # same override had to be closed: the gate, the inherited block, and now
        # the renderer.
        _fund_fail = (_bff_gate is False or _core_gate is False)
        steps[1] = dict(n=2, title="QUALITY",
             sub=("Fundamentals · HARD" if _fund_fail else "Overlay · status only"),
             hard=_fund_fail, ok=not _fund_fail,
             metrics=[("Asset Qual", f"{alpha:.0f}/100", alpha >= 70),
                      ("Minervini", f"{mpass}/8", mpass >= 6),
                      ("RRG", rrg, rrg_ok),
                      ("BFF (funda)", _bff_val, _bff_ok),
                      ("Size/pledge", _core_val, _core_gate is not False)],
             do_pass="Technical quality is an OVERLAY here — Chartink + Screener.in already "
                     "vetted leadership. Strong reads rank it higher; weak TECHNICAL reads "
                     "never block. Fundamentals (BFF, size/pledge) DO block.",
             do_fail=("Fails the fundamental floor — "
                      + ("BFF below the bar. " if _bff_gate is False else "")
                      + ("below the size/pledge/ownership floor. " if _core_gate is False else "")
                      + "Inheritance covers the technical screen, not the business. SKIP."))
        steps[2] = dict(n=3, title="SETUP", sub="Inherited archetype", hard=False, ok=True,
             metrics=[("Archetype", _arche_lbl, True),
                      ("Catalyst", cat, cat_on),
                      ("VCP/Base", ("valid" if vcp else "no"), vcp),
                      ("PA Patterns", (f"+{_pa_tier}" if _pa_tier else "none"), _pa_tier >= 2)],
             do_pass=f"Setup = the inherited {_arche_lbl} thesis. No live catalyst required — "
                     f"go straight to location & trigger.",
             do_fail="")

    stop_at = None
    for s in steps:
        if s.get("hard") and not s["ok"]:
            stop_at = s["n"]; break

    # Catalyst-Scan names have NO structural setup — the catalyst WAS their thesis (a
    # time-localized event), unlike Hunter/Pullback (a structure that persists). So a
    # catalyst-scan-ONLY inherited name must still have a LIVE catalyst OR a fired PA
    # trigger to stay actionable; otherwise it's a stale scan hit → WATCHLIST.
    _structural_bull = any(a in STRUCTURAL_BULL_ARCHETYPES
                           for a in (inherited_setup or []))
    _catalyst_only = inherited and not _structural_bull
    if inherited:
        # INHERITED path: qualification is trusted; the ONLY veto is the break-down
        # guard. Everything else is pure timing (arm → trigger).
        if not still_valid:
            verdict, color = "INVALIDATED · broke down", "#EF5350"
        elif _catalyst_only and not (cat_on or pa_fired):
            verdict, color = "WATCHLIST · catalyst expired", "var(--warn)"
        elif pa_fired:
            verdict = "BUY — TRIGGER LIVE" + (f" · {loc_note}" if loc_note else "")
            color = "#26A69A"
        elif not g4:
            verdict, color = "WAIT FOR PULLBACK", "var(--warn)"
        else:
            verdict, color = "ARMED · AWAIT TRIGGER", "var(--warn)"
    elif s34 or not rs:
        verdict, color = "AVOID / EXIT", "#EF5350"
    elif stop_at == 1:
        verdict, color = "AVOID", "#EF5350"
    elif stop_at == 2:
        verdict, color = "WATCHLIST", "var(--warn)"
    elif pa_fired:
        # TRIGGER WINS — a live Step-5 trigger is NEVER vetoed by Step-3 (catalyst)
        # or Step-4 (location). The name is already pre-qualified by its source
        # watchlist (hard Context + Quality still passed), so a fired pattern is
        # actionable on its OWN setup; missing catalyst / weak location = caveat.
        verdict = "BUY — TRIGGER LIVE" + (f" · {loc_note}" if loc_note else "")
        color = "#26A69A"
    elif not g3:
        verdict, color = "BUY-WATCH · no catalyst", "var(--warn)"
    elif not g4:
        verdict, color = "WAIT FOR PULLBACK", "var(--warn)"
    else:
        verdict, color = "ARMED · AWAIT TRIGGER", "var(--warn)"

    # The single step that needs attention right now
    if inherited and not still_valid:
        current = 1
    elif inherited and _catalyst_only and not (cat_on or pa_fired):
        current = 3                      # its thesis (the catalyst) is gone
    elif stop_at:
        current = stop_at
    elif pa_fired:
        current = 5
    elif not g3:
        current = 3
    elif not g4:
        current = 4
    else:
        current = 5
    actionable = not verdict.startswith(("AVOID", "WATCHLIST", "INVALIDATED"))
    return dict(steps=steps, verdict=verdict, color=color, stop_at=stop_at,
                # fund_block: the FUNDAMENTAL floor rejected this name (BFF or the
                # size/pledge/ownership core). Exposed so the board can suppress the
                # S4-GO cell - a 4/4 GO is the most eye-catching thing on a glance
                # surface, and advertising it on a name the engine has rejected
                # invites exactly the trade the gate exists to prevent.
                fund_block=bool(_bff_gate is False or _core_gate is False),
                # tri-state for the board's fifth gate. False = a floor rejected it;
                # None = a floor could not be READ, which is a judgement about our
                # data and never about the company; True = actually verified.
                fund_ok=(False if (_bff_gate is False or _core_gate is False)
                         else None if (_bff_gate is None or _core_gate is None)
                         else True),
                current=current, actionable=actionable, loc_note=loc_note,
                inherited=inherited, still_valid=still_valid, location_ok=bool(g4),
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
    # SCORED AND BELOW THE FLOOR - distinct from "not scored". S4's fundGate makes the
    # same split (an unscored name passes while fund_strict is off; a scored one below
    # the floor fails), and so does the stage guard further down: an UNKNOWN passes,
    # only a positively-observed failure rejects. Derived from rff_ok rather than
    # restating the comparison, so the two can never drift apart.
    _rff_scored_fail = (rff_q != "INSUFFICIENT") and not rff_ok
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

    # ROBUST LEVELS (mirror the bull path). The recovery engine row can lack
    # absolute Entry/SL/T1 (a Wyckoff WYC-* signal, or an ad-hoc name not in the
    # batch scan) — which left the guided-execution sizer EMPTY on a live recovery
    # trigger, unlike the bull path (which defaults Entry to CMP + derives SL/T1
    # from %). Default Entry to CMP and derive SL/T1 from % / R / ATR so an
    # actionable recovery trigger ALWAYS populates the plan.
    if entry is None:
        entry = cmp_px
    if sl is None and entry and sl_pct is not None:
        sl = entry * (1 - sl_pct / 100.0)
    if sl is None and entry:
        # LOCATION FALLBACK (Jay's rule, mirror of the bull path): the engine gave no
        # SL. Prefer EMA20 as DYNAMIC support when there's no nearby demand zone/OB/FVG
        # and price has reclaimed it (turn confirmed) — the natural stop for a recovery
        # turn. Only fall to 2.5×ATR when EMA20 doesn't apply (price below it).
        _sup0 = _g(ctx, "support", default={}) or {}
        _ema20_0 = _g(ctx, "ema20")
        if (not _sup0.get("at_support")) and _ema20_0 and cmp_px and cmp_px > _ema20_0:
            sl = _ema20_0                        # EMA20 dynamic support (no zone nearby)
        else:
            _atr_r = _g(ctx, "atr")
            if _atr_r:
                sl = entry - 2.5 * _atr_r        # recovery catalyst-aware fallback (2.5×ATR)
    # STRUCTURAL + ATR-CAPPED SL (twin of the bull path + S4 Pine v3.0). Prefer the
    # nearest FRESH zone distal BELOW entry; cap risk at 3×ATR so the stop is never
    # absurdly far. Done BEFORE R:R so t1/rr resolve off the disciplined stop.
    _atr_r2 = _g(ctx, "atr")
    _ssl_r = _plan_structural_sl(ctx, entry, _atr_r2)
    if entry and _ssl_r is not None:
        sl = _ssl_r
    if entry and sl and sl < entry:
        sl_pct = (entry - sl) / entry * 100.0
    if rr is None and entry and sl and t1 and (entry - sl):
        rr = (t1 - entry) / (entry - sl)
    if t1 is None and entry and sl:
        t1 = entry + (rr if rr else 2.5) * (entry - sl)   # engine R:R, else 2.5R default
    if rr is None and entry and sl and t1 and (entry - sl) > 0:
        rr = (t1 - entry) / (entry - sl)                  # final R:R once all levels resolved

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
    not_chased = (ext_ema is None) or (ext_ema <= EMA20_RECLAIM_BAND_PCT)  # ≤ band % above 20-EMA
    # R:R is the real "room" here too. EMA20 for recovery is RESISTANCE being
    # reclaimed (the mirror of the bull rule): turn_ok = price reclaimed it.
    rr_ok = (rr is not None and rr >= RR_MIN_LOCATION)
    loc_ok = turn_ok and not_chased and rr_ok
    _loc_fail = []
    if not turn_ok:        _loc_fail.append("below EMA20 (turn unconfirmed)")
    elif not not_chased:   _loc_fail.append("extended")
    if not rr_ok:          _loc_fail.append("thin R:R" if rr is not None else "no R:R")
    loc_note = " / ".join(_loc_fail)

    g1 = beaten and reg_ok
    g2 = rff_ok
    # Same size/pledge/ownership floor as the bull path (13 Aug 2026). The
    # recovery screener.in screens carry mcap > 5000, but a name reaching this
    # surface from the Python recovery engine has never met that floor - which is
    # exactly the inconsistency Jay's microcap came through.
    # None = gate unavailable → keep, never silently reject on an outage.
    _rec_core = _gm_core_gate(_g(rec_r, "Symbol", default=""))
    if _rec_core is False:
        g2 = False
    g3 = sig >= 2

    # ── P1 INHERITED QUALIFICATION (recovery) ───────────────────────────────────
    # A name from a rigorous Recovery list (Rec RS / Climax / Early) was ALREADY
    # vetted beaten-down + fundamentally by the Chartink+Screener recovery scan. The
    # board runs in fast/cache mode where RFF is often INSUFFICIENT (no deep fetch),
    # which was dead-ending these names at "SKIP · weak fundamentals" — the exact
    # blocker P1 removes. Trust the source qualification; run only a break-down guard
    # (still declining: Stage 4, or collapsed well past the recovery band) and TIME it.
    inherited_setup = _g(ctx, "inherited_setup")
    inherited = bool(INHERIT_QUALIFICATION and inherited_setup)
    # 29-Jul: was Stage-4 ONLY, so a Stage-3 (topping) name PASSED the recovery guard
    # while the BULL guard (line ~2846) already invalidated on Stage 3 OR 4 — two paths,
    # two different definitions of broken. S4 v5.9 now resolves Stage 3/4 to NO TRADE
    # regardless of path, so this closes the drift: COLPAL (Stage 3, forced to Recovery)
    # read "still valid" here while S4 said NO TRADE. A recovery is a Stage-1 turn; Stage 3
    # is topping — neither is a recovery setup. Honesty rule preserved: an UNKNOWN stage
    # still passes (benefit of the doubt), only a positively-observed 3 or 4 invalidates.
    still_valid = (stage_num not in ("3", "4")) and (corr is None or corr <= 50.0)
    if inherited:
        g1 = still_valid       # CONTEXT → still-valid (not Stage-4, not collapsed >50%)
        g2 = True              # QUALITY → RFF overlay (recovery scan already vetted funda)
        # ...except the size/pledge/ownership floor, which the recovery scan does
        # NOT vet for names reaching this surface from the Python recovery engine
        # rather than the screener.in screens. Same fix as the bull path: the
        # inherited assignment above would otherwise undo the gate for most names.
        if _rec_core is False:
            g2 = False
        # ...and the RFF FLOOR itself (2 Sep 2026). The bull branch re-applies BFF here
        # because "inheritance was never meant to wave through the BUSINESS"; recovery
        # re-applied only the size floor, so the ONE path whose doctrine calls
        # fundamentals a hard gate - quality on sale, not falling knives - was the path
        # not enforcing them. S4's Gate 6 does gate on RFF, so an inherited row could
        # preview a clean trigger here and be refused at the chart.
        # ONLY on a MEASURED failure. P1 set g2 = True because fast/cache mode leaves RFF
        # INSUFFICIENT and that dead-ended the whole recovery board - that case still
        # passes, untouched. MEASURED on the three live boards: 0 rows change.
        if _rff_scored_fail:
            g2 = False
        g3 = True              # SETUP → inherited recovery archetype

    if entry and sl:
        plan = (f"Set SL {inr(sl)}" + (f" (-{sl_pct:.1f}%)" if sl_pct is not None else "") +
                f", size at {_HP.risk_label()} risk, place order + GTT. "
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
        dict(n=4, title="LOCATION", sub="Room: R:R + EMA20 reclaim", hard=False, ok=loc_ok,
             metrics=[("R:R", (f"{rr:.1f}:1" if rr is not None else "—"), rr_ok),
                      ("Turn (≥20-EMA)", "reclaimed" if turn_ok else "below 20-EMA (res)", turn_ok),
                      ("Ext vs 20-EMA", fnum(ext_ema, 1, "%") if ext_ema is not None else "—", not_chased),
                      ("Support (auto)", str((_g(ctx, "support", default={}) or {}).get("zone", "outside")),
                       bool((_g(ctx, "support", default={}) or {}).get("at_support")))],
             do_pass="Turn confirmed (reclaimed 20-EMA), not extended, adequate R:R — mark the FRESH demand zone.",
             do_fail=("Location weak (" + (loc_note or "turn unconfirmed") + ") — a fired TRIGGER still buys "
                      "(with the caveat); otherwise WAIT for the reclaim / a pullback into the zone.")),
        dict(n=5, title="TRIGGER", sub=(f"Recovery PA battery · {_tf_lbl}" if _is_intra else "Recovery PA battery + intraday confirm"),
             hard=False, ok=None, manual=True,
             metrics=[("PA trigger", (_rpa_names if rpa_fired else
                       ("⚠ DETECTION ERROR" if _g(ctx, "pa_error") else "none yet")), rpa_fired),
                      ("Σ tier", (f"+{_rpa_tier}" if _rpa_tier else "0"), _rpa_tier >= 2),
                      ("Confirm on", _confirm_lbl, None)],
             do_now=((f"TRIGGER LIVE — {_rpa_names} (Σ+{_rpa_tier}) fired on the {_fired_on}"
                      + (f" bar at the zone → {_gm_entry_instruction(_tf_lbl)}."
                         if _is_intra else
                         f". Drop to 75/125m, confirm a CLOSED bar at the zone → {_gm_entry_instruction()}."))
                     if rpa_fired else
                     (f"No {_fired_on} recovery PA trigger yet. Wait for a closed-bar reversal (Climax reclaim / Spring / "
                      f"Higher-Low-2B / Base-Breakout / Engulf / Hammer …) at the base on the {_tf_lbl} chart."))),
        dict(n=6, title="EXECUTE", sub="Recovery plan & GTT", hard=False, ok=None, execute=True,
             metrics=[], do_now=plan),
    ]

    # ── INHERITED-MODEL DISPLAY (recovery) — same doctrine as the bull path: for a
    # name pre-qualified by a Recovery scan, Steps 1-3 become "confirm it hasn't
    # broken down → time it", with RFF/RS demoted to status (the scan already
    # RFF-gated it). Relabels the DISPLAY to match the gating switched above.
    if inherited:
        _arche_lbl = ", ".join(inherited_setup) if isinstance(inherited_setup, (list, tuple)) else str(inherited_setup)
        steps[0] = dict(n=1, title="STILL VALID?", sub="Break-down guard", hard=True, ok=g1,
             metrics=[("Stage", f"Stage {stage_num}", stage_num != "4"),
                      ("Off 52W high", fnum(corr, 1, "%") if corr is not None else "—",
                       (corr is None or corr <= 50)),
                      ("Recovery regime", "OPEN" if reg_ok else "closed", reg_ok),
                      ("RS turning", ("yes · " + rrg) if rs_up else ("no · " + rrg), rs_up)],
             do_pass=f"Still valid — not Stage 4 and not collapsed past the recovery band. Qualified "
                     f"by its {_arche_lbl} scan; the board is TIMING it, not re-screening.",
             do_fail="Broke down (Stage 4 or collapsed >50% off-high) → INVALIDATED. The recovery "
                     "thesis failed — drop it.")
        # Same fix as the bull path: RFF stays an overlay (the recovery scan
        # already gated it), but the size/pledge/ownership floor is NOT something
        # those screens check — verified live, the Recovery screener.in screens
        # carry market cap only. So it blocks even here.
        _rec_fund_fail = (_rec_core is False)
        steps[1] = dict(n=2, title="QUALITY",
             sub=("Size/pledge · HARD" if _rec_fund_fail else "Overlay · status only"),
             hard=_rec_fund_fail, ok=not _rec_fund_fail,
             metrics=[("RFF gate", f"{rff_b}/6 (min {_rff_min})", rff_ok),
                      ("RFF quality", rff_q, rff_q == "FULL"),
                      ("Size/pledge", ("below floor" if _rec_core is False else
                                       ("PASS" if _rec_core else "—")), _rec_core is not False),
                      ("Mansfield RS", fnum(rs_val, 1), (rs_val or 0) > 0)],
             do_pass="RFF is an OVERLAY here — the Recovery scan already RFF-gated it "
                     "(fundamentally strong on sale). Size/pledge/ownership still blocks.",
             do_fail="Below the size/pledge/ownership floor. The Recovery screens check "
                     "market cap only, so this was never vetted upstream. SKIP.")
        steps[2] = dict(n=3, title="SETUP", sub="Inherited archetype", hard=False, ok=True,
             metrics=[("Archetype", _arche_lbl, True),
                      ("Signal", label, sig >= 2),
                      ("PA Patterns", (f"+{_rpa_tier}" if _rpa_tier else "none"), _rpa_tier >= 2)],
             do_pass=f"Setup = the inherited {_arche_lbl} recovery thesis. No live signal required — "
                     f"go straight to location & trigger.",
             do_fail="")

    stop_at = None
    for s in steps:
        if s.get("hard") and not s["ok"]:
            stop_at = s["n"]; break

    # Rec-Catalyst-Scan names have no persistent structural thesis — the recovery
    # SIGNAL was their reason. So a catalyst-scan-ONLY inherited recovery name must
    # have a live signal (sig ≥ 2) OR a fired recovery PA trigger to stay actionable.
    _rec_structural = any(a in STRUCTURAL_RECOVERY_ARCHETYPES
                          for a in (inherited_setup or []))
    _rec_catalyst_only = inherited and not _rec_structural
    if inherited:
        # INHERITED path: qualification is trusted; only the break-down guard vetoes.
        if not still_valid:
            verdict, color = "INVALIDATED · still declining", "#EF5350"
        elif _rec_catalyst_only and not (sig >= 2 or rpa_fired):
            verdict, color = "WATCHLIST · signal expired", "var(--warn)"
        elif rpa_fired:
            verdict = "BUY — TRIGGER LIVE · Recovery" + (f" · {loc_note}" if loc_note else "")
            color = "#26A69A"
        elif not loc_ok:
            verdict, color = "WAIT FOR PULLBACK", "var(--warn)"
        else:
            verdict, color = "ARMED · AWAIT TRIGGER · Recovery", "var(--warn)"
    elif stop_at == 1:
        verdict, color = "NOT A RECOVERY CONTEXT", "#EF5350"
    elif stop_at == 2:
        verdict, color = "SKIP · weak fundamentals", "#EF5350"
    elif stop_at == 3:
        verdict, color = "NO RECOVERY CATALYST", "var(--warn)"
    elif rpa_fired:
        # TRIGGER WINS — location never vetoes a live recovery trigger; weak location
        # is surfaced as a caveat.
        verdict = "BUY — TRIGGER LIVE · Recovery" + (f" · {loc_note}" if loc_note else "")
        color = "#26A69A"
    elif not loc_ok:
        verdict, color = "WAIT FOR PULLBACK", "var(--warn)"
    else:
        verdict, color = "ARMED · AWAIT TRIGGER · Recovery", "var(--warn)"

    if inherited and not still_valid:
        current = 1
    elif inherited and _rec_catalyst_only and not (sig >= 2 or rpa_fired):
        current = 3                      # the recovery signal (its thesis) is gone
    elif stop_at:
        current = stop_at
    elif rpa_fired:
        current = 5
    elif not loc_ok:
        current = 4
    else:
        current = 5
    actionable = verdict.startswith("BUY") or verdict.startswith("ARMED") or verdict.startswith("WAIT")
    return dict(steps=steps, verdict=verdict, color=color, stop_at=stop_at,
                # see the bull path. RFF joins it only when actually scored: an
                # unreadable RFF is a judgement about our data, never about the company.
                fund_block=bool(_rec_core is False or _rff_scored_fail),
                # see the bull path. INSUFFICIENT is the recovery flavour of unreadable:
                # fast/cache mode leaves RFF unscored, and that must not read as verified.
                fund_ok=(False if (_rec_core is False or _rff_scored_fail)
                         else None if (_rec_core is None or rff_q == "INSUFFICIENT")
                         else True),
                current=current, actionable=actionable, recovery=True, loc_note=loc_note,
                inherited=inherited, still_valid=still_valid, location_ok=bool(loc_ok),
                plan_entry=entry, plan_sl=sl, plan_t1=t1)

def _gm_apply_location_rule(_s, vp_at=False):
    """The ONE location rule — rule A2 + GM_LOC_STRICT — for every Trigger TF.

    Lived inside `if trigger_tf in ("75m","125m")` until 26-Aug-2026, so the DAILY tab
    never ran it: Daily kept the old saturated six-way OR while the intraday tabs used
    A2. That is why Daily showed 19 "Buy Trigger Live" against 13 on 75m, and why names
    11-27% below their nearest zone were still scoring 4/4. It also blanked the
    descriptive Loc field on Daily, because the loc_* keys it reads were never set.

    Trigger-TF terms (tf_*) are simply absent on Daily and fall to False -- the D/W/M
    terms carry it -- so one definition serves both without a second copy to drift.
    """
    _s["loc_pattern"] = bool(_s.get("ize_at_support_pattern") or _s.get("tf_zone_pattern"))
    # PIVOT LEVELS FEED LOCATION (26-Aug-2026, Jay) — S4 parity with _pivLvl. A pivot
    # LINE and a RECLAIMED "Pivot S->R" are the same evidence as a pivot zone: price
    # turned there. They enter as loc_pivot, never loc_pattern, so rule A2 still makes
    # them earn a confirming source.
    # Mirrors Pine's f_nearpiv exactly: price at or above the level, within 1.5%. The
    # directionality is what makes the flipped S->R safe -- it counts only once price
    # has RECLAIMED it. While it sits overhead it stays an obstacle, not a location.
    _pivLvl = False
    try:
        # Off means off: a pivot LEVEL is pivot evidence like a pivot ZONE, so the
        # same switch governs it. Without this the toggle would remove pivot zones
        # and silently leave pivot lines satisfying location.
        if not _gm_use_pivot_zones():
            raise StopIteration
        _px = _s.get("_px")
        for _leg in ("daily", "weekly"):
            _d = _s.get(_leg) or {}
            for _k in ("pivot", "pivot_res"):
                _lv = _d.get(_k)
                if _px and _lv and _px >= _lv and (_px - _lv) / _lv <= 0.015:
                    _pivLvl = True
    except (Exception, StopIteration):
        _pivLvl = False
    _s["loc_pivot_level"] = bool(_pivLvl)
    _s["loc_pivot"] = bool(_s.get("ize_at_support_pivot") or _s.get("tf_zone_pivot") or _pivLvl)
    # Fallback for a zone_engine predating the pattern/pivot split: treat an unlabelled
    # hit as a PATTERN zone rather than silently losing it.
    if not (_s["loc_pattern"] or _s["loc_pivot"]):
        _s["loc_pattern"] = bool(_s.get("ize_at_support") or _s.get("tf_zone_at"))
    _s["loc_zone"] = _s["loc_pattern"] or _s["loc_pivot"]
    _s["loc_reacting"] = bool(_s.get("ize_reacting") or _s.get("tf_reacting"))
    # The timeframe of the pattern zone that PASSED (trigger TF first, then D/W/M).
    _s["loc_pattern_tf"] = _s.get("tf_pattern_tf") or _s.get("ize_pattern_tf")
    _s["loc_soft"] = bool(_s.get("ize_near_sr") or _s.get("ize_near_avwap")
                          or vp_at or _s.get("tf_near_sr"))
    if GM_LOC_STRICT:
        _s["at_support"] = bool(
            _s["loc_pattern"]
            or (_s["loc_pivot"] and (_s["loc_soft"] if GM_PIVOT_NEEDS_CONFLUENCE else True)))
    else:
        _s["at_support"] = bool(_s["loc_zone"] or _s["loc_soft"])
    return _s

def _s4_rv(v):
    """S4's RV: this bar's volume / mean of the PRIOR 50 bars (S4 `volume / sma(volume,50)[1]`).
    One definition for the board and Single Symbol, so the V gate is S4's test."""
    try:
        import s4_sizing as _s4z
        return _s4z.s4_rv(pd.DataFrame({"Volume": v}))
    except Exception:
        return None

def render_pa_banner(ctx, recovery: bool = False) -> str:
    """High-visibility banner when strong PA patterns are live — Jay can't
    spot these on the chart; the dashboard must shout them. `recovery` = active
    path, so the banner reflects the recovery battery on a recovery name."""
    _key = "recovery_pa_patterns" if recovery else "pa_patterns"
    pats = [(n, t) for n, f, t, _ in (_g(ctx, _key, default=[]) or []) if f]
    if not pats:
        return ""
    tier_sum = sum(t for _, t in pats)
    chips = " · ".join(f"{n} (+{t})" for n, t in sorted(pats, key=lambda x: -x[1]))
    col = "#6D28D9" if tier_sum >= 4 else "#047857"
    bg  = "var(--acc-bg)" if tier_sum >= 4 else "var(--bull-bg)"
    bdr = "var(--acc-rule)" if tier_sum >= 4 else "var(--bull-rule)"
    return (f"<div style='border:1.5px solid {bdr};border-left:5px solid {col};background:{bg};border-radius:8px;"
            f"padding:8px 14px;margin:8px 0;font-size:13.5px;color:var(--ink);font-weight:600;'>"
            f"<b style='color:{col};font-weight:800;'>🔥 PA PATTERNS LIVE (Σ +{tier_sum}):</b> {chips}</div>")
