"""nse_calendar.py - NSE trading days: weekends AND exchange holidays.

2-Oct-2026 (Jay). Every "is the market open / which session closed last" check in the
app treated any weekday as a trading day, so on Gandhi Jayanti the board warned
"Live market - snapshot is 1177 min old". Source of truth: NSE's own holiday master
(the API behind nseindia.com/resources/exchange-communication-holidays), segment CM.

    python nse_calendar.py            print this year's holidays and the source
    python nse_calendar.py --refresh  re-read NSE and rewrite data/nse_holidays.json

Lookups never touch the network on the hot path: they read data/nse_holidays.json,
and only when that file has no entry for the current year do they try NSE once per
process (short timeout). If NSE cannot be reached the built-in list below is used,
so a failure degrades to "weekday = trading day" only for years not listed here.
Muhurat trading (a special evening session on a Diwali Sunday) is not modelled.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "nse_holidays.json")
API = "https://www.nseindia.com/api/holiday-master?type=trading"
PAGE = "https://www.nseindia.com/resources/exchange-communication-holidays"

# NSE CM trading holidays 2026, read from the holiday master on 2-Oct-2026.
_BUILTIN = {
    "2026": ["2026-01-15", "2026-01-26", "2026-02-15", "2026-03-03", "2026-03-21",
             "2026-03-26", "2026-03-31", "2026-04-03", "2026-04-14", "2026-05-01",
             "2026-05-28", "2026-06-26", "2026-08-15", "2026-09-14", "2026-10-02",
             "2026-10-20", "2026-11-08", "2026-11-10", "2026-11-24", "2026-12-25"],
}

_HOL: set | None = None
_TRIED_FETCH = False

SESSION_OPEN = (9, 15)
SESSION_CLOSE = (15, 30)


def fetch(timeout: float = 15.0) -> dict:
    """{year: [iso dates]} from NSE's holiday master (CM segment). Raises on failure."""
    import nse_options as no                      # the cookie dance already lives there
    s = no._get_session()
    r = s.get(API, headers={"Referer": PAGE}, timeout=timeout)
    r.raise_for_status()
    out: dict = {}
    for x in (r.json() or {}).get("CM") or []:
        d = dt.datetime.strptime(x["tradingDate"], "%d-%b-%Y").date()
        out.setdefault(str(d.year), []).append(d.isoformat())
    if not out:
        raise ValueError("holiday master returned no CM dates")
    return {y: sorted(v) for y, v in out.items()}


def refresh() -> dict:
    data = fetch()
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    payload = {"source": API, "fetched": dt.datetime.now().isoformat(timespec="seconds"), "years": data}
    try:
        from io_utils import atomic_write_text
        atomic_write_text(CACHE, json.dumps(payload, indent=2))
    except Exception:
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    global _HOL
    _HOL = None
    return data


def _load() -> set:
    global _HOL, _TRIED_FETCH
    if _HOL is not None:
        return _HOL
    years = dict(_BUILTIN)
    try:
        with open(CACHE, encoding="utf-8") as f:
            years.update((json.load(f) or {}).get("years") or {})
    except Exception:
        pass
    this_year = str(dt.date.today().year)
    if this_year not in years and not _TRIED_FETCH:
        _TRIED_FETCH = True
        try:
            years.update(refresh())
        except Exception:
            pass
    _HOL = {d for v in years.values() for d in v}
    return _HOL


def is_holiday(d: dt.date) -> bool:
    return d.isoformat() in _load()


def is_trading_day(d: dt.date) -> bool:
    return d.weekday() < 5 and not is_holiday(d)


def prev_trading_day(d: dt.date) -> dt.date:
    """The last trading day strictly before d."""
    d = d - dt.timedelta(days=1)
    while not is_trading_day(d):
        d -= dt.timedelta(days=1)
    return d


def last_completed_session(now: dt.datetime | None = None) -> dt.date:
    """Most recently COMPLETED session: today once the 15:30 close has passed on a
    trading day, otherwise the previous trading day."""
    now = now or dt.datetime.now()
    d = now.date()
    if is_trading_day(d) and (now.hour, now.minute) >= SESSION_CLOSE:
        return d
    return prev_trading_day(d)


def is_session_open(now: dt.datetime | None = None) -> bool:
    """True between 09:15 and 15:30 IST on a trading day."""
    now = now or dt.datetime.now()
    return is_trading_day(now.date()) and SESSION_OPEN <= (now.hour, now.minute) <= SESSION_CLOSE


if __name__ == "__main__":
    if "--refresh" in sys.argv:
        print({y: len(v) for y, v in refresh().items()}, "->", CACHE)
    y = str(dt.date.today().year)
    hol = sorted(d for d in _load() if d.startswith(y))
    print(f"{y}: {len(hol)} NSE holidays")
    for d in hol:
        print(" ", d, dt.date.fromisoformat(d).strftime("%a"))
