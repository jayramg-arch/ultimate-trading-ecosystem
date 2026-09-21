/* Re-bind S4's `input.source` fields to the v67 Dashboard and Swing Zigzag plots.
 *
 * WHY THIS EXISTS: TradingView drops source bindings on EVERY recompile of S4.
 * MEASURED, not assumed (7-Aug-2026): after a compile that changed NO inputs at
 * all, 0 of 18 bindings survived. An earlier theory blamed input-id shifting —
 * ids are positional, and deleting five unused inputs to reclaim tokens really
 * did renumber everything after them — but that is a SECOND, independent way to
 * break them, not the cause. The recompile alone is sufficient.
 *
 * So this is not a one-off setup step, it is a chore that follows every compile.
 * Eighteen dropdowns by hand, every time, is how the panel silently goes back to
 * reading `close` and printing "-" in half its rows — or worse, dropping a field
 * entirely, which is how the Daily trend arrow disappeared without a trace.
 *
 * Matching is by NAME on both sides — S4's input titles and the exporter's plot
 * titles. Entity ids (DDeb97 / EKxZK4 / NlkikE) change whenever an indicator is
 * removed and re-added, and input ids renumber whenever the input list changes,
 * so binding by id would break in exactly the situations this is meant to survive.
 *
 * RUN: paste into the TradingView console, or via the MCP `ui_evaluate`.
 * Returns a per-field report; anything not "ok" names what was missing.
 */
