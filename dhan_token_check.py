# -*- coding: utf-8 -*-
"""dhan_token_check.py — pre-open Dhan token check that FIXES, not just reports.

Task Scheduler entry (run_token_check.bat, 08:00 IST Mon-Fri). The in-app job at
the same hour only Telegrams "expired" and depends on Web Commander being up;
this one calls dhan_auth.get_valid_token(), which refreshes via TOTP when the
JWT is inside its 10-minute buffer, writes .env, and reports either way. A
missed refresh is the silent path to a yfinance day (dhan_data_feed_wiring).
"""
import os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, HERE)


def main() -> int:
    from dhan_auth import token_status, get_valid_token
    before = token_status()
    if before.get("valid"):
        print(f"token valid until {before.get('expires_at', '?')} — nothing to do")
        return 0
    print(f"token NOT valid ({before.get('reason') or before.get('expires_at') or 'expired'}) — refreshing")
    try:
        tok = get_valid_token(force_refresh=True)
        after = token_status()
        ok = bool(after.get("valid"))
        msg = ("✅ Dhan token refreshed — valid until %s" % after.get("expires_at", "?")) if ok \
              else "⚠️ Dhan token refresh returned but the token still reads invalid"
    except Exception as e:
        ok, msg = False, f"⚠️ Dhan token refresh FAILED: {e}\nRegenerate at web.dhan.co → API → Access Token and update .env"
    print(msg)
    try:
        from scheduler_daemon import send_telegram
        send_telegram(msg)
    except Exception:
        pass
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
