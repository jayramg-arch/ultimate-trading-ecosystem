"""review_many.py — queue several names for the AI reviewer in one go (25-Sep-2026).

Called by REVIEW.bat. Accepts any mix of these, separated by spaces, commas or newlines:

    TITAN 75            symbol then timeframe
    TITAN:125           symbol:timeframe
    GOLDBEES            no timeframe -> 75
    RRKABEL D           D = daily

    REVIEW.bat TITAN 75 RRKABEL 125 GOLDBEES:D NIFTYBEES

Each name is POSTed to the local receiver (:8000) exactly like an S4 GO alert, so it takes
the same path: the queue (ONE worker — they are reviewed one after another, ~90 s each),
the 30-min dedup, the reviewer's own tabs, the banner, Telegram and the Reviewer Log.
"""
import os
import re
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
TFS = {"75": "75", "125": "125", "D": "D", "1D": "D", "DAILY": "D"}


def key():
    try:
        for line in open(os.path.join(HERE, ".env"), encoding="utf-8"):
            if line.strip().upper().startswith("S4_REVIEW_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def parse(text):
    """Tokens -> [(SYMBOL, TF)]. A token that is a timeframe attaches to the symbol before it."""
    toks = [t for t in re.split(r"[\s,;]+", text.strip()) if t]
    out = []
    for t in toks:
        if ":" in t:
            s, tf = t.split(":", 1)
            out.append([s.upper(), TFS.get(tf.upper(), tf.upper())])
        elif t.upper() in TFS and out:
            out[-1][1] = TFS[t.upper()]
        else:
            out.append([t.upper(), None])
    return [(s, tf or "75") for s, tf in out if s]


def main():
    text = " ".join(sys.argv[1:])
    if not text:
        text = input("Names and timeframes (e.g. TITAN 75, RRKABEL 125, GOLDBEES D): ")
    pairs = parse(text)
    if not pairs:
        print("  nothing to review")
        return 1
    k = key()
    if not k:
        print("  [X] S4_REVIEW_KEY missing from .env")
        return 1
    print(f"\n  queueing {len(pairs)} review(s) — one at a time, about 90 s each:")
    bad = 0
    for s, tf in pairs:
        try:
            r = requests.post(f"http://127.0.0.1:8000/s4-review?key={k}",
                              data=f"{s} S4 GO {tf} - manual".encode("utf-8"), timeout=10)
            print(f"   {s:14} {tf:>4}   {r.text.strip()[:90]}")
        except requests.RequestException:
            bad += 1
            print(f"   {s:14} {tf:>4}   [X] receiver not answering on :8000 — is the S4 Alert Reviewer window up?")
    print("\n  Watch the banner; each ruling lands on Telegram and in the Reviewer Log.")
    print('  "duplicate within 30 min" = that name and timeframe was read recently.')
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
