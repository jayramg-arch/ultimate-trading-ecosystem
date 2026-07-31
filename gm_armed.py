"""ARMED REGISTER — the GM board's memory.

WHY THIS EXISTS (Jay, 31-Jul-2026): "when I set an alert on a stock filtered from
GM today, the alert might [fire] tomorrow. By that time, the new Golden Matcher
Watchlist might have lost it. So, how do I track such stocks?"

The Trigger Board is a SNAPSHOT. It is rebuilt from whatever the FINAL_*.csv
watchlists say today, and those churn nightly. So the sequence that actually
happens is:

    Mon  arm NAME, set the TV alert          <- plan exists only in your head
    Tue  auto-pilot rebuilds the watchlists  <- NAME drops out of every list
    Thu  the alert fires                     <- no row, no entry, no stop, no thesis

Nothing else in the system remembers. The pullback finder and the PA-recency work
both address HOURS; this addresses DAYS.

THE MODEL — the same inherited-qualification doctrine as every other source:
the register QUALIFIES, the board TIMES. An armed name is injected into the
watchlist union carrying the archetypes it had WHEN ARMED, so it keeps its
original path and thesis, plus an "Armed" badge. Every rebuild re-evaluates it
through the unchanged gm_evaluate(), so you see what has changed since — and the
existing break-down guard marks it INVALIDATED if the structure broke.

WHAT IS STORED is the PLAN AS OF ARMING — trigger, entry, stop, target, verdict,
sigma. That is the thing you cannot reconstruct on Thursday, because the levels
were computed from Monday's bar. Live re-evaluation is what the board already
does; the snapshot is what it cannot do.

Pure data layer — no Streamlit, no network. Safe to import headless (run_pipeline,
tests, a scheduled job).
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta

_ROOT = os.path.dirname(os.path.abspath(__file__))
_STORE = os.path.join(_ROOT, "gm_armed.json")

# The badge an armed name carries on the board, ON TOP of its original archetypes.
# Registered in BOTH the bull and recovery archetype sets in gm_trigger_board so it
# can never, on its own, flip a name's path — the path comes from the archetypes the
# name was armed WITH.
ARMED_ARCHETYPE = "Armed"

# How long an alert is allowed to stay pending before the register stops carrying
# the name. A TV alert has no expiry, so without this the register grows forever and
# a 3-month-old plan quietly presents itself as current. 30 sessions ~ 6 weeks.
DEFAULT_EXPIRY_DAYS = 45

STATUS_ARMED = "ARMED"
STATUS_TRIGGERED = "TRIGGERED"
STATUS_CANCELLED = "CANCELLED"
STATUS_EXPIRED = "EXPIRED"
_TERMINAL = {STATUS_TRIGGERED, STATUS_CANCELLED, STATUS_EXPIRED}

try:
    from gm_log import gm_log as _log
except Exception:                                    # pragma: no cover
    import logging as _logging
    _log = _logging.getLogger("gm_armed_null")

try:
    from io_utils import atomic_write_text as _atomic
except Exception:                                    # pragma: no cover
    def _atomic(path, text):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

try:
    from dhan_ohlcv import canonical_nse_symbol as _canonical
except Exception:                                    # pragma: no cover
    _canonical = None


def canon(s) -> str:
    """Symbol -> the ONE key form. Must match gm_trigger_board._canon_key or an
    armed name silently fails to join the board — the [[gm_symbol_ns_normalization]]
    bug class, which has bitten this codebase twice."""
    if _canonical is not None:
        try:
            out = str(_canonical(s) or "").strip().upper()
            if out:
                return out
        except Exception:
            pass
    s = str(s or "").strip().upper()
    for p in ("NSE:", "BSE:"):
        if s.startswith(p):
            s = s[len(p):]
    for suf in (".NS", ".BO"):
        if s.endswith(suf):
            s = s[:-len(suf)]
    return s.strip()


# ── store ────────────────────────────────────────────────────────────────────
def load() -> dict:
    """{SYMBOL: record}. A corrupt store must never take the board down with it —
    it degrades to empty and SAYS SO in the log rather than raising into a rebuild."""
    if not os.path.exists(_STORE):
        return {}
    try:
        with open(_STORE, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception as e:
        _log.warning(f"gm_armed: store unreadable — register treated as empty: {e}")
        return {}


def save(reg: dict) -> None:
    _atomic(_STORE, json.dumps(reg, indent=2, sort_keys=True, default=str))


# ── arming ───────────────────────────────────────────────────────────────────
def arm(symbol, *, path="bull", archetypes=None, verdict="", category="",
        trigger=None, entry=None, sl=None, t1=None, rr=None, sigma_pa=None,
        s4go="", cmp_px=None, tf="", note="", expiry_days=DEFAULT_EXPIRY_DAYS,
        today=None) -> dict:
    """Record a name as armed, with the plan AS OF NOW. Re-arming an existing
    symbol REPLACES the snapshot (you re-read the chart, you get new levels) but
    preserves `first_armed` so the age reflects how long you have actually been
    waiting — not how recently you refreshed it."""
    s = canon(symbol)
    if not s:
        raise ValueError("arm() needs a symbol")
    reg = load()
    prev = reg.get(s) or {}
    d0 = today or date.today()
    reg[s] = {
        "symbol": s,
        "first_armed": prev.get("first_armed") or d0.isoformat(),
        "armed_on": d0.isoformat(),
        "armed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "expires_on": (d0 + timedelta(days=int(expiry_days))).isoformat(),
        "status": STATUS_ARMED,
        "path": "recovery" if str(path).lower() == "recovery" else "bull",
        "archetypes": list(archetypes or []),
        # The plan as armed — the part that cannot be reconstructed later.
        "verdict": str(verdict or ""),
        "category": str(category or ""),
        "trigger": _num(trigger),
        "entry": _num(entry),
        "sl": _num(sl),
        "t1": _num(t1),
        "rr": _num(rr),
        "sigma_pa": _num(sigma_pa),
        "s4go": str(s4go or ""),
        "cmp_at_arm": _num(cmp_px),
        "tf": str(tf or ""),
        "note": str(note or ""),
        "rearmed": bool(prev),
    }
    save(reg)
    return reg[s]


def mark(symbol, status, note="") -> bool:
    s = canon(symbol)
    reg = load()
    if s not in reg:
        return False
    reg[s]["status"] = status
    reg[s]["closed_on"] = date.today().isoformat()
    if note:
        reg[s]["note"] = note
    save(reg)
    return True


def disarm(symbol, note="") -> bool:
    """Explicitly stop watching. Kept as a CANCELLED record rather than deleted —
    'I armed this and dropped it' is information, and a silent delete would make
    the register unable to answer why a name stopped appearing."""
    return mark(symbol, STATUS_CANCELLED, note)


def triggered(symbol, note="") -> bool:
    return mark(symbol, STATUS_TRIGGERED, note)


def purge(symbol) -> bool:
    """Hard-remove a record. For fixing a mistaken entry, not for normal flow."""
    s = canon(symbol)
    reg = load()
    if s not in reg:
        return False
    del reg[s]
    save(reg)
    return True


# ── reading ──────────────────────────────────────────────────────────────────
def expire_stale(today=None) -> list:
    """Flip past-expiry ARMED records to EXPIRED. Returns the symbols expired.
    Called on every read so the register self-maintains — an expiry that only ran
    on a button press would be an expiry that never ran."""
    d0 = today or date.today()
    reg = load()
    hit = []
    for s, r in reg.items():
        if r.get("status") != STATUS_ARMED:
            continue
        try:
            if date.fromisoformat(str(r.get("expires_on"))) < d0:
                r["status"] = STATUS_EXPIRED
                r["closed_on"] = d0.isoformat()
                hit.append(s)
        except Exception:
            continue                       # unparseable date: leave it armed, visibly
    if hit:
        save(reg)
        _log.info(f"gm_armed: expired {len(hit)} stale record(s): {', '.join(hit)}")
    return hit


def active(today=None) -> dict:
    """{SYMBOL: record} for names still being watched. Expires first."""
    expire_stale(today)
    return {s: r for s, r in load().items() if r.get("status") == STATUS_ARMED}


def get(symbol) -> dict:
    return load().get(canon(symbol)) or {}


def is_armed(symbol) -> bool:
    return (get(symbol).get("status") or "") == STATUS_ARMED


def days_armed(rec, today=None) -> int | None:
    """Calendar days since FIRST armed — the number that answers 'how long have I
    been waiting on this'."""
    try:
        return ((today or date.today()) - date.fromisoformat(
            str(rec.get("first_armed") or rec.get("armed_on")))).days
    except Exception:
        return None


def summary_line(rec, today=None) -> str:
    """Compact board-cell text: age + the trigger level as armed."""
    d = days_armed(rec, today)
    bits = [f"{d}d" if d is not None else "?"]
    if rec.get("trigger"):
        bits.append(f"trg {rec['trigger']:,.2f}")
    elif rec.get("entry"):
        bits.append(f"ent {rec['entry']:,.2f}")
    if rec.get("rearmed"):
        bits.append("re")
    return " · ".join(bits)


def _num(v):
    try:
        if v is None or v == "":
            return None
        f = float(v)
        return None if f != f else round(f, 2)
    except Exception:
        return None
