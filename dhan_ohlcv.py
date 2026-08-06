"""dhan_ohlcv.py — Dhan API historical OHLCV fetcher.

Provides deeper history than yfinance (which truncates Indian symbols at ~2y).
Used by data_provider.py as fallback when yfinance is short.

Setup:
  1. Dhan credentials in .env (DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN, etc.)
  2. First call downloads api-scrip-master.csv (~5MB, cached locally)
  3. Symbol --> security_id mapping built once per process

API: dhanhq.historical_daily_data(security_id, exchange_segment,
                                    instrument_type, from_date, to_date)
"""
from __future__ import annotations
import os, sys, time, logging
from datetime import datetime, date, timedelta
from typing import Optional

import pandas as pd
import requests

from dhanhq import dhanhq
try:
    from dhanhq import DhanContext
except ImportError:
    DhanContext = None
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

# ── Scrip master ──────────────────────────────────────────────────────────
SCRIP_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"
SCRIP_CACHE = os.path.join(os.path.dirname(__file__), "data", "dhan_scrip_master.csv")
_SCRIP_CACHE_TTL_SEC = 7 * 86400  # refresh weekly

_scrip_df: Optional[pd.DataFrame] = None
_sym_to_secid: Optional[dict] = None

# ── Rate limiting ──────────────────────────────────────────────────────────
# The Dhan Data API rate-limits (DH-904). Under a 500-symbol screen the data
# path used to hammer it and silently lose those symbols to yfinance. Throttle
# Dhan calls and do one backoff retry on DH-904 so the PAID feed holds up.
_DHAN_MIN_INTERVAL_S = float(os.getenv("DHAN_MIN_INTERVAL_S", "0.30"))  # ~3.3 req/s
_DHAN_RETRY_SLEEP_S = float(os.getenv("DHAN_RETRY_SLEEP_S", "1.0"))
_DHAN_MAX_RETRIES = int(os.getenv("DHAN_MAX_RETRIES", "2"))
_last_dhan_call = 0.0


def _is_transient_failure(resp) -> bool:
    """True if a non-success Dhan response looks transient (rate-limit / empty
    body) and is worth a backoff retry — as opposed to a hard error (bad symbol,
    auth) where retrying is pointless."""
    if not isinstance(resp, dict):
        return True  # garbage/None response — worth one retry
    rem = resp.get("remarks")
    code = ""
    msg = ""
    if isinstance(rem, dict):
        code = str(rem.get("error_code") or rem.get("errorCode") or "")
        msg = str(rem.get("error_message") or rem.get("errorMessage") or "")
    elif rem is not None:
        msg = str(rem)
    # DH-904 = explicit rate limit. Blank code+msg = empty/non-JSON body (the
    # SDK's find_error_code choked) = almost always a 429 under burst load.
    if "DH-904" in code:
        return True
    if not code and not msg:
        return True
    # DH-901 (auth) and DH-905 (bad input) are NOT transient — don't retry.
    return False


def _throttle_dhan() -> None:
    global _last_dhan_call
    dt = time.time() - _last_dhan_call
    if dt < _DHAN_MIN_INTERVAL_S:
        time.sleep(_DHAN_MIN_INTERVAL_S - dt)
    _last_dhan_call = time.time()


def _download_scrip_master():
    os.makedirs(os.path.dirname(SCRIP_CACHE), exist_ok=True)
    print(f"  Downloading Dhan scrip master from {SCRIP_URL} ...", flush=True)
    r = requests.get(SCRIP_URL, timeout=60)
    r.raise_for_status()
    with open(SCRIP_CACHE, "wb") as f:
        f.write(r.content)
    print(f"  Saved scrip master ({len(r.content)/1e6:.1f} MB) to {SCRIP_CACHE}")


