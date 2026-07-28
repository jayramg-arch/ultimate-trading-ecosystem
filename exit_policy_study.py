"""exit_policy_study.py — which exit policy is best, given the entries we already take?

Implements docs/PREREG_exit_policy_study.md EXACTLY. Six fixed configurations, declared
before any was run, evaluated per family on a fixed IS/OOS split.

DESIGN
------
Entries are held CONSTANT: every config replays the same 1,103 trades from the 48-month
run (20260728_191035). Only the exit policy varies, which isolates the question Jay
asked — given the entries the screener already produces, which exit scheme is best?

The simulator here is written SEPARATELY from replay.py (production untouched). That
makes E0 a genuine control: if this reimplementation cannot reproduce the recorded
per-trade returns, the whole comparison is void and says so.

WHY THE STOP AND THE TRAIL ARE ONE PARAMETER NOW
------------------------------------------------
Dhan's Trailing SL preserves its gap and ratchets — it can never be tighter than where
it started. So the initial SL distance IS the trail distance. This study therefore also
bears on the largest known leak (40% of trades dying at the initial stop in ~7 days),
not just on the 12.7% that reach T1.

Usage:
  python exit_policy_study.py [--details validation_runs/validation_20260728_191035_details.csv]
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

COST_PER_LEG = 0.10          # matches replay.COST_PER_LEG_DEFAULT
ATR_LEN = 14
IS_END = pd.Timestamp("2024-06-01")     # IS = anchors before this; OOS = on/after
DETAILS_DEFAULT = "validation_runs/validation_20260728_191035_details.csv"


# ── configurations (FIXED — see the prereg; do not add cells after seeing results) ──
def _cfg(**kw):
    base = dict(
        trail_mode="chandelier",     # chandelier | ratchet
        trail_atr_mult=4.5,          # chandelier gap
        trail_jump_atr=1.5,          # ratchet step
        target_mode="fixed",         # fixed | none   (per-leg trailing set below)
        target_jump_atr=0.5,         # trailing-target step (small on purpose)
        # PER-LEG trailing (bugfix 28-Jul): Gemini's plan is OCO-1 FIXED T1 + OCO-2
        # TRAILING target. A single target_mode trailed BOTH legs, so the fixed T1 ran
        # away and could never fill — E3 was not testing the plan as written.
        t1_trailing=False,
        t2_trailing=False,
        t1_qty=None,                 # None -> catalyst-aware default
        t2_qty=None,
        breakeven_after_t1=True,
        tighten_at_r=None,           # None or ATR multiple to tighten the gap to at +1R
        ratchet_lag=False,           # step the ratchet on the PRIOR bar's high
        family_override=None,        # dict(fam -> overrides)
    )
    base.update(kw)
    return base


CONFIGS = {
    # control — current production behaviour
    "E0_control": _cfg(),
    # full position sits behind ONE trailing target: it runs away, but a violent spike
    # can still pierce it (t1_qty=100), which is what actually happens on Dhan.
    "E1_dhan_native": _cfg(trail_mode="ratchet", breakeven_after_t1=False,
                           t1_trailing=True, t1_qty=100, t2_qty=0),
    "E2_dhan_tighten1R": _cfg(trail_mode="ratchet", breakeven_after_t1=False,
                              t1_trailing=True, t1_qty=100, t2_qty=0,
                              family_override={"POS": {"tighten_at_r": 4.5},
                                               "SWG": {"tighten_at_r": 1.5}}),
    # Gemini as written: OCO-1 50% FIXED T1, OCO-2 50% TRAILING target, 1.5x everywhere
    "E3_gemini": _cfg(trail_mode="ratchet", breakeven_after_t1=False,
                      t1_trailing=False, t1_qty=50,
                      t2_trailing=True, t2_qty=50,
                      trail_jump_atr=1.5, target_jump_atr=1.5),
    # Claude: POS = one order, trailing target, tighten at 1R; SWG = 50/50 fixed T1+T2
    "E4_claude": _cfg(trail_mode="ratchet", breakeven_after_t1=False,
                      family_override={
                          "POS": {"t1_trailing": True, "t1_qty": 100, "t2_qty": 0,
                                  "tighten_at_r": 4.5},
                          "SWG": {"t1_trailing": False, "t2_trailing": False,
                                  "t1_qty": 50, "t2_qty": 50, "tighten_at_r": 1.5}}),
    "E5_pure_trail": _cfg(trail_mode="ratchet", target_mode="none",
                          breakeven_after_t1=False, t1_qty=0, t2_qty=0),
}


def _catalyst_qty(cat: str):
    """replay.py's catalyst-aware scale-out (the CONTROL's behaviour)."""
    c = str(cat or "").upper()
    if c.startswith("SWG-GAP") or c == "SWG-REV":
        return 50, 50
    if c.startswith("SWG"):
        return 33, 33
    return 25, 25


def _family(cat: str) -> str:
    return "SWG" if str(cat or "").upper().startswith("SWG") else "POS"


def _atr(df, n=ATR_LEN):
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def simulate(df, entry_pos, entry_price, sl_price, t1_price, t2_price,
             max_bars, cfg, cat) -> dict | None:
    """Generalized exit simulator. Mirrors replay._simulate_one_trade for the control
    path, and adds Dhan's ratcheting stop / trailing target."""
    if df is None or df.empty or entry_pos < 0 or entry_pos >= len(df):
        return None
    end = min(entry_pos + 1 + max_bars, len(df))
    win = df.iloc[entry_pos + 1:end]
    if win.empty:
        return None

    t1q, t2q = cfg["t1_qty"], cfg["t2_qty"]
    if t1q is None or t2q is None:
        _a, _b = _catalyst_qty(cat)
        t1q = _a if t1q is None else t1q
        t2q = _b if t2q is None else t2q
    if cfg["target_mode"] == "none":
        t1_price = t2_price = None

    atr_s = _atr(df)
    qty = 100.0
    realized = 0.0
    hit_sl = hit_t1 = hit_t2 = False
    hit_init = hit_trail = False
    reason = ""
    trail_sl = sl_price
    gap = entry_price - sl_price          # ratchet keeps THIS gap
    step_anchor = entry_price             # last price level the ratchet stepped from
    tgt_anchor = entry_price
    highest_close = entry_price
    lo, hi = float("inf"), -float("inf")
    days = 0
    prev_high = entry_price
    tightened = False
    exit_px = None

    tighten = cfg["tighten_at_r"]
    r_unit = entry_price - sl_price

    for i, (_, row) in enumerate(win.iterrows()):
        days = i + 1
        b_lo, b_hi, b_cl = float(row["Low"]), float(row["High"]), float(row["Close"])
        lo, hi = min(lo, b_lo), max(hi, b_hi)
        pos = entry_pos + 1 + i
        atr_now = float(atr_s.iloc[pos]) if pos < len(atr_s) else np.nan
        atr_ok = not np.isnan(atr_now)

        # --- tighten once at +1R (Dhan: you manually reduce the gap; it is preserved after)
        if tighten and atr_ok and not tightened and r_unit > 0 and b_hi >= entry_price + r_unit:
            new_gap = atr_now * tighten
            if new_gap < gap:
                gap = new_gap
                trail_sl = max(trail_sl, (entry_price + r_unit) - gap)
                step_anchor = max(step_anchor, entry_price + r_unit)
            tightened = True

        # --- stop update
        if cfg["trail_mode"] == "chandelier":
            if atr_ok:
                trail_sl = max(trail_sl, highest_close - atr_now * cfg["trail_atr_mult"])
        else:  # ratchet: gap-preserving, steps when price advances by jump
            if atr_ok:
                jump = atr_now * cfg["trail_jump_atr"]
                # ROBUSTNESS: with ratchet_lag the step uses the PRIOR bar's high, so the
                # stop is never raised by an intrabar move that may have occurred AFTER
                # the low that then stops us out. Mirrors how the Chandelier consumes
                # prior-bar closes. Sensitivity check, not a new pre-registered cell.
                _ref = prev_high if cfg["ratchet_lag"] else b_hi
                if jump > 0 and _ref >= step_anchor + jump:
                    steps = np.floor((_ref - step_anchor) / jump)
                    step_anchor += steps * jump
                    trail_sl = max(trail_sl, step_anchor - gap)

        # --- target update: PER LEG. Only a leg flagged trailing ratchets away; a
        # fixed leg stays put (Gemini's OCO-1 must be able to actually fill).
        if atr_ok and (cfg["t1_trailing"] or cfg["t2_trailing"]):
            tjump = atr_now * cfg["target_jump_atr"]
            if tjump > 0 and b_hi >= tgt_anchor + tjump:
                steps = np.floor((b_hi - tgt_anchor) / tjump)
                tgt_anchor += steps * tjump
                if cfg["t1_trailing"] and t1_price is not None:
                    t1_price += steps * tjump
                if cfg["t2_trailing"] and t2_price is not None:
                    t2_price += steps * tjump

        # --- same-bar priority: SL -> T1 -> T2 (pessimistic, mirrors production)
        if b_lo <= trail_sl and qty > 0:
            realized += (trail_sl - entry_price) / entry_price * 100 * (qty / 100.0)
            qty = 0
            hit_sl = True
            if trail_sl == sl_price:
                hit_init, reason = True, "SL hit"
            else:
                hit_trail, reason = True, "Trail SL"
            exit_px = trail_sl
            break

        if t1_price is not None and t1q > 0 and b_hi >= t1_price and not hit_t1 and qty > 0:
            q = min(qty, float(t1q))
            realized += (t1_price - entry_price) / entry_price * 100 * (q / 100.0)
            qty -= q
            hit_t1 = True
            if cfg["breakeven_after_t1"]:
                trail_sl = max(trail_sl, entry_price)

        if t2_price is not None and t2q > 0 and b_hi >= t2_price and not hit_t2 and qty > 0:
            q = min(qty, float(t2q))
            realized += (t2_price - entry_price) / entry_price * 100 * (q / 100.0)
            qty -= q
            hit_t2 = True

        highest_close = max(highest_close, b_cl)
        prev_high = b_hi

    if qty > 0:
        fc = float(win["Close"].iloc[-1])
        realized += (fc - entry_price) / entry_price * 100 * (qty / 100.0)
        if not reason:
            reason = "Time expiry"
        exit_px = fc

    n_legs = 2 + (1 if hit_t1 else 0) + (1 if hit_t2 else 0)
    realized -= n_legs * COST_PER_LEG
    return {"ret": round(realized, 2), "reason": reason, "days": days,
            "hit_sl": hit_sl, "hit_init": hit_init, "hit_trail": hit_trail,
            "hit_t1": hit_t1, "hit_t2": hit_t2,
            "runup": round((hi - entry_price) / entry_price * 100, 2) if hi > -np.inf else 0.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--details", default=DETAILS_DEFAULT)
    args = ap.parse_args()

    import data_provider as dp

    d = pd.read_csv(args.details)
    d = d[d["Alpha_Matched_pct"].notna()].copy()
    d["ts"] = pd.to_datetime(d["as_of"])
    d["fam"] = d["Catalyst_used"].map(_family)
    print(f"source trades={len(d)}  symbols={d['Symbol'].nunique()}  "
          f"anchors {d['as_of'].min()} -> {d['as_of'].max()}")

    frames = {}
    for i, s in enumerate(sorted(d["Symbol"].unique()), 1):
        try:
            f = dp.fetch_ohlcv(s, period="10y", interval="1d")
            if f is not None and len(f) >= 260:
                frames[s] = f
        except Exception:
            pass
        if i % 50 == 0:
            print(f"  fetched {i} …", file=sys.stderr)
    print(f"frames: {len(frames)}/{d['Symbol'].nunique()}")

    rows = []
    for _, r in d.iterrows():
        f = frames.get(r["Symbol"])
        if f is None:
            continue
        try:
            cut = f.loc[:r["ts"]]
            if len(cut) < 30:
                continue
            entry_pos = len(cut) - 1
            ep = float(r["Entry_Close"]) if pd.notna(r.get("Entry_Close")) else float(r["Entry"])
            slp = float(r["SL_price"]); t1p = r.get("T1_price"); t2p = r.get("T2_price")
            t1p = float(t1p) if pd.notna(t1p) else None
            t2p = float(t2p) if pd.notna(t2p) else None
            fwd = int(r["forward_days_used"]) if pd.notna(r.get("forward_days_used")) else 30
        except Exception:
            continue

        rec = {"Symbol": r["Symbol"], "ts": r["ts"], "fam": r["fam"],
               "cat": r["Catalyst_used"], "rec_ret": r["Return_pct"],
               "bench": r["Benchmark_Matched_pct"], "days_rec": r["Days_Held"]}
        for name, cfg in CONFIGS.items():
            c = dict(cfg)
            fo = c.get("family_override") or {}
            if r["fam"] in fo:
                c.update(fo[r["fam"]])
            out = simulate(f, entry_pos, ep, slp, t1p, t2p, fwd, c, r["Catalyst_used"])
            if out is None:
                rec[name] = np.nan
            else:
                rec[name] = out["ret"]
                rec[f"{name}__days"] = out["days"]
                rec[f"{name}__init"] = out["hit_init"]
                rec[f"{name}__t1"] = out["hit_t1"]
        rows.append(rec)

    R = pd.DataFrame(rows)
    print(f"simulated {len(R)} trades\n")

    # ---- VALIDITY CHECK: E0 must reproduce the recorded returns ----
    diff = (R["E0_control"] - R["rec_ret"]).abs()
    med, within = diff.median(), (diff <= 1.0).mean()
    print("=== VALIDITY (E0 must reproduce production) ===")
    print(f"  median |E0 - recorded| = {med:.3f}pp   within 1.0pp = {within*100:.1f}%")
    ok = (med <= 0.25) and (within >= 0.95)
    print(f"  {'PASS — comparison is valid' if ok else 'FAIL — STUDY VOID, do not read the table below'}\n")

    # alpha = config return - the SAME matched benchmark leg
    for name in CONFIGS:
        R[f"a_{name}"] = R[name] - R["bench"]

    def block(sub, label):
        print(f"--- {label}  (n={len(sub)}) ---")
        hdr = f"  {'config':18} {'meanA':>7} {'medA':>7} {'win%':>6} {'PF':>6} {'days':>6} {'initSL%':>8} {'T1%':>6}"
        print(hdr)
        base = sub["a_E0_control"].mean()
        for name in CONFIGS:
            a = sub[f"a_{name}"]
            w = sub[name]
            pf_p = w[w > 0].sum(); pf_n = -w[w <= 0].sum()
            pf = (pf_p / pf_n) if pf_n > 0 else np.inf
            dd = f"{name:18} {a.mean():+7.2f} {a.median():+7.2f} {(a>0).mean()*100:6.1f} {pf:6.2f} " \
                 f"{sub[f'{name}__days'].mean():6.1f} {sub[f'{name}__init'].mean()*100:8.1f} {sub[f'{name}__t1'].mean()*100:6.1f}"
            mark = "  <-- control" if name == "E0_control" else (f"   ({a.mean()-base:+.2f}pp)")
            print("  " + dd + mark)
        print()

    IS = R[R["ts"] < IS_END]
    OOS = R[R["ts"] >= IS_END]
    for fam in ("POS", "SWG"):
        block(IS[IS["fam"] == fam], f"IN-SAMPLE · {fam}")
        block(OOS[OOS["fam"] == fam], f"OUT-OF-SAMPLE · {fam}")

    # ---- adoption rule ----
    print("=== ADOPTION (prereg: IS >= +1.0pp vs E0, OOS also beats E0, median not worse by >1.0pp) ===")
    for fam in ("POS", "SWG"):
        i_s, o_s = IS[IS["fam"] == fam], OOS[OOS["fam"] == fam]
        b_i, b_o = i_s["a_E0_control"].mean(), o_s["a_E0_control"].mean()
        bm_i = i_s["a_E0_control"].median()
        winner = None
        for name in CONFIGS:
            if name == "E0_control":
                continue
            A = i_s[f"a_{name}"].mean() - b_i >= 1.0
            B = o_s[f"a_{name}"].mean() > b_o
            C = i_s[f"a_{name}"].median() >= bm_i - 1.0
            print(f"  {fam} {name:18} IS{i_s[f'a_{name}'].mean()-b_i:+6.2f}pp {'PASS' if A else 'fail':4} | "
                  f"OOS{o_s[f'a_{name}'].mean()-b_o:+6.2f}pp {'PASS' if B else 'fail':4} | "
                  f"med {'PASS' if C else 'fail'}")
            if A and B and C and winner is None:
                winner = name
        print(f"  --> {fam}: {'ADOPT ' + winner if winner else 'KEEP E0 (nothing cleared the rule)'}\n")

    R.to_csv("validation_runs/_exit_policy_study.csv", index=False)
    print("saved: validation_runs/_exit_policy_study.csv")


if __name__ == "__main__":
    main()
