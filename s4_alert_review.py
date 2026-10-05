# -*- coding: utf-8 -*-
"""
s4_alert_review.py — alert-triggered AI review (13-Sep-2026, Jay: "when the alerts are
triggered, can it trigger the AI analysis on those stocks/ETFs only?").

Flow:  TradingView "S4 GO" alert  →  webhook (dhan_tv_webhook.py /s4-review, one ngrok
tunnel on :8000)  →  enqueue(symbol, tf)  →  ONE worker thread runs s4_review on the
two chart tabs, in order  →  Telegram: RULING · DECIDING FACTOR · PLAN · R-CHECK /
OI-CHECK, with the full review saved under logs/ai_reviews/ as usual.

Why a queue with one worker: a review takes the two chart tabs over for ~60 s. Five
alerts at a 75m close would otherwise fight for the charts; queued they arrive over
~5 min, which is fine — the alert marks a BAR, and the bar does not change.

Dedup: the same symbol+TF within DEDUP_MIN minutes is ignored (a 75m and a 125m alert
on one name are two reviews, by design — different bars). The chart is switched BACK to
whatever it showed before the review (S4_ALERT_RESTORE_CHART=0 to leave it).

The alert message S4 emits already starts "{{ticker}} S4 GO {{interval}} - …", which
is all parse() needs; a JSON body {"ticker": …, "interval": …} is accepted too.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import queue
import re
import threading
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "logs", "s4_alert_review.log")
DEDUP_MIN = int(os.getenv("S4_ALERT_DEDUP_MIN", "30"))
RESTORE = os.getenv("S4_ALERT_RESTORE_CHART", "1") != "0"


def _restore_wanted(sr) -> bool:
    """Put the chart back after a review? Not when the reviewer drives its OWN tabs
    (S4_REVIEW_CHARTS - the S4 Reviewer / S5 Reviewer layouts, 2-Oct-2026, Jay): no
    one is looking at those, so restoring only costs a chart switch and a settle wait
    per alert, and was the step that failed and left a chart parked. An explicit
    S4_ALERT_RESTORE_CHART=1 still forces it; =0 still turns it off everywhere."""
    if os.getenv("S4_ALERT_RESTORE_CHART") == "1":
        return True
    return RESTORE and not getattr(sr, "REVIEW_CHARTS", None)
# 21-Sep-2026: one retry on a settle timeout. The three failures on 21 Sep were all the
# first review after a bar close, when TV is still recalculating; a second attempt a
# minute later is what the queue's later items effectively got, and they all passed.
RETRY_ON_TVERROR = os.getenv("S4_ALERT_RETRY", "1") != "0"
STATUS = os.path.join(HERE, "logs", "reviewer_status.json")   # read by reviewer_banner.py

_q: "queue.Queue[tuple[str, str, str]]" = queue.Queue()
_seen: dict[tuple[str, str], float] = {}
_lock = threading.Lock()
_worker: threading.Thread | None = None

_TF = {"75": "75", "125": "125", "D": "D", "1D": "D", "W": "W", "1W": "W", "60": "60", "30": "30", "15": "15"}
_RE = re.compile(r"^\s*(?:NSE:|BSE:)?([A-Z0-9&_\-]+)\s+S4\s+GO\s+(\d+|[DW]|1[DW])\b", re.I)


def _log(msg: str) -> None:
    line = "%s  %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print("[s4-alert] " + msg, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def parse(body: bytes | str) -> tuple[str, str] | None:
    """(symbol, tf) from a TradingView alert body — the S4 GO text or a JSON object."""
    txt = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)
    txt = txt.strip()
    if txt.startswith("{"):
        try:
            d = json.loads(txt)
            sym = str(d.get("ticker") or d.get("symbol") or "").replace("NSE:", "").replace("BSE:", "").strip().upper()
            tf = str(d.get("interval") or d.get("tf") or "").strip().upper()
            if sym and tf:
                return sym, _TF.get(tf, tf)
        except Exception:
            pass
        # a JSON wrapper around the plain message (TV does this when the body is JSON-ish)
        for k in ("message", "text", "alert"):
            try:
                inner = json.loads(txt).get(k)
                if inner:
                    return parse(inner)
            except Exception:
                pass
        return None
    m = _RE.match(txt)
    if not m:
        return None
    sym, tf = m.group(1).upper(), m.group(2).upper()
    return sym, _TF.get(tf, tf)


def summary(review: str, symbol: str, tf: str) -> str:
    """The Telegram-sized cut: ruling, deciding factor, plan, the script's checks."""
    def grab(tag: str, n: int = 6) -> str:
        m = re.search(r"\*{0,2}%s:?\*{0,2}:?\s*(.*?)(?=\n\s*\n|\n\*{0,2}(?:DECIDING|PLAN|FLIPS|R-CHECK|OI-CHECK|OPTIONS)|\Z)" % tag,
                      review, re.S | re.I)
        if not m:
            return ""
        lines = [l.strip(" *") for l in m.group(1).strip().splitlines() if l.strip()]
        return "\n".join(lines[:n])
    parts = ["🔔 S4 GO · %s · %s" % (symbol, tf)]
    r = grab("RULING", 1)
    if r:
        parts.append("RULING: " + r)
    d = grab("DECIDING FACTOR", 2)
    if d:
        parts.append("WHY: " + d)
    p = grab("PLAN", 8)
    if p:
        parts.append("PLAN:\n" + p)
    f = grab("FLIPS IF", 2)
    if f:
        parts.append("FLIPS IF: " + f)
    for tag in ("R-CHECK", "OI-CHECK"):
        m = re.search(r"^(%s[^\n]*(?:\n  [^\n]*)*)" % tag, review, re.M)
        if m:
            parts.append(m.group(1))
    return "\n\n".join(parts)