def _load_scrip_master() -> pd.DataFrame:
    global _scrip_df
    if _scrip_df is not None:
        return _scrip_df
    # Refresh if missing or older than TTL
    need_dl = True
    have_cache = os.path.exists(SCRIP_CACHE)
    cache_age_days = None
    if have_cache:
        age = time.time() - os.path.getmtime(SCRIP_CACHE)
        cache_age_days = age / 86400.0
        if age < _SCRIP_CACHE_TTL_SEC:
            need_dl = False
    if need_dl:
        try:
            _download_scrip_master()
        except Exception as e:
            # Don't silently use stale symbol mappings — warn loudly. Stale
            # scrip master means IPO/renamed symbols silently fail to resolve.
            if have_cache:
                print(f"  [!] Dhan scrip-master refresh FAILED ({e}); using STALE "
                      f"cache ({cache_age_days:.1f} days old). New/renamed symbols "
                      f"may not resolve to Dhan -- they will fall back to yfinance.",
                      flush=True)
            else:
                print(f"  [X] Dhan scrip-master download FAILED ({e}) and no local "
                      f"cache exists. Dhan symbol resolution is UNAVAILABLE; all "
                      f"equities will fall back to yfinance this run.", flush=True)
                raise
    _scrip_df = pd.read_csv(SCRIP_CACHE, low_memory=False)
    return _scrip_df


def _build_symbol_map():
    """Build NSE EQUITY + INDEX symbol --> (security_id, segment, instrument)."""
    global _sym_to_secid
    if _sym_to_secid is not None:
        return _sym_to_secid
    df = _load_scrip_master()
    flt = df[df["SEM_EXM_EXCH_ID"].astype(str).str.upper() == "NSE"].copy()
    # Use SEM_TRADING_SYMBOL (clean ticker like RELIANCE) — NOT SM_SYMBOL_NAME (company name)
    # Series 'EQ' = standard equity; exclude bonds (SG/GS/YL), MF, etc.
    eq = flt[(flt["SEM_INSTRUMENT_NAME"].astype(str).str.upper() == "EQUITY") &
              (flt["SEM_SERIES"].astype(str).str.upper().isin(["EQ", "BE", "BZ"]))]
    ix = flt[flt["SEM_INSTRUMENT_NAME"].astype(str).str.upper() == "INDEX"]
    _sym_to_secid = {}
    for _, row in eq.iterrows():
        key = str(row["SEM_TRADING_SYMBOL"]).strip().upper()
        if key and key != "NAN":
            _sym_to_secid[key] = {
                "security_id":      str(int(row["SEM_SMST_SECURITY_ID"])),
                "exchange_segment": "NSE_EQ",
                "instrument_type":  "EQUITY",
            }
    for _, row in ix.iterrows():
        # Index trading symbols often have spaces; also map SM_SYMBOL_NAME as alias
        for key_src in (row.get("SEM_TRADING_SYMBOL"), row.get("SM_SYMBOL_NAME")):
            key = str(key_src).strip().upper()
            if key and key != "NAN":
                _sym_to_secid[key] = {
                    "security_id":      str(int(row["SEM_SMST_SECURITY_ID"])),
                    "exchange_segment": "IDX_I",
                    "instrument_type":  "INDEX",
                }
    # Sector & Index Aliases for Yahoo Finance carets (^...) and standard names
    INDEX_ALIASES = {
        "^NSEI": ["NIFTY 50", "NIFTY"],
        "^NSEBANK": ["BANKNIFTY", "NIFTY BANK"],
        "^CNXFIN": ["FINNIFTY", "NIFTY FINANCIAL SERVICES", "NIFTY FIN SERVICE"],
        "^CNXAUTO": ["NIFTY AUTO"],
        "^CNXIT": ["NIFTYIT", "NIFTY IT"],
        "^CNXFMCG": ["NIFTY FMCG"],
        "^CNXPHARMA": ["NIFTY PHARMA"],
        "^CNXREALTY": ["NIFTY REALTY"],
        "^CNXMETAL": ["NIFTY METAL"],
        "^CNXMEDIA": ["NIFTY MEDIA"],
        "^CNXENERGY": ["NIFTY ENERGY"],
        "^CNXINFRA": ["NIFTYINFRA", "NIFTY INFRA"],
        "^CNXSERVICE": ["NIFTY SERV SECTOR"],
        "^CNXCONSUM": ["NIFTY CONSUMPTION"],
        "^CNXCMDT": ["NIFTY COMMODITIES"],
        "^CNX100": ["NIFTY 100"],
        "^CNX200": ["NIFTY 200"],
        "^CNX500": ["NIFTY 500", "NIFTY500"],
        "^CRSLDX": ["NIFTY 500", "NIFTY500"],
        "^NIFTY": ["NIFTY 50", "NIFTY"],
    }
    for alias_key, target_names in INDEX_ALIASES.items():
        for tname in target_names:
            if tname in _sym_to_secid:
                target_meta = _sym_to_secid[tname]
                _sym_to_secid[alias_key] = target_meta
                _sym_to_secid[alias_key.lstrip("^")] = target_meta
                break
    print(f"  Built symbol-->meta map: {len(_sym_to_secid)} NSE EQUITY + INDEX")
    return _sym_to_secid


