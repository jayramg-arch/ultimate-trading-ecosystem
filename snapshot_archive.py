"""
snapshot_archive.py — Forward-archive of Chartink + Screener.in CSVs.

Purpose: today we lack historical Screener.in data, so fundamental_replay.py
falls back to yfinance (limited depth, often missing). Going forward we
snapshot the daily output of the production scrape to a dated folder so that
a year from now we have *real* historical Screener.in fundamentals — and
historical Chartink scan output as well — for proper validation.

Layout:
  data/snapshots/YYYY-MM-DD/
      MASTER_scan_results.csv        # Screener.in fundamentals snapshot
      FINAL_Hunter_Picks.csv         # 4 Chartink bull scans
      FINAL_Pullback_Picks.csv
      FINAL_EarlyBird_Picks.csv
      FINAL_Leader_Picks.csv
      FINAL_Recovery_*.csv           # Recovery scans
      FINAL_WATCHLIST.csv            # Combined matcher output
      manifest.json                   # what was archived + size + sha

Public API:
  snapshot_today(src_dir=None)             -> dict   # archive + manifest
  available_dates()                         -> list[str]
  load_snapshot_master(date)                -> pd.DataFrame
  load_snapshot_finals(date)                -> dict[str, pd.DataFrame]
  nearest_snapshot(date)                    -> str | None
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from datetime import datetime, date
from typing import Optional

import pandas as pd


logger = logging.getLogger(__name__)

ROOT_DIR     = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT_DIR = os.path.join(ROOT_DIR, "data", "snapshots")

# Files we archive in each snapshot. Anything missing is recorded in manifest
# as "missing" but does not abort the snapshot.
ARCHIVED_FILES: list[str] = [
    "MASTER_scan_results.csv",
    "FINAL_Hunter_Picks.csv",
    "FINAL_Pullback_Picks.csv",
    "FINAL_EarlyBird_Picks.csv",
    "FINAL_Leader_Picks.csv",
    "FINAL_Hunter_Picks_RRG.csv",
    "FINAL_Pullback_Picks_RRG.csv",
    "FINAL_EarlyBird_Picks_RRG.csv",
    "FINAL_Leader_Picks_RRG.csv",
    "FINAL_Recovery_ClimaxBounce.csv",
    "FINAL_Recovery_EarlyBirds.csv",
    "FINAL_Recovery_RSLeaders.csv",
    "FINAL_COMBINED_BULL_PICKS.csv",
    "FINAL_COMBINED_RECOVERY_PICKS.csv",
    "FINAL_COMBINED_PICKS.csv",
    "FINAL_WATCHLIST.csv",
]


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def snapshot_today(src_dir: Optional[str] = None,
                     overwrite: bool = False) -> dict:
    """Copy the production scan output to data/snapshots/{today}.
    `overwrite=True` replaces an existing same-day snapshot."""
    src = src_dir or ROOT_DIR
    today = date.today().isoformat()
    dest_dir = os.path.join(SNAPSHOT_DIR, today)
    if os.path.isdir(dest_dir) and not overwrite:
        manifest = _read_manifest(dest_dir)
        manifest["status"] = "already-exists"
        return manifest
    os.makedirs(dest_dir, exist_ok=True)

    archived, missing = [], []
    total_bytes = 0
    for fname in ARCHIVED_FILES:
        src_path = os.path.join(src, fname)
        if not os.path.isfile(src_path):
            missing.append(fname)
            continue
        dst_path = os.path.join(dest_dir, fname)
        shutil.copy2(src_path, dst_path)
        size = os.path.getsize(dst_path)
        total_bytes += size
        archived.append({"file": fname, "size_bytes": size,
                          "sha256_16": _sha256(dst_path)})

    manifest = {
        "snapshot_date":  today,
        "captured_at":    datetime.now().isoformat(timespec="seconds"),
        "src_dir":        os.path.abspath(src),
        "n_archived":     len(archived),
        "n_missing":      len(missing),
        "total_bytes":    total_bytes,
        "archived":       archived,
        "missing":        missing,
    }
    with open(os.path.join(dest_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)
    return manifest


def _read_manifest(snapshot_dir: str) -> dict:
    p = os.path.join(snapshot_dir, "manifest.json")
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def available_dates() -> list[str]:
    """Sorted list of YYYY-MM-DD strings for which we have snapshots."""
    if not os.path.isdir(SNAPSHOT_DIR):
        return []
    out = []
    for entry in os.listdir(SNAPSHOT_DIR):
        full = os.path.join(SNAPSHOT_DIR, entry)
        if os.path.isdir(full):
            try:
                datetime.strptime(entry, "%Y-%m-%d")
                out.append(entry)
            except ValueError:
                continue
    return sorted(out)


def load_snapshot_master(snap_date: str) -> pd.DataFrame:
    """Load a date's MASTER_scan_results.csv (Screener.in fundamentals)."""
    path = os.path.join(SNAPSHOT_DIR, snap_date, "MASTER_scan_results.csv")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"no MASTER_scan_results.csv for {snap_date}")
    return pd.read_csv(path)


def load_snapshot_finals(snap_date: str) -> dict[str, pd.DataFrame]:
    """Load all FINAL_*.csv frames for a date as a dict keyed by basename."""
    snap_dir = os.path.join(SNAPSHOT_DIR, snap_date)
    if not os.path.isdir(snap_dir):
        raise FileNotFoundError(f"no snapshot for {snap_date}")
    out: dict[str, pd.DataFrame] = {}
    for entry in os.listdir(snap_dir):
        if entry.startswith("FINAL_") and entry.endswith(".csv"):
            try:
                out[entry] = pd.read_csv(os.path.join(snap_dir, entry))
            except Exception as e:
                logger.debug("load_snapshot_finals: %s -> %s", entry, e)
    return out


def nearest_snapshot(target_date: str,
                       direction: str = "back") -> Optional[str]:
    """Find the snapshot date nearest to `target_date` (ISO YYYY-MM-DD).
    direction='back': latest snapshot ≤ target (no look-ahead). Default.
    direction='any':  closest snapshot in either direction.
    """
    dates = available_dates()
    if not dates:
        return None
    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    if direction == "back":
        before = [d for d in dates
                    if datetime.strptime(d, "%Y-%m-%d").date() <= target]
        return before[-1] if before else None
    # direction='any'
    return min(dates,
                 key=lambda d: abs((datetime.strptime(d, "%Y-%m-%d").date()
                                     - target).days))


__all__ = [
    "snapshot_today", "available_dates",
    "load_snapshot_master", "load_snapshot_finals",
    "nearest_snapshot",
    "ARCHIVED_FILES", "SNAPSHOT_DIR",
]


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "encoding") and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try: sys.stdout.reconfigure(encoding="utf-8")
        except Exception: pass

    m = snapshot_today()
    print(json.dumps(m, indent=2, default=str))
    print(f"\navailable snapshot dates: {available_dates()}")