(function () {
  var MAP = {
    "v67: Action Signal":              ["v67", "s4_actionSignal"],
    "v67: Asset Quality":              ["v67", "s4_assetQuality"],
    "v67: Daily RSI":                  ["v67", "s4_rsiDaily"],
    "v67: RS-Ratio vs N500":           ["v67", "s4_rsRatio500"],
    "v67: RS-Momentum vs N500":        ["v67", "s4_rsMom500"],
    "v67: RS slope vs N500":           ["v67", "s4_rsSlope500"],
    "v67: RS slope vs Sector":         ["v67", "s4_rsSlopeSec"],
    "v67: Sector stage":               ["v67", "s4_secStage"],
    "v67: Stage age (weeks)":          ["v67", "s4_stageWeeks"],
    "v67: Macro stage age":            ["v67", "s4_macroWeeks"],
    "v67: 50-DMA slope":               ["v67", "s4_slope50"],
    "v67: Futures OI":                 ["v67", "s4_oi"],
    "v67: Futures OI prior":           ["v67", "s4_oiPrev"],
    "v67: RS-Ratio vs Sector":         ["v67", "s4_rsRatioSec"],
    // Added 1-Sep-2026 with the stock-vs-SECTOR RRG. The pair was always being
    // computed inside v67's weekly security call and had simply never been plotted,
    // so S4 could show the sector RS LEVEL but not its rotation. Without this entry
    // the sector half of the RRG row reads an em-dash - and it cannot be spotted by
    // na(), because an unbound input.source returns close, which is a valid number.
    "v67: RS-Momentum vs Sector":      ["v67", "s4_rsMomSec"],
    // The TRAILING sector pair (2 Sep 2026). Without it the sector RRG passed its own
    // current value as its trailing value, so dv = dm = 0: the arrow was always ➡️, the
    // gradient always +2-or-0 and the signal just "is it LEADING". 26 -> 28 bindings.
    "v67: RS-Ratio trail (sector)":    ["v67", "s4_rsValTrailSec"],
    "v67: RS-Momentum trail (sector)": ["v67", "s4_rsMomTrailSec"],
    "v67: RS val trail (N500)":        ["v67", "s4_rsValTrail500"],
    "v67: RS mom trail (N500)":        ["v67", "s4_rsMomTrail500"],
    "v67: Pyramid rung":               ["v67", "s4_pyrClass"],
    "v67: Position P&L %":             ["v67", "s4_pyrPnl"],
    "v67: Position R":                 ["v67", "s4_pyrR"],
    "v67: Days held":                  ["v67", "s4_pyrDays"],
    "v67: Days to time-stop":          ["v67", "s4_pyrDaysLeft"],
    "v67: Chandelier stop":            ["v67", "s4_pyrChand"],
    "v67: Pyramid reason":             ["v67", "s4_pyrReason"],
    "v67: Entry date (epoch)":         ["v67", "s4_pyrEntryTime"],
    "Zigzag: MTF-1 trend state (Daily)":  ["zz", "mtfTrendState"],
    "Zigzag: MTF-2 trend state (Weekly)": ["zz", "mtfTrendState2"],
    // 23-Aug-2026: the CHART-TF trend. S4's Structure-basis row used to read an
    // EMA20 proxy for this column while D and W came from the Zigzag, so on a
    // daily chart it printed "Trend 1D down" beside "D up" — one timeframe, two
    // methods. `trendState` is the Zigzag's LIVE chart-TF state (the same value
    // its own TREND row shows); `confirmedTrend` is the pivot-confirmed-only
    // variant, deliberately NOT used here so the two panels agree by construction.
    "Zigzag: CHART-TF trend state":       ["zz", "trendState"],
    // 5-Sep-2026: this points at the BRIDGE, never at the Unified Ecosystem itself.
    // Bound to Unified it HANGS S4 - measured both directions on one chart: 0 bound =
    // ready · Zigzag only = ready · all 32 including Unified = never completes (type 1,
    // 0 bars, no error, while all twelve other studies finish) · 31 bound with Unified
    // alone off = ready. Unified is a strategy(); the bridge is the same catalyst code
    // as an indicator. If this row ever resolves to the strategy again, S4 stops dead.
    "Unified: catalyst code":             ["uni", "s4_catalystCode"]
  };
  try {
    var chart = (window.TradingViewApi || window.tvWidget).activeChart();
    var studies = chart.getAllStudies();
    function findBy(pred) { for (var i = 0; i < studies.length; i++) if (pred(studies[i].name)) return studies[i].id; return null; }
    var ids = {
      s4:  findBy(function (n) { return n.indexOf("Section 4") === 0; }),
      v67: findBy(function (n) { return n.indexOf("Weinstein & Swing Pro Dashboard") === 0; }),
      zz:  findBy(function (n) { return n.indexOf("Weinstein Swing Zigzag") === 0; }),
      // 4-Sep-2026: the Unified Ecosystem publishes the CATALYST as a numeric code.
      // S4 used to infer its playbook from structure, which collapsed POS-ACCUM into
      // BREAKOUT and judged a base-building setup by a breakout's standards.
      // MUST match the BRIDGE, not the strategy. Anchored with indexOf(...)===0 so
      // "Weinstein Unified Ecosystem [v3.5]" can never satisfy it.
      uni: findBy(function (n) { return n.indexOf("Unified Catalyst Bridge") === 0; })
    };
    if (!ids.s4)  return "S4 not on this chart";
    if (!ids.v67) return "v67 Dashboard not on this chart — load it first, the plots are the source";
    if (!ids.zz)  return "Swing Zigzag not on this chart";
    if (!ids.uni) return "Unified Catalyst Bridge not on this chart - add it; do NOT bind the strategy";

    // plot title -> "<studyId>$<plotIndex>"; the index is the plot's position in
    // metaInfo.plots, which is what a source value actually references.
    var plotRef = {};
    // A missing study id is skipped rather than throwing - the bind used to die on
    // getStudyById(null) if any one source script was not on the chart.
    ["v67", "zz", "uni"].forEach(function (key) {
      if (!ids[key]) return;
      var meta = chart.getStudyById(ids[key])._study.metaInfo();
      meta.plots.forEach(function (pl, ix) {
        var title = (meta.styles && meta.styles[pl.id] && meta.styles[pl.id].title) || "";
        if (title) plotRef[key + "|" + title] = ids[key] + "$" + ix;
      });
    });

    var s4 = chart.getStudyById(ids.s4);
    var pending = [], report = [];
    s4.getInputsInfo().forEach(function (inp) {
      if (String(inp.type) !== "source") return;          // leave trendline sources alone
      var want = MAP[inp.name];
      if (!want) return;                                   // not one of ours
      var ref = plotRef[want[0] + "|" + want[1]];
      if (!ref) { report.push("MISSING PLOT " + want[1] + " <- " + inp.name); return; }
      pending.push({ id: inp.id, value: ref });
      report.push("ok " + inp.name + " -> " + want[1]);
    });
    if (!pending.length) return "nothing to bind — check the input titles still match MAP";
    s4.setInputValues(pending);

    var got = {};
    s4.getInputValues().forEach(function (v) { got[v.id] = v.value; });
    var bad = pending.filter(function (p) { return got[p.id] !== p.value; });
    return "bound " + pending.length + "/" + Object.keys(MAP).length +
           " | mismatches: " + (bad.length ? JSON.stringify(bad) : "none") +
           (report.filter(function (r) { return r.indexOf("ok ") !== 0; }).length
              ? "\n" + report.filter(function (r) { return r.indexOf("ok ") !== 0; }).join("\n") : "");
  } catch (e) { return "ERR " + e.message; }
})();
