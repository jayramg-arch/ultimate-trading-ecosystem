#!/usr/bin/env python3
"""tv_fire_backstop.py - recover TradingView alerts whose webhook never reached us (22-Oct-2026).

WHY: at bar closes (10:30, 15:15, 15:30 ...) TradingView fires alerts for all its users at
once. The webhook then travels TradingView -> ngrok -> this PC, and that path is slow exactly
then: on 22 Oct AUBANK fired at 10:30:01 and reached the PC at 10:30:26, after TradingView had
given up ("request took too long and timed out"); ALPHA never arrived at all. Our handler
answers in 2-14 ms - the loss is in the delivery path, which we do not control.

THE BACKSTOP: TradingView Desktop runs on this PC, and TradingView's own alerts client has
`listFires` - every fire, with its message and the webhook outcome
(`"webhook": {"error": "request took too long and timed out"}`). Read over the local debug
port (no internet path involved), every fire whose webhook FAILED is put through the same
path a delivered webhook takes:
  - an S4 GO fire  -> s4_alert_review.enqueue (same parser, same 30-min dedup, same Daily
                      hold-to-15:31 rule) -> review -> Telegram + Reviewer Log
  - a GM-THESIS fire -> logs/thesis_alerts.log + the Telegram the /thesis-alert route sends
Delivered fires are skipped, so nothing is reviewed twice. Each fire id is handled once
(logs/fires_seen.json). Runs as a thread inside the receiver (dhan_tv_webhook.py) every
POLL_S seconds in market hours; on start it looks back over the whole day, which also
recovers alerts that fired while the receiver was down. FIRE_BACKSTOP=0 turns it off.

    python tv_fire_backstop.py            one pass now, print what it found (no thread)
    python tv_fire_backstop.py --dry-run  same, but enqueue / send nothing
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SEEN = os.path.join(HERE, "logs", "fires_seen.json")
POLL_S = int(os.getenv("FIRE_BACKSTOP_POLL_S", "60"))
IST = timezone(timedelta(hours=5, minutes=30))
THESIS_PREFIX = "GM-THESIS "
WAIT_FOR_OUTCOME_S = 180        # a fire with no webhook outcome yet: TradingView may still be trying

JS = r"""
(async () => {
  try {
    if (!window.__tvAlertsApi) {
      const W = window.webpackChunktradingview;
      if (!W) return JSON.stringify({err: "TradingView module loader not found"});
      if (!window.__tvReq) W.push([["fires" + Date.now()], {}, r => { window.__tvReq = r; }]);
      let modId = null;
      for (const c of W) { const m = c[1] || {}; for (const k in m) { let s; try { s = m[k].toString(); } catch (e) { continue; }
        if (s.indexOf('"Alerts.AlertsRestApi"') >= 0 && s.indexOf("getAlertsRestApi") >= 0) { modId = k; break; } } if (modId) break; }
      if (!modId || !window.__tvReq) return JSON.stringify({err: "TradingView alerts client not found"});
      window.__tvAlertsApi = window.__tvReq(modId).getAlertsRestApi();
    }
    const r = await window.__tvAlertsApi.listFires({limit: __LIMIT__});
    return JSON.stringify({fires: (r || []).map(f => ({id: f.fire_id, alert_id: f.alert_id, name: f.name,
      symbol: f.symbol, resolution: f.resolution, message: f.message, fire_time: f.fire_time,
      bar_time: f.bar_time, webhook: f.webhook}))});
  } catch (e) { return JSON.stringify({err: String((e && (e.code || e.message)) || e)}); }
})()
"""


def _log(msg: str) -> None:
    try:
        import s4_alert_review
        s4_alert_review._log("backstop: " + msg)
    except Exception:
        print("[backstop] " + msg, flush=True)


def _load_seen() -> dict:
    try:
        return json.load(open(SEEN, encoding="utf-8"))
    except Exception:
        return {}


def _save_seen(seen: dict) -> None:
    keep = dict(sorted(seen.items(), key=lambda kv: kv[1])[-800:])       # newest 800 ids
    os.makedirs(os.path.dirname(SEEN), exist_ok=True)
    tmp = SEEN + ".tmp"
    json.dump(keep, open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, SEEN)


def fetch_fires(limit: int = 60) -> list:
    """The latest fires from TradingView's own log, over the local debug port."""
    import tv_bind_s4
    import tv_gm_alerts
    targets = tv_bind_s4._chart_targets_all()
    if not targets:
        raise RuntimeError("no TradingView chart tab over the debug port")
    raw = tv_gm_alerts._eval(targets[0]["webSocketDebuggerUrl"], JS.replace("__LIMIT__", str(int(limit))))
    res = json.loads(raw) if raw else {"err": "no result"}
    if res.get("err"):
        raise RuntimeError(res["err"])
    return res.get("fires") or []