def _chart_state():
    try:
        import s4_review as sr
        for st in sr._tv_all(sr.READY_JS):
            if isinstance(st, str):          # READY_JS returns a JSON string, not an object
                st = json.loads(st)
            if st and st.get("symbol"):
                return st.get("symbol"), st.get("res")
    except Exception:
        pass
    return None, None


def _status(state: str, symbol: str = "", tf: str = "", started: float | None = None,
            last: str = "") -> None:
    """The banner's source of truth: busy / restoring / idle, written at each transition.
    Best-effort — the review never fails because the banner could not be told."""
    try:
        d = {"state": state, "symbol": symbol, "tf": tf, "started": started,
             "pending": _q.qsize(), "last": last, "ts": time.time()}
        tmp = STATUS + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, STATUS)
    except Exception:
        pass


def _review_with_retry(sr, symbol: str, tf: str, source: str = "s4-alert") -> dict:
    try:
        return sr.review_symbol(symbol, tf, source=source)
    except sr.TVError as e:
        if not RETRY_ON_TVERROR or "settle" not in str(e):
            raise
        _log("%s %s settle timeout — retrying once in 20s" % (symbol, tf))
        time.sleep(20)
        return sr.review_symbol(symbol, tf, source=source)


def _err_tail(buf: io.StringIO, n: int = 3) -> str:
    """The last few non-empty stderr lines, flattened onto one log line.

    23-Sep-2026. A failed review logged `review rc 1` and nothing else, so
    BAJAJ_AUTO 125 (13:25 alert) could not be diagnosed afterwards at all: no .md,
    no Reviewer Log row, no reason. The reason DID exist — review_one prints it to
    stderr ("S4 is not on this chart (tables found: …)") — but stderr goes to the
    receiver's console window, which nobody is watching and which does not persist.
    """
    lines = [ln.strip() for ln in buf.getvalue().splitlines() if ln.strip()]
    return " | ".join(lines[-n:])[:400]


def _src_label(source: str) -> str:
    """Receiver queue source -> the Reviewer Log's trigger label."""
    s = str(source or "").lower()
    if "manual" in s:
        return "manual"
    if "board" in s:
        return "board"
    return "s4-alert" if ("webhook" in s or "alert" in s) else (s or "s4-alert")