def get_security_meta(symbol: str) -> Optional[dict]:
    """Return Dhan meta {security_id, exchange_segment, instrument_type}.

    P0 fix (14-Jul-2026): this is the gate that decides Dhan-vs-yfinance, but it
    only did a direct map lookup — a separator-variant symbol (BAJAJ_AUTO vs
    BAJAJ-AUTO, M_M vs M&M) missed and SILENTLY fell to yfinance, splitting the
    data source between surfaces. Now falls back to the separator-insensitive
    canonical_nse_symbol resolver before giving up. Fast path (direct hit) first.
    """
    m = _build_symbol_map()
    s = symbol.strip().upper()
    for suffix in (".NS", ".BO", ".NSE", "-EQ"):
        if s.endswith(suffix):
            s = s[:-len(suffix)]
    meta = m.get(s)
    if meta is None and s.startswith("^"):
        meta = m.get(s[1:])
    if meta is None:
        canon = canonical_nse_symbol(s)
        if canon != s:
            meta = m.get(canon)
    return meta


def get_security_id(symbol: str) -> Optional[str]:
    meta = get_security_meta(symbol)
    return meta["security_id"] if meta else None


# Separator-insensitive alias index (built lazily from the scrip master).
_norm_alias_map: Optional[dict] = None


def _norm_symbol_key(s) -> str:
    """Strip every separator TradingView / NSE / yfinance disagree on so that
    'BAJAJ_AUTO', 'BAJAJ-AUTO' and 'BAJAJAUTO' collapse to one key; likewise
    'M_M' and 'M&M' -> 'MM'."""
    out = []
    for ch in str(s).upper():
        if ch.isalnum():
            out.append(ch)
    return "".join(out)


def canonical_nse_symbol(symbol: str) -> str:
    """Resolve any separator variant to the exchange's canonical NSE trading
    symbol via the Dhan scrip master.

    TradingView reports 'BAJAJ_AUTO' / 'NAM_INDIA' (underscores) while the
    scrip master + yfinance use 'BAJAJ-AUTO' / 'NAM-INDIA' (hyphens), and a few
    names use '&' ('M&M' <-> TV 'M_M') — so a blind '_'->'-' swap is wrong. This
    matches on a separator-stripped key against the authoritative master.

    Returns the canonical bare trading symbol (no exchange prefix / .NS suffix),
    or the cleaned input unchanged if it can't be resolved (never raises).
    Indices ('^...') and non-NSE inputs pass through untouched.
    """
    global _norm_alias_map
    s = str(symbol or "").strip().upper()
    for pre in ("NSE:", "BSE:"):
        if s.startswith(pre):
            s = s[len(pre):]
    for suf in (".NS", ".BO", ".NSE", "-EQ"):
        if s.endswith(suf):
            s = s[:-len(suf)]
            break
    if not s or s.startswith("^") or s.endswith(("=X", "=F")):
        return s
    try:
        m = _build_symbol_map()
        if s in m:                       # already canonical
            return s
        if _norm_alias_map is None:
            _norm_alias_map = {}
            for k in m:
                _norm_alias_map.setdefault(_norm_symbol_key(k), k)
        hit = _norm_alias_map.get(_norm_symbol_key(s))
        if hit:
            return hit
    except Exception as e:
        logger.debug("canonical_nse_symbol: master lookup failed for %s: %s", symbol, e)
    # Last-resort when the master is unavailable: TV underscore -> NSE hyphen
    # (fixes the common reported names; ampersand names are rare and the master
    # is almost always present).
    if "_" in s:
        return s.replace("_", "-")
    return s


# ── Dhan client ───────────────────────────────────────────────────────────
_client = None
_client_token = None            # the token _client was BUILT with (see _get_client)

