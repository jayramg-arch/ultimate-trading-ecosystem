#!/usr/bin/env python
# scheduler_daemon.py — Commander Web v4.0 Background Scheduler
# Runs APScheduler jobs for automated report delivery
# Start with: python scheduler_daemon.py
# Or import and call start_scheduler() from the Streamlit app
#
# Directories auto-created on first run:
#   reports/  — JSON and TXT report files
#   logs/     — scheduler.log

import os
import sys
import logging
import json
import time
import requests
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv

# Ensure the GeminiVSCode directory is in path
_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(_DIR))
load_dotenv(_DIR / ".env", override=True)

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
import pytz

IST = pytz.timezone("Asia/Kolkata")

# ── LOGGING SETUP ────────────────────────────────────────────────────────────
os.makedirs(_DIR / "logs", exist_ok=True)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(_DIR / "logs" / "scheduler.log"),
        logging.StreamHandler(),
    ],
)

# ── CONFIG ───────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
REPORT_STORE_DIR   = _DIR / "reports"  # Where generated reports are saved as JSON

TELEGRAM_MAX_CHARS = 4096  # Telegram API hard limit per message


# ── TELEGRAM DELIVERY ────────────────────────────────────────────────────────

def send_telegram(message: str, parse_mode: str = "HTML") -> bool:
    """Send a message to Telegram. Splits messages > 4096 chars into chunks.

    Args:
        message:    The text to send (HTML or Markdown).
        parse_mode: "HTML" (default) or "Markdown".

    Returns:
        True if all chunks sent successfully, False on any failure.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured — BOT_TOKEN or CHAT_ID missing")
        return False

    url = f"https://telegram-proxy.jayramg.workers.dev/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = [
        message[i : i + TELEGRAM_MAX_CHARS]
        for i in range(0, len(message), TELEGRAM_MAX_CHARS)
    ]

    all_ok = True
    for idx, chunk in enumerate(chunks, start=1):
        payload = {
            "chat_id":    TELEGRAM_CHAT_ID,
            "text":       chunk,
            "parse_mode": parse_mode,
        }
        try:
            resp = requests.post(url, json=payload, timeout=15)
            if resp.ok:
                logger.info(f"Telegram chunk {idx}/{len(chunks)} sent OK")
            else:
                logger.error(
                    f"Telegram chunk {idx}/{len(chunks)} failed: "
                    f"{resp.status_code} {resp.text}"
                )
                all_ok = False
        except requests.RequestException as exc:
            logger.error(f"Telegram request error (chunk {idx}): {exc}")
            all_ok = False

    return all_ok


# ── REPORT PERSISTENCE ───────────────────────────────────────────────────────

def save_report(report_type: str, content: str, data_dict: dict = None) -> None:
    """Persist a generated report to disk.

    Writes three files:
      reports/{report_type}_{YYYY-MM-DD}.txt   — human-readable text
      reports/{report_type}_{YYYY-MM-DD}.json  — raw data dict
      reports/latest_{report_type}.json        — always overwritten; used by Streamlit

    Args:
        report_type: Short label e.g. "premarket", "postmarket", "weekly".
        content:     Formatted text of the report.
        data_dict:   Raw data snapshot (optional).
    """
    REPORT_STORE_DIR.mkdir(parents=True, exist_ok=True)

    today_str = date.today().isoformat()          # e.g. "2026-04-17"
    now_ist   = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")

    # ── dated .txt ──────────────────────────────────────────────────────────
    txt_path = REPORT_STORE_DIR / f"{report_type}_{today_str}.txt"
    txt_path.write_text(content, encoding="utf-8")
    logger.info(f"Report text saved: {txt_path}")

    # ── dated .json ─────────────────────────────────────────────────────────
    if data_dict is not None:
        json_path = REPORT_STORE_DIR / f"{report_type}_{today_str}.json"
        try:
            json_path.write_text(
                json.dumps(data_dict, indent=2, default=str), encoding="utf-8"
            )
            logger.info(f"Report data saved: {json_path}")
        except (TypeError, ValueError) as exc:
            logger.error(f"Could not serialise data_dict for {report_type}: {exc}")

    # ── latest .json (Streamlit reads this) ─────────────────────────────────
    latest_payload = {
        "generated_at": now_ist,
        "report_type":  report_type,
        "text":         content,
        "data":         data_dict or {},
        "date":         today_str,
    }
    latest_path = REPORT_STORE_DIR / f"latest_{report_type}.json"
    latest_path.write_text(
        json.dumps(latest_payload, indent=2, default=str), encoding="utf-8"
    )
    logger.info(f"Latest report updated: {latest_path}")


# ── SCHEDULED JOBS ───────────────────────────────────────────────────────────

def job_premarket_report() -> None:
    """8:30 AM IST, Mon–Fri — generate and deliver pre-market brief."""
    logger.info("=== PRE-MARKET REPORT JOB START ===")
    try:
        from market_data_hub import (build_premarket_snapshot,
                                      refresh_calendar_from_investing)
        from gemini_reporter import generate_premarket_brief

        # Pull a fresh India economic calendar from investing.com before
        # building the snapshot so the brief and the Calendar tab share
        # the same up-to-date data. Failure here is non-fatal — the snapshot
        # will fall back to the on-disk JSON if the fetch fails.
        try:
            _cal_res = refresh_calendar_from_investing(days_ahead=14)
            logger.info("Calendar refresh: %s", _cal_res)
        except Exception as _ce:
            logger.warning("Calendar refresh failed (non-fatal): %s", _ce)

        snapshot    = build_premarket_snapshot()
        text_report = generate_premarket_brief(snapshot)
        save_report("premarket", text_report, snapshot)

        msg = (
            f"🌅 <b>PRE-MARKET BRIEF — {date.today().strftime('%d %b %Y')}</b>\n\n"
            f"{text_report[:3500]}"
        )
        success = send_telegram(msg)
        logger.info(f"Pre-market report sent to Telegram: {success}")
    except Exception as exc:
        logger.error(f"Pre-market job failed: {exc}", exc_info=True)
        send_telegram(f"⚠️ Pre-market report failed: {exc}")


def job_postmarket_report() -> None:
    """4:30 PM IST, Mon–Fri — generate and deliver post-market summary."""
    logger.info("=== POST-MARKET REPORT JOB START ===")
    try:
        from market_data_hub import build_postmarket_snapshot
        from gemini_reporter import generate_postmarket_summary
        from breadth_engine import calculate_breadth_metrics, build_breadth_regime

        snapshot = build_postmarket_snapshot()
        breadth  = calculate_breadth_metrics()
        snapshot["breadth"]        = breadth
        snapshot["breadth_regime"] = build_breadth_regime(breadth)

        text_report = generate_postmarket_summary(snapshot)
        save_report("postmarket", text_report, snapshot)

        msg = (
            f"🌙 <b>POST-MARKET SUMMARY — {date.today().strftime('%d %b %Y')}</b>\n\n"
            f"{text_report[:3500]}"
        )
        success = send_telegram(msg)
        logger.info(f"Post-market report sent to Telegram: {success}")
    except Exception as exc:
        logger.error(f"Post-market job failed: {exc}", exc_info=True)
        send_telegram(f"⚠️ Post-market report failed: {exc}")


def job_weekly_report() -> None:
    """Sunday 7:00 PM IST — generate and deliver weekly market review."""
    logger.info("=== WEEKLY REPORT JOB START ===")
    try:
        from market_data_hub import build_premarket_snapshot, build_postmarket_snapshot
        from gemini_reporter import generate_postmarket_summary  # reuse as weekly base

        # Build a combined weekly snapshot
        snapshot = build_postmarket_snapshot()
        try:
            pre_snap = build_premarket_snapshot()
            snapshot["weekly_premarket_data"] = pre_snap
        except Exception as inner:
            logger.warning(f"Could not attach premarket data to weekly: {inner}")

        snapshot["report_label"] = "weekly"

        text_report = generate_postmarket_summary(snapshot)
        save_report("weekly", text_report, snapshot)

        week_label = date.today().strftime("Week of %d %b %Y")
        msg = (
            f"📊 <b>WEEKLY MARKET REVIEW — {week_label}</b>\n\n"
            f"{text_report[:3500]}"
        )
        success = send_telegram(msg)
        logger.info(f"Weekly report sent to Telegram: {success}")
    except Exception as exc:
        logger.error(f"Weekly job failed: {exc}", exc_info=True)
        send_telegram(f"⚠️ Weekly report failed: {exc}")


def job_breadth_update() -> None:
    """4:45 PM IST, Mon–Fri — refresh breadth metrics cache AND append A/D row."""
    logger.info("=== BREADTH UPDATE JOB START ===")
    try:
        from breadth_engine import calculate_breadth_metrics, build_breadth_regime

        breadth = calculate_breadth_metrics()
        regime  = build_breadth_regime(breadth)

        REPORT_STORE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
            "date":         date.today().isoformat(),
            "breadth":      breadth,
            "regime":       regime,
        }
        breadth_path = REPORT_STORE_DIR / "latest_breadth.json"
        breadth_path.write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )
        logger.info(f"Breadth metrics updated: {breadth_path}")
    except Exception as exc:
        logger.error(f"Breadth update job failed: {exc}", exc_info=True)

    # ── Append today's A/D row to McClellan history ───────────────────────
    try:
        _ad_file = REPORT_STORE_DIR / "ad_history.json"
        today_str = date.today().isoformat()

        # Load existing history
        existing: list = []
        if _ad_file.exists():
            try:
                import pandas as _pd
                _df_ex = _pd.read_json(str(_ad_file))
                existing = _df_ex.to_dict(orient="records")
            except Exception:
                existing = []

        # Avoid duplicate entries for today
        if any(str(r.get("date", ""))[:10] == today_str for r in existing):
            logger.info("A/D history: entry for %s already exists — skipping", today_str)
        else:
            adv = breadth.get("advance_count", 0)
            dec = breadth.get("decline_count", 0)
            if adv + dec > 0:
                existing.append({
                    "date":          today_str,
                    "advance_count": adv,
                    "decline_count": dec,
                })
                # Keep last 500 rows
                existing = existing[-500:]
                _ad_file.write_text(
                    json.dumps(existing, indent=2), encoding="utf-8"
                )
                logger.info("A/D history: appended %s (adv=%d dec=%d) — total %d rows",
                            today_str, adv, dec, len(existing))
    except Exception as exc:
        logger.warning(f"A/D history append failed: {exc}")


# ── ALERT CHECK JOB ─────────────────────────────────────────────────────────

def job_check_price_alerts() -> None:
    """Every 15 min during market hours — evaluate active price alerts."""
    logger.info("=== PRICE ALERT CHECK START ===")
    try:
        from alert_engine import check_alerts, build_telegram_message

        def _notify(alert, cur_price):
            msg = build_telegram_message(alert, cur_price)
            send_telegram(msg)

        fired = check_alerts(notify_fn=_notify)
        if fired:
            logger.info("Price alerts fired: %d", len(fired))
        else:
            logger.debug("Price alert check: nothing fired")
    except Exception as exc:
        logger.error("Price alert check failed: %s", exc, exc_info=True)


# ── AUTO-PILOT JOB ──────────────────────────────────────────────────────────

def job_auto_pilot() -> None:
    """4:30 PM IST, Mon–Fri — run the full Auto-Pilot pipeline."""
    logger.info("=== AUTO-PILOT JOB START ===")
    try:
        import subprocess
        # Run run_pipeline.py in a separate process so it doesn't block or pollute the scheduler's memory space.
        # Use --batch to bypass the blocking input() at the end.
        subprocess.run([sys.executable, "run_pipeline.py", "--batch"], check=True)
        send_telegram("🚀 <b>AUTO-PILOT</b> pipeline completed successfully.")
        logger.info("Auto-Pilot job completed.")
    except Exception as exc:
        logger.error(f"Auto-Pilot job failed: {exc}", exc_info=True)
        send_telegram(f"⚠️ Auto-Pilot job failed: {exc}")


# ── GTT TRAIL JOB (RS-P1, 14-Jul-2026) ──────────────────────────────────────

def job_gtt_trail() -> None:
    """3:45 PM IST, Mon–Fri — tighten-only Chandelier trail of live Dhan GTT SL
    legs (gtt_auto_shield --trail --yes). Closes the audit's biggest gap: the
    broker stop used to stay FROZEN at the entry SL forever (the shield was
    create-only and skipped shielded symbols). Runs just after the 15:30 close
    so the trail reads the completed daily bar. Tighten-only — never loosens;
    breached names (Chandelier ≥ LTP) are reported, never auto-sold."""
    logger.info("=== GTT TRAIL JOB START ===")
    try:
        import subprocess
        res = subprocess.run([sys.executable, "gtt_auto_shield.py", "--trail", "--yes"],
                             check=True, capture_output=True, text=True, timeout=600)
        tail = "\n".join((res.stdout or "").strip().splitlines()[-6:])
        send_telegram(f"🛡️ <b>GTT TRAIL</b> pass done.\n<pre>{tail[:800]}</pre>")
        logger.info("GTT trail job completed.")
    except Exception as exc:
        logger.error(f"GTT trail job failed: {exc}", exc_info=True)
        send_telegram(f"⚠️ GTT trail job failed: {exc}")


def job_exit_scan() -> None:
    """4:00 PM IST, Mon–Fri — exit-signal watchdog (STOP-LOSS / TARGET /
    STAGE-DECAY / RS-FADE) on all open positions. The engine itself Telegrams
    the ACTION rows (RS-P1) — a stop hit or a Stage-3/4 decay used to be silent
    until someone opened the COMMAND page."""
    logger.info("=== EXIT SCAN JOB START ===")
    try:
        import subprocess
        subprocess.run([sys.executable, "exit_signal_engine.py", "--silent"],
                       check=True, timeout=900)
        logger.info("Exit scan job completed.")
    except Exception as exc:
        logger.error(f"Exit scan job failed: {exc}", exc_info=True)
        send_telegram(f"⚠️ Exit-scan job failed: {exc}")


# ── APScheduler EVENT LISTENER ───────────────────────────────────────────────

def on_job_event(event) -> None:
    """Log APScheduler job execution events and alert on failures.

    Listens for EVENT_JOB_EXECUTED and EVENT_JOB_ERROR.
    """
    if event.exception:
        # EVENT_JOB_ERROR
        logger.error(
            f"Job '{event.job_id}' raised an exception: {event.exception}",
            exc_info=event.traceback,
        )
        send_telegram(
            f"⚠️ <b>Scheduler job failed</b>\n"
            f"Job: <code>{event.job_id}</code>\n"
            f"Error: {event.exception}"
        )
    else:
        # EVENT_JOB_EXECUTED
        run_time = getattr(event, "scheduled_run_time", None)
        rt_str   = run_time.strftime("%H:%M:%S IST") if run_time else "unknown"
        logger.info(f"Job '{event.job_id}' completed successfully (scheduled: {rt_str})")


# ── SCHEDULER LIFECYCLE ──────────────────────────────────────────────────────

def start_scheduler() -> BackgroundScheduler:
    """Create, configure, and start the APScheduler BackgroundScheduler.

    Registers six cron jobs:
      - token_check  : 08:00 IST Mon–Fri  (Dhan token validity alert)
      - premarket    : 08:30 IST Mon–Fri
      - postmarket   : 16:30 IST Mon–Fri
      - breadth      : 16:45 IST Mon–Fri  (also appends A/D row to ad_history.json)
      - weekly       : 19:00 IST Sunday
      - price_alerts : every 15 min 09:00–15:45 IST Mon–Fri

    Returns:
        A running BackgroundScheduler instance.
    """
    os.makedirs(REPORT_STORE_DIR, exist_ok=True)
    os.makedirs(_DIR / "logs", exist_ok=True)

    scheduler = BackgroundScheduler(timezone=IST)
    scheduler.add_listener(on_job_event, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)

    # Token validity check: 8:00 AM IST, Mon–Fri
    def _job_token_check():
        try:
            from dhan_auth import token_status
            ts = token_status()
            if not ts.get("valid"):
                send_telegram(
                    "⚠️ <b>Dhan token expired!</b>\n"
                    "Regenerate at web.dhan.co → API → Access Token\n"
                    "Then paste in Commander Web sidebar or update .env"
                )
                logger.warning("Token check: EXPIRED — Telegram alert sent")
            else:
                logger.info("Token check: valid until %s", ts.get("expires_at","?"))
        except Exception as e:
            logger.warning("Token check job failed: %s", e)

    scheduler.add_job(
        _job_token_check,
        CronTrigger(hour=8, minute=0, day_of_week="mon-fri", timezone=IST),
        id="token_check",
        name="Dhan Token Check",
        replace_existing=True,
    )

    # Pre-market: 8:30 AM IST, Mon–Fri
    scheduler.add_job(
        job_premarket_report,
        CronTrigger(hour=8, minute=30, day_of_week="mon-fri", timezone=IST),
        id="premarket",
        name="Pre-Market Brief",
        replace_existing=True,
    )

    # Post-market: 4:30 PM IST, Mon–Fri
    scheduler.add_job(
        job_postmarket_report,
        CronTrigger(hour=16, minute=30, day_of_week="mon-fri", timezone=IST),
        id="postmarket",
        name="Post-Market Summary",
        replace_existing=True,
    )

    # Breadth update: 4:45 PM IST, Mon–Fri
    scheduler.add_job(
        job_breadth_update,
        CronTrigger(hour=16, minute=45, day_of_week="mon-fri", timezone=IST),
        id="breadth",
        name="Breadth Update",
        replace_existing=True,
    )

    # Weekly report: Sunday 7:00 PM IST
    scheduler.add_job(
        job_weekly_report,
        CronTrigger(hour=19, minute=0, day_of_week="sun", timezone=IST),
        id="weekly",
        name="Weekly Market Report",
        replace_existing=True,
    )

    # Price alert check: every 15 min, 9:00 AM – 3:45 PM IST, Mon–Fri
    scheduler.add_job(
        job_check_price_alerts,
        CronTrigger(
            hour="9-15", minute="0,15,30,45",
            day_of_week="mon-fri", timezone=IST
        ),
        id="price_alerts",
        name="Price Alert Check",
        replace_existing=True,
    )

    # Auto-Pilot Full Run: 4:30 PM IST, Mon–Fri
    scheduler.add_job(
        job_auto_pilot,
        CronTrigger(hour=16, minute=30, day_of_week="mon-fri", timezone=IST),
        id="auto_pilot",
        name="Auto-Pilot Full Run",
        replace_existing=True,
    )

    # GTT Trail (tighten-only Chandelier): 3:45 PM IST, Mon–Fri (post-close,
    # before the 16:30 auto-pilot so the trail reads today's completed bar).
    scheduler.add_job(
        job_gtt_trail,
        CronTrigger(hour=15, minute=45, day_of_week="mon-fri", timezone=IST),
        id="gtt_trail",
        name="GTT Trail (tighten-only)",
        replace_existing=True,
    )

    # Exit-signal watchdog: 4:00 PM IST, Mon–Fri (after the trail pass; the
    # engine Telegrams ACTION rows itself).
    scheduler.add_job(
        job_exit_scan,
        CronTrigger(hour=16, minute=0, day_of_week="mon-fri", timezone=IST),
        id="exit_scan",
        name="Exit Signal Scan",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"Scheduler started with {len(scheduler.get_jobs())} jobs")
    return scheduler


# ── SCHEDULER STATUS (for Streamlit UI) ─────────────────────────────────────

def get_scheduler_status(scheduler: BackgroundScheduler = None) -> dict:
    """Return a status dict suitable for display in the Streamlit dashboard.

    Args:
        scheduler: A running BackgroundScheduler instance, or None if not started.

    Returns:
        Dict with keys: running, jobs, next_premarket, next_postmarket.
    """
    if scheduler is None or not scheduler.running:
        return {
            "running":        False,
            "jobs":           [],
            "next_premarket": None,
            "next_postmarket": None,
        }

    jobs_info = []
    next_premarket  = None
    next_postmarket = None

    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        next_run_str = next_run.isoformat() if next_run else "paused"

        jobs_info.append({
            "id":       job.id,
            "name":     job.name,
            "next_run": next_run_str,
            "last_run": None,  # APScheduler doesn't expose last_run natively
        })

        if job.id == "premarket" and next_run:
            next_premarket = next_run_str
        elif job.id == "postmarket" and next_run:
            next_postmarket = next_run_str

    return {
        "running":         scheduler.running,
        "jobs":            jobs_info,
        "next_premarket":  next_premarket,
        "next_postmarket": next_postmarket,
    }


# ── REPORT LOADER (for Streamlit UI) ────────────────────────────────────────

def load_latest_report(report_type: str) -> dict:
    """Read the latest saved report from disk.

    Args:
        report_type: e.g. "premarket", "postmarket", "weekly", "breadth".

    Returns:
        Parsed JSON dict, or a safe empty shell if the file doesn't exist yet.
    """
    path = REPORT_STORE_DIR / f"latest_{report_type}.json"
    if not path.exists():
        logger.debug(f"No latest report found for type '{report_type}': {path}")
        return {"generated_at": None, "text": None, "data": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error(f"Failed to load report '{report_type}': {exc}")
        return {"generated_at": None, "text": None, "data": {}}


# ── MANUAL TRIGGER (for Streamlit "Refresh Now" buttons) ────────────────────

def trigger_manual_report(report_type: str) -> str:
    """Synchronously run a report job and return the generated text.

    Useful for "Refresh Now" buttons in the Streamlit dashboard.
    Calls the underlying job function directly (blocking).

    Args:
        report_type: "premarket", "postmarket", "weekly", or "breadth".

    Returns:
        The generated report text, or an error message string.
    """
    _job_map = {
        "premarket":  job_premarket_report,
        "postmarket": job_postmarket_report,
        "weekly":     job_weekly_report,
        "breadth":    job_breadth_update,
    }

    job_fn = _job_map.get(report_type)
    if job_fn is None:
        msg = f"Unknown report type: '{report_type}'. Valid: {list(_job_map)}"
        logger.warning(msg)
        return msg

    logger.info(f"Manual trigger: {report_type}")
    job_fn()  # runs synchronously in the calling thread

    # Return the text from the just-saved latest report
    result = load_latest_report(report_type)
    return result.get("text") or f"{report_type} report generated (no text field)."


# ── ENTRY POINT ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting Weinstein Commander Scheduler Daemon...")
    print(f"IST timezone: {IST}")
    print(f"Reports dir : {REPORT_STORE_DIR}")
    print(f"Logs dir    : {_DIR / 'logs'}")

    scheduler = start_scheduler()

    print("\nScheduler running. Press Ctrl+C to stop.")
    print("\nNext runs:")
    for job in scheduler.get_jobs():
        print(f"  {job.name}: {job.next_run_time}")

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("\nScheduler stopped.")