def _run(symbol: str, tf: str, source: str) -> None:
    import s4_review as sr
    t0 = time.time()
    _status("busy", symbol, tf, t0)
    last = "%s %sm · failed" % (symbol, tf)
    _restore = _restore_wanted(sr)
    prev_sym, prev_res = _chart_state() if _restore else (None, None)
    err = io.StringIO()
    try:
        # stderr is captured for the duration of the review ONLY so a failure can say
        # why (see _err_tail). _log prints to stdout, so the running commentary is
        # unaffected, and on success the buffer is simply dropped.
        with contextlib.redirect_stderr(err):
            res = _review_with_retry(sr, symbol, tf, _src_label(source))
        rc, review, path = res["rc"], res["review"], res["path"]
        if rc == 0 and review:
            msg = summary(review, symbol, tf)
            sent = sr.telegram(msg + "\n\nfull: %s" % os.path.relpath(path, HERE).replace("\\", "/"))
            _log("%s %s reviewed in %ds → %s (telegram %s)" % (symbol, tf, time.time() - t0,
                 os.path.basename(path), "sent" if sent else "not configured"))
            last = "%s %sm · %ds" % (symbol, tf, time.time() - t0)
        else:
            why = _err_tail(err)
            sr.telegram("🔔 S4 GO · %s · %s — review FAILED (rc %s)%s" %
                        (symbol, tf, rc, ("\n" + why) if why else "; see logs/s4_alert_review.log"))
            _log("%s %s review rc %s · %s" % (symbol, tf, rc, why or "nothing on stderr"))
    except Exception as e:
        why = _err_tail(err)
        _log("%s %s FAILED: %s: %s%s" % (symbol, tf, type(e).__name__, e, (" · " + why) if why else ""))
        try:
            sr.telegram("🔔 S4 GO · %s · %s — review FAILED: %s" % (symbol, tf, e))
        except Exception:
            pass
    finally:
        try:
            import build_review_portal
            build_review_portal.build()          # the Reviewer Log page, always current
        except Exception as e:
            _log("portal rebuild failed: %s" % e)
        if _restore and prev_sym and prev_sym.upper() != ("NSE:" + symbol).upper():
            _status("restoring", symbol, tf, t0, last)
            try:
                sr.switch_chart(prev_sym.replace("NSE:", ""), prev_res)
                _log("chart restored to %s %s" % (prev_sym, prev_res))
            except Exception as e:
                _log("chart restore failed: %s" % e)
        _status("idle", last=last)


def _loop() -> None:
    while True:
        symbol, tf, source = _q.get()
        try:
            _run(symbol, tf, source)
        finally:
            _q.task_done()


def _daily_wait_s(tf: str, source: str) -> float:
    """Seconds to hold a DAILY alert that arrived before the close (5-Oct-2026). ANANDRATHI's
    1D alert came in at 15:15:59 and the panel read a minute later said "waiting on: no PA
    pattern" - the alert had fired on an unfinished Daily bar (1-Oct also had 75m/125m
    pings at 15:15, which is no bar's close). The Daily plan is decided on the closed bar,
    so the review runs at 15:31 IST on it. 0 = review now."""
    if str(tf).upper() not in ("D", "1D") or source != "tv-webhook":
        return 0.0
    from datetime import timedelta, timezone
    now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    close = now.replace(hour=15, minute=31, second=0, microsecond=0)
    if now.weekday() >= 5 or now.hour < 9 or now >= close:
        return 0.0
    return (close - now).total_seconds()


def enqueue(symbol: str, tf: str, source: str = "webhook", body: str = "") -> dict:
    """Queue a review. Returns {"queued": bool, "reason": str, "pending": n}."""
    global _worker
    key = (symbol.upper(), str(tf).upper())
    now = time.time()
    with _lock:
        last = _seen.get(key)
        if last and now - last < DEDUP_MIN * 60:
            _log("dedup %s %s (%.0f min ago)" % (key[0], key[1], (now - last) / 60))
            return {"queued": False, "reason": "duplicate within %d min" % DEDUP_MIN, "pending": _q.qsize()}
        _seen[key] = now
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_loop, name="s4-alert-review", daemon=True)
            _worker.start()
    if body:      # the alert's own text: bar time + close tell WHICH bar it fired on
        _log("alert body %s %s: %s" % (key[0], key[1], " ".join(str(body)[:160].split())))
    wait = _daily_wait_s(key[1], source)
    if wait > 0:
        threading.Timer(wait, lambda: _q.put((key[0], key[1], source))).start()
        _log("deferred %s %s from %s - Daily alert before the close, reviewing at 15:31 on the closed bar (in %.0f s)"
             % (key[0], key[1], source, wait))
        return {"queued": True, "reason": "deferred to 15:31 (Daily alert before the close)", "pending": _q.qsize()}
    _q.put((key[0], key[1], source))
    _log("queued %s %s from %s (pending %d)" % (key[0], key[1], source, _q.qsize()))
    return {"queued": True, "reason": "ok", "pending": _q.qsize()}


if __name__ == "__main__":
    # smoke: parse a few bodies, then (optionally) review one name end-to-end
    import sys
    for b in ("PNBHOUSING S4 GO 75 - bar 1757756400000 - close 1178.9 - loc-src 3",
              '{"ticker":"NSE:SAILIFE","interval":"125"}', "garbage"):
        print(repr(b[:40]), "->", parse(b))
    if len(sys.argv) > 1:
        s, t = sys.argv[1].upper(), (sys.argv[2] if len(sys.argv) > 2 else "75")
        print(enqueue(s, t, "cli")); _q.join()
