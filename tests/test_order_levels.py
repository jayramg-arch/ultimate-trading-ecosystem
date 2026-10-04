"""order_levels (4-Oct-2026): which Dhan stop is current, and the coverage warning."""
import order_levels as ol


def _o(leg, otype, trig, ts, qty, oid):
    return {"leg": leg, "otype": otype, "price": trig - 1, "trigger": trig, "ts": ts, "qty": qty, "oid": oid}


VIJAYA = [
    _o("STOP_LOSS_LEG", "SINGLE", 1268.5, "2026-10-04 23:19:46", 15, "A"),
    _o("TARGET_LEG", "OCO", 2209.5, "2026-08-23 21:15:59", 8, "B"),
    _o("STOP_LOSS_LEG", "OCO", 1275.5, "2026-08-23 21:15:59", 8, "B"),
    _o("STOP_LOSS_LEG", "OCO", 1275.5, "2026-08-23 21:15:15", 8, "C"),
    _o("TARGET_LEG", "OCO", 1742.5, "2026-08-23 21:15:15", 8, "C"),
]


def test_latest_stop_wins_not_highest():
    sl, t1, t2 = ol.derive_sl_targets(VIJAYA, 1400.0)
    assert sl == 1268.5 and t1 == 1741.5 and t2 == 2208.5


def test_report_names_disagreement_and_uncovered_shares():
    r = ol.stop_report(VIJAYA, 1400.0, 98)
    assert "16 sh @ 1275.5" in r and "15 sh @ 1268.5" in r and "1275.5 fires first" in r
    assert "67 of 98 shares have no stop" in r


def test_consistent_full_cover_is_silent():
    o = [_o("STOP_LOSS_LEG", "OCO", 100.0, "t", 10, "X"), _o("TARGET_LEG", "OCO", 150.0, "t", 10, "X")]
    assert ol.stop_report(o, 120.0, 10) == ""
    assert ol.derive_sl_targets(o, 120.0)[0] == 100.0