# Failure visibility (19 Jun 2026): a silent empty-DataFrame on an expired
# token meant the WHOLE ecosystem ran on yfinance while believing it was on the
# paid Dhan feed. Surface the real reason once, loudly, then fast-fail.
_AUTH_FAILED = False
_FAILURE_BANNER_SHOWN = False
# 17-Jul-2026: _AUTH_FAILED used to be a PERMANENT process-wide latch — once an
# expired token tripped it, EVERY later fetch fast-failed to the fallback feed
# for the life of the process and the only cure was a restart. That is exactly
# the "long-running Streamlit returns ok=False while a fresh process returns
# ok=True" symptom (it surfaced as an all-"n/a" S4-GO column on the Trigger
# Board — a data/feed problem wearing a scoring problem's clothes). The latch is
# now time-boxed: after the cooldown ONE probe is allowed through on a REBUILT
# client, so a token that has since refreshed heals itself.
_AUTH_FAILED_AT = 0.0
_AUTH_RETRY_COOLDOWN_S = float(os.getenv("DHAN_AUTH_RETRY_COOLDOWN_S", "300"))


def _note_dhan_failure(symbol, resp) -> None:
    """Surface the Dhan failure reason once. Detects expired/invalid auth and
    flips _AUTH_FAILED so the rest of the run fast-fails to the fallback feed
    instead of issuing one doomed API call per symbol."""
    global _AUTH_FAILED, _FAILURE_BANNER_SHOWN, _AUTH_FAILED_AT
    remarks = {}
    if isinstance(resp, dict):
        remarks = resp.get("remarks") or resp.get("data") or {}
    code = ""
    msg = ""
    if isinstance(remarks, dict):
        code = str(remarks.get("error_code") or remarks.get("errorCode") or "")
        msg = str(remarks.get("error_message") or remarks.get("errorMessage") or "")
    is_auth = ("DH-901" in code) or ("auth" in msg.lower()) or ("token" in msg.lower())
    is_fatal = is_auth or ("DH-905" in code)
    if is_fatal and not _AUTH_FAILED:
        _AUTH_FAILED = True
        _AUTH_FAILED_AT = time.time()      # starts the recovery cooldown (_auth_blocked)
    if not _FAILURE_BANNER_SHOWN:
        _FAILURE_BANNER_SHOWN = True
        if is_auth:
            banner = (
                "\n" + "=" * 70 +
                "\n[X] DHAN API AUTH FAILED -- the PAID feed is NOT being used.\n"
                f"   {code} {msg}\n"
                "   Every price fetch is silently falling back to FREE yfinance.\n"
                "   FIX: regenerate DHAN_ACCESS_TOKEN (Dhan tokens expire) and set it\n"
                "   in the environment / .env, then re-run.\n" + "=" * 70)
        elif "DH-905" in code:
            banner = (
                "\n" + "=" * 70 +
                "\n[X] DHAN API BROKEN (DH-905) -- the PAID feed is NOT being used.\n"
                f"   {code} {msg}\n"
                "   Dhan's backend is rejecting valid parameters. Fast-failing to yfinance.\n"
                "   This is a broker-side API issue.\n" + "=" * 70)
        else:
            detail = (f"{code} {msg}").strip() or "empty/non-JSON body (likely rate-limit/429)"
            banner = (f"\n[!] Dhan API non-success for {symbol}: {detail} "
                      f"-- retried then fell back to yfinance. If frequent, raise "
                      f"DHAN_MIN_INTERVAL_S (current {_DHAN_MIN_INTERVAL_S}s).")
        print(banner, flush=True)
        logger.warning("Dhan failure: %s %s (symbol=%s)", code, msg, symbol)

