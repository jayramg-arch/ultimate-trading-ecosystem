import os
import sys
# Force UTF-8 on Windows console so the emoji-heavy output (existing 🎯 / 🚀 / ✅
# and the new 🛂 pre-flight banner) doesn't crash on cp1252 terminals.
if hasattr(sys.stdout, 'encoding') and sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
import argparse
import pandas as pd  # E8 earnings-date parsing
from dotenv import load_dotenv
from dhanhq import dhanhq
import math
import time
import sqlite3
from datetime import datetime, date
from dhan_symbols import get_nse_id_map
from ai_journaler_helper import generate_tactical_analysis

# ==========================================
# 1. CONFIGURATION & SETUP
# ==========================================
load_dotenv()
CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
import journal_path as _jp  # AUD-INT-14: one owner of the journal location
DB_FILE = _jp.JOURNAL_DB

RISK_PER_TRADE_PERCENT = 0.01  # 1% Risk
MAX_CAPITAL_USAGE = 0.20       # Max 20% per stock

def cls():
    os.system('cls' if os.name == 'nt' else 'clear')

def connect_dhan():
    try:
        dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)
        resp = dhan.get_fund_limits()
        if resp['status'] == 'success':
            return dhan, resp['data']
        else:
            print("❌ API Connection Failed.")
            return None, None
    except Exception as e:
        print(f"❌ Error connecting to Dhan: {e}")
        return None, None

def log_trade_to_db(symbol, entry, stoploss, quantity, rationale):
    """Logs the trade to the SQLite journal database."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Ensure table exists (safeguard)
        c.execute('''
            CREATE TABLE IF NOT EXISTS journal (
                symbol TEXT PRIMARY KEY,
                trade_type TEXT,
                stoploss REAL,
                target REAL,
                rationale TEXT,
                timeframe TEXT,
                entry_date TEXT,
                quantity REAL, 
                buy_price REAL,
                exit_date TEXT,
                exit_price REAL,
                exit_reason TEXT,
                status TEXT DEFAULT 'OPEN',
                sector TEXT,
                trade_quality TEXT,
                compromises TEXT,
                lessons TEXT,
                screenshot_path TEXT,
                planned_rr TEXT,
                ai_analysis TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # B11 fix: target = entry + 2.5×risk (was 2.0R). Aligns with the
        # screeners — bull_screener and recovery_screener both use 2.5R for
        # T1 on swing/positional setups, so the journal target now matches
        # what the screeners flagged.
        risk = entry - stoploss
        target = entry + (risk * 2.5)

        # B12 fix: ON CONFLICT no longer overwrites a user-edited target.
        # COALESCE keeps the existing target if non-NULL/positive; only fills
        # it on first insert. Stoploss still updates (it's signal-driven).
        sql = '''
            INSERT INTO journal (symbol, trade_type, stoploss, target, rationale, timeframe, entry_date, quantity, buy_price, status, planned_rr)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                stoploss=excluded.stoploss,
                target=COALESCE(NULLIF(journal.target, 0), excluded.target),
                rationale=excluded.rationale,
                entry_date=excluded.entry_date,
                quantity=excluded.quantity,
                buy_price=excluded.buy_price,
                status='OPEN',
                planned_rr=COALESCE(NULLIF(journal.planned_rr, ''), excluded.planned_rr)
        '''

        c.execute(sql, (
            symbol,
            "Positional", # Default to Positional as per scanner context
            stoploss,
            target,
            rationale,
            "Daily",
            str(date.today()),
            quantity,
            entry,
            "OPEN",
            "1:2.5"
        ))
        
        conn.commit()
        conn.close()
        print(f"✅ Trade logged to Journal: {DB_FILE}")
        
    except Exception as e:
        print(f"⚠️ Failed to log trade to DB: {e}")

def log_ai_analysis_to_db(symbol, analysis):
    """Updates the AI analysis column in the journal."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE journal SET ai_analysis = ? WHERE symbol = ?", (analysis, symbol))
        conn.commit()
        conn.close()
        print(f"🤖 AI Tactical Analysis saved for {symbol}.")
    except Exception as e:
        print(f"⚠️ Failed to log AI analysis: {e}")

# ==========================================
# 2. RISK CALCULATOR
# ==========================================

# E2: Setup-aware sizing multipliers.
# Final risk = base_risk × regime_mult × adr_mult.
# regime_mult lowers risk in a weak market (defensive); adr_mult lowers risk
# on volatile small/mid-caps where 1% nominal risk hides large slippage.
def _regime_size_multiplier(score: float | None) -> float:
    """Map the 0-10 regime score to a 0.30–1.50 risk multiplier.

    score 10 -> 1.50 (Bull-Healthy: lean into setups)
    score  6 ->  ~1.05 (Cautious Bull)
    score  4 ->  0.70 (Neutral / Choppy)
    score  2 ->  0.40 (Defensive)
    score  0 ->  0.30 (Bear / Cash)
    None    ->  1.00 (regime unavailable — neutral, don't over-react)
    """
    if score is None:
        return 1.00
    s = max(0.0, min(10.0, float(score)))
    # Linear interpolation: score 0→0.30, score 10→1.50
    return round(0.30 + (s / 10.0) * 1.20, 2)


def _adr_size_multiplier(adr_pct: float | None) -> float:
    """Map daily ADR% to a 0.50–1.00 risk multiplier.

    Slippage on a 5%-ADR small-cap is ~3× the slippage on a 1.5%-ADR large-cap;
    nominal 1% risk is therefore much more punishing on the volatile name.
    Lower the position to bring real-money risk in line.

      ADR < 2.0% -> 1.00 (large-cap, stable)
      2.0–3.0%   -> 0.85
      3.0–5.0%   -> 0.70
      > 5.0%     -> 0.50 (highly volatile)
      None       -> 1.00 (unknown — neutral)
    """
    if adr_pct is None:
        return 1.00
    a = float(adr_pct)
    if a < 2.0:  return 1.00
    if a < 3.0:  return 0.85
    if a < 5.0:  return 0.70
    return 0.50


