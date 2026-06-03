# Python ↔ Pine Signal Parity Audit — Deep Dive (started 3 Jun 2026)

Triggered by Jay's observation: catalyst signals were visible in CSV reports
~Mar/Apr, then disappeared (few/zero firing). Root finding: a batch
**"R-series" rewrite** silently replaced Pine-faithful indicator gates (RSI,
ADX) and base gates with stricter price-action proxies / squeeze conditions,
diverging the entire Python signal layer from the canonical Pine
(`Weinstein_Unified_Ecosystem_v3.4`). Prior audits missed it because they
checked that code *ran* and that *params/scores* matched — never the per-gate
*trigger logic* or *firing rates* line-by-line vs Pine.

Live corroboration: `Bull_Screener_N500_Results.csv` = 498 rows, **490 no-catalyst,
8 firing, 0 POS-BO**. `FINAL_Hunter_Picks.csv` empty. POS book was dead live too.

## DECISION (Jay, 3 Jun): PRICE ACTION is canonical
Jay confirmed the "R-series" indicator→price-action rewrites were **intentional
and his preference** (replace lagging indicators — RSI/MACD/BB/ADX — with pure
price action *wherever possible*). Constraints: must NOT create ambiguity, must
NOT break code logic.

Therefore:
- **Python price-action gates are canonical.** Do NOT revert them to Pine's
  RSI/ADX.
- **Pine must be SYNCED to the price-action Python** (resolves the ambiguity;
  both platforms price-action). → pending Pine-edit task.
- Where the PA rewrite **broke logic** (squeeze killing POS, SWG-PB dying), fix
  **with price action**, never by importing an indicator.

### Correction to my own 3-Jun catalyst fix
My first pass "restored Pine parity" by importing Pine's ADX/RSI into 3 gates —
the OPPOSITE of the PA preference. Reverted to price action (commit):
- POS-BO: ADX≥25 → `_pb_dir_ok` (7/14 up-bars w/ higher highs).
- SWG-PB: RSI 30-70 → `pb_pocket_pa` (38-62% retrace depth).
- SWG-REV: RSI<35 → `pa_oversold` (3-bar down + low-in-range).
Kept (genuine PA/structural logic-break fixes): squeeze removal from
weinstein_setup, bull_pullback, breakout structure, volume dry-up.

---

## bull_screener.py  — AUDITED
| Item | Class | Status | Note |
|---|---|---|---|
| `weinstein_setup` squeeze gates (R5 NR7 + R6 coil) | **A bug** | ✅ FIXED | AND-ed into POS-BO base; mutually exclusive with breakout → 0 POS for 24mo. Not in Pine (line 1622). |
| Catalyst cascade — all 6 triggers | **A bug** | ✅ FIXED | SWG-PB (dominant) was 0; wholesale divergence. All 6 realigned to Pine 1723-1768. |
| `calculate_alpha_score` R1 (RSI→N-bar mom) | **B = intended PA** | ✅ KEEP | Per Jay's preference. Sync Pine to match. |
| `calculate_alpha_score` R4 (ADX→bar-dir) | **B = intended PA** | ✅ KEEP | Per Jay's preference. Sync Pine to match. |
| `calculate_alpha_score` macro-edge term | gap (volume, not lagging) | ⏳ TODO | Pine (use_macro_edge default TRUE): v>va +10 else −20. Python MISSING → alpha slightly inflated. Volume-based so PA-compatible; add for parity. |
| Catalyst gates: ADX/RSI imports (my error) | A | ✅ REVERTED→PA | POS-BO/SWG-PB/SWG-REV now price-action. |
| Remaining indicator gates | B (PA todo) | ⏳ FLAG | POS-BO weekly `wRSI>=60`, POS-ACCUM daily `RSI<=50` — locked Hunter/v2 params; convert to PA "wherever possible" (needs PA-momentum design). |
| `mature_trend_ok` in base_confirmed | A (minor) | ⚠️ APPROX | Pine uses weeks-in-stage; Python lacks it → approximated. |
| `ma_sqz_ok`/`bb_sqz_ok` now dead code | cleanup | TODO | No longer used after weinstein fix; verify + remove. |
| **Pine sync to PA gates** | parity | 🟡 PARTIAL | Weinstein_Unified_Ecosystem_v3.4 DONE (alpha score + POS-BO/SWG-PB/SWG-REV → PA). NOT compile-verified (TV off). TODO: Commander_Bull_Screener_v3.2, v67 dashboard; macro-edge alpha term (Pine-only). |

