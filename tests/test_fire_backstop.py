"""tv_fire_backstop: recover S4 GO alerts whose webhook failed (22-Oct-2026)."""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tv_fire_backstop as fb  # noqa: E402


def _ago(sec):
    return (datetime.now(timezone.utc) - timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fire(fid, msg, sec_ago, webhook, name="S4 GO 75"):
    return {"id": fid, "name": name, "message": msg, "fire_time": _ago(sec_ago), "webhook": webhook}


def test_outcome_and_classify():
    assert fb.outcome({"webhook": {"error": "request took too long and timed out"}}) == "failed"
    assert fb.outcome({"webhook": {}}) == "delivered"
    assert fb.outcome({"webhook": None, "fire_time": _ago(30)}) == "pending"
    assert fb.outcome({"webhook": None, "fire_time": _ago(900)}) == "delivered"
    assert fb.classify({"name": "GM-THESIS SAILIFE", "message": "x"})[0] == "thesis"
    assert fb.classify({"name": "a", "message": "AUBANK S4 GO 75 - bar 10:30"})[0] == "s4"
    assert fb.classify({"name": "GM-POS zone X", "message": "price crossed"})[0] == "other"


def test_too_late():
    assert not fb.too_late("75", 60 * 74)
    assert fb.too_late("75", 60 * 76)
    assert fb.too_late("125", 60 * 126)
    assert not fb.too_late("1D", 3600 * 5)


def test_run_once_recovers_only_failed_and_once(tmp_path, monkeypatch):
    fires = [
        _fire("1", "AUBANK S4 GO 75 - x", 60, {"error": "request took too long and timed out"}),
        _fire("2", "NETWEB S4 GO 75 - x", 60, {}),                                   # delivered
        _fire("3", "ALPHA S4 GO 75 - x", 60 * 90, {"error": "timed out"}),            # bar moved on
        _fire("4", "TITAN S4 GO 75 - x", 20, None),                                    # still trying
    ]
    monkeypatch.setattr(fb, "SEEN", str(tmp_path / "seen.json"))
    monkeypatch.setattr(fb, "fetch_fires", lambda limit=60: fires)
    queued, sent = [], []
    import s4_alert_review
    import s4_review
    monkeypatch.setattr(s4_alert_review, "enqueue", lambda s, t, source="", body="": queued.append((s, t, source)))
    monkeypatch.setattr(s4_alert_review, "_log", lambda m: None)
    monkeypatch.setattr(s4_review, "telegram", lambda m: sent.append(m) or True)
    r = fb.run_once(lookback_h=12)
    assert queued == [("AUBANK", "75", "tv-webhook-recovered")]
    assert r["recovered"] == 1 and r["missed"] == 1 and r["delivered"] == 1 and r["pending"] == 1
    assert len(sent) == 1 and "ALPHA" in sent[0]
    r2 = fb.run_once(lookback_h=12)                # same fires again: nothing handled twice
    assert queued == [("AUBANK", "75", "tv-webhook-recovered")] and r2["recovered"] == 0
    assert r2["pending"] == 1                      # the pending fire is looked at again


def test_recovered_label_is_s4_alert_and_daily_hold():
    import s4_alert_review as sar
    assert sar._src_label("tv-webhook-recovered") == "s4-alert"
    assert sar._daily_wait_s("75", "tv-webhook-recovered") == 0.0