def calculate_position_size(total_capital, entry, stoploss,
                              regime_score=None, adr_pct=None):
    """Compute share quantity for a long trade.

    E2 enhancement: when regime_score and/or adr_pct are supplied, the base
    1% risk is scaled by both multipliers. Backwards-compatible — calling
    with just (capital, entry, sl) preserves the original behavior.

    Returns (quantity, risk_per_share, total_risk_rupees, sizing_detail)
    where sizing_detail is a dict with the multipliers applied.
    """
    if entry <= stoploss:
        print("❌ Error: Entry must be higher than Stoploss for a Long trade.")
        return None, None, None, None

    risk_per_share = entry - stoploss
    if risk_per_share <= 0: return None, None, None, None

    base_risk_pct  = RISK_PER_TRADE_PERCENT
    regime_mult    = _regime_size_multiplier(regime_score)
    adr_mult       = _adr_size_multiplier(adr_pct)
    final_risk_pct = base_risk_pct * regime_mult * adr_mult
    max_risk_rupees = total_capital * final_risk_pct

    quantity = math.floor(max_risk_rupees / risk_per_share)

    max_capital_allowed = total_capital * MAX_CAPITAL_USAGE
    cost_of_trade = quantity * entry

    if cost_of_trade > max_capital_allowed:
        print(f"⚠️ Quantity adjusted for Diversification (Max {int(MAX_CAPITAL_USAGE*100)}% Capital rule applied).")
        quantity = math.floor(max_capital_allowed / entry)

    if quantity < 1:
        print(f"❌ Error: Risk allows 0 quantity. (Capital: {total_capital}, "
              f"Risk/Share: {risk_per_share}, final risk%: {final_risk_pct*100:.3f}%)")
        return None, None, None, None

    sizing_detail = {
        "base_risk_pct":  round(base_risk_pct * 100, 3),
        "regime_score":   regime_score,
        "regime_mult":    regime_mult,
        "adr_pct":        adr_pct,
        "adr_mult":       adr_mult,
        "final_risk_pct": round(final_risk_pct * 100, 3),
    }
    return quantity, risk_per_share, max_risk_rupees, sizing_detail

import yfinance as yf
# import pandas_ta as ta # Removed unused import to avoid dependency issues

def get_technical_analysis(symbol):
    """Fetches key technical indicators for display.
    C1 sweep: prefers data_provider (parquet-cached), falls back to yfinance.
    """
    try:
        print(f"   • Fetching Technicals for {symbol}...")
        try:
            import data_provider as _dp
            df = _dp.fetch_ohlcv(symbol, period="6mo", interval="1d")
        except Exception:
            df = yf.Ticker(f"{symbol}.NS").history(period="6mo")

        if df is None or df.empty: return None

        # Calculate Indicators (Simple Pandas)
        # EMA 20
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        # SMA 50, 150, 200
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['SMA_150'] = df['Close'].rolling(window=150).mean()
        df['SMA_200'] = df['Close'].rolling(window=200).mean()
        
        # RSI 14
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        latest = df.iloc[-1]
        
        return {
            'close': latest['Close'],
            'ema_20': latest['EMA_20'],
            'sma_50': latest['SMA_50'],
            'sma_150': latest['SMA_150'],
            'sma_200': latest['SMA_200'],
            'rsi': latest['RSI']
        }
    except Exception as e:
        print(f"⚠️ Technical Fetch failed: {e}")
        return None

# ==========================================
# 2.5  PRE-FLIGHT CHECK  (B1 + B2 + B14)
# ==========================================
# Three gates run before order placement:
#   • F&O Ban List         (B14) — block if symbol is in NSE ban-period list
#   • Market Regime Gate   (B2)  — block if regime score < block-threshold
#   • Volume / Extension   (B1)  — warn if rel_vol < 1.5 or price extended
#                                  >5% above EMA20 (chasing risk)
#
# Result: {"ok": bool, "blocks": [...], "warnings": [...], "details": {...}}
# Hard blocks require typed OVERRIDE confirmation; warnings only need Y/N.
REGIME_BLOCK_THRESHOLD = 2   # score < 2 → hard block (Bear/Cash)
REGIME_WARN_THRESHOLD  = 4   # score < 4 → soft warning (Defensive territory)
REL_VOL_FLOOR          = 1.0 # below this = institutional confirmation missing
REL_VOL_PREFERRED      = 1.5 # below this = sub-Minervini volume
EXTENDED_PCT           = 5.0 # price > X% above EMA20 = chasing risk

# E7 — Sector / correlation gate
# ONE sector cap (24-Sep-2026, audit AUD-PAR-11): this gate blocked at 35% while the order
# gate every other surface uses (pre_trade_gate) blocks at 25%, so the same entry could pass
# here and fail there. The cap is imported, never restated; warn at 80% of it.
try:
    from pre_trade_gate import SECTOR_CAP_PCT as _SECTOR_CAP
except Exception:
    _SECTOR_CAP = 25.0
SECTOR_CONCENTRATION_BLOCK_PCT = float(_SECTOR_CAP)          # post-trade sector exposure > cap → block
SECTOR_CONCENTRATION_WARN_PCT  = 0.8 * float(_SECTOR_CAP)    # > 80% of the cap → warn
CORRELATION_BLOCK              = 0.90  # any pair r > 0.90 with new entry → block
CORRELATION_WARN               = 0.75  # > 0.75 → warn

