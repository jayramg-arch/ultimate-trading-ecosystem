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


def _run(symbol: str, tf: str, source: str) -> None:
    import s4_review as sr
    t0 = time.time()
    prev_sym, prev_res = _chart_state() if RESTORE else (None, None)
    try:
        res = sr.review_symbol(symbol, tf)
        rc, review, path = res["rc"], res["review"], res["path"]
        if rc == 0 and review:
            msg = summary(review, symbol, tf)
            sent = sr.telegram(msg + "\n\nfull: %s" % os.path.relpath(path, HERE).replace("\\", "/"))
            _log("%s %s reviewed in %ds → %s (telegram %s)" % (symbol, tf, time.time() - t0,
                 os.path.basename(path), "sent" if sent else "not configured"))
        else:
            sr.telegram("🔔 S4 GO · %s · %s — review FAILED (rc %s); see logs/s4_alert_review.log" % (symbol, tf, rc))
            _log("%s %s review rc %s" % (symbol, tf, rc))
    except Exception as e:
        _log("%s %s FAILED: %s: %s" % (symbol, tf, type(e).__name__, e))
        try:
            sr.telegram("🔔 S4 GO · %s · %s — review FAILED: %s" % (symbol, tf, e))
        except Exception:
            pass
    finally:
        if RESTORE and prev_sym and prev_sym.upper() != ("NSE:" + symbol).upper():
            try:
                sr.switch_chart(prev_sym.replace("NSE:", ""), prev_res)
                _log("chart restored to %s %s" % (prev_sym, prev_res))
            except Exception as e:
                _log("chart restore failed: %s" % e)


def _loop() -> None:
    while True:
        symbol, tf, source = _q.get()
        try:
            _run(symbol, tf, source)
        finally:
            _q.task_done()


def enqueue(symbol: str, tf: str, source: str = "webhook") -> dict:
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