def _auth_blocked() -> bool:
    """True when the paid feed should be skipped this call (fast-fail to fallback).

    Replaces the bare `_AUTH_FAILED` reads at the fetch gates. The latch is now
    RECOVERABLE: once the cooldown elapses the cached client is dropped and ONE
    probe is let through — _get_client() then re-validates the token (TOTP-
    refreshing, or picking up a token another process wrote to .env), so a
    process whose token expired mid-session heals itself instead of needing a
    restart. A still-bad token simply re-trips the latch via _note_dhan_failure,
    so we still never hammer the API one-doomed-call-per-symbol.
    """
    global _AUTH_FAILED, _FAILURE_BANNER_SHOWN, _client, _client_token
    if not _AUTH_FAILED:
        return False
    if (time.time() - _AUTH_FAILED_AT) < _AUTH_RETRY_COOLDOWN_S:
        return True
    logger.info("Dhan auth latch expired after %.0fs -- retrying the paid feed with "
                "a re-validated token.", _AUTH_RETRY_COOLDOWN_S)
    _AUTH_FAILED = False
    _FAILURE_BANNER_SHOWN = False       # a NEW failure must be reported again, not swallowed
    _client = None                      # the probe must NOT reuse the token that failed
    _client_token = None
    return False


def auth_failed() -> bool:
    """Public read of the auth-latch state. Lets callers report 'Dhan auth
    expired' instead of a generic 'no data' — the difference between a column
    that reads as a scoring problem and one that names its real cause."""
    return bool(_AUTH_FAILED)


def _get_client():
    global _client, _client_token
    cid = os.getenv("DHAN_CLIENT_ID")
    # Root cause of the "paid feed silently dead" bug: the data path used the
    # RAW env token (which expires daily) while the journal path auto-refreshed
    # via dhan_auth. Use the same auto-refresh here so the data feed stays live.
    tok = ""
    try:
        import dhan_auth
        tok = dhan_auth.get_valid_token()   # validates JWT expiry; TOTP-refreshes if stale
    except Exception as e:
        logger.warning("dhan_auth.get_valid_token failed (%s) -- using raw env token", e)
        tok = os.getenv("DHAN_ACCESS_TOKEN", "").strip("'\"")
    # Reuse the cached client ONLY while it still holds the CURRENT token.
    # 17-Jul-2026: this function used to `return _client` on its first line, so the
    # token was resolved ONCE per process and baked into the client forever — a
    # long-running Streamlit kept presenting a token that had since expired
    # (DH-901) while a fresh process worked, which is why "restart Web Commander"
    # was the only known cure. get_valid_token() is cheap while the token is still
    # valid (local JWT-expiry check, no network), so re-checking every call costs
    # nothing and rebuilds only when the token actually rotated.
    if _client is not None and tok and tok == _client_token:
        return _client
    if not tok and _client is not None:
        # Couldn't resolve a token this call (offline / dhan_auth error) but we
        # hold a client — keep using it rather than hard-failing a feed that may
        # still be live. Preserves the old cached-client behaviour on that path.
        return _client
    if not cid or not tok:
        raise RuntimeError("DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN missing from env")
    if DhanContext:
        _client = dhanhq(DhanContext(cid, tok))
    else:
        _client = dhanhq(cid, tok)
    _client_token = tok
    # Root cause #2 of the dead data feed: the Dhan v2 /charts/historical
    # endpoint requires BOTH 'access-token' AND 'client-id' headers, but the
    # dhanhq SDK only sets 'access-token' -> every historical call returned
    # DH-905 (Input_Exception). Inject client-id so historical_daily_data works.
    try:
        if isinstance(getattr(_client, "header", None), dict):
            _client.header.setdefault("client-id", str(cid))
    except Exception:
        pass
    return _client


# ── Freshness: fill the just-closed session from intraday ───────────────────
def _last_completed_session_date():
    """Date of the most-recently COMPLETED NSE session (IST clock). Today only
    after the 15:30 close; otherwise the previous trading day. Weekend-aware;
    NSE holidays not modelled (errs to the last weekday)."""
    now = datetime.now()
    d = now.date()
    if d.weekday() < 5 and (now.hour * 60 + now.minute) >= (15 * 60 + 30):
        return d
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _append_completed_session_from_intraday(symbol: str, meta: dict, df_daily):
    """If the Dhan daily frame is behind the last COMPLETED session (their daily
    endpoint lags a day), aggregate the missing session(s) from the intraday
    feed and append them. Only appends CLOSED sessions (never today's forming
    bar). No-op / early-return when the daily is already current. Never raises."""
    if df_daily is None or getattr(df_daily, "empty", True):
        return df_daily
    target = _last_completed_session_date()
    last = df_daily.index[-1].date()
    if last >= target:
        return df_daily                       # daily already current — the common path
    # Daily lags: pull recent intraday and aggregate per-day into daily bars.
    dfi = fetch_intraday(symbol,
                         from_date=(target - timedelta(days=6)).isoformat(),
                         to_date=target.isoformat(), interval=15)
    if dfi is None or dfi.empty:
        return df_daily
    agg = dfi.resample("D").agg({"Open": "first", "High": "max", "Low": "min",
                                 "Close": "last", "Volume": "sum"}).dropna(subset=["Close"])
    agg.index = agg.index.normalize()
    # Keep only fully-CLOSED sessions after the daily's last bar and on/before
    # the target (target itself is completed by construction).
    import pandas as _pd
    add = agg[(agg.index > _pd.Timestamp(last)) & (agg.index <= _pd.Timestamp(target))]
    if add.empty:
        return df_daily
    out = _pd.concat([df_daily, add[["Open", "High", "Low", "Close", "Volume"]]])
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out.index.name = df_daily.index.name
    logger.info("intraday session-fill: %s appended %d bar(s) up to %s (daily lagged at %s)",
                symbol, len(add), target, last)
    return out


