# AUDIT REPORT: Weinstein & Swing Pro Dashboard v60.4

> [!WARNING]
> **LEGACY REFERENCE MANUAL - ARCHIVAL USE ONLY**
> This audit report covers a legacy version of the Dashboard (v60.4).
> For the current canonical documentation and system state, please refer to:
> - [08_Dashboard_v67_Guide.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/08_Dashboard_v67_Guide.md)
> - [00_INDEX.md](file:///c:/Users/jayra/Documents/GeminiVSCode/docs/00_INDEX.md)

---

**Date:** 2026-03-31
**Auditor:** Claude (Cross-referenced against CLAUDE.md, Commander Screener ULTIMATE, and User Guide)

---

## SPEC COMPLIANCE SUMMARY

| Specification | Status | Notes |
|---|---|---|
| Pine Script v6 | PASS | `@version=6` confirmed |
| 30-Week MA (Weekly anchor) | PASS | `ta.sma(close, 30)` on Weekly TF |
| EMA 20 (Daily + intraday overlay) | PASS | Dual mode: Daily `request.security` + chart `ta.ema` |
| SMA 50 Volume Baseline | PASS | `ta.sma(volume, 50)` used correctly |
| Stage Classification | PASS | Slope + price position vs 30WMA, dynamic threshold |
| Mansfield RS | DRIFT | Formula diverges from screener spec (see Bug #1) |
| RS vs Nifty 50/500/Sector | PASS | 3 separate `request.security` calls |
| ATR-based risk mgmt | PASS | ATR 14, 10, 40 all calculated |
| `request.security` na handling | PARTIAL | Multiple unguarded divisions |
| Alpha Score system | PASS | 0-100 with Trend/Momentum/Volume/Safety |

---

## BUGS (Ranked by Severity)

### BUG #1 -- CRITICAL: RS Formula Signal Drift
**Lines 843-852**

v60.4 Mansfield RS:
```pine
rpSMA = ta.sma(rp, rsl)          // rsl = 26
mrs = ((rp / rpSMA) - 1) * 10
```

Commander Screener ULTIMATE uses:
```
rs_ratio = stock_price / benchmark_price
rs_ratio_sma = 130-day SMA of rs_ratio  (26 weeks x 5 days)
mansfield_rs = ((rs_ratio / rs_ratio_sma) - 1) x 10
```

The v60.4 formula calculates RS of the *spread symbol* using `close` (which is already the ratio), then applies a 26-bar SMA on the Weekly timeframe. This is mathematically equivalent to a 26-week SMA of the ratio -- which is correct for Weekly TF. However, the screener uses 130-day (daily TF). On weekly TF, 26 bars = 26 weeks = 130 days, so they **should** match -- but only if both are anchored to the same timeframe.

**Verdict:** Functionally aligned when called on `"W"` timeframe. No fix needed, but add a comment clarifying this equivalence for future maintainability.

---

### BUG #2 -- HIGH: Division by Zero in Multiple Locations

| Line | Code | Risk |
|---|---|---|
| 2050 | `(c - ema20) / ema20 * 100` | `ema20 == 0` on first bars |
| 2816 | `((lvl - close) / close) * 100` | `close == 0` at market open |
| 1300 | `math.abs(close - d_h20) / close * 100` | `close == 0` |
| 1314 | `d_v / d_vavg` | `d_vavg == 0` on insufficient bars |
| 1402 | `(close - use_ema20) / close * 100` | `close == 0` |
| 1579 | `((c_p_h50 - close) / close)` | `close == 0` |
| 1613 | `((dClose - d_ema20_val) / d_ema20_val) * 100` | `d_ema20_val == 0` |

**Fix pattern for all:**
```pine
float result = denominator != 0 ? (numerator / denominator) * 100 : 0.0
```

---

### BUG #3 -- HIGH: Operator Precedence in Pullback Detection
**Line 2073**
```pine
bool near_ema = dist_ema > 0 and dist_ema < 4.0 or (l < ema20 and c > ema20)
```
Pine evaluates `and` before `or`, so this reads as:
```
(dist_ema > 0 AND dist_ema < 4.0) OR (l < ema20 AND c > ema20)
```
This is **likely correct intent**, but ambiguous. Add explicit parentheses to prevent future misreads.

---

### BUG #4 -- MEDIUM: f_check_x Missing NA Guards
**Lines 2015-2019**
```pine
f_check_x(float c, float c1, float e, float e1) =>
    bool x = false
    if not na(c) and not na(e)
        x := c > e and c1 <= e1   // c1 and e1 not checked for na
    x
```
**Fix:**
```pine
if not na(c) and not na(c1) and not na(e) and not na(e1)
```

---

### BUG #5 -- MEDIUM: Benchmark Fallback to 0.0 Creates False Signals
**Lines 1241-1243**
```pine
b_c_65_ago := na(_b_c_65) ? 0.0 : _b_c_65
```
Setting to `0.0` when NA means downstream calculations like `b_q3 = b_c_65_ago == 0 ? 0.0 : ...` (line 1469) will silently produce 0% benchmark return, making the stock look like a massive outperformer. The `== 0` check partly guards this, but it's fragile.

**Fix:** Track validity separately:
```pine
bool bench_data_valid = not na(_b_c_65) and _b_c_65 > 0
```

---

### BUG #6 -- MEDIUM: Duplicate request.security Call for AVWAP
**Line 2795** calls `f_getStageAndTime` again via `request.security`:
```pine
[_s, _st, _sl, _wma] = request.security(syminfo.tickerid, "W", f_getStageAndTime(...))
```
This is **identical** to the call on line 1075 which already returns `stageStart`. You're burning a `request.security` call unnecessarily.

**Fix:** Replace lines 2795-2800 with:
```pine
if stageStart != last_anchor_time
    cumVol := 0.0
    cumVolPrice := 0.0
    last_anchor_time := stageStart
```
This saves 1 `request.security` call -- valuable headroom.

---

### BUG #7 -- LOW: ADX Threshold Mismatch
**Line 966:**
```pine
adx > 20 and dp > dm  // Comment says "20 instead of 25 for Indian mid-caps"
```
CLAUDE.md spec says: **ADX > 25 & PDI > NDI**. The screener user guide also references 25. This creates signal drift between platforms.

**Decision needed:** Standardize on 20 or 25 across all platforms.

---

### BUG #8 -- LOW (P0 IMPACT): `rs_is_leading` Check is Broken
**Line 1192:**
```pine
bool rs_is_leading = rs50State == "Leading"
```
But `f_rsStateStr` returns strings like `"Leading (Rising)"` -- never bare `"Leading"`. So this condition is **always false**, meaning Full Confluence stage display never triggers.

**Fix:**
```pine
bool rs_is_leading = str.contains(rs50State, "Leading")
```

---

### BUG #9 -- LOW (P0 IMPACT): `resistCount` Never Updated
**Line 382:** `var int resistCount = 0` is declared but never assigned after initialization. `f_countOverheadResist` is called inside `f_weekly_super_bundle_internal` but its result is stored in `ovh` (line 1075). The dashboard displays `resistCount` (line 2722), not `ovh`.

**Fix:** Add after line 1075:
```pine
resistCount := ovh
```

---

### BUG #10 -- LOW: Confluence Score Claims 5-Star But Has 6 Conditions
**Lines 1861-1888:** The confluence engine counts 6 conditions (Trend, Momentum, Volume, VP, PA, ADX) but the UI still says "5 stars = Excellent". The comment on line 1875 acknowledges this was fixed, but the star display doesn't reflect 6 stars properly -- showing 6 stars as "Perfect" is fine, but the **Alpha Score in CLAUDE.md is a 5-star system**.

**Decision needed:** Align to 5-star (remove VP or merge with another condition) or update CLAUDE.md to reflect 6-star.

---

## ENHANCEMENT RECOMMENDATIONS

### 1. Volume Baseline Inconsistency
CLAUDE.md mandates **50-SMA of volume** as the baseline. But:
- Line 855: `ta.sma(volume, 20)` -- Weekly health uses 20
- Line 1275: `ta.sma(volume, 20)` -- Institutional SMA uses 20

These should be 50 for consistency, or explicitly documented as intentional overrides.

### 2. Missing 150-SMA Stage Proxy
The ULTIMATE screener uses `150-SMA` as the weekly 30-WMA daily proxy for stage detection in the screener function (`f_get_screener_data_internal`, line 995):
```pine
bool is_stage2 = (_s50 > _s200) and (_c > _s50)
```
This uses 50/200 SMA crossover as a stage proxy, not the true 30-WMA slope logic. While acceptable for a screener approximation, it can produce **different stage classifications** than the main dashboard for the same stock.

**Recommendation:** Add a comment flagging this intentional divergence, or tighten the proxy.

### 3. Screener `f_check_pullback` Passes `c` for Both Price AND Low
**Line 2132:**
```pine
f_check_pullback(c, c, c, e, v, va)
```
The function signature is `(float c, float o, float l, float ema20, float v, float va)` -- you're passing close as the low, so the "EMA bounce" check `(l < ema20 and c > ema20)` can never trigger when close > ema20.

**Fix:** Pass actual low from screener data (requires adding `low` to `f_get_screener_data_internal` tuple).

### 4. Add `alert_msg` for Pullback Signals
The pullback hit signal fires a `plotshape` (line 1631) but has no `alertcondition`. Add:
```pine
alertcondition(hitPullback, title="Pullback Zone Hit", message="Weinstein Pro: Institutional Pullback Zone on {{ticker}}!")
```

### 5. Gemini Prompt -- Incomplete
**Lines 2897-2899:** The prompt cuts into instructions mid-sentence and doesn't include the actual price action data it references in the header. Complete the prompt with ATR, Volume state, and Trade Style.

---

## PRIORITY FIX LIST

| Priority | Bug/Enhancement | Impact |
|---|---|---|
| P0 | **Bug #8** -- `rs_is_leading` always false | Full Confluence stage NEVER displays |
| P0 | **Bug #9** -- `resistCount` never updated | Dashboard always shows "0 Level(s)" |
| P1 | **Bug #2** -- Division by zero (6 locations) | Runtime errors on edge cases |
| P1 | **Bug #6** -- Duplicate `request.security` | Wastes 1 of your limited MTF calls |
| P2 | **Bug #4** -- `f_check_x` NA guards | False EMA cross signals |
| P2 | **Bug #5** -- Benchmark 0.0 fallback | Inflated alpha scores |
| P2 | **Enhancement #3** -- Pullback low param | Missed bounce signals in screener |
| P3 | **Bug #7** -- ADX 20 vs 25 | Cross-platform signal drift |
| P3 | **Bug #10** -- 5-star vs 6-star | Spec alignment |
| P3 | **Enhancement #4** -- Pullback alert | Missing alert channel |