## recovery_screener.py — AUDITED ✅ CLEAN
REV-CB / REV-RS / REV-EARLY gates are **already pure price action** (drawdown %,
red-bar counts, widest-range, higher-low, strict-trend pivot zigzag, trendline
reclaim). `rsi14`/`rsi3` are computed but used ONLY as display columns
(RSI14/RSI3 output), NOT in any gate. Firing (78 rows). The v1.2/v1.3 PA redesign
was done CORRECTLY here (unlike bull). Low priority; a full line-by-line Pine
trace could still find subtle drift but there is no indicator-in-gate or
blackout problem.

## chartink_replay.py — AUDITED ✅ KEEP FAITHFUL (Jay's decision)
Hunter scan uses `weekly_rsi_min=60` + `daily_adx_min=25` (RSI + ADX) — but these
are faithful ports of the actual **Chartink.com scans** (indicator-based by
nature). **Jay's decision (3 Jun): keep them faithful to Chartink** — do NOT
convert to PA (they must mirror the external Chartink source). No change.
`FINAL_Hunter_Picks.csv` empty was the (now-fixed) bull_screener POS-BO blackout.

## matcher_replay.py — AUDITED ✅ CLEAN
Conviction filter (min_conviction=6.0). No RSI/ADX/MACD anywhere. Score/conviction
based. NOTE: this + Top-N are the cleanest FUNNEL-RELAXATION dials if the daily
list is ever too thin (lower min_conviction ~5 / raise Top-N) — preferred over
loosening screener gates.

## etf_screener.py — AUDITED ✅ CLEAN
4-axis scoring (Liquidity / Trend / RS / Rotation). No RSI/ADX/MACD in gates.

## data_provider.py — AUDITED ✅ CLEAN (data layer, no gates)
Date-pinning OHLCV provider; no signal logic. (Pinning correctness was implicitly
validated by the historical-anchor funnel runs returning the full ~440-symbol
universe with correct as-of bars.)

## AUDIT CONCLUSION
The indicator-in-gate / PA-drift problem was **ISOLATED to bull_screener.py**
(now fixed + Pine-synced). recovery_screener was already PA-clean; matcher/etf/
data_provider don't use these indicators in gates; chartink is intentionally
indicator-faithful to Chartink. The systemic fear ("drift everywhere") did not
materialize beyond bull_screener — but the bull layer feeds everything, which is
why its breakage cascaded to empty CSVs.

## matcher_replay.py — PENDING
Conviction filter (min_conviction=6.0). Verify weighting.

## etf_screener.py / etf_rotation.py — PENDING
vs `Commander_ETF_Strategy_v1.1` / `Commander_ETF_Dashboard_v1.1`.

## data_provider.py — PENDING
Date-pinning correctness (a pinning bug would silently corrupt ALL backtests).
Spot-check: pinned historical fetch returns full universe, correct as-of bars.

## Score / output path — PENDING
`compute_score` (E3 VCP boost) vs Pine `pyScore`. Why `Bull_Screener_Results.csv`
empty while `_N500_` populated — output-file routing.

---

## CALIBRATION PRINCIPLE (Jay, 3 Jun)
Do NOT make individual gates too strict. The pipeline has MULTIPLE levels of
checks (screener catalyst gates → matcher conviction ≥6 → Top-N → Golden Picks),
so over-tight individual gates COMPOUND and starve the funnel → too few/zero
candidates. When a gate fires ~0 (e.g. SWG-REV on strict 3-bar+20% PA oversold),
RELAX it (→ 2-bar+25%) rather than leave it dead. Keep quality, but ensure a
workable candidate set flows through. Applies to all future gate changes + the
part-(a) RSI→PA conversions.

Relaxation watch-list:
- SWG-REV pa_oversold: 3-bar+20% → **2-bar+25%** ✅ done (Python+Pine).
- POS-ACCUM (only ~2 fires): is_vcp_tight@1.0 is tight + the daily-RSI≤50 gate
  (part a). Relax holistically when converting its RSI gate to PA.

## Methodology (the fix for the audit gap)
For each signal module: (1) extract every Pine trigger/gate + its helpers,
(2) map to the Python gate line-by-line, (3) instrument a per-gate FUNNEL,
(4) run at a historical anchor, (5) compare firing rate to the Mar/Apr–May
baseline, (6) classify A-bug vs B-design, (7) fix A immediately, escalate B.