# ── Public fetcher ────────────────────────────────────────────────────────
def fetch_intraday(symbol: str,
                   from_date: Optional[str] = None,
                   to_date: Optional[str] = None,
                   interval: int = 1) -> pd.DataFrame:
    """Fetch intraday minute OHLCV from Dhan API. Returns DataFrame.

    Window limits (verified empirically 8-Jul-2026): Dhan serves up to ~90 days
    for coarser intervals (25-min requests return ~900 bars over 90d — the GM
    trigger-TF path relies on this); the old "max 5 days" note applies to
    interval=1 (per-minute) only, which is why the default from_date stays at
    today-4d. Callers wanting 75/125m resamples should request 25-min bars over
    up to 90 days."""
    meta = get_security_meta(symbol)
    if meta is None or _auth_blocked():
        return pd.DataFrame()

    if to_date is None:
        to_date = date.today().isoformat()
    if from_date is None:
        from_date = (date.today() - timedelta(days=4)).isoformat()

    cli = _get_client()

    def _call():
        _throttle_dhan()
        return cli.intraday_minute_data(
            security_id=meta["security_id"],
            exchange_segment=meta["exchange_segment"],
            instrument_type=meta["instrument_type"],
            from_date=from_date,
            to_date=to_date,
            interval=interval
        )

    try:
        resp = _call()
        attempts = 0
        while (attempts < _DHAN_MAX_RETRIES
               and isinstance(resp, dict)
               and resp.get("status") != "success"
               and _is_transient_failure(resp)):
            attempts += 1
            time.sleep(_DHAN_RETRY_SLEEP_S * attempts)
            resp = _call()
    except Exception as e:
        logger.warning(f"Dhan intraday fetch failed for {symbol}: {e}")
        return pd.DataFrame()

    if not isinstance(resp, dict) or resp.get("status") != "success":
        _note_dhan_failure(symbol, resp)
        return pd.DataFrame()
    data = resp.get("data", {})
    # FIX 10-Jul-2026: Dhan's intraday response returns the time key as
    # `timestamp` (epoch seconds) — same as the daily endpoint — NOT `start_Time`.
    # The old `start_Time` key made this guard bail out as empty on EVERY intraday
    # response (data was present all along: open/high/low/close/volume/timestamp).
    if not data or not data.get("timestamp"):
        return pd.DataFrame()

    df = pd.DataFrame({
        "Open":   data.get("open", []),
        "High":   data.get("high", []),
        "Low":    data.get("low", []),
        "Close":  data.get("close", []),
        "Volume": data.get("volume", []),
    })
    # Epoch seconds → IST datetime (UTC→IST convert, no normalize — keep the
    # intra-day time), mirroring the daily endpoint's tz handling.
    try:
        df.index = (pd.to_datetime(data["timestamp"], unit="s", utc=True)
                      .tz_convert("Asia/Kolkata").tz_localize(None))
        df.index.name = "Datetime"
        df = df.sort_index()
        df = df[~df.index.duplicated(keep="last")]
    except Exception as e:
        logger.warning("Dhan intraday timestamp parse failed for %s: %s", symbol, e)
        return pd.DataFrame()

    # ── DROP THE SESSION-CLOSE STUB (6-Aug-2026) ────────────────────────────────
    # After the close Dhan publishes a phantom bar stamped 15:30 with
    # O=H=L=C=<last close> and Volume=0. It is a marker, not a bar: no trades
    # happened in it.
    #
    # Left in, it is a zero-range doji that resamples into a WHOLE EXTRA 75m/125m
    # bar — RELIANCE showed five real 75m bars plus a sixth reading
    # 1325/1325/1325/1325 vol 0. Any surface reading "the last closed bar" after
    # the close then reads the stub, and this is exactly what happened: the GM
    # trigger boards rebuilt at 23:13 returned ZERO S4-GOs on both 75m and 125m
    # (RV = 0 on every name, so the volume gate failed everywhere) while Daily,
    # which never sees the stub, returned 12. The damage is not limited to
    # volume — a zero-range bar also feeds the PA battery and the bar-strength
    # test, so the entire read lands on a bar in which nothing occurred.
    #
    # Scoped deliberately to TRAILING rows: the stub is always last (observed 1
    # zero-volume row in 76 over five sessions, always 15:30). A genuine
    # zero-volume bar mid-series in an illiquid name is left alone — dropping it
    # would silently rewrite history to fix a boundary artifact.
    if not df.empty and "Volume" in df.columns:
        vol = pd.to_numeric(df["Volume"], errors="coerce").fillna(0.0)
        rng = pd.to_numeric(df["High"], errors="coerce") - pd.to_numeric(df["Low"], errors="coerce")
        stub = (vol <= 0) & (rng.abs() <= 0)
        n = 0
        while n < len(df) and bool(stub.iloc[len(df) - 1 - n]):
            n += 1
        if n:
            logger.debug("%s: dropped %d trailing zero-volume stub bar(s) (last %s)",
                         symbol, n, df.index[-1])
            df = df.iloc[:len(df) - n]
    return df