def _age_s(fire_time: str) -> float:
    try:
        t = datetime.fromisoformat(str(fire_time).replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - t).total_seconds()
    except Exception:
        return 1e9


def classify(f: dict) -> tuple[str, str]:
    """('s4', '') | ('thesis', '') | ('other', why). Pure, for tests."""
    name = str(f.get("name") or "")
    if name.startswith(THESIS_PREFIX):
        return "thesis", ""
    try:
        import s4_alert_review
        if s4_alert_review.parse(str(f.get("message") or "")):
            return "s4", ""
    except Exception as e:
        return "other", "parser unavailable (%s)" % e
    return "other", "not an S4 GO or thesis alert"


def outcome(f: dict) -> str:
    """'failed' | 'delivered' | 'pending'. Pure, for tests."""
    wh = f.get("webhook")
    if isinstance(wh, dict) and wh.get("error"):
        return "failed"
    if isinstance(wh, dict):
        return "delivered"
    return "pending" if _age_s(f.get("fire_time")) < WAIT_FOR_OUTCOME_S else "delivered"


def too_late(tf: str, age_s: float) -> bool:
    """An intraday fire older than one bar of its own timeframe is too late to review: the
    panel would read a later bar. Daily fires stay reviewable through the day (they are read
    on the closed Daily bar anyway). Pure, for tests."""
    t = str(tf).upper()
    if t in ("D", "1D", "W", "1W", "M", "1M"):
        return age_s > 20 * 3600
    try:
        mins = int(t)
    except ValueError:
        return age_s > 3600
    return age_s > mins * 60


def _ist(fire_time: str) -> str:
    try:
        return datetime.fromisoformat(str(fire_time).replace("Z", "+00:00")).astimezone(IST).strftime("%d-%b %H:%M")
    except Exception:
        return str(fire_time)


def _thesis_logged_today(sym: str) -> bool:
    """True when /thesis-alert already logged this symbol today (a 'failed' webhook can still
    arrive late and be forwarded - do not send the same Telegram twice)."""
    sym = sym.strip().upper()
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        for ln in open(os.path.join(HERE, "logs", "thesis_alerts.log"), encoding="utf-8", errors="replace"):
            if ln.startswith(today) and sym and sym in ln.upper():
                return True
    except Exception:
        pass
    return False


def _source_of(message: str) -> str:
    m = str(message or "")
    return ("manual" if "- manual" in m else "board" if "- board" in m else "v2" if "- v2" in m else "tv-webhook-recovered")


