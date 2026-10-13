"""Close-below-THESIS alerts for open holdings, refreshed nightly (12-Oct-2026, Jay).

THE TWO-TIER STOP. Measured on Jay's exits: of 8 stop-outs that matched the journal stop,
3 were wick sweeps (the day closed back >= 0.5 ATR above the fill) and half of the sweeps
filled at 09:15-09:18. So a trade carries two levels:
  THESIS SL   (journal thesis_sl) - exited only on a CLOSE below it, on the trade's own
              clock: the Daily close for every trade (13-Oct-2026, Jay: risk/trade
              management is limited to the Daily timeframe).
  DISASTER SL (the resting Dhan stop) - further away, for gaps and real collapses.
A resting order cannot wait for a close, so the thesis needs an ALERT. This sets one
TradingView price alert per holding: "crossing down <thesis>, once per bar close", on the
trade's clock, with a webhook to the receiver's /thesis-alert, which Telegrams it. It never
sells - the exit is Jay's order.

WHO GETS ONE: open holdings whose thesis sits ABOVE their Dhan stop. A thesis at or below
the Dhan stop (all 18 holdings on 12-Oct, migrated as thesis = stop) is single-tier -
the resting order fires first - so it is skipped and listed. New trades carry a real
thesis from S4's INVAL (s4_take) or Risk Shield.

Same route as tv_zone_alerts.py: TradingView's alerts client inside the logged-in page,
cloning the permanent 'GM-POS zone SEED' price alert (createAlert is refused from the
page). Only alerts whose name starts with PREFIX are ever deleted.

    python tv_thesis_alerts.py --dry-run    list what would be set
    python tv_thesis_alerts.py              replace yesterday's set
    python tv_thesis_alerts.py --selftest   create ONE far-away test alert, read it back, delete it
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PREFIX = "GM-THESIS "
SEED = "GM-POS zone SEED"        # shared with tv_zone_alerts.py, which keeps it alive
EXPIRY_DAYS = 7
LOG = os.path.join(HERE, "logs", "tv_thesis_alerts.log")


def _log(msg: str) -> None:
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))


def _tv_symbol(sym: str) -> str:
    return "NSE:" + sym.strip().upper().replace("-", "_")


def _webhook() -> str | None:
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(HERE, ".env"))
    except Exception:
        pass
    dom = (os.getenv("NGROK_DOMAIN") or "").strip()
    key = (os.getenv("S4_REVIEW_KEY") or os.getenv("WEBHOOK_SECRET") or "").strip()
    if not dom or not key:
        return None
    dom = dom.replace("https://", "").replace("http://", "").strip("/")
    return "https://%s/thesis-alert?key=%s" % (dom, key)


def clock_of(timeframe: str | None) -> tuple[str, str]:
    """(TradingView resolution, label) - the trade's own clock."""
    tf = str(timeframe or "").strip().lower()
    return ("1D", "Daily")      # every trade: management is Daily (13-Oct-2026)


def candidates() -> tuple[list[dict], list[str]]:
    from journal_path import JOURNAL_DB
    con = sqlite3.connect(JOURNAL_DB)
    try:
        rows = con.execute("SELECT symbol, thesis_sl, stoploss, timeframe FROM journal "
                           "WHERE UPPER(status)='OPEN'").fetchall()
    finally:
        con.close()
    out, skipped = [], []
    for sym, th, sl, tf in rows:
        sym = str(sym or "").strip()
        if not sym or sym.upper().startswith("LIQUID"):
            continue
        try:
            th = float(th) if th is not None else None
            sl = float(sl) if sl is not None else None
        except (TypeError, ValueError):
            th = None
        if not th or th <= 0:
            skipped.append("%s (no thesis)" % sym)
            continue
        if sl is not None and th <= sl + 1e-9:
            skipped.append("%s (thesis %.2f <= Dhan stop %.2f - single tier)" % (sym, th, sl))
            continue
        res, lbl = clock_of(tf)
        out.append({"sym": sym, "tv": _tv_symbol(sym), "level": round(th, 2), "dsl": sl,
                    "res": res, "clock": lbl})
    return out, skipped