def fetch_daily(symbol: str,
                  from_date: Optional[str] = None,
                  to_date: Optional[str] = None,
                  years: int = 5) -> pd.DataFrame:
    """Fetch daily OHLCV from Dhan API. Returns DataFrame indexed by date.

    Args:
        symbol: plain ticker (e.g., 'RELIANCE'). Will be mapped to security_id.
        from_date / to_date: ISO 'YYYY-MM-DD'. If None, defaults to last `years`.
        years: lookback if from_date not given (default 5).
    """
    meta = get_security_meta(symbol)
    if meta is None:
        return pd.DataFrame()

    # If auth already failed this process, don't hammer the API for every
    # symbol (and don't stay silent). One loud banner, then fast-fail — but only
    # until the cooldown lets a re-validated probe through (_auth_blocked).
    if _auth_blocked():
        return pd.DataFrame()

    if to_date is None:
        to_date = date.today().isoformat()
    if from_date is None:
        from_date = (date.today() - timedelta(days=365 * years)).isoformat()

    cli = _get_client()

    def _call():
        _throttle_dhan()
        return cli.historical_daily_data(
            security_id=meta["security_id"],
            exchange_segment=meta["exchange_segment"],
            instrument_type=meta["instrument_type"],
            from_date=from_date,
            to_date=to_date,
        )

    try:
        resp = _call()
        # Retry transient failures with backoff before conceding to fallback.
        # Transient = explicit rate-limit (DH-904) OR an empty/non-JSON body
        # (the dhanhq SDK logs "find_error_code: Expecting value: line 1
        # column 1 (char 0)" and returns blank remarks) — under burst load this
        # is almost always a 429/throttle, so it deserves a backoff retry too.
        attempts = 0
        while (attempts < _DHAN_MAX_RETRIES
               and isinstance(resp, dict)
               and resp.get("status") != "success"
               and _is_transient_failure(resp)):
            attempts += 1
            time.sleep(_DHAN_RETRY_SLEEP_S * attempts)  # linear backoff
            resp = _call()
    except Exception as e:
        logger.warning(f"Dhan fetch failed for {symbol}: {e}")
        return pd.DataFrame()

    # Response shape: {'status':'success','data':{'open':[],'high':[],'low':[],'close':[],'volume':[],'timestamp':[]}}
    if not isinstance(resp, dict) or resp.get("status") != "success":
        _note_dhan_failure(symbol, resp)
        return pd.DataFrame()
    data = resp.get("data", {})
    if not data or not data.get("timestamp"):
        return pd.DataFrame()

    df = pd.DataFrame({
        "Open":   data.get("open", []),
        "High":   data.get("high", []),
        "Low":    data.get("low", []),
        "Close":  data.get("close", []),
        "Volume": data.get("volume", []),
    })
    # Timestamps are epoch seconds stamped at IST-midnight of the session date.
    # FIX 8-Jul-2026: reading them as UTC then normalize() shifted every daily
    # bar back ONE calendar day (a Monday session showed as "Sunday"). Convert
    # UTC->IST before normalize so bars carry their true NSE session date.
    df.index = (pd.to_datetime(data["timestamp"], unit="s", utc=True)
                  .tz_convert("Asia/Kolkata").tz_localize(None).normalize())
    df.index.name = "Date"
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    # Dhan's daily endpoint publishes a session's bar the NEXT day, so after
    # today's close the just-completed session is missing. Fill it from the
    # (same-day-available) intraday feed so EOD analysis isn't a session behind.
    # No-op early-return whenever the daily is already current (the common case).
    try:
        df = _append_completed_session_from_intraday(symbol, meta, df)
    except Exception as e:
        logger.debug("intraday session-fill skipped for %s: %s", symbol, e)
    return df