def run_once(lookback_h: float = 1.0, dry: bool = False) -> dict:
    """One pass. Returns counts. lookback_h bounds how old a fire may be to be recovered."""
    out = {"read": 0, "recovered": 0, "missed": 0, "thesis": 0, "delivered": 0, "pending": 0, "skipped": 0}
    fires = fetch_fires()
    out["read"] = len(fires)
    seen = _load_seen()
    changed = False
    for f in fires:
        fid = str(f.get("id"))
        if not fid or fid in seen or _age_s(f.get("fire_time")) > lookback_h * 3600:
            continue
        kind, _why = classify(f)
        if kind == "other":
            seen[fid] = time.time(); changed = True; out["skipped"] += 1
            continue
        oc = outcome(f)
        if oc == "pending":
            out["pending"] += 1
            continue
        seen[fid] = time.time(); changed = True
        if oc == "delivered":
            out["delivered"] += 1
            continue
        msg = str(f.get("message") or "")
        err = str((f.get("webhook") or {}).get("error") or "")
        if kind == "thesis":
            if _thesis_logged_today(str(f.get("name"))[len(THESIS_PREFIX):]):
                out["delivered"] += 1          # the late request did arrive and was forwarded
                continue
            out["thesis"] += 1
            _log("recovered thesis alert %s (webhook: %s)" % (f.get("name"), err))
            if not dry:
                try:
                    with open(os.path.join(HERE, "logs", "thesis_alerts.log"), "a", encoding="utf-8") as fh:
                        fh.write("%s %s [recovered from the TradingView log]\n"
                                 % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg.replace("\n", " ")[:900]))
                    import s4_review
                    s4_review.telegram("🟠 THESIS BROKEN · " + msg[:900] + "\n(recovered - the webhook failed: " + err + ")")
                except Exception as e:
                    _log("thesis forward failed: %s" % e)
            continue
        import s4_alert_review
        sym, tf = s4_alert_review.parse(msg)
        if too_late(tf, _age_s(f.get("fire_time"))):
            # a review now would read a later bar than the one that fired - say so instead
            out["missed"] += 1
            _log("missed %s %s fired %s, too late to review (webhook: %s)" % (sym, tf, f.get("fire_time"), err))
            if not dry:
                try:
                    import s4_review
                    s4_review.telegram("⚠️ MISSED S4 GO · %s %s fired %s IST - the webhook failed (%s). "
                                       "Not reviewed: the bar has moved on. Run REVIEW %s %s for a fresh read."
                                       % (sym, tf, _ist(f.get("fire_time")), err, sym, tf))
                except Exception as e:
                    _log("missed-alert notice failed: %s" % e)
            continue
        out["recovered"] += 1
        _log("recovered %s %s fired %s (webhook: %s)" % (sym, tf, f.get("fire_time"), err))
        if not dry:
            s4_alert_review.enqueue(sym, tf, source=_source_of(msg), body=msg)
    if changed and not dry:
        _save_seen(seen)
    return out


def _in_window(now: datetime) -> bool:
    if now.weekday() >= 5:
        return False
    m = now.hour * 60 + now.minute
    return 9 * 60 + 14 <= m <= 15 * 60 + 50


def _loop() -> None:
    first = True
    while True:
        try:
            now = datetime.now(IST)
            if first or _in_window(now):
                # first pass looks back over the day: recovers fires missed while we were down
                r = run_once(lookback_h=(12.0 if first else 1.0))
                if r["recovered"] or r["thesis"] or r["missed"]:
                    _log("pass: %s" % r)
            first = False
        except Exception as e:
            _log("pass failed: %s" % str(e)[:200])
            first = False
        time.sleep(POLL_S)


def start() -> threading.Thread | None:
    if os.getenv("FIRE_BACKSTOP", "1") == "0":
        print("[backstop] off (FIRE_BACKSTOP=0)", flush=True)
        return None
    t = threading.Thread(target=_loop, name="tv-fire-backstop", daemon=True)
    t.start()
    print("[backstop] on - TradingView's fire log is read every %d s in market hours" % POLL_S, flush=True)
    return t


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    dry = "--dry-run" in sys.argv
    fires = fetch_fires()
    for f in fires[:20]:
        k, _ = classify(f)
        print("%s  %-10s %-6s %-9s %s" % (f.get("fire_time"), str(f.get("symbol"))[12:40], f.get("resolution"),
                                          k, outcome(f) if k != "other" else ""))
    print(run_once(lookback_h=12.0, dry=dry))