JS = r"""
(async () => {
  const cfg = __CFG__;
  const out = {created: [], deleted: 0, failed: [], test: null};
  try {
    const W = window.webpackChunktradingview;
    if (!W) return JSON.stringify({err: "TradingView module loader not found"});
    if (!window.__tvReq) W.push([["gmthesis" + Date.now()], {}, r => { window.__tvReq = r; }]);
    let modId = null;
    for (const c of W) { const m = c[1] || {}; for (const k in m) { let s; try { s = m[k].toString(); } catch (e) { continue; }
      if (s.indexOf('"Alerts.AlertsRestApi"') >= 0 && s.indexOf("getAlertsRestApi") >= 0) { modId = k; break; } } if (modId) break; }
    if (!modId || !window.__tvReq) return JSON.stringify({err: "TradingView alerts client not found"});
    const api = window.__tvReq(modId).getAlertsRestApi();
    const la = (await api.listAlerts()) || [];
    const seed = la.filter(a => a.name === cfg.seed).sort((x, y) => String(x.create_time).localeCompare(String(y.create_time)))[0];
    const ours = la.filter(a => String(a.name || "").indexOf(cfg.prefix) === 0);
    out.old = ours.length;
    if (!seed) return JSON.stringify(Object.assign(out, {err: "no seed alert named '" + cfg.seed + "'"}));
    if (cfg.dry) return JSON.stringify(out);
    const exp = new Date(Date.now() + cfg.days * 86400000).toISOString().replace(/\.\d+Z$/, "Z");
    // CLOSE BELOW, on the trade's clock: crossing down, evaluated once per BAR CLOSE at
    // that resolution - an intrabar wick through the level does not fire it.
    const mk = (id, sym, level, res, name, msg) => {
      const cond = {type: "cross_down", frequency: "on_bar_close", cross_interval: false, resolution: res,
                    series: [{type: "barset"}, {type: "value", value: level}]};
      return {alert_id: id, symbol: '={"adjustment":"splits","symbol":"' + sym + '"}', resolution: res,
              condition: cond, message: msg, web_hook: cfg.hook, name: name, popup: true, email: false,
              sms_over_email: false, mobile_push: true, sound_file: null, sound_duration: 0,
              expiration: exp, auto_deactivate: false, cross_interval: false, active: true, ignore_warnings: true};
    };
    const one = async (c, name, msg) => {
      let newId = null;
      const cl = await api.cloneAlerts({alert_ids: [seed.alert_id]});
      newId = cl && cl[0] && cl[0].alert_id;
      if (!newId) throw new Error("clone returned no id");
      try {
        await api.modifyRestartAlert(mk(newId, c.tv, c.level, c.res, name, msg));
        const chk = ((await api.getAlerts({alert_ids: [newId]})) || [])[0];
        const cd = (chk && chk.condition) || {};
        const v = cd.series && cd.series[1] && cd.series[1].value;
        // the symbol comes back JSON-escaped: NSE:M&MFIN reads "NSE:M&MFIN" (13-Oct-2026)
        const symBack = String(chk && chk.symbol).replace(/\\u0026/g, "&");
        if (!chk || symBack.indexOf(c.tv) < 0 || Math.abs(v - c.level) > 0.01
            || String(chk.resolution) !== String(c.res) || cd.frequency !== "on_bar_close")
          throw new Error("verify failed: " + (chk && chk.symbol) + " @ " + v + " res " + (chk && chk.resolution) + " freq " + cd.frequency);
        return {id: newId, chk: {symbol: chk.symbol, res: chk.resolution, freq: cd.frequency, type: cd.type, value: v, hook: !!chk.web_hook}};
      } catch (e) { try { await api.deleteAlerts({alert_ids: [newId]}); } catch (x) {} throw e; }
    };
    if (cfg.selftest) {
      const c = {tv: cfg.selftest, level: 1, res: "1D"};
      const r = await one(c, cfg.prefix + "SELFTEST", "selftest - deleted at once");
      out.test = r.chk;
      await api.deleteAlerts({alert_ids: [r.id]});
      return JSON.stringify(out);
    }
    for (const c of cfg.items) {
      try {
        const msg = c.sym + " CLOSED below its THESIS " + c.level + " on the " + c.clock + " bar. Two-tier stop: exit at the next bar - your order. The Dhan disaster stop rests at " + (c.dsl == null ? "?" : c.dsl) + ".";
        const r = await one(c, cfg.prefix + c.sym, msg);
        out.created.push(c.sym + "@" + c.level + "/" + c.res + "#" + r.id);
      } catch (e) { out.failed.push(c.sym + ": " + String((e && (e.code || e.message)) || e).slice(0, 160)); }
    }
    if (ours.length) {
      try { await api.deleteAlerts({alert_ids: ours.map(a => a.alert_id)}); out.deleted = ours.length; }
      catch (e) { out.failed.push("delete old: " + String((e && e.message) || e).slice(0, 120)); }
    }
    return JSON.stringify(out);
  } catch (e) { out.err = String((e && (e.code || e.message)) || e); return JSON.stringify(out); }
})()
"""


def run(dry: bool = False, selftest: str | None = None) -> int:
    items, skipped = candidates()
    hook = _webhook()
    print("Thesis alerts: %d holding(s) two-tier · %d skipped%s" % (len(items), len(skipped), " [dry run]" if dry else ""), flush=True)
    for c in items:
        print("  %-12s close < %10.2f on the %-5s  (Dhan disaster stop %s)" % (c["sym"], c["level"], c["clock"], c["dsl"]))
    for s in skipped:
        print("  skip " + s)
    if not hook:
        print("  WARN no NGROK_DOMAIN / key in .env - alerts would carry no webhook (TradingView push only)")
    from tv_gm_alerts import _eval
    from tv_bind_s4 import _chart_targets_all
    targets = _chart_targets_all()
    if not targets:
        print("ERROR: no TradingView chart tab over CDP - is TradingView running with the debug port?")
        return 2
    cfg = {"prefix": PREFIX, "seed": SEED, "items": items, "days": EXPIRY_DAYS, "dry": bool(dry),
           "hook": hook, "selftest": selftest}
    raw = _eval(targets[0]["webSocketDebuggerUrl"], JS.replace("__CFG__", json.dumps(cfg)))
    try:
        res = json.loads(raw) if raw else {"err": "no result"}
    except Exception:
        res = {"err": "unparseable: " + str(raw)[:200]}
    if res.get("err"):
        print("ERROR: " + res["err"]); _log("ERROR " + res["err"])
        return 1
    if selftest:
        print("SELFTEST read back:", res.get("test"))
        _log("selftest %s" % res.get("test"))
        return 0
    line = "existing %s (of ours) · created %d · deleted %d · failed %d · skipped %d" % (
        res.get("old"), len(res.get("created", [])), res.get("deleted", 0), len(res.get("failed", [])), len(skipped))
    print(("DRY RUN - " if dry else "") + line)
    for f in res.get("failed", []):
        print("  FAILED " + f)
    _log(line + (" · " + "; ".join(res.get("failed", [])) if res.get("failed") else ""))
    return 1 if res.get("failed") else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", nargs="?", const="NSE:SAILIFE", help="create one test alert at level 1 on this symbol, read it back, delete it")
    a = ap.parse_args()
    return run(dry=a.dry_run, selftest=a.selftest)


if __name__ == "__main__":
    sys.exit(main())
