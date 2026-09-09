# breadth_engine.py — Market Breadth Engine for Commander Web v4.0
# Calculates A/D ratio, McClellan Oscillator, Stage distribution, % above SMAs
# Part of Weinstein Commander Web v4.0 for NSE India

import os
import json
import logging
import time
from datetime import datetime, timedelta
from net_utils import is_internet_available

import pandas as pd
import numpy as np
import yfinance as yf

# C1: route OHLCV through the unified data_provider when available.
try:
    import data_provider as _dp
    USE_DATA_PROVIDER = True
except Exception:
    _dp = None
    USE_DATA_PROVIDER = False

logger = logging.getLogger(__name__)
_cache: dict = {}  # TTL cache: {key: {"data": any, "expires_at": float}}

# ---------------------------------------------------------------------------
# NSE Sector indices available on Yahoo Finance
# Phase-2A: sourced from sectors.db.sector_meta. The hardcoded dict is kept as
# fallback for environments where sectors.db hasn't been built yet.
# ---------------------------------------------------------------------------
_NSE_SECTORS_FALLBACK = {
    # Core 11 — sector indices (always present)
    "Bank Nifty":          "^NSEBANK",
    "Nifty IT":            "^CNXIT",
    "Pharma":              "^CNXPHARMA",
    "Auto":                "^CNXAUTO",
    "FMCG":                "^CNXFMCG",
    "Metal":               "^CNXMETAL",
    "Energy":              "^CNXENERGY",
    "Realty":              "^CNXREALTY",
    "Media":               "^CNXMEDIA",
    # Financial Services: Yahoo's ^CNXFIN was effectively dead (1 row); the live
    # ticker is NIFTY_FIN_SERVICE.NS (verified 10 May 2026).
    "Financial Services":  "NIFTY_FIN_SERVICE.NS",
    "Infra":               "^CNXINFRA",
    # Expanded set (10 May 2026 — user feedback: "Only 11 sectors are shown and
    # add more"). These are additional NSE sector / thematic indices verified
    # against Yahoo Finance for reliable daily history. Tickers that returned
    # 0 rows on probe (e.g. ^CNXHEALTH, ^NIFTYHEALTH, NIFTYHEALTHCARE.NS for
    # the Healthcare index) have been EXCLUDED rather than left in to silently
    # disappear from the rendered table — see Pharma (^CNXPHARMA) for the
    # health-adjacent coverage that actually works.
    "PSU Bank":            "^CNXPSUBANK",
    "Private Bank":        "NIFTY_PVT_BANK.NS",
    "Services":            "^CNXSERVICE",
    "Consumption":         "^CNXCONSUM",
    "Commodities":         "^CNXCMDT",       # was ^CNXCOMMOD (0 rows)
    "MNC":                 "^CNXMNC",
    "PSE":                 "^CNXPSE",
}

BROAD_MARKET_INDICES = {
    "Nifty 50": "NIFTY",
    "Nifty 500": "NIFTY 500",
    "Nifty Next 50": "NIFTYNXT50",
    "Nifty Midcap 150": "NIFTY MIDCAP 150",
    "Nifty Smallcap 250": "NIFTY SMALLCAP 250",
    "Nifty Microcap 250": "NIFTY MICROCAP250"
}

def _load_nse_sectors_yf():
    """Build the merged sector→yf-ticker map.

    Strategy: take sector_lookup.get_sector_yf_map() as primary (driven by
    sectors.db, kept up-to-date by the maintenance jobs) and augment with any
    missing tickers from _NSE_SECTORS_FALLBACK so users always see the broadest
    feasible sector roster — not just whatever the db happened to have at last
    refresh. Deduplication is by yf-ticker: if two display names map to the
    same ticker, keep the first encountered (sector_lookup's display name wins).
    """
    merged: dict[str, str] = {}
    seen_tickers: set[str] = set()

    try:
        import sector_lookup as _sl
        primary = _sl.get_sector_yf_map(include_broad=False) or {}
    except Exception:
        primary = {}

    # Primary first (sector_lookup output), then fallback fills gaps
    for name, ticker in primary.items():
        if ticker and ticker not in seen_tickers:
            merged[name] = ticker
            seen_tickers.add(ticker)

    for name, ticker in _NSE_SECTORS_FALLBACK.items():
        if ticker and ticker not in seen_tickers:
            merged[name] = ticker
            seen_tickers.add(ticker)

    return merged if merged else dict(_NSE_SECTORS_FALLBACK)

NSE_SECTORS_YF = _load_nse_sectors_yf()