# E8 — Earnings-window guard
EARNINGS_BLOCK_DAYS = 2      # earnings within ≤ 2 trading days → block (gap risk)
EARNINGS_WARN_DAYS  = 5      # ≤ 5 trading days → warn


def _pre_flight_check(symbol, entry, sl):
    """Run F&O / regime / volume-extension gates before order placement.

    Heavy work (benchmark+breadth download, F&O ban fetch) is contained
    in try/except so a transient yfinance/NSE outage degrades to a warning,
    never a silent free pass.
    """
    blocks   = []
    warnings = []
    details  = {"symbol": symbol, "entry": entry, "sl": sl}

    # ── B14: F&O ban list ──────────────────────────────────────────────
    try:
        from market_data_hub import fetch_fno_ban_list
        ban_list = fetch_fno_ban_list() or []
        details["fno_ban_count"] = len(ban_list)
        details["fno_banned"]    = symbol.upper() in {s.upper() for s in ban_list}
        if details["fno_banned"]:
            blocks.append(
                f"F&O BAN: {symbol} is in today's NSE securities-in-ban-period list — "
                "no fresh F&O positions allowed; spot positions still permitted by "
                "the exchange but this script blocks by default."
            )
    except Exception as e:
        warnings.append(f"F&O ban check failed: {e}")

    # ── B2: Regime gate (uses cached regime_state.json if <30 min old) ─
    try:
        import os as _os, json as _json
        from datetime import datetime as _dt, timedelta as _td
        regime = None
        state_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                     "regime_state.json")
        if _os.path.exists(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as _f:
                    state = _json.load(_f)
                last = state.get("last", {})
                ts = last.get("computed_at", "")
                if ts:
                    age = _dt.now() - _dt.fromisoformat(ts)
                    if age < _td(minutes=30):
                        regime = last
            except Exception:
                pass

        if regime is None:
            print("   ⏳ Computing market regime (this can take 30–60s)...")
            import market_regime as _mr
            try:
                import breadth_engine as _be
                _bm  = _be.calculate_breadth_metrics()
                _ad  = _be.load_or_bootstrap_ad_history(min_rows=40)
            except Exception:
                _bm, _ad = None, None
            regime = _mr.compute_regime(_bm, _ad)

        details["regime_score"]   = regime.get("score")
        details["regime_verdict"] = regime.get("verdict")
        if regime.get("score", 0) < REGIME_BLOCK_THRESHOLD:
            blocks.append(
                f"REGIME WEAK: {regime['score']}/10 — {regime['verdict']}. "
                "Bear/cash regime; new long swing/positional entries are blocked."
            )
        elif regime.get("score", 0) < REGIME_WARN_THRESHOLD:
            warnings.append(
                f"REGIME CAUTION: {regime['score']}/10 — {regime['verdict']}. "
                "Reduce size or wait for confirmation."
            )
        # Distribution-day stress always warns (even at score ≥ 4)
        dd = regime.get("distribution", {}) or {}
        details["distribution_days"] = dd.get("count", 0)
        if dd.get("stress"):
            warnings.append(
                f"DISTRIBUTION STRESS: {dd.get('count','?')} distribution days in "
                f"last {dd.get('window','?')} sessions — institutions selling."
            )
    except Exception as e:
        warnings.append(f"Regime check failed: {e}")

    # ── B1: Volume confirmation + extension gate ──────────────────────
    try:
        import data_provider as dp
        import pandas as _pd
        df = dp.fetch_ohlcv(symbol, period="3mo", interval="1d",
                            auto_adjust=True, use_cache=True)
        if df.empty or len(df) < 50:
            warnings.append("Volume / extension check skipped — insufficient history.")
        else:
            close  = df["Close"]; vol = df["Volume"]
            ema20  = close.ewm(span=20, adjust=False).mean().iloc[-1]
            vol_avg = vol.rolling(50).mean().iloc[-1]
            rel_vol = float(vol.iloc[-1] / vol_avg) if vol_avg else 0.0
            ext_pct = float((entry - ema20) / ema20 * 100) if ema20 else 0.0
            details["rel_vol"]            = round(rel_vol, 2)
            details["ext_pct_vs_ema20"]   = round(ext_pct, 2)

            if rel_vol < REL_VOL_FLOOR:
                warnings.append(
                    f"LOW VOLUME: today's volume {rel_vol:.2f}x 50-day average "
                    f"(< {REL_VOL_FLOOR:.1f}x — no institutional confirmation)."
                )
            elif rel_vol < REL_VOL_PREFERRED:
                warnings.append(
                    f"SUB-MINERVINI VOLUME: {rel_vol:.2f}x 50-day average "
                    f"(< {REL_VOL_PREFERRED:.1f}x preferred for breakouts)."
                )
            if ext_pct > EXTENDED_PCT:
                warnings.append(
                    f"EXTENDED ENTRY: price is {ext_pct:.1f}% above EMA20 "
                    f"(> {EXTENDED_PCT:.0f}% threshold — chasing risk; "
                    "consider waiting for a pullback)."
                )
    except Exception as e:
        warnings.append(f"Volume / extension check failed: {e}")

    # ── E7: Sector concentration + correlation gate ───────────────────
    try:
        # Pull current open positions from the journal
        _open_syms = []
        try:
            _conn = sqlite3.connect(DB_FILE)
            _cur  = _conn.cursor()
            _cur.execute(
                "SELECT symbol, COALESCE(buy_price,0)*COALESCE(quantity,0) AS deployed "
                "FROM journal WHERE status='OPEN'"
            )
            _rows = _cur.fetchall()
            _conn.close()
            _open_syms = [(r[0], float(r[1] or 0)) for r in _rows
                            if r[0] and (r[1] or 0) > 0]
        except Exception as _je:
            details["e7_journal_read"] = f"failed: {_je}"

        if _open_syms:
            # Resolve sectors via the unified DB
            try:
                import sector_lookup as _sl_e7
                _new_rec = _sl_e7.get_sector(symbol)
                _new_sector = (_new_rec.get("display_name") or _new_rec.get("sector_name")
                                ) if _new_rec else "Unassigned"
            except Exception:
                _new_sector = "Unassigned"

            # Compute post-trade sector exposure %
            from collections import defaultdict
            _new_deploy = float(entry) * 1  # placeholder — actual qty unknown here;
            # Use position-size estimate via 1% risk × 50× leverage proxy: assume
            # typical deployment ≈ 5–8% of capital per trade. We approximate by
            # using the *risk* amount × 100/RISK% → the typical capital cost.
            # Cleaner: caller supplies true deployment via report["details"].
            _est_new_deploy = abs(float(entry) - float(sl)) / max(0.01, RISK_PER_TRADE_PERCENT)
            _by_sector = defaultdict(float)
            for _s, _d in _open_syms:
                _rec = None
                try:
                    _rec = _sl_e7.get_sector(_s)
                except Exception:
                    pass
                _sec = (_rec.get("display_name") or _rec.get("sector_name")
                         ) if _rec else "Unassigned"
                _by_sector[_sec] += _d
            _by_sector[_new_sector] += _est_new_deploy
            _total_deploy = sum(_by_sector.values()) or 1.0
            _pct_new = _by_sector[_new_sector] / _total_deploy * 100
            details["e7_new_sector"]           = _new_sector
            details["e7_post_trade_sector_pct"] = round(_pct_new, 1)

            if _pct_new >= SECTOR_CONCENTRATION_BLOCK_PCT:
                blocks.append(
                    f"SECTOR CONCENTRATION: post-trade exposure to {_new_sector} "
                    f"would be {_pct_new:.1f}% (limit {SECTOR_CONCENTRATION_BLOCK_PCT:.0f}%). "
                    "Trim an existing position in the same sector before adding."
                )
            elif _pct_new >= SECTOR_CONCENTRATION_WARN_PCT:
                warnings.append(
                    f"SECTOR HEAVY: {_new_sector} would reach {_pct_new:.1f}% "
                    f"(soft cap {SECTOR_CONCENTRATION_WARN_PCT:.0f}%)."
                )

            # Pairwise correlation check via the existing risk-manager helper
            try:
                from ai_risk_manager import get_portfolio_correlation_matrix
                _check_syms = [s for s, _ in _open_syms] + [symbol]
                _corr_df, _shadows, _div = get_portfolio_correlation_matrix(_check_syms)
                # Find the highest |r| pair involving the new symbol
                _max_r, _max_partner = 0.0, None
                if _corr_df is not None and not _corr_df.empty and symbol in _corr_df.columns:
                    for _other in _corr_df.columns:
                        if _other == symbol:
                            continue
                        _r = float(_corr_df.loc[symbol, _other])
                        if abs(_r) > abs(_max_r):
                            _max_r, _max_partner = _r, _other
                details["e7_max_corr"]         = round(_max_r, 2)
                details["e7_max_corr_partner"] = _max_partner

                if abs(_max_r) >= CORRELATION_BLOCK:
                    blocks.append(
                        f"CORRELATION: new entry has r={_max_r:.2f} with existing "
                        f"holding {_max_partner} (limit {CORRELATION_BLOCK}). "
                        "Adding it would compound a single risk factor."
                    )
                elif abs(_max_r) >= CORRELATION_WARN:
                    warnings.append(
                        f"CORRELATED HOLDING: r={_max_r:.2f} with {_max_partner} "
                        f"(soft cap {CORRELATION_WARN}) — diversification may be hollow."
                    )
            except Exception as _ce:
                details["e7_corr_check"] = f"failed: {_ce}"
        else:
            details["e7_open_positions"] = 0
    except Exception as e:
        warnings.append(f"E7 sector/correlation check failed: {e}")

    # ── E3: Pivot/VCP extension check ────────────────────────────────
    try:
        from pivot_detector import detect_vcp
        # Reuse the same daily frame the volume-extension check pulled.
        # Only attempt if the dataframe came back; otherwise skip gracefully.
        _vcp_df = None
        try:
            import data_provider as _dp_e3
            _vcp_df = _dp_e3.fetch_ohlcv(symbol, period="1y", interval="1d")
        except Exception:
            pass
        if _vcp_df is not None and not _vcp_df.empty:
            _vcp_res = detect_vcp(_vcp_df)
            details["e3_vcp_valid"]    = bool(_vcp_res.get("is_valid"))
            details["e3_vcp_score"]    = int(_vcp_res.get("quality_score", 0))
            details["e3_pivot_price"]  = _vcp_res.get("pivot_price")
            details["e3_broke_pivot"]  = bool(_vcp_res.get("broke_pivot"))
            details["e3_days_since_pivot"] = _vcp_res.get("days_since_pivot")

            _piv = _vcp_res.get("pivot_price")
            if _piv and _piv > 0:
                _ext_pct = (entry - _piv) / _piv * 100
                # Buying >5% above the pivot is the canonical chase mistake.
                if _ext_pct > 5.0:
                    warnings.append(
                        f"PIVOT EXTENSION: entry ₹{entry:.2f} is {_ext_pct:.1f}% "
                        f"above the VCP pivot ₹{_piv:.2f}. Wait for a tight "
                        "handle / pullback to within 5% of pivot."
                    )
                elif _ext_pct < -2.0 and not _vcp_res.get("broke_pivot"):
                    warnings.append(
                        f"PRE-PIVOT ENTRY: entry ₹{entry:.2f} is {abs(_ext_pct):.1f}% "
                        f"below the VCP pivot ₹{_piv:.2f}. Setup hasn't triggered — "
                        "consider waiting for a confirmed breakout."
                    )

            if not _vcp_res.get("is_valid"):
                # Not a hard warning — just a soft note. A good catalyst can
                # fire without a textbook VCP base.
                details["e3_vcp_note"] = "no valid VCP base detected"
    except Exception as e:
        warnings.append(f"E3 VCP check failed: {e}")

    # ── E8: Earnings-window guard ─────────────────────────────────────
    try:
        import yfinance as _yf_e8
        from datetime import datetime as _dt8, date as _date8
        _next_earn = None
        try:
            _tk = _yf_e8.Ticker(f"{symbol.upper()}.NS")
            # Two endpoints expose earnings dates depending on yfinance version:
            # Ticker.calendar (DataFrame in 0.2+) and Ticker.earnings_dates (DatetimeIndex)
            _cal = getattr(_tk, "calendar", None)
            if isinstance(_cal, pd.DataFrame) and not _cal.empty:
                # First column typically has 'Earnings Date' row
                for _col in _cal.columns:
                    _val = _cal[_col].iloc[0] if "Earnings Date" in str(_cal.index[0]) else None
                    if _val is not None:
                        _next_earn = pd.to_datetime(_val, errors="coerce")
                        break
            elif isinstance(_cal, dict) and _cal.get("Earnings Date"):
                # yfinance 0.2.x fast-info-style dict
                _ed = _cal["Earnings Date"]
                if isinstance(_ed, (list, tuple)) and _ed:
                    _next_earn = pd.to_datetime(_ed[0], errors="coerce")
                else:
                    _next_earn = pd.to_datetime(_ed, errors="coerce")
            if _next_earn is None:
                _ed = getattr(_tk, "earnings_dates", None)
                if _ed is not None and len(_ed) > 0:
                    # earnings_dates is sorted desc; first future entry is the next event
                    _today = pd.Timestamp.utcnow().normalize().tz_localize(None)
                    _idx = pd.to_datetime(_ed.index, errors="coerce").tz_localize(None)
                    _future = sorted([d for d in _idx if d >= _today])
                    if _future:
                        _next_earn = _future[0]
        except Exception as _ee:
            details["e8_earnings_lookup"] = f"failed: {_ee}"

        if _next_earn is not None and not pd.isna(_next_earn):
            _today = pd.Timestamp(_date8.today())
            _trading_days = max(0, int((_next_earn - _today).days))
            details["e8_next_earnings"]    = str(_next_earn.date())
            details["e8_calendar_days"]    = _trading_days
            if _trading_days <= EARNINGS_BLOCK_DAYS:
                blocks.append(
                    f"EARNINGS IN ≤{EARNINGS_BLOCK_DAYS}d: next report on "
                    f"{_next_earn.date()} ({_trading_days}d away). "
                    "Pre-earnings entries carry a gap-risk multiple of normal SL distance."
                )
            elif _trading_days <= EARNINGS_WARN_DAYS:
                warnings.append(
                    f"EARNINGS IN ≤{EARNINGS_WARN_DAYS}d: report on "
                    f"{_next_earn.date()} ({_trading_days}d away). Consider "
                    "smaller size or waiting until after the print."
                )
        else:
            details["e8_next_earnings"] = "unknown"
    except Exception as e:
        warnings.append(f"E8 earnings check failed: {e}")

    # ── E-3 (v2.3): Portfolio Heat Ceiling ──────────────────────────────
    # Blocks new entries when total portfolio risk exceeds 6% of capital.
    try:
        import v2_fixes as _v2_e3
        _open_pos_for_heat = []
        _total_capital = 0.0
        try:
            _conn_e3 = sqlite3.connect(DB_FILE)
            _cur_e3 = _conn_e3.cursor()
            _cur_e3.execute(
                "SELECT buy_price, stoploss, quantity FROM journal WHERE status='OPEN'"
            )
            _heat_rows = _cur_e3.fetchall()
            _conn_e3.close()
            for _r in _heat_rows:
                _open_pos_for_heat.append({
                    "buy_price": _r[0], "stoploss": _r[1], "quantity": _r[2],
                })
        except Exception as _he:
            details["e3_heat_journal"] = f"failed: {_he}"

        # Bug #3 fix (10 May 2026): canonical capital source order is now
        #   1. AVAILABLE_CAPITAL env var (operator override)
        #   2. Live Dhan balance via quant_analyst.get_dhan_balance() — same
        #      function the Streamlit sidebar uses, so heat-check sees the
        #      same number the trader sees. Avoids the old ₹10L hardcoded
        #      fallback (3× the typical user's actual capital → blocks
        #      fired far too late).
        #   3. 2× sum of deployed positions (assumes ~50% deployment)
        #   4. ₹1L last-resort floor (was ₹10L) so a botched fetch can't
        #      grant infinite leverage; ₹1L is conservative enough that any
        #      real trade exceeds the 6% ceiling, forcing a manual review.
        try:
            _total_capital = float(os.environ.get("AVAILABLE_CAPITAL", 0))
        except (ValueError, TypeError):
            _total_capital = 0.0
        if _total_capital <= 0:
            try:
                from quant_analyst import get_dhan_balance as _gdb
                _live_bal = float(_gdb() or 0)
                if _live_bal > 0:
                    _total_capital = _live_bal
            except Exception as _bal_e:
                details["e3_dhan_balance_fetch"] = f"failed: {_bal_e}"
        if _total_capital <= 0:
            _total_capital = sum(
                float(p.get("buy_price", 0) or 0) * float(p.get("quantity", 0) or 0)
                for p in _open_pos_for_heat
            ) * 2.0  # assume ~50% deployed → capital ~ 2× deployed
            if _total_capital <= 0:
                _total_capital = 100_000.0  # last-resort floor (was 1_000_000)
        details["e3_capital_used"] = round(_total_capital, 0)

        # Compute new trade risk
        _new_risk_rupees = max(0, float(entry) - float(sl)) * 1  # per share
        # Use estimated qty from sizing (1% risk of capital ÷ risk per share)
        _est_qty = int(_total_capital * RISK_PER_TRADE_PERCENT / max(0.01, _new_risk_rupees))
        _new_risk_total = _new_risk_rupees * max(1, _est_qty)

        _heat = _v2_e3.portfolio_heat_check(_open_pos_for_heat, _new_risk_total, _total_capital)
        details["e3_heat_current_pct"]   = _heat["current_heat_pct"]
        details["e3_heat_projected_pct"] = _heat["projected_heat_pct"]
        if _heat["status"] == "block":
            blocks.append(_heat["message"])
        elif _heat["status"] == "warn":
            warnings.append(_heat["message"])
    except Exception as e:
        warnings.append(f"E-3 portfolio heat check failed: {e}")

    # ── E-4 (v2.3): Consecutive-Loss Circuit Breaker ─────────────────
    # Blocks new entries after 3+ consecutive losing trades.
    try:
        import v2_fixes as _v2_e4
        _recent_closed = []
        try:
            _conn_e4 = sqlite3.connect(DB_FILE)
            _cur_e4 = _conn_e4.cursor()
            _cur_e4.execute(
                "SELECT buy_price, exit_price FROM journal "
                "WHERE status='CLOSED' AND exit_price IS NOT NULL "
                "ORDER BY exit_date DESC LIMIT 10"
            )
            _loss_rows = _cur_e4.fetchall()
            _conn_e4.close()
            for _r in _loss_rows:
                _recent_closed.append({
                    "buy_price": _r[0], "exit_price": _r[1],
                })
        except Exception as _le:
            details["e4_loss_journal"] = f"failed: {_le}"

        _loss = _v2_e4.consecutive_loss_check(_recent_closed)
        details["e4_loss_streak"] = _loss["streak"]
        if _loss["status"] == "block":
            blocks.append(_loss["message"])
        elif _loss["status"] == "warn":
            warnings.append(_loss["message"])
    except Exception as e:
        warnings.append(f"E-4 consecutive loss check failed: {e}")

    return {
        "ok":       len(blocks) == 0,
        "blocks":   blocks,
        "warnings": warnings,
        "details":  details,
    }


def _print_pre_flight_report(report):
    """Render the pre-flight result to console."""
    print("\n" + "=" * 60)
    print("🛂 PRE-FLIGHT CHECK")
    print("=" * 60)
    d = report.get("details", {})
    if "regime_score" in d:
        print(f"   Regime           : {d.get('regime_score','?')}/10  -  {d.get('regime_verdict','?')}")
    if "distribution_days" in d:
        print(f"   Distribution Days: {d.get('distribution_days','?')}")
    if d.get("fno_banned") is not None:
        print(f"   F&O Ban List     : {'BANNED' if d.get('fno_banned') else 'clear'}")
    if "rel_vol" in d:
        print(f"   Rel Volume       : {d['rel_vol']}x  (50-day average)")
    if "ext_pct_vs_ema20" in d:
        print(f"   Ext vs EMA20     : {d['ext_pct_vs_ema20']:+.1f}%")
    # E7
    if "e7_new_sector" in d:
        _spct = d.get("e7_post_trade_sector_pct")
        _spct_str = f"{_spct:.1f}%" if _spct is not None else "?"
        print(f"   Sector (post)    : {d['e7_new_sector']} → {_spct_str}")
    if "e7_max_corr" in d and d.get("e7_max_corr_partner"):
        print(f"   Max Corr         : {d['e7_max_corr']:.2f} vs {d['e7_max_corr_partner']}")
    # E3
    if "e3_pivot_price" in d and d.get("e3_pivot_price"):
        _piv = d.get("e3_pivot_price")
        _vsc = d.get("e3_vcp_score", 0)
        _vv  = "valid" if d.get("e3_vcp_valid") else "—"
        _broken = " BROKEN" if d.get("e3_broke_pivot") else ""
        print(f"   VCP Pivot        : ₹{_piv}  (score {_vsc}/100, {_vv}{_broken})")
    # E8
    if "e8_next_earnings" in d:
        _ed = d.get("e8_next_earnings")
        _dd = d.get("e8_calendar_days")
        _dd_str = f"  ({_dd}d away)" if _dd is not None else ""
        print(f"   Next Earnings    : {_ed}{_dd_str}")
    # E-3 (v2.3): Portfolio Heat
    if "e3_heat_current_pct" in d:
        _cur = d.get("e3_heat_current_pct", 0)
        _proj = d.get("e3_heat_projected_pct", 0)
        print(f"   Portfolio Heat   : {_cur:.1f}% current -> {_proj:.1f}% projected (ceiling 6%)")
    # E-4 (v2.3): Loss Streak
    if "e4_loss_streak" in d:
        _streak = d.get("e4_loss_streak", 0)
        _label = "clear" if _streak == 0 else f"{_streak} consecutive losses"
        print(f"   Loss Streak      : {_label}")
    print("-" * 60)

    if report["blocks"]:
        print(f"❌ BLOCKS ({len(report['blocks'])}):")
        for b in report["blocks"]:
            print(f"   • {b}")
    if report["warnings"]:
        print(f"⚠️  WARNINGS ({len(report['warnings'])}):")
        for w in report["warnings"]:
            print(f"   • {w}")
    if not report["blocks"] and not report["warnings"]:
        print("✅ All pre-flight checks passed.")
    print("=" * 60)


# ==========================================
# 3. EXECUTION ENGINE
# ==========================================
def run_sniper():
    parser = argparse.ArgumentParser(description="Sniper Execution Engine")
    parser.add_argument("symbol", nargs="?", default="", help="Stock Symbol")
    parser.add_argument("entry", nargs="?", type=float, default=0.0, help="Entry Price")
    parser.add_argument("sl", nargs="?", type=float, default=0.0, help="Stop Loss Price")
    parser.add_argument("--auto", action="store_true", help="Auto-pick from Golden Matches")
    args, unknown = parser.parse_known_args()

    cls()
    print("="*60)
    print("🎯 WEINSTEIN SNIPER: PRE-FLIGHT CHECK")
    print("="*60)

    # 0. LOAD SYMBOLS
    print("⏳ Loading Symbol Map...")
    id_map = get_nse_id_map()
    if not id_map:
        print("❌ CRITICAL: Could not load Security IDs.")
        return

    # 1. CONNECT & FETCH FUNDS
    print("⏳ Connecting to Dhan...")
    dhan, funds = connect_dhan()
    if not dhan: return

    # --- SMART CAPITAL FETCH ---
    avail_cash = 0.0
    try:
        if isinstance(funds, dict):
            avail_cash = float(funds.get('availabelBalance', 0) or 
                             funds.get('availableBalance', 0) or 
                             funds.get('availLimit', 0) or 
                             funds.get('sodLimit', 0))
    except: pass

    if avail_cash <= 0:
        print(f"\n⚠️ Could not read balance automatically.") 
        try:
            avail_cash = float(input("👉 Please Enter Available Capital Manually: "))
        except:
            print("❌ Invalid Number.")
            return

    print(f"\n💰 AVAILABLE CAPITAL: ₹ {avail_cash:,.2f}")
    print("-" * 60)

    # 2. INPUTS & ARGUMENTS
    symbol = args.symbol.upper()
    entry_price = args.entry
    sl_price = args.sl

    if args.auto and not symbol:
        import pandas as pd
        import glob
        golden_files = glob.glob("FINAL_*_Picks.csv")
        candidates = []
        for f in golden_files:
            try:
                df = pd.read_csv(f)
                sym_col = next((c for c in df.columns if 'symbol' in c.lower() or 'nsecode' in c.lower() or 'ticker' in c.lower()), None)
                if not sym_col: sym_col = df.columns[0] # Fallback
                for _, row in df.head(3).iterrows():
                    sym = str(row[sym_col]).replace("NSE:","").strip()
                    if sym: candidates.append((sym, f.replace("FINAL_","").replace("_Picks.csv","")))
            except: pass
        if candidates:
            print("\n🌟 GOLDEN MATCH CANDIDATES (Auto-Mode)")
            for i, (sym, src) in enumerate(candidates):
                print(f"  [{i+1}] {sym:<12} | {src}")
            print("  [0] CANCEL")
            try:
                idx = int(input("\n👉 Select candidate number: ")) - 1
                if 0 <= idx < len(candidates):
                    symbol = candidates[idx][0]
                else: return
            except: return
        else:
            print("⚠️ No Golden Matches found in CSVs.")

    while not symbol:
        symbol = input("👉 Enter Stock Symbol (e.g. CUB): ").strip().upper()
        if not symbol:
            print("⚠️ Symbol cannot be empty.")
            
    # VALIDATE SYMBOL
    security_id = id_map.get(symbol)
    if not security_id:
        print(f"❌ ERROR: Symbol '{symbol}' not found in NSE Equity Master.")
        input("\nPress Enter to exit...")
        return
        
    # --- TECHNICAL PREVIEW & LIVE LTP ---
    techs = get_technical_analysis(symbol)
    live_ltp = 0.0
    if techs:
        live_ltp = techs['close']
        print(f"\n📊 TECHNICAL SNAPSHOT ({symbol})")
        print(f"   • CMP (Live) : ₹ {live_ltp:.2f}")
        print(f"   • RSI (14)   : {techs['rsi']:.1f}")
        print(f"   • EMA 20     : {techs['ema_20']:.2f} (Trend: {'UP' if live_ltp>techs['ema_20'] else 'DOWN'})")
        print(f"   • SMA 50     : {techs['sma_50']:.2f}")
        print(f"   • SMA 200    : {techs['sma_200']:.2f}")
        
    if entry_price <= 0:
        try:
            print("")
            entry_price = float(input(f"👉 Enter ENTRY Price (Limit) [LTP: {live_ltp:.2f}]: "))
        except ValueError:
            print("❌ Invalid numbers.")
            return

    if sl_price <= 0:
        try:
            sl_price = float(input("👉 Enter STOPLOSS Price: "))
        except ValueError:
            print("❌ Invalid numbers.")
            return

    # 3. CALCULATE — E2: setup-aware sizing pulls regime & ADR
    _e2_regime_score = None
    _e2_adr_pct      = None
    try:
        import os as _os, json as _json
        _state_p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                   "regime_state.json")
        if _os.path.exists(_state_p):
            with open(_state_p, "r", encoding="utf-8") as _f:
                _e2_regime_score = (_json.load(_f).get("last") or {}).get("score")
    except Exception:
        pass
    try:
        # Reuse the daily frame already cached by data_provider for ATR/ext checks
        import data_provider as _dp_e2
        _e2_df = _dp_e2.fetch_ohlcv(symbol, period="1mo", interval="1d")
        if not _e2_df.empty and {"High","Low","Close"}.issubset(_e2_df.columns):
            _e2_adr_pct = float(((_e2_df["High"] - _e2_df["Low"]) /
                                   _e2_df["Close"] * 100).tail(20).mean())
    except Exception:
        pass

    qty, risk_share, total_risk, sizing_detail = calculate_position_size(
        avail_cash, entry_price, sl_price,
        regime_score=_e2_regime_score, adr_pct=_e2_adr_pct,
    )

    if not qty:
        input("\nPress Enter to restart...")
        return

    trade_value = qty * entry_price

    # 4. DASHBOARD
    print("\n" + "="*50)
    print(f"📋 TRADE PLAN: {symbol}")
    print("="*50)
    print(f"   • Entry Price :  ₹ {entry_price}")
    print(f"   • Stop Loss   :  ₹ {sl_price} ({(sl_price-entry_price)/entry_price:.2%})")
    print(f"   • Quantity    :  {qty} shares")
    print("-" * 50)
    print(f"   • Total Value :  ₹ {trade_value:,.2f} (Margin Req)")
    if sizing_detail:
        _rs = sizing_detail.get("regime_score")
        _ap = sizing_detail.get("adr_pct")
        _rs_str = f"{_rs}/10" if _rs is not None else "?/10"
        _ap_str = f"{_ap:.2f}%" if _ap is not None else "?%"
        print(f"   • TOTAL RISK  :  ₹ {total_risk:,.2f} ({sizing_detail['final_risk_pct']:.2f}% of Capital)")
        print(f"      sizing: base {sizing_detail['base_risk_pct']:.1f}% × "
              f"regime {sizing_detail['regime_mult']:.2f} ({_rs_str}) × "
              f"adr {sizing_detail['adr_mult']:.2f} ({_ap_str})")
    else:
        print(f"   • TOTAL RISK  :  ₹ {total_risk:,.2f} ({RISK_PER_TRADE_PERCENT*100}% of Capital)")
    if techs:
        print(f"   • RSI Check   : {'✅ Bullish' if techs['rsi']>50 else '⚠️ Weak'}")
        print(f"   • Trend Check : {'✅ Above EMA20' if techs['close']>techs['ema_20'] else '⚠️ Below EMA20'}")
    print("="*50)

    # 4.5  PRE-FLIGHT CHECK  (B1 + B2 + B14)
    pre_flight = _pre_flight_check(symbol, entry_price, sl_price)
    _print_pre_flight_report(pre_flight)

    if pre_flight["blocks"]:
        # Hard block — require typed OVERRIDE to proceed
        print("\n❌ Order is BLOCKED by pre-flight checks.")
        print("   To override, type the word OVERRIDE (case-sensitive).")
        print("   Anything else cancels the order.")
        ovr = input("> ").strip()
        if ovr != "OVERRIDE":
            print("🚫 Order cancelled (block not overridden).")
            input("\nPress Enter to exit...")
            return
        print("⚠️  Pre-flight blocks overridden by user. Proceeding under your responsibility.")
    elif pre_flight["warnings"]:
        # Soft warning — Y/N to proceed
        ack = input("\n⚠️  Proceed despite warning(s)? (Y/N): ").strip().upper()
        if ack != "Y":
            print("🚫 Order cancelled by user after warnings.")
            input("\nPress Enter to exit...")
            return

    # 5. EXECUTE
    now = datetime.now()
    mkt_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    mkt_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    is_market_open = (mkt_open <= now <= mkt_close) and (now.weekday() < 5)
    is_amo = not is_market_open

    order_type_str = "MARKET-HOURS (LIMIT)" if is_market_open else "AMO (LIMIT)"
    confirm = input(f"\n🚀 EXECUTE {order_type_str} ORDER? (Y/N): ").strip().upper()

    if confirm == 'Y':
        # GET RATIONALE (Required by Logic)
        print("\n📝 JOURNAL ENTRY")
        rationale = input("👉 Enter Trade Rationale (or type 'AI' for auto-gen): ")
        
        if rationale.strip().upper() == "AI":
            print("   ...Contacting AI Analyst (Institutional Flash)...")
            # B11 fix: 2.5R target matches the screeners and the journal insert.
            t_risk = entry_price - sl_price
            t_target = entry_price + (t_risk * 2.5)
            
            # Use the high-intelligence helper
            ai_report = generate_tactical_analysis(
                symbol=symbol,
                sector="General Market", # Sector detection could be added later
                buy_price=entry_price,
                ltp=live_ltp if live_ltp > 0 else entry_price, 
                sl=sl_price,
                target=t_target,
                force_refresh=True
            )
            
            print(f"\n   🤖 INSTITUTIONAL VERDICT:\n   {ai_report}\n")
            confirm_ai = input("   Confirm entries and execute? (Y/N): ").upper()
            if confirm_ai != 'Y':
                print("🚫 Order Cancelled by User.")
                return
            
            # In our new structure, 'rationale' is manual. We leave it blank or user can add.
            rationale = "AI Validated Order"
            auto_ai_analysis = ai_report
        else:
            auto_ai_analysis = ""
        
        if not rationale: rationale = " Technically Validated Setup"

        print("\n⏳ Placing Order...")
        try:
            # Using the Correct Security ID now
            order = dhan.place_order(
                security_id=security_id, 
                exchange_segment=dhan.NSE,
                transaction_type=dhan.BUY,
                quantity=qty,
                order_type=dhan.LIMIT,
                product_type=dhan.CNC,
                price=entry_price,
                after_market_order=is_amo,
                trading_symbol=symbol
            )
            
            if order['status'] == 'success':
                print(f"✅ SUCCESS! Order ID: {order['data']['orderId']}")
                
                # AUTO-LOG TO JOURNAL
                log_trade_to_db(symbol, entry_price, sl_price, qty, rationale)
                if auto_ai_analysis:
                    log_ai_analysis_to_db(symbol, auto_ai_analysis)

            else:
                print(f"❌ ORDER FAILED: {order['remarks']}")
                
        except Exception as e:
            print(f"❌ Execution Error: {e}")

    else:
        print("\n🚫 SIMULATION ENDED. No order placed.")

    input("\nPress Enter to exit...")

if __name__ == "__main__":
    run_sniper()