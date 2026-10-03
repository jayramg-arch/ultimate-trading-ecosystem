"""run_daemon_job.py - run one scheduler_daemon job once, for Windows Task Scheduler (3-Oct-2026).

Audit AUD-OCT-07: the in-app scheduler only fires while Web Commander is running and has no
catch-up after the PC sleeps, and it duplicated jobs Task Scheduler already owned. The daily
jobs now run from Task Scheduler through this wrapper (StartWhenAvailable catches a missed
time); the daemon keeps only the in-session pollers.

    python run_daemon_job.py breadth | premarket | postmarket | weekly
"""
import sys

JOBS = {"breadth": "job_breadth_update", "premarket": "job_premarket_report",
        "postmarket": "job_postmarket_report", "weekly": "job_weekly_report"}

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if name not in JOBS:
        print("usage: run_daemon_job.py " + " | ".join(JOBS)); sys.exit(2)
    if name != "weekly":
        try:
            import datetime as dt
            import nse_calendar
            if not nse_calendar.is_trading_day(dt.date.today()):
                print("not a trading day - %s skipped" % name); sys.exit(0)
        except Exception:
            pass
    import scheduler_daemon
    getattr(scheduler_daemon, JOBS[name])()
    print("%s done" % name)
