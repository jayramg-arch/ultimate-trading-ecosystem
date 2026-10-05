"""Per-stock Daily S4 GO alerts for every GM_Positional name, refreshed nightly (5-Oct-2026, Jay).

WHY: TradingView's plan allows two WATCHLIST alerts and both time the SWING clock (75m +
125m on GM_Swing). Single-symbol alerts are not limited that way, so each positional name
gets its OWN S4 GO alert on the Daily close - the bar its plan is decided on - instead of
waiting for the evening Daily-board review. The alert fires at the 15:30 close and its
webhook queues the AI reviewer exactly as the watchlist alerts do.

HOW (the tv_gm_alerts / tv_zone_alerts route, inside the logged-in page over CDP):
  * TEMPLATE = an existing S4 GO watchlist alert (it carries the alertcondition, "once per
    bar close", the message, the webhook and the bound v67/Zigzag studies);
  * per name: cloneAlerts(template) -> modifyRestartAlert with the stock as the symbol,
    resolution 1D, S4's three pushed inputs fresh from the chart (both bundles + pivot
    toggle), the chart's compiled version, a name "GM-POS GO <SYM>" and a 7-day expiry;
    then read back;
  * yesterday's set is deleted only AFTER today's was built, and only alerts whose NAME
    starts with PREFIX. The two watchlist alerts and every other alert are never touched.
Names come from FINAL_GM_POSITIONAL.csv (run_pipeline Phase 4.8) - the board names only,
not the index rows the TradingView list also carries. TradingView spells "-" as "_".

    python tv_pos_alerts.py --dry-run   # list what would be set, touch nothing
    python tv_pos_alerts.py             # replace yesterday's set

Runs in the auto-pilot (Phase 12b3, after the bundles are pushed). After an S4 compile
TradingView deletes the template alerts - recreate the two watchlist alerts once by hand,
then this job works again.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PREFIX = "GM-POS GO "         # identifies OUR alerts; nothing without it is ever deleted
EXPIRY_DAYS = 7
MAX_ALERTS = 60
BATCH = 8                     # names per page call (each clone+modify+verify ~6 s)
LIST_CSV = os.path.join(HERE, "FINAL_GM_POSITIONAL.csv")
LOG = os.path.join(HERE, "logs", "tv_pos_alerts.log")


def _log(msg: str) -> None:
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))


def _tv_symbol(sym: str) -> str:
    """TradingView keeps '&' (NSE:M&MFIN) and turns '-' into '_' (NSE:NAM_INDIA)."""
    return "NSE:" + sym.strip().upper().replace("NSE:", "").replace("-", "_")


def names() -> tuple[list[str], str]:
    import pandas as pd
    if not os.path.exists(LIST_CSV):
        return [], "no FINAL_GM_POSITIONAL.csv"
    age_h = (time.time() - os.path.getmtime(LIST_CSV)) / 3600
    syms = [str(s).strip() for s in pd.read_csv(LIST_CSV)["Symbol"].dropna() if str(s).strip()]
    return syms[:MAX_ALERTS], "list %.1fh old" % age_h + (" - STALE" if age_h > 30 else "")


JS = r"""
(async () => {
  const cfg = __CFG__;
  const out = {created: [], deleted: 0, failed: [], kept_foreign: 0};
  try {
    const W = window.webpackChunktradingview;
    if (!W) return JSON.stringify({err: "TradingView module loader not found"});
    if (!window.__tvReq) W.push([["gmpos" + Date.now()], {}, r => { window.__tvReq = r; }]);
    let modId = null;
    for (const c of W) { const m = c[1] || {}; for (const k in m) { let s; try { s = m[k].toString(); } catch (e) { continue; }
      if (s.indexOf('"Alerts.AlertsRestApi"') >= 0 && s.indexOf("getAlertsRestApi") >= 0) { modId = k; break; } } if (modId) break; }
    if (!modId || !window.__tvReq) return JSON.stringify({err: "TradingView alerts client not found"});
    const api = window.__tvReq(modId).getAlertsRestApi();

    // S4 on this chart: the inputs the evening run pushes, and the compiled version
    const chart = (window.TradingViewApi || window.tvWidget).activeChart();
    const st = chart.getAllStudies().find(s => s.name.indexOf("Section 4") === 0);
    if (!st) return JSON.stringify({err: "S4 is not on this chart tab"});
    const s4 = chart.getStudyById(st.id);
    let curVer = null; try { curVer = s4._study.metaInfo().pine.version; } catch (e) {}
    const ids = {}; s4.getInputsInfo().forEach(i => { if (cfg.titles.indexOf(i.name) >= 0) ids[i.name] = i.id; });
    const vals = {}; s4.getInputValues().forEach(v => { vals[v.id] = v.value; });
    const fresh = {}; cfg.titles.forEach(t => { if (t in ids) fresh[ids[t]] = vals[ids[t]]; });
    if (!String(fresh[ids[cfg.titles[0]]] || "").length)
      return JSON.stringify({err: "bundle 1 is EMPTY on the chart - refusing to build alerts on it"});

    const la = (await api.listAlerts()) || [];
    // template: a watchlist S4 GO alert, else any S4 GO alert left (5-Oct-2026 - a deleted
    // watchlist takes its alerts with it, and this job must not depend on those two)
    const s4a = la.filter(a => a.condition && a.condition.type === "alert_cond" && String(a.message || "").indexOf("S4 GO") >= 0);
    const tpl = s4a.find(a => /WATCHLIST:\d+/.test(String(a.symbol || ""))) || s4a[0];
    if (!tpl) return JSON.stringify({err: "no S4 GO alert of any kind to use as a template - after an S4 compile, recreate the 75m/125m alerts by hand once"});
    const ours = la.filter(a => String(a.name || "").indexOf(cfg.prefix) === 0);
    out.old = ours.length; out.kept_foreign = la.length - ours.length; out.total_before = la.length;
    out.old_ids = ours.map(a => a.alert_id);
    if (cfg.dry || cfg.mode === "list") return JSON.stringify(out);
    if (cfg.mode === "delete") {     // only ids this run listed as OURS before it created anything
      const del = (cfg.del || []).filter(id => out.old_ids.indexOf(id) >= 0);
      if (del.length) { await api.deleteAlerts({alert_ids: del}); out.deleted = del.length; }
      return JSON.stringify(out);
    }

    const exp = new Date(Date.now() + cfg.days * 86400000).toISOString().replace(/\.\d+Z$/, "Z");
    const KEEP = ["alert_id", "symbol", "resolution", "condition", "message", "web_hook", "name", "popup", "email",
                  "sms_over_email", "mobile_push", "sound_file", "sound_duration", "expiration", "auto_deactivate",
                  "cross_interval", "active"];
    for (const sym of cfg.items) {
      let newId = null;
      try {
        const cl = await api.cloneAlerts({alert_ids: [tpl.alert_id]});
        newId = cl && cl[0] && cl[0].alert_id;
        if (!newId) throw new Error("clone returned no id");
        const p = JSON.parse(JSON.stringify(tpl));
        const q = {}; KEEP.forEach(k => { if (k in p) q[k] = p[k]; });
        q.alert_id = newId; q.ignore_warnings = true; q.active = true;
        q.symbol = '={"session":"regular","symbol":"' + sym + '"}';
        q.resolution = "1D"; q.name = cfg.prefix + sym.replace("NSE:", ""); q.expiration = exp;
        [q.condition].concat(q.conditions || []).forEach(c => {
          if (!c) return; if ("resolution" in c) c.resolution = "1D";
          ((c.series) || []).forEach(sr => { if (sr && sr.inputs) Object.keys(fresh).forEach(k => { if (k in sr.inputs) sr.inputs[k] = fresh[k]; });
                                             if (sr && sr.pine_version && curVer) sr.pine_version = curVer; });
        });
        await api.modifyRestartAlert(q);
        const chk = ((await api.getAlerts({alert_ids: [newId]})) || [])[0];
        if (!chk || String(chk.symbol).indexOf(sym) < 0 || String(chk.resolution) !== "1D")
          throw new Error("verify failed: " + (chk && chk.symbol) + " @ " + (chk && chk.resolution));
        out.created.push(sym.replace("NSE:", ""));
      } catch (e) {
        out.failed.push(sym + ": " + String((e && (e.code || e.message)) || e).slice(0, 140));
        if (newId) { try { await api.deleteAlerts({alert_ids: [newId]}); } catch (x) {} }
      }
    }
    return JSON.stringify(out);
  } catch (e) { out.err = String(e); return JSON.stringify(out); }
})()
"""


def run(dry: bool = False, limit: int | None = None) -> int:
    syms, note = names()
    if limit:
        syms = syms[:limit]
    tv = [_tv_symbol(s) for s in syms]
    print("Positional Daily S4 GO alerts: %d name(s) · %s%s" % (len(tv), note, " [dry run]" if dry else ""), flush=True)
    if not tv:
        print("nothing to do - yesterday's alerts left as they are")
        return 0
    from tv_gm_alerts import _eval
    from tv_bind_s4 import _chart_targets_all
    from tv_push_bundles import IN1, IN2, IN3, IN4
    targets = [t for t in _chart_targets_all() if "x7xQoXWx" not in t["url"]]   # never the Phase-1 index tab
    if not targets:
        print("ERROR: no TradingView chart tab over CDP - is TradingView running with the debug port?")
        return 2
    base = {"prefix": PREFIX, "days": EXPIRY_DAYS, "titles": [IN1, IN2, IN3, IN4]}

    def call(cfg):
        for t in targets:      # the first tab that carries S4
            raw = _eval(t["webSocketDebuggerUrl"], JS.replace("__CFG__", json.dumps(dict(base, **cfg))))
            try:
                r = json.loads(raw) if raw else {"err": "no result"}
            except Exception:
                r = {"err": "unparseable: " + str(raw)[:200]}
            if r.get("err") != "S4 is not on this chart tab":
                return r
        return {"err": "S4 is not on any chart tab"}

    # 1. what is ours now (yesterday's set), 2. build today's in batches - one call per
    # batch, so no single page call runs into the 120 s CDP timeout (38 at once did, 5-Oct),
    # 3. delete yesterday's set only if today's has alerts in it.
    first = call({"mode": "list", "items": [], "dry": bool(dry)})
    if first.get("err"):
        print("ERROR: " + first["err"]); _log("ERROR " + first["err"])
        return 1
    old_ids = first.get("old_ids", [])
    created, failed = [], []
    if not dry:
        for i in range(0, len(tv), BATCH):
            r = call({"mode": "create", "items": tv[i:i + BATCH]})
            if r.get("err"):
                failed.append("batch %d: %s" % (i // BATCH + 1, r["err"]))
                break
            created += r.get("created", [])
            failed += r.get("failed", [])
    deleted = 0
    if created and old_ids:
        r = call({"mode": "delete", "items": [], "del": old_ids})
        deleted = r.get("deleted", 0)
        if r.get("err"):
            failed.append("delete old: " + r["err"])
    line = "alerts on the account %s · ours before %d · created %d · deleted %d · failed %d" % (
        first.get("total_before"), len(old_ids), len(created), deleted, len(failed))
    print(("DRY RUN - " if dry else "") + line)
    if created:
        print("  " + ", ".join(created))
    for f in failed:
        print("  FAILED " + f)
    _log(line + (" · " + "; ".join(failed) if failed else ""))
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="first N names only (a trial)")
    a = ap.parse_args()
    return run(dry=a.dry_run, limit=a.limit)


if __name__ == "__main__":
    sys.exit(main())
