# -*- coding: utf-8 -*-
"""Quarantine cache frames written during a bad run — MOVE, never delete.

WHY THIS EXISTS. When the paid feed fails, data_provider falls back to yfinance and
the frame it gets is cached under a FRESH timestamp like any other. The cache records
no provenance, so a yfinance frame and a Dhan frame are indistinguishable on disk —
and every later reader (screeners, the GM board, FINAL_*.csv) will serve the fallback
data as good until its TTL expires. On 3-Sep-2026 a single DH-905 on ^CNXFIN latched
_AUTH_FAILED for 300s and put ~500 equities on yfinance inside one auto-pilot run;
2,782 cache files were written in 30 minutes.

BECAUSE PROVENANCE IS NOT STORED, THIS TOOL CANNOT BE SURGICAL. It selects by
MODIFICATION TIME, so it will also move frames the run fetched correctly from Dhan.
That is the intended trade: a re-fetch costs minutes, while a silently-wrong price
feeds a trade decision. Do not reach for a cleverer filter — there is no field to
filter on.

MOVE, NOT DELETE, for the same reason the journal work never deletes a row on
inference: if the diagnosis was wrong, `--restore` puts every file back byte-for-byte.
The house precedent is data/market_cache.backup_20260708.

STOP THE AUTO-PILOT FIRST. A running process holds its own module state (including
the failure latch) and will keep writing into the cache while this moves files out.

    python cache_quarantine.py --minutes 60              # what WOULD move
    python cache_quarantine.py --minutes 60 --apply      # move it
    python cache_quarantine.py --restore data/_quarantine/20260904_003012
"""
from __future__ import annotations
import argparse
import os
import shutil
import sys
import time
from datetime import datetime

CACHE_DIR = os.path.join("data", "market_cache")
QUAR_ROOT = os.path.join("data", "_quarantine")


def _human(nbytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024 or unit == "GB":
            return f"{nbytes:,.1f} {unit}"
        nbytes /= 1024.0


def _scan(cache_dir: str, minutes: float) -> list:
    """Files modified within the window, newest first. Recurses: the cache is flat
    today, but a nested layout must not silently fall out of the selection."""
    cutoff = time.time() - minutes * 60.0
    hits = []
    for root, _dirs, files in os.walk(cache_dir):
        for fn in files:
            p = os.path.join(root, fn)
            try:
                st = os.stat(p)
            except OSError:
                continue                      # vanished mid-scan; nothing to move
            if st.st_mtime >= cutoff:
                hits.append((p, st.st_mtime, st.st_size))
    hits.sort(key=lambda t: t[1], reverse=True)
    return hits


def quarantine(cache_dir: str, minutes: float, apply: bool) -> int:
    if not os.path.isdir(cache_dir):
        print(f"cache dir not found: {cache_dir}")
        return 1
    hits = _scan(cache_dir, minutes)
    total = sum(h[2] for h in hits)
    allf = sum(len(f) for _r, _d, f in os.walk(cache_dir))
    print(f"cache      : {cache_dir}  ({allf:,} files)")
    print(f"window     : last {minutes:g} min")
    print(f"selected   : {len(hits):,} files  ({_human(total)})")
    if not hits:
        print("nothing in the window — the cache is already clean for that period.")
        return 0
    newest = datetime.fromtimestamp(hits[0][1]).strftime("%H:%M:%S")
    oldest = datetime.fromtimestamp(hits[-1][1]).strftime("%H:%M:%S")
    print(f"written    : {oldest} .. {newest}")
    print("sample     : " + ", ".join(os.path.basename(h[0]) for h in hits[:5]))

    if not apply:
        print("\nDRY RUN — nothing moved. Re-run with --apply to quarantine these.")
        return 0

    dest = os.path.join(QUAR_ROOT, datetime.now().strftime("%Y%m%d_%H%M%S"))
    os.makedirs(dest, exist_ok=True)
    moved = failed = 0
    for p, _mt, _sz in hits:
        rel = os.path.relpath(p, cache_dir)
        out = os.path.join(dest, rel)
        try:
            os.makedirs(os.path.dirname(out), exist_ok=True)
            shutil.move(p, out)               # move: the file is never in two places
            moved += 1
        except Exception as e:
            failed += 1
            print(f"  ! could not move {rel}: {type(e).__name__}: {e}")
    # The manifest is what makes --restore trustworthy: it records the window and the
    # count, so a later restore can be checked against what was actually taken.
    with open(os.path.join(dest, "_MANIFEST.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"quarantined  {datetime.now():%Y-%m-%d %H:%M:%S}\n"
                 f"from         {os.path.abspath(cache_dir)}\n"
                 f"window       last {minutes:g} minutes\n"
                 f"files moved  {moved}\n"
                 f"files failed {failed}\n"
                 f"bytes        {total}\n"
                 f"reason       cache written during a run that fell back to yfinance;\n"
                 f"             provenance is not stored, so selection is by mtime.\n")
    print(f"\nmoved {moved:,} files -> {dest}")
    if failed:
        print(f"{failed} could not be moved (likely open by a running process — "
              f"stop the auto-pilot and re-run)")
    print("next: re-run the auto-pilot and confirm the first fetches say 'served by dhan'.")
    print(f"undo: python {os.path.basename(__file__)} --restore {dest}")
    return 0


def restore(src: str, cache_dir: str) -> int:
    if not os.path.isdir(src):
        print(f"quarantine dir not found: {src}")
        return 1
    back = failed = 0
    for root, _dirs, files in os.walk(src):
        for fn in files:
            if fn == "_MANIFEST.txt":
                continue
            p = os.path.join(root, fn)
            out = os.path.join(cache_dir, os.path.relpath(p, src))
            try:
                os.makedirs(os.path.dirname(out), exist_ok=True)
                # A file re-fetched since the quarantine is NEWER and better than the
                # one being restored, so it is left alone rather than overwritten.
                if os.path.exists(out):
                    continue
                shutil.move(p, out)
                back += 1
            except Exception as e:
                failed += 1
                print(f"  ! {fn}: {type(e).__name__}: {e}")
    print(f"restored {back:,} files to {cache_dir}"
          + (f"  ({failed} failed)" if failed else ""))
    print("files already re-fetched since the quarantine were left in place.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", default=CACHE_DIR)
    ap.add_argument("--minutes", type=float, default=60.0,
                    help="quarantine cache files modified within this many minutes")
    ap.add_argument("--apply", action="store_true",
                    help="actually move the files (default is a dry run)")
    ap.add_argument("--restore", metavar="DIR",
                    help="put a previous quarantine back into the cache")
    a = ap.parse_args()
    sys.exit(restore(a.restore, a.cache) if a.restore
             else quarantine(a.cache, a.minutes, a.apply))