FALLBACK_NIFTY50_YF = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "BHARTIARTL.NS", "ICICIBANK.NS",
    "INFY.NS", "SBIN.NS", "HINDUNILVR.NS", "ITC.NS", "LT.NS",
    "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS", "ASIANPAINT.NS",
    "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS", "WIPRO.NS", "ONGC.NS",
    "NESTLEIND.NS", "POWERGRID.NS", "NTPC.NS", "HCLTECH.NS", "TECHM.NS",
    "TATASTEEL.NS", "JSWSTEEL.NS", "TATAMOTORS.NS", "M&M.NS", "ADANIENT.NS",
    "ADANIPORTS.NS", "COALINDIA.NS", "BAJAJFINSV.NS", "INDUSINDBK.NS", "DRREDDY.NS",
    "CIPLA.NS", "DIVISLAB.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "APOLLOHOSP.NS",
    "BRITANNIA.NS", "BPCL.NS", "HINDALCO.NS", "SHREECEM.NS", "TATACONSUM.NS",
    "GRASIM.NS", "SBILIFE.NS", "HDFCLIFE.NS", "PIDILITIND.NS", "BAJAJ-AUTO.NS",
]


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------
def _ttl_get(key: str):
    entry = _cache.get(key)
    if entry and time.time() < entry["expires_at"]:
        return entry["data"]
    return None


def _ttl_set(key: str, data, ttl: int) -> None:
    _cache[key] = {"data": data, "expires_at": time.time() + ttl}


# ---------------------------------------------------------------------------
# Function 1: load_universe_symbols
# ---------------------------------------------------------------------------
def load_universe_symbols() -> list:
    """
    Load the NSE universe symbol list for breadth calculations.
    Tries nifty500_symbols.json first; falls back to FALLBACK_NIFTY50_YF.

    Returns:
        List of Yahoo Finance ticker strings (e.g. 'RELIANCE.NS').
    """
    json_path = os.path.join(os.path.dirname(__file__), "nifty500_symbols.json")
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        symbols = data if isinstance(data, list) else data.get("symbols", [])
        if symbols:
            logger.info("Loaded %d symbols from nifty500_symbols.json", len(symbols))
            return symbols
    except FileNotFoundError:
        logger.info("nifty500_symbols.json not found — using Nifty 50 fallback")
    except Exception as e:
        logger.warning("Failed to load nifty500_symbols.json: %s — using fallback", e)
    return FALLBACK_NIFTY50_YF