def fetch_weekly(symbol: str, years: int = 5) -> pd.DataFrame:
    """Fetch daily then resample to weekly (W-MON, label=left)."""
    df_d = fetch_daily(symbol, years=years)
    if df_d.empty:
        return df_d
    df_w = df_d.resample("W-MON", closed="left", label="left").agg({
        "Open":  "first", "High": "max", "Low": "min",
        "Close": "last", "Volume": "sum",
    }).dropna(subset=["Close"])
    return df_w


def fetch_ltp(symbols) -> dict:
    """Live last-traded-price for one or many symbols via Dhan's ohlc_data
    (BATCHED — a single API call covers all symbols). Returns
    {CLEAN_SYMBOL_UPPER: ltp_float} for whatever resolved. Never raises; returns
    {} (or partial) on auth/throttle/parse failure so callers fall back to EOD.

    Note: outside market hours Dhan still returns the last traded price
    (= previous close), so callers should gate on market hours if they need a
    truly *live* tick vs EOD.
    """
    if isinstance(symbols, str):
        symbols = [symbols]
    if _auth_blocked():
        return {}
    seg_ids = {}              # exchange_segment -> [security_id int]
    id_to_sym = {}            # (segment, sid) -> clean upper symbol
    for s in symbols:
        meta = get_security_meta(s)
        if not meta:
            continue
        seg = meta["exchange_segment"]
        try:
            sid = int(meta["security_id"])
        except Exception:
            continue
        seg_ids.setdefault(seg, []).append(sid)
        id_to_sym[(seg, sid)] = (str(s).strip().upper()
                                 .replace("NSE:", "").replace("BSE:", "").replace(".NS", ""))
    if not seg_ids:
        return {}

    out = {}
    try:
        cli = _get_client()
        _throttle_dhan()
        resp = cli.ohlc_data(securities=seg_ids)
        if not isinstance(resp, dict) or resp.get("status") != "success":
            _note_dhan_failure("ohlc_data(LTP)", resp)
            return out
        data = ((resp.get("data") or {}).get("data")) or {}
        for seg, by_id in data.items():
            for sid_str, rec in (by_id or {}).items():
                try:
                    lp = (rec or {}).get("last_price")
                    sym = id_to_sym.get((seg, int(sid_str)))
                    if sym and lp is not None and float(lp) > 0:
                        out[sym] = float(lp)
                except Exception:
                    continue
    except Exception as e:
        logger.warning("Dhan fetch_ltp failed: %s", e)
    return out


if __name__ == "__main__":
    # Smoke test
    for sym in ["RELIANCE", "TCS", "GESHIP", "^CRSLDX"]:
        print(f"\n--- {sym} ---")
        df = fetch_daily(sym, years=5)
        if df.empty:
            print(f"  no data")
        else:
            print(f"  {len(df)} bars  {df.index[0].date()} --> {df.index[-1].date()}")
            print(df.tail(3).round(2))
