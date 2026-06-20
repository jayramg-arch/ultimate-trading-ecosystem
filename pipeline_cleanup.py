"""
pipeline_cleanup.py — pre-flight cleanup for the Auto-Pilot.

Running the auto-pilot several times in a short span (e.g. after a hang/reboot)
can leave a mess that makes the NEXT run hang or misbehave:
  • zombie Playwright browser processes (Strike / TradingView) holding RAM and
    locking the profile dirs,
  • stale browser Singleton* lock files that block a fresh Playwright launch,
  • leftover temp_strike_*.csv chunk files,
  • duplicate pick_log rows for today from repeated runs.

`preflight_cleanup()` clears all of that so each run starts from a clean slate.
Wired into run_pipeline.py as Phase 0 (and runnable standalone).

SAFETY — browser processes are matched ONLY by this project's Playwright
user-data-dir paths (strike_user_data / tv_user_data_v2). Your normal Chrome and
any Claude-in-Chrome session are matched by neither and are NEVER touched.
Pick_log dedupe keeps the newest row per (screener, as_of_date, symbol) for TODAY
and never deletes a row already referenced by the evaluations table.
"""
from __future__ import annotations

import os
import sys
import glob
import sqlite3
import logging
import datetime
import subprocess

_DIR = os.path.dirname(os.path.abspath(__file__))
logger = logging.getLogger(__name__)

# Playwright profile dirs the auto-pilot launches browsers under. The kill is
# scoped to processes whose command line references one of these — nothing else.
_PROFILE_DIRS = ("strike_user_data", "tv_user_data_v2")
_LOCK_NAMES = ("SingletonLock", "SingletonCookie", "SingletonSocket")


def _kill_stale_browsers() -> int:
    """Kill chrome/chromium/msedge processes whose command line references this
    project's Playwright profile dirs. Surgical — never the user's own Chrome."""
    if sys.platform != "win32":
        return 0
    markers = "|".join(_PROFILE_DIRS)
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe' OR "
        "Name='chromium.exe' OR Name='msedge.exe'\" | "
        f"Where-Object {{ $_.CommandLine -match '{markers}' }} | "
        "ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop; "
        "Write-Output $_.ProcessId } catch {} }"
    )
    try:
        out = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=30,
        )
        return len([l for l in out.stdout.splitlines() if l.strip().isdigit()])
    except Exception as e:
        logger.warning("browser cleanup failed: %s", e)
        return 0


def _clear_profile_locks() -> int:
    """Remove stale Singleton* lock files that block a fresh Playwright launch."""
    removed = 0
    for prof in _PROFILE_DIRS:
        for name in _LOCK_NAMES:
            p = os.path.join(_DIR, prof, name)
            try:
                if os.path.islink(p) or os.path.exists(p):
                    os.remove(p)
                    removed += 1
            except Exception:
                pass
    return removed


def _clear_temp_files() -> int:
    """Remove leftover temp_strike_*.csv chunk files."""
    removed = 0
    for p in glob.glob(os.path.join(_DIR, "temp_strike_*.csv")):
        try:
            os.remove(p)
            removed += 1
        except Exception:
            pass
    return removed


def _dedupe_pick_log() -> int:
    """Remove duplicate (screener, as_of_date, symbol) pick_log rows from TODAY,
    keeping the newest per group. Never deletes a row referenced by evaluations
    (forward-return tracking). Safe/idempotent; returns rows removed."""
    db = os.path.join(_DIR, "pick_log.db")
    if not os.path.exists(db):
        return 0
    today = datetime.date.today().isoformat()
    try:
        c = sqlite3.connect(db)
        # tables may not exist on a fresh DB — guard
        tables = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "picks" not in tables:
            c.close(); return 0
        has_eval = "evaluations" in tables
        eval_clause = ("AND log_id NOT IN (SELECT log_id FROM evaluations)"
                       if has_eval else "")
        cur = c.execute(f"""
            DELETE FROM picks WHERE log_id IN (
                SELECT log_id FROM picks
                WHERE substr(logged_at,1,10)=?
                AND log_id NOT IN (
                    SELECT MAX(log_id) FROM picks
                    WHERE substr(logged_at,1,10)=?
                    GROUP BY screener, as_of_date, symbol)
                {eval_clause}
            )""", (today, today))
        n = cur.rowcount or 0
        c.commit(); c.close()
        return n
    except Exception as e:
        logger.warning("pick_log dedupe failed: %s", e)
        return 0


def _prune_old_logs(keep: int = 15) -> int:
    """Keep only the newest `keep` auto_pilot_*.log files in the project root so
    they don't accumulate. The current run's log is the newest, so it is never
    pruned (Phase 0 runs after the log is opened)."""
    try:
        logs = sorted(glob.glob(os.path.join(_DIR, "auto_pilot_*.log")),
                      key=os.path.getmtime, reverse=True)
        removed = 0
        for p in logs[keep:]:
            try:
                os.remove(p); removed += 1
            except Exception:
                pass
        return removed
    except Exception:
        return 0


def preflight_cleanup(verbose: bool = True) -> dict:
    """Clear leftover browsers/locks/temp/pick-log-dupes/old-logs from a prior
    run. Never raises; each step degrades independently."""
    res = {
        "browsers_killed":  _kill_stale_browsers(),
        "locks_removed":    _clear_profile_locks(),
        "temp_removed":     _clear_temp_files(),
        "pick_log_deduped": _dedupe_pick_log(),
        "old_logs_pruned":  _prune_old_logs(),
    }
    if verbose:
        print(f"[cleanup] stale browsers killed={res['browsers_killed']} | "
              f"profile locks={res['locks_removed']} | "
              f"temp files={res['temp_removed']} | "
              f"pick_log dupes={res['pick_log_deduped']} | "
              f"old logs pruned={res['old_logs_pruned']}")
    return res


def main() -> int:
    preflight_cleanup(verbose=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