# ---------------------------------------------------------------------------
# Function 2: calculate_breadth_metrics
# ---------------------------------------------------------------------------
def calculate_breadth_metrics(symbols=None, period: str = "15mo", ttl: int = 1800) -> dict:
    """
    Core breadth calculation across the NSE universe.

    Downloads OHLCV data in batches and computes per-stock and aggregate
    metrics including SMA relationships, Stage 2 classification, A/D ratio,
    52-week extremes, and breadth regime.

    NOTE: period must be >= "15mo" (~300 trading days) to have enough bars
    for SMA150 (150 bars) and SMA200 (200 bars). Using "6mo" makes
    above_sma150_pct and above_sma200_pct return 0% for all stocks.

    Args:
        symbols: List of yfinance tickers. Loads from universe if None.
        period:  yfinance period string (e.g. '6mo', '1y').
        ttl:     Cache TTL in seconds (default 1800 = 30 minutes).

    Returns:
        Dict of aggregate metrics plus 'detailed_df' (per-stock DataFrame).
        Returns empty dict on failure.
    """
    cache_key = f"breadth_{period}_{len(symbols) if symbols else 'auto'}"
    cached = _ttl_get(cache_key)
    if cached is not None:
        logger.debug("Breadth metrics cache hit")
        return cached

    if not is_internet_available():
        logger.warning("[breadth_engine] Internet offline: loading cached breadth metrics from disk.")
        _reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
        _latest_file = os.path.join(_reports_dir, "latest_breadth.json")
        if os.path.exists(_latest_file):
            try:
                with open(_latest_file, "r", encoding="utf-8") as _f:
                    _data = json.load(_f)
                _bm = _data.get("breadth", {})
                if _bm:
                    _bm["detailed_df"] = pd.DataFrame()
                    return _bm
            except Exception as _err:
                logger.warning("Failed to load latest_breadth.json: %s", _err)
        return {
            "total_stocks": 0,
            "advance_count": 0,
            "decline_count": 0,
            "unchanged_count": 0,
            "ad_ratio": 1.0,
            "above_sma50_pct": 0.0,
            "above_sma150_pct": 0.0,
            "above_sma200_pct": 0.0,
            "new_52w_high_count": 0,
            "new_52w_low_count": 0,
            "high_low_ratio": 0.0,
            "stage2_count": 0,
            "stage2_pct": 0.0,
            "calculated_at": datetime.now().isoformat(timespec="seconds"),
            "symbols_analyzed": 0,
            "detailed_df": pd.DataFrame(),
        }

    if symbols is None:
        symbols = load_universe_symbols()

    rows = []
    batch_size = 50

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i: i + batch_size]
        # C1: data_provider with parquet cache when available; per-symbol cache
        # hits short-circuit network calls. Falls back to direct yfinance.
        close_df = None
        import data_provider as _dp
        try:
            bd = _dp.fetch_batch_ohlcv(batch, period=period, interval="1d", use_cache=True, auto_adjust=True)
            if bd:
                close_df = pd.DataFrame({sym: df["Close"] for sym, df in bd.items()
                                            if "Close" in df.columns})
        except Exception as e:
            logger.warning("data_provider batch %d failed: %s", i // batch_size, e)
            continue

        for sym in batch:
            # data_provider strips the .NS suffix from keys; yfinance keeps it.
            # Try both forms.
            sym_key = sym if sym in close_df.columns else sym.replace(".NS", "")
            if sym_key not in close_df.columns:
                continue
            s = close_df[sym_key].dropna()
            if len(s) < 50:
                continue
            try:
                latest = float(s.iloc[-1])
                prev   = float(s.iloc[-2]) if len(s) >= 2 else latest

                sma50  = float(s.rolling(50).mean().iloc[-1])
                sma150 = float(s.rolling(150).mean().iloc[-1]) if len(s) >= 150 else float("nan")
                sma200 = float(s.rolling(200).mean().iloc[-1]) if len(s) >= 200 else float("nan")
                sma200_20d_ago = (
                    float(s.rolling(200).mean().iloc[-21])
                    if len(s) >= 221 else float("nan")
                )
                sma50_prev = float(s.rolling(50).mean().iloc[-2]) if len(s) >= 51 else float("nan")

                high_52w = float(s.tail(252).max())
                low_52w  = float(s.tail(252).min())

                above_sma50  = latest > sma50  if not np.isnan(sma50)  else False
                above_sma150 = latest > sma150 if not np.isnan(sma150) else False
                above_sma200 = latest > sma200 if not np.isnan(sma200) else False

                at_52w_high = latest >= high_52w * 0.97
                at_52w_low  = latest <= low_52w  * 1.05

                sma200_slope_positive = (
                    (sma200 > sma200_20d_ago)
                    if not (np.isnan(sma200) or np.isnan(sma200_20d_ago))
                    else False
                )
                stage2 = above_sma200 and sma200_slope_positive

                prev_above_sma50 = (prev > sma50_prev) if not np.isnan(sma50_prev) else False

                rows.append({
                    "symbol":           sym,
                    "close":            latest,
                    "prev_close":       prev,
                    "sma50":            sma50,
                    "sma150":           sma150,
                    "sma200":           sma200,
                    "high_52w":         high_52w,
                    "low_52w":          low_52w,
                    "above_sma50":      above_sma50,
                    "above_sma150":     above_sma150,
                    "above_sma200":     above_sma200,
                    "at_52w_high":      at_52w_high,
                    "at_52w_low":       at_52w_low,
                    "stage2":           stage2,
                    "prev_above_sma50": prev_above_sma50,
                    "advance":          latest > prev,
                    "decline":          latest < prev,
                })
            except Exception as e:
                logger.debug("Error processing %s: %s", sym, e)
                continue

    if not rows:
        logger.error("No breadth data collected — returning empty dict")
        return {}

    df = pd.DataFrame(rows)

    total        = len(df)
    adv          = int(df["advance"].sum())
    dec          = int(df["decline"].sum())
    unch         = total - adv - dec
    ad_ratio     = round(adv / dec, 3) if dec > 0 else float("inf")

    above50_pct  = round(df["above_sma50"].mean()  * 100, 1)
    above150_pct = round(df["above_sma150"].mean() * 100, 1)
    above200_pct = round(df["above_sma200"].mean() * 100, 1)

    nh_count     = int(df["at_52w_high"].sum())
    nl_count     = int(df["at_52w_low"].sum())
    stage2_count = int(df["stage2"].sum())
    stage2_pct   = round(stage2_count / total * 100, 1) if total > 0 else 0.0
    hl_ratio     = round(nh_count / (nh_count + nl_count + 0.001), 3)

    result = {
        "total_stocks":       total,
        "advance_count":      adv,
        "decline_count":      dec,
        "unchanged_count":    unch,
        "ad_ratio":           ad_ratio,
        "above_sma50_pct":    above50_pct,
        "above_sma150_pct":   above150_pct,
        "above_sma200_pct":   above200_pct,
        "new_52w_high_count": nh_count,
        "new_52w_low_count":  nl_count,
        "high_low_ratio":     hl_ratio,
        "stage2_count":       stage2_count,
        "stage2_pct":         stage2_pct,
        "calculated_at":      datetime.now().isoformat(timespec="seconds"),
        "symbols_analyzed":   total,
        "detailed_df":        df,
    }

    _ttl_set(cache_key, result, ttl)
    logger.info(
        "Breadth metrics: %d stocks | A/D %.2f | Above50 %.1f%% | Stage2 %.1f%%",
        total, ad_ratio, above50_pct, stage2_pct,
    )
    return result


# ---------------------------------------------------------------------------
# Function 3: calculate_mcclellan
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# McClellan persistent state (B9): the Summation Index is a running cumulative
# sum of the Oscillator. Bootstrapping cumsum on a fresh 60-day window every
# run made the absolute MSI level meaningless. This state file accumulates
# MSI across runs so the level becomes a real long-term breadth signal.
# ---------------------------------------------------------------------------
import os as _bre_os
import json as _bre_json

_MSI_STATE_PATH = _bre_os.path.join(
    _bre_os.path.dirname(_bre_os.path.abspath(__file__)),
    "mcclellan_state.json",
)


def _load_mcclellan_state() -> dict:
    """Return {"last_date": "YYYY-MM-DD", "msi": float, "history": [...]}."""
    if not _bre_os.path.exists(_MSI_STATE_PATH):
        return {"last_date": None, "msi": 0.0, "history": []}
    try:
        with open(_MSI_STATE_PATH, "r", encoding="utf-8") as f:
            s = _bre_json.load(f)
        return {
            "last_date": s.get("last_date"),
            "msi":       float(s.get("msi", 0.0)),
            "history":   s.get("history", []),
        }
    except Exception as e:
        logger.warning("McClellan state load failed: %s", e)
        return {"last_date": None, "msi": 0.0, "history": []}


def _save_mcclellan_state(last_date: str, msi: float, mco: float) -> None:
    """Persist latest MSI + append to a 365-day history for trend charts."""
    try:
        state = _load_mcclellan_state()
        state["last_date"] = last_date
        state["msi"]        = round(float(msi), 4)
        history = state.get("history", []) or []
        # Replace today's entry if present, else append; cap at 365 days
        history = [h for h in history if h.get("date") != last_date]
        history.append({"date": last_date, "msi": round(float(msi), 4),
                         "mco": round(float(mco), 4)})
        state["history"] = sorted(history, key=lambda x: x.get("date") or "")[-365:]
        with open(_MSI_STATE_PATH, "w", encoding="utf-8") as f:
            _bre_json.dump(state, f, indent=2, default=str)
    except Exception as e:
        logger.warning("McClellan state save failed: %s", e)


def calculate_mcclellan(breadth_history_df: pd.DataFrame,
                          persist: bool = True) -> dict:
    """
    Compute McClellan Oscillator and Summation Index from daily A/D history.

    B9 fix: the Summation Index is now persisted across runs in
    mcclellan_state.json so its level reflects a true long-running cumsum
    rather than restarting from zero on every 60-day bootstrap.

    Args:
        breadth_history_df: DataFrame with columns 'advance_count' and
                            'decline_count', ordered oldest → newest. Should
                            include a 'date' column or DatetimeIndex; if both
                            are absent, the trailing rows are treated as the
                            most-recent days.
        persist: if False, skip writing state (read-only mode for previews).

    Returns:
        Dict: oscillator (float), summation (float), summation_history (list),
              last_date (str), signal (str).
        Returns safe empty dict on failure.
    """
    try:
        df = breadth_history_df.copy()
        df["net_advances"] = df["advance_count"] - df["decline_count"]

        # Pandas EWM uses span= which gives alpha = 2/(span+1)
        df["ema19"] = df["net_advances"].ewm(span=19, adjust=False).mean()
        df["ema39"] = df["net_advances"].ewm(span=39, adjust=False).mean()
        df["mco"]   = df["ema19"] - df["ema39"]

        # Resolve date column: prefer explicit 'date', then DatetimeIndex,
        # then fall back to today/yesterday for the trailing rows.
        if "date" in df.columns:
            df["_date_norm"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        elif isinstance(df.index, pd.DatetimeIndex):
            df["_date_norm"] = df.index.strftime("%Y-%m-%d")
        else:
            from datetime import datetime as _dt, timedelta as _td
            today = _dt.now().date()
            df["_date_norm"] = [
                (today - _td(days=(len(df) - 1 - i))).isoformat()
                for i in range(len(df))
            ]

        # ── Summation Index with state continuity ─────────────────────
        state = _load_mcclellan_state()
        last_persisted_date = state.get("last_date")
        running_msi = state.get("msi", 0.0)

        # Build MSI series: for each bar, if its date > last_persisted_date,
        # add its MCO to the running total. Otherwise re-use whatever is in
        # the persisted history (so chart preserves the published level).
        history_map = {h.get("date"): h.get("msi") for h in state.get("history", [])}
        msi_values = []
        for _i, row in df.iterrows():
            d = row["_date_norm"]
            mco_v = float(row["mco"]) if not pd.isna(row["mco"]) else 0.0
            if last_persisted_date is None or d > last_persisted_date:
                running_msi = running_msi + mco_v
                msi_values.append(running_msi)
            else:
                # use historical level if we have it; else best-effort current run
                msi_values.append(history_map.get(d, running_msi))
        df["msi"] = msi_values

        oscillator = round(float(df["mco"].iloc[-1]), 2)
        summation  = round(float(df["msi"].iloc[-1]), 2)
        last_date  = df["_date_norm"].iloc[-1]

        if oscillator > 100:
            signal = "OVERBOUGHT"
        elif oscillator < -100:
            signal = "OVERSOLD"
        else:
            signal = "NEUTRAL"

        # Persist only the most recent bar (other bars already in history map)
        if persist and (last_persisted_date is None or last_date > last_persisted_date):
            _save_mcclellan_state(last_date, summation, oscillator)

        logger.info("McClellan Oscillator: %.2f | Summation: %.2f | %s",
                    oscillator, summation, signal)
        # Build summation_history view for chart consumers (last 90 days)
        summation_history = (
            df[["_date_norm", "msi"]]
              .rename(columns={"_date_norm": "date"})
              .tail(90)
              .to_dict("records")
        )
        return {
            "oscillator":         oscillator,
            "summation":          summation,
            "summation_history":  summation_history,
            "last_date":          last_date,
            "signal":             signal,
            "persisted":          bool(persist),
        }

    except Exception as e:
        logger.error("calculate_mcclellan failed: %s", e)
        return {"oscillator": 0.0, "summation": 0.0, "signal": "UNAVAILABLE",
                 "summation_history": [], "last_date": None, "persisted": False}


# ---------------------------------------------------------------------------
# Function 4: calculate_breadth_thrust
# ---------------------------------------------------------------------------
def calculate_breadth_thrust(breadth_history_df: pd.DataFrame) -> dict:
    """
    Compute Zweig Breadth Thrust indicator.

    Args:
        breadth_history_df: DataFrame with 'advance_count' and 'decline_count'.

    Returns:
        Dict: current_value, threshold, thrust_active (bool), signal (str).
    """
    THRESHOLD = 0.615
    try:
        df = breadth_history_df.copy()
        df["breadth"] = df["advance_count"] / (df["advance_count"] + df["decline_count"])
        df["ema10"]   = df["breadth"].ewm(span=10, adjust=False).mean()

        current_value = round(float(df["ema10"].iloc[-1]), 4)
        thrust_active = current_value >= THRESHOLD

        signal = "BREADTH THRUST ACTIVE" if thrust_active else "NO THRUST"

        logger.info("Breadth Thrust EMA10: %.4f | Threshold: %.3f | %s",
                    current_value, THRESHOLD, signal)
        return {
            "current_value": current_value,
            "threshold":     THRESHOLD,
            "thrust_active": thrust_active,
            "signal":        signal,
        }

    except Exception as e:
        logger.error("calculate_breadth_thrust failed: %s", e)
        return {"current_value": 0.0, "threshold": THRESHOLD,
                "thrust_active": False, "signal": "UNAVAILABLE"}


# ---------------------------------------------------------------------------
# Function 5: get_sector_breadth
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Function 5a: get_broad_market_breadth
# ---------------------------------------------------------------------------
def get_broad_market_breadth() -> pd.DataFrame:
    """
    Fetch ~9 months of daily data for each broad market index and compute
    stage classification plus Daily / Weekly / Monthly momentum metrics.

    Returns:
        DataFrame with columns:
        [Index, LTP, Daily%, Weekly%, Monthly%, Stage, SMA150D_slope]
        Sorted by Monthly% descending.
        Returns empty DataFrame on failure.
    """
    if not is_internet_available():
        logger.warning("[breadth_engine] Internet offline: returning empty broad market breadth.")
        return pd.DataFrame(columns=["Sector", "LTP", "Daily%", "Weekly%",
                                     "Monthly%", "Stage", "SMA150D_slope"])

    records = []
    for index_name, ticker in BROAD_MARKET_INDICES.items():
        try:
            import data_provider as _dp
            raw = _dp.fetch_ohlcv(ticker, period="9mo", interval="1d", use_cache=True, auto_adjust=True)
            if raw.empty or len(raw) < 50:
                logger.warning("Insufficient daily data for %s (%s): %d bars",
                               index_name, ticker, len(raw))
                continue

            close = raw["Close"].squeeze().dropna()
            ltp   = float(close.iloc[-1])

            sma50d  = float(close.rolling(50).mean().iloc[-1]) \
                      if len(close) >= 50  else float("nan")
            sma150d = float(close.rolling(150).mean().iloc[-1]) \
                      if len(close) >= 150 else float("nan")
            sma150d_prev = float(close.rolling(150).mean().iloc[-6]) \
                           if len(close) >= 155 else float("nan")

            def _pct(bars_back: int) -> float:
                if len(close) > bars_back:
                    prev = float(close.iloc[-(bars_back + 1)])
                    return round((ltp - prev) / prev * 100, 2) if prev else 0.0
                return 0.0

            daily_chg   = _pct(1)
            weekly_chg  = _pct(5)
            monthly_chg = _pct(21)

            sma150d_slope = (
                round((sma150d - sma150d_prev) / sma150d_prev * 100, 3)
                if not (np.isnan(sma150d) or np.isnan(sma150d_prev)
                        or sma150d_prev == 0)
                else float("nan")
            )

            is_stage2 = (
                not (np.isnan(sma50d) or np.isnan(sma150d) or np.isnan(sma150d_slope))
                and ltp > sma50d
                and ltp > sma150d
                and sma150d_slope > 0
            )
            is_stage4 = (
                not (np.isnan(sma50d) or np.isnan(sma150d) or np.isnan(sma150d_slope))
                and ltp < sma50d
                and ltp < sma150d
                and sma150d_slope < 0
            )
            stage_label = "Stage 2" if is_stage2 else "Stage 4" if is_stage4 else "Transitional"

            records.append({
                "Sector":         index_name,
                "LTP":            round(ltp, 2),
                "Daily%":         daily_chg,
                "Weekly%":        weekly_chg,
                "Monthly%":       monthly_chg,
                "Stage":          stage_label,
                "SMA150D_slope":  sma150d_slope,
            })

        except Exception as e:
            logger.warning("get_broad_market_breadth failed for %s: %s", index_name, e)
            continue

    if not records:
        return pd.DataFrame(columns=["Sector", "LTP", "Daily%", "Weekly%",
                                     "Monthly%", "Stage", "SMA150D_slope"])

    # Do not sort Broad Market table by default so it stays in hierarchical order
    # (Nifty 50 -> 500 -> Next 50 -> Mid 150 -> Small 250 -> Micro 250)
    df = pd.DataFrame(records)
    logger.info("Broad market breadth computed for %d indices", len(df))
    return df

def get_sector_breadth() -> pd.DataFrame:
    """
    Fetch ~9 months of daily data for each NSE sector index and compute
    stage classification plus Daily / Weekly / Monthly momentum metrics.

    Uses daily bars throughout so all three timeframes come from one download.
    Equivalent moving averages:
      SMA50d  ≈ SMA10W  (short-term trend)
      SMA150d ≈ SMA30W  (long-term trend / Weinstein stage gate)

    Returns:
        DataFrame with columns:
        [Sector, LTP, Daily%, Weekly%, Monthly%, Stage, SMA150D_slope]
        Sorted by Monthly% descending.
        Returns empty DataFrame on failure.
    """
    if not is_internet_available():
        logger.warning("[breadth_engine] Internet offline: returning empty sector breadth.")
        return pd.DataFrame(columns=["Sector", "LTP", "Daily%", "Weekly%",
                                     "Monthly%", "Stage", "SMA150D_slope"])

    records = []
    for sector_name, ticker in NSE_SECTORS_YF.items():
        try:
            # C1: cached fetch — sector indices change ~once a day; the parquet
            # cache turns 14 sequential network calls into 14 disk reads.
            import data_provider as _dp
            raw = _dp.fetch_ohlcv(ticker, period="9mo", interval="1d", use_cache=True, auto_adjust=True)
            if raw.empty or len(raw) < 50:
                logger.warning("Insufficient daily data for %s (%s): %d bars",
                               sector_name, ticker, len(raw))
                continue

            close = raw["Close"].squeeze().dropna()
            ltp   = float(close.iloc[-1])

            # ── Moving averages ───────────────────────────────────────────
            sma50d  = float(close.rolling(50).mean().iloc[-1]) \
                      if len(close) >= 50  else float("nan")
            sma150d = float(close.rolling(150).mean().iloc[-1]) \
                      if len(close) >= 150 else float("nan")
            # Slope: compare SMA150 today vs 5 trading days ago
            sma150d_prev = float(close.rolling(150).mean().iloc[-6]) \
                           if len(close) >= 155 else float("nan")

            # ── Period changes (daily bar offsets) ────────────────────────
            # Daily  = vs yesterday (1 bar)
            # Weekly = vs ~1 week ago (5 bars)
            # Monthly= vs ~1 month ago (21 bars)
            def _pct(bars_back: int) -> float:
                if len(close) > bars_back:
                    prev = float(close.iloc[-(bars_back + 1)])
                    return round((ltp - prev) / prev * 100, 2) if prev else 0.0
                return 0.0

            daily_chg   = _pct(1)
            weekly_chg  = _pct(5)
            monthly_chg = _pct(21)

            sma150d_slope = (
                round((sma150d - sma150d_prev) / sma150d_prev * 100, 3)
                if not (np.isnan(sma150d) or np.isnan(sma150d_prev)
                        or sma150d_prev == 0)
                else float("nan")
            )

            # ── Stage classification (Weinstein daily-bar logic) ──────────
            # B5 fix: Stage 4 now also requires SMA150 slope to be NEGATIVE.
            # Prior version classified late-Stage-1 bases (price below both MAs
            # but the longer MA flattening upward) as "Stage 4", over-flagging
            # accumulation bottoms as breakdowns.
            is_stage2 = (
                not (np.isnan(sma50d) or np.isnan(sma150d) or np.isnan(sma150d_slope))
                and ltp > sma50d
                and ltp > sma150d
                and sma150d_slope > 0
            )
            is_stage4 = (
                not (np.isnan(sma50d) or np.isnan(sma150d) or np.isnan(sma150d_slope))
                and ltp < sma50d
                and ltp < sma150d
                and sma150d_slope < 0
            )
            stage_label = "Stage 2" if is_stage2 else "Stage 4" if is_stage4 else "Transitional"

            records.append({
                "Sector":         sector_name,
                "LTP":            round(ltp, 2),
                "Daily%":         daily_chg,
                "Weekly%":        weekly_chg,
                "Monthly%":       monthly_chg,
                "Stage":          stage_label,
                "SMA150D_slope":  sma150d_slope,
            })

        except Exception as e:
            logger.warning("get_sector_breadth failed for %s: %s", sector_name, e)
            continue

    if not records:
        return pd.DataFrame(columns=["Sector", "LTP", "Daily%", "Weekly%",
                                     "Monthly%", "Stage", "SMA150D_slope"])

    df = pd.DataFrame(records).sort_values("Monthly%", ascending=False).reset_index(drop=True)
    logger.info("Sector breadth computed for %d sectors", len(df))
    return df


# ---------------------------------------------------------------------------
# Function 6: build_breadth_regime
# ---------------------------------------------------------------------------
def build_breadth_regime(metrics_dict: dict) -> str:
    """
    Classify the current market breadth regime from aggregate metrics.

    Args:
        metrics_dict: Output of calculate_breadth_metrics().

    Returns:
        One of five regime strings with emoji prefix.
    """
    if not metrics_dict:
        return "REGIME UNAVAILABLE"

    above50  = metrics_dict.get("above_sma50_pct",  0.0)
    ad_ratio = metrics_dict.get("ad_ratio",          0.0)
    stage2   = metrics_dict.get("stage2_pct",        0.0)

    if above50 > 70 and ad_ratio > 2.0 and stage2 > 35:
        return "BULL THRUST"
    elif above50 > 55 and stage2 > 25:
        return "BULL HEALTHY"
    elif 40 <= above50 <= 55:
        return "NEUTRAL"
    elif 25 <= above50 < 40:
        return "CORRECTION"
    else:
        return "BEAR"


# ---------------------------------------------------------------------------
# Function 7: bootstrap_ad_history
# ---------------------------------------------------------------------------
def bootstrap_ad_history(symbols=None, days: int = 65) -> pd.DataFrame:
    """
    Build advance/decline history from yfinance historical prices.

    Downloads daily closing prices for the universe over the past `days`
    trading days, then for each date counts how many stocks advanced vs
    declined vs the prior day.

    Args:
        symbols: List of YF tickers. Loads from universe if None.
        days:    Number of trading days of history to build (default 65).

    Returns:
        DataFrame with columns: date, advance_count, decline_count.
        Returns empty DataFrame on failure.
    """
    if not is_internet_available():
        logger.warning("[breadth_engine] Internet offline: cannot bootstrap A/D history.")
        return pd.DataFrame()

    if symbols is None:
        symbols = load_universe_symbols()

    period     = "4mo" if days <= 65 else "6mo"
    all_close  = pd.DataFrame()
    batch_size = 50

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i: i + batch_size]
        close_batch = None
        import data_provider as _dp
        try:
            bd = _dp.fetch_batch_ohlcv(batch, period=period, interval="1d", use_cache=True, auto_adjust=True)
            if bd:
                close_batch = pd.DataFrame({sym: df["Close"] for sym, df in bd.items()
                                              if "Close" in df.columns})
                # yfinance returns columns suffixed with .NS; data_provider strips
                # them. Restore the suffix so the outer-join key set stays stable.
                close_batch.columns = [c if c.endswith(".NS") or c.startswith("^")
                                        else f"{c}.NS"
                                        for c in close_batch.columns]
        except Exception as e:
            logger.warning("data_provider batch %d failed: %s", i // batch_size, e)
            
        if close_batch is None or close_batch.empty:
            logger.warning("data_provider batch %d returned empty data", i // batch_size)
            continue

        all_close = close_batch if all_close.empty else all_close.join(close_batch, how="outer")

    if all_close.empty:
        logger.error("bootstrap_ad_history: no data downloaded")
        return pd.DataFrame()

    daily_change = all_close.diff()
    records      = []

    for dt in daily_change.index[-days:]:
        row = daily_change.loc[dt].dropna()
        adv = int((row > 0).sum())
        dec = int((row < 0).sum())
        if adv + dec > 0:
            records.append({
                "date":          dt.strftime("%Y-%m-%d"),
                "advance_count": adv,
                "decline_count": dec,
            })

    df = pd.DataFrame(records)
    logger.info("bootstrap_ad_history: built %d rows of A/D data", len(df))
    return df


# ---------------------------------------------------------------------------
# Function 8: load_or_bootstrap_ad_history
# ---------------------------------------------------------------------------
def load_or_bootstrap_ad_history(symbols=None, min_rows: int = 40,
                                    force: bool = False,
                                    max_age_days: int = 2) -> pd.DataFrame:
    """
    Load the A/D history from reports/ad_history.json.
    If the file is missing, has fewer than min_rows rows, or its newest row
    is older than `max_age_days` calendar days, bootstraps fresh data from
    yfinance and saves it. `force=True` always re-bootstraps.

    The freshness gate exists because callers (McClellan recompute, regime
    score) were silently consuming a stale cached frame — calculate_mcclellan
    only persists new MSI when the input's last_date advances, so a stale
    cache makes "Compute McClellan" a no-op from the user's perspective.

    Returns:
        DataFrame with columns: date, advance_count, decline_count.
    """
    _reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    _hist_file   = os.path.join(_reports_dir, "ad_history.json")
    os.makedirs(_reports_dir, exist_ok=True)

    # Try loading from disk (skipped when force=True)
    if not force and os.path.exists(_hist_file):
        try:
            df = pd.read_json(_hist_file, dtype={"advance_count": int, "decline_count": int})
            df = df.sort_values("date").reset_index(drop=True)
            if len(df) >= min_rows:
                # Freshness check: newest row must be within `max_age_days`
                _newest = pd.to_datetime(df["date"].iloc[-1], errors="coerce")
                _age = (pd.Timestamp.now().normalize() - _newest).days if pd.notna(_newest) else 999
                if _age <= max_age_days or not is_internet_available():
                    if _age > max_age_days:
                        logger.warning("[breadth_engine] Internet offline: serving stale A/D history from disk.")
                    logger.info("Loaded %d rows of A/D history from %s (age=%dd)",
                                len(df), _hist_file, _age)
                    return df
                logger.info("A/D history cache is %d days stale (last=%s) — re-bootstrapping",
                            _age, df["date"].iloc[-1])
        except Exception as e:
            logger.warning("Could not load ad_history.json: %s", e)

    # Bootstrap from yfinance
    logger.info("Bootstrapping A/D history from yfinance (%d days)...", min_rows + 15)
    df = bootstrap_ad_history(symbols=symbols, days=min_rows + 15)

    if not df.empty:
        try:
            df.to_json(_hist_file, orient="records", indent=2)
            logger.info("Saved %d rows of A/D history to %s", len(df), _hist_file)
        except Exception as e:
            logger.warning("Could not save ad_history.json: %s", e)

    return df


# ---------------------------------------------------------------------------
# Function 9: format_breadth_for_report
# ---------------------------------------------------------------------------
def format_breadth_for_report(metrics_dict: dict) -> str:
    """
    Format breadth metrics as a plain-text block suitable for injecting
    into a Gemini prompt or printing to a console report.

    Args:
        metrics_dict: Output of calculate_breadth_metrics().

    Returns:
        Formatted multi-line string. Returns a warning string on empty input.
    """
    if not metrics_dict:
        return "Breadth Summary: data unavailable."

    regime = build_breadth_regime(metrics_dict)

    lines = [
        "Breadth Summary (NSE Universe):",
        f"- Stocks analyzed: {metrics_dict.get('symbols_analyzed', 'N/A')}",
        f"- Above SMA50: {metrics_dict.get('above_sma50_pct', 'N/A')}%"
        f" | Above SMA200: {metrics_dict.get('above_sma200_pct', 'N/A')}%",
        f"- Stage 2: {metrics_dict.get('stage2_pct', 'N/A')}%"
        f" | Stage 2 count: {metrics_dict.get('stage2_count', 'N/A')}",
        f"- New 52W Highs: {metrics_dict.get('new_52w_high_count', 'N/A')}"
        f" | New 52W Lows: {metrics_dict.get('new_52w_low_count', 'N/A')}",
        f"- A/D Ratio: {metrics_dict.get('ad_ratio', 'N/A')}",
        f"- Breadth Regime: {regime}",
    ]
    return "\n".join(lines)
