#!/usr/bin/env python3
"""debate_ab.py - the pre-registered A/B of a debate-style Reviewer (docs/PREREG_debate_reviewer.md).

    python debate_ab.py --placebo        scoring code on RANDOM rulings (no model calls) - must FAIL
    python debate_ab.py --plumbing 5     5 rows through both arms; rulings printed, outcomes NOT shown
    python debate_ab.py --run            every unit once; cached per row; writes the result once

A = the live single Reviewer; B = BULL brief + BEAR brief, then the same Reviewer prompt as JUDGE.
Both arms read the identical saved panel read, with an empty position context, no current market
line and no house gates. Outcome = entry_shadow R10 (S_4atrD; no fill = 0R). Separation S = mean R10
of TAKE - mean R10 of non-TAKE; CIs by symbol-block bootstrap.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SHADOW = os.path.join(HERE, "logs", "entry_shadow.csv")
LOG = os.path.join(HERE, "logs", "ai_review_log.csv")
REVIEWS = os.path.join(HERE, "logs", "ai_reviews")
OUTDIR = os.path.join(HERE, "data", "debate_ab")
CACHE = os.path.join(OUTDIR, "cache")
RESULT = os.path.join(OUTDIR, "result.json")
PREREG = os.path.join(HERE, "docs", "PREREG_debate_reviewer.md")
REG_CUTOFF = "2026-10-13 23:59"            # last trigger in the registered set (rows after are not added)
H1_EDGE, H2_SEP, MIN_N, MIN_SIDE, BOOT = 0.15, 0.10, 100, 20, 10000

ADVOCATE = """You are one of two advocates briefing a senior NSE price-action trader before he rules on a
trade. You do NOT rule. You argue ONE side only, as strongly as the evidence allows.
Rules: at most 200 words; 3 to 5 numbered points; every point must cite a number that appears in the
panel read (a price, a level, an R, a percentage, a score, a count) - a point without a panel number
is worthless; do not invent levels or data; plain text, no LaTeX, no headings."""
BULL = "Argue FOR taking this trade now, as S4 plans it (entry, stop, targets on the panel)."
BEAR = "Argue AGAINST taking this trade now (WAIT for something specific, or PASS). Name what is wrong."


# ── units ──────────────────────────────────────────────────────────────────────────────
def units() -> pd.DataFrame:
    E = pd.read_csv(SHADOW)
    E = E[(E["variant"] == "S_4atrD") & E["status"].isin(["scored", "no fill"])].copy()
    E = E[E["ts"].astype(str) <= REG_CUTOFF]
    L = pd.read_csv(LOG, on_bad_lines="skip")[["ts", "symbol", "tf", "file", "ai_ruling"]]
    L = L.drop_duplicates(["ts", "symbol", "tf"])
    U = E.merge(L, on=["ts", "symbol", "tf"], how="left")
    U["md"] = U["file"].map(lambda f: os.path.join(REVIEWS, os.path.basename(f.replace("\\", "/")))
                            if isinstance(f, str) else None)
    U = U[U["md"].map(lambda p: bool(p) and os.path.exists(p))].copy()
    U["y"] = np.where(U["status"] == "no fill", 0.0, pd.to_numeric(U["R10"], errors="coerce"))
    U = U[U["y"].notna()].reset_index(drop=True)
    return U


def panel_read(md: str) -> str:
    t = open(md, encoding="utf-8").read()
    m = re.search(r"## PANEL READ\s*```\n(.*)\n```", t, re.S)
    return m.group(1) if m else ""


def word(ruling: str) -> str | None:
    m = re.search(r"\b(TAKE|WAIT|PASS)\b", str(ruling or "").upper())
    return m.group(1) if m else None


# ── model calls ────────────────────────────────────────────────────────────────────────
def _sr():
    import s4_review as sr
    sr.market_context = lambda: ""          # today's market line would leak the present
    return sr


def _advocate(side: str, read_txt: str) -> str:
    sr = _sr()
    from google import genai
    errs = []
    for model, key_env in ((sr.GEMINI_MODEL, "GEMINI_API_KEY"), (sr.GEMINI_FALLBACK_MODEL, "GEMINI_API_KEY_2")):
        if not model:
            continue
        try:
            key = os.getenv(key_env) or os.getenv("GEMINI_API_KEY")
            c = genai.Client(api_key=key, http_options={"timeout": 180_000})
            r = c.models.generate_content(model=model, contents=ADVOCATE + "\n\n" + side + "\n\nPANEL READ\n" + read_txt)
            txt = (getattr(r, "text", "") or "").strip()
            if txt:
                return txt
        except Exception as e:
            errs.append(str(e)[:160])
    raise RuntimeError("advocate: " + " | ".join(errs))


def _rule(prompt: str) -> tuple[str, str]:
    sr = _sr()
    txt, prov = sr.deliberate(prompt, "auto")
    if sr._placeholder_echo(txt) or not word(sr._ruling_line(txt)):
        txt, prov = sr.deliberate(prompt + "\n\nYOUR PREVIOUS ANSWER DID NOT STATE A RULING. Write the RULING "
                                  "line out in full: TAKE, TAKE · reduced size, WAIT (with what) or PASS.", "auto")
    return txt, prov


def run_row(md: str) -> dict:
    os.makedirs(CACHE, exist_ok=True)
    cp = os.path.join(CACHE, os.path.basename(md) + ".json")
    if os.path.exists(cp):
        return json.load(open(cp, encoding="utf-8"))
    sr = _sr()
    read_txt = panel_read(md)
    base = sr.build_prompt(read_txt, "")
    a_txt, a_prov = _rule(base)
    bull = _advocate(BULL, read_txt)
    bear = _advocate(BEAR, read_txt)
    judge = (base + "\n\nTWO ADVOCATES HAVE BRIEFED YOU ON THIS TRADE. Weigh both against the panel; an "
             "argument that cites no panel number counts for nothing, and neither advocate decides for you.\n\n"
             "BULL CASE (for taking it)\n%s\n\nBEAR CASE (against taking it now)\n%s" % (bull, bear))
    b_txt, b_prov = _rule(judge)
    rec = {"md": os.path.basename(md), "A": a_txt, "A_prov": a_prov, "bull": bull, "bear": bear, "B": b_txt,
           "B_prov": b_prov, "A_ruling": sr._ruling_line(a_txt), "B_ruling": sr._ruling_line(b_txt),
           "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    tmp = cp + ".tmp"
    json.dump(rec, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, cp)
    return rec


# ── scoring ────────────────────────────────────────────────────────────────────────────
def separation(df: pd.DataFrame, col: str) -> float | None:
    t = df[df[col] == "TAKE"]["y"]
    n = df[df[col].isin(["WAIT", "PASS"])]["y"]
    if not len(t) or not len(n):
        return None
    return float(t.mean() - n.mean())


def score(df: pd.DataFrame, seed: int = 7) -> dict:
    """df: y, symbol, A, B (TAKE/WAIT/PASS or None)."""
    d = df[df["A"].notna() & df["B"].notna()].copy()
    sa, sb = separation(d, "A"), separation(d, "B")
    out = {"n": int(len(d)), "symbols": int(d["symbol"].nunique()),
           "A_take": int((d["A"] == "TAKE").sum()), "B_take": int((d["B"] == "TAKE").sum()),
           "S_A": sa, "S_B": sb, "diff": (sb - sa) if (sa is not None and sb is not None) else None,
           "agree_pct": float((d["A"] == d["B"]).mean() * 100) if len(d) else None}
    rng = np.random.default_rng(seed)
    syms = d["symbol"].unique()
    groups = {s: d[d["symbol"] == s] for s in syms}
    diffs, sbs = [], []
    for _ in range(BOOT):
        bs = pd.concat([groups[s] for s in rng.choice(syms, size=len(syms), replace=True)])
        a, b = separation(bs, "A"), separation(bs, "B")
        if a is not None and b is not None:
            diffs.append(b - a)
            sbs.append(b)
    out["diff_ci"] = [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))] if diffs else None
    out["S_B_ci"] = [float(np.percentile(sbs, 2.5)), float(np.percentile(sbs, 97.5))] if sbs else None
    nt = lambda c: int((d[c] == "TAKE").sum())
    nn = lambda c: int(d[c].isin(["WAIT", "PASS"]).sum())
    thin = len(d) < MIN_N or min(nt("A"), nn("A"), nt("B"), nn("B")) < MIN_SIDE
    h1 = (out["diff"] is not None and out["diff"] >= H1_EDGE and out["diff_ci"] and out["diff_ci"][0] > 0)
    h2 = (sb is not None and sb >= H2_SEP and out["S_B_ci"] and out["S_B_ci"][0] > 0)
    out.update({"H1": bool(h1), "H2": bool(h2), "verdict": "THIN" if thin else ("PASS" if (h1 and h2) else "FAIL")})
    return out


def _fmt(s: dict) -> str:
    f = lambda v: "—" if v is None else "%+.3fR" % v
    ci = lambda c: "—" if not c else "[%+.3f, %+.3f]" % tuple(c)
    return ("n %d (%d symbols) · TAKE A %d / B %d · agree %.0f %%\n"
            "S(A) %s · S(B) %s CI %s\nS(B) - S(A) %s CI %s\nH1 %s · H2 %s · VERDICT %s" % (
                s["n"], s["symbols"], s["A_take"], s["B_take"], s["agree_pct"] or 0, f(s["S_A"]), f(s["S_B"]),
                ci(s["S_B_ci"]), f(s["diff"]), ci(s["diff_ci"]), s["H1"], s["H2"], s["verdict"]))


# ── modes ──────────────────────────────────────────────────────────────────────────────
def placebo() -> int:
    U = units()
    rng = random.Random(20261020)
    pool = ["TAKE"] * 45 + ["WAIT"] * 30 + ["PASS"] * 25
    U["A"] = [rng.choice(pool) for _ in range(len(U))]
    U["B"] = [rng.choice(pool) for _ in range(len(U))]
    s = score(U[["y", "symbol", "A", "B"]])
    print("PLACEBO (random rulings, no model calls) - must not PASS\n" + _fmt(s))
    return 0 if s["verdict"] != "PASS" else 1


def plumbing(n: int) -> int:
    U = units()
    for md in U["md"].head(n):
        r = run_row(md)
        print("%-40s A: %-40s | B: %s" % (r["md"][:40], (r["A_ruling"] or "?")[:40], (r["B_ruling"] or "?")[:60]))
        print("   bull: %s" % r["bull"][:160].replace("\n", " "))
        print("   bear: %s" % r["bear"][:160].replace("\n", " "))
    print("plumbing: %d rows cached (outcomes not shown)" % n)
    return 0


def run() -> int:
    if os.path.exists(RESULT):
        print("already run - %s exists (pre-registered: one run)" % RESULT)
        return 2
    U = units()
    print("units: %d rows, %d symbols" % (len(U), U["symbol"].nunique()))
    recs, fails = {}, []

    def _one(md):
        try:
            return md, run_row(md), None
        except Exception as e:
            return md, None, str(e)[:200]
    with ThreadPoolExecutor(max_workers=3) as ex:
        for i, (md, rec, err) in enumerate(ex.map(_one, U["md"]), 1):
            if rec:
                recs[md] = rec
            else:
                fails.append((md, err))
            if i % 10 == 0:
                print("  %d / %d done (%d failed)" % (i, len(U), len(fails)), flush=True)
    if fails:
        print("%d rows failed to get answers - re-run --run to resume them before scoring:" % len(fails))
        for md, e in fails[:10]:
            print("   %s: %s" % (os.path.basename(md), e))
        return 3
    U["A"] = U["md"].map(lambda m: word(recs[m]["A_ruling"]))
    U["B"] = U["md"].map(lambda m: word(recs[m]["B_ruling"]))
    U["H"] = U["ai_ruling"].map(word)
    s = score(U[["y", "symbol", "A", "B"]])
    s["dropped_A"] = int(U["A"].isna().sum())
    s["dropped_B"] = int(U["B"].isna().sum())
    s["S_hist"] = separation(U[U["H"].notna()], "H")
    s["take_R"] = {c: (float(U[U[c] == "TAKE"]["y"].mean()) if (U[c] == "TAKE").any() else None) for c in ("A", "B", "H")}
    s["all_R"] = float(U["y"].mean())
    s["calls"] = {"A": len(U), "B": 3 * len(U)}
    os.makedirs(OUTDIR, exist_ok=True)
    U[["ts", "symbol", "tf", "y", "H", "A", "B", "md"]].to_csv(os.path.join(OUTDIR, "rows.csv"), index=False)
    json.dump(s, open(RESULT, "w", encoding="utf-8"), indent=1)
    txt = _fmt(s) + ("\nhistorical live rulings S %s · mean R10 of TAKEs: A %s, B %s, live %s · all rows %+.3fR\n"
                     "dropped (no ruling): A %d, B %d" % (
                         "—" if s["S_hist"] is None else "%+.3fR" % s["S_hist"],
                         *["—" if s["take_R"][c] is None else "%+.3fR" % s["take_R"][c] for c in ("A", "B", "H")],
                         s["all_R"], s["dropped_A"], s["dropped_B"]))
    print("RESULT\n" + txt)
    return 0


def main() -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    a = sys.argv[1:]
    if "--placebo" in a:
        return placebo()
    if "--plumbing" in a:
        return plumbing(int(a[a.index("--plumbing") + 1]) if len(a) > a.index("--plumbing") + 1 else 5)
    if "--run" in a:
        return run()
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
