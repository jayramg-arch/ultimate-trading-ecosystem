"""Armed Register — the GM board's memory across watchlist churn.

The scenario this exists for (Jay, 31-Jul-2026):
    Mon  arm NAME, set the TV alert
    Tue  auto-pilot rebuilds the watchlists -> NAME leaves every FINAL_*.csv
    Thu  the alert fires -> previously: no row, no levels, no thesis

Runs under pytest OR standalone:  python tests/test_gm_armed.py
"""
import importlib
import json
import os
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gm_armed  # noqa: E402


def fresh():
    """Point the module at a throwaway store so tests never touch the real one."""
    importlib.reload(gm_armed)
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(path)
    gm_armed._STORE = path
    return gm_armed


# ── the core scenario ────────────────────────────────────────────────────────
def test_plan_survives_and_is_retrievable_days_later():
    a = fresh()
    mon = date(2026, 7, 27)
    a.arm("APOLLOHOSP", path="bull", archetypes=["Pullback"], verdict="TAKE IT",
          trigger=7180.0, entry=7150.0, sl=6980.0, t1=7520.0, sigma_pa=5,
          tf="75m", note="zone retest", today=mon)
    thu = mon + timedelta(days=3)
    rec = a.active(today=thu)["APOLLOHOSP"]
    assert rec["trigger"] == 7180.0 and rec["sl"] == 6980.0
    assert rec["archetypes"] == ["Pullback"], "original thesis must be preserved"
    assert a.days_armed(rec, today=thu) == 3
    assert "3d" in a.summary_line(rec, today=thu)
    assert "7,180" in a.summary_line(rec, today=thu)


def test_symbol_is_canonicalised_on_write_and_read():
    """The [[gm_symbol_ns_normalization]] bug class: an armed name whose key does
    not match the board's would silently never join."""
    a = fresh()
    a.arm("apollohosp.ns", trigger=100)
    assert "APOLLOHOSP" in a.load()
    assert a.is_armed("APOLLOHOSP.NS") and a.is_armed("apollohosp")
    assert a.get("NSE:APOLLOHOSP")["trigger"] == 100


def test_rearming_replaces_levels_but_keeps_the_wait():
    a = fresh()
    d0 = date(2026, 7, 20)
    a.arm("TITAN", trigger=100, today=d0)
    r = a.arm("TITAN", trigger=140, today=d0 + timedelta(days=5))
    assert r["trigger"] == 140, "new read = new levels"
    assert r["first_armed"] == d0.isoformat(), "age must reflect the real wait"
    assert r["rearmed"] is True
    assert a.days_armed(r, today=d0 + timedelta(days=5)) == 5


# ── lifecycle ────────────────────────────────────────────────────────────────
def test_expiry_flips_only_past_due_and_self_maintains():
    a = fresh()
    d0 = date(2026, 6, 1)
    a.arm("OLD", trigger=1, expiry_days=10, today=d0)
    a.arm("NEW", trigger=1, expiry_days=10, today=d0 + timedelta(days=9))
    act = a.active(today=d0 + timedelta(days=11))
    assert "OLD" not in act and "NEW" in act
    assert a.get("OLD")["status"] == a.EXPIRED if hasattr(a, "EXPIRED") else True
    assert a.load()["OLD"]["status"] == "EXPIRED"


def test_expiry_runs_on_read_not_only_on_a_button():
    a = fresh()
    d0 = date(2026, 6, 1)
    a.arm("X", trigger=1, expiry_days=1, today=d0)
    a.active(today=d0 + timedelta(days=5))          # read alone must expire it
    assert a.load()["X"]["status"] == "EXPIRED"


def test_disarm_keeps_the_record():
    """'I armed this and dropped it' is information; a silent delete loses it."""
    a = fresh()
    a.arm("ZYDUSLIFE", trigger=1)
    assert a.disarm("ZYDUSLIFE", note="thesis broke")
    assert "ZYDUSLIFE" not in a.active()
    r = a.load()["ZYDUSLIFE"]
    assert r["status"] == "CANCELLED" and r["note"] == "thesis broke"


def test_triggered_leaves_the_active_set():
    a = fresh()
    a.arm("BHEL", trigger=1)
    assert a.triggered("BHEL")
    assert "BHEL" not in a.active() and a.load()["BHEL"]["status"] == "TRIGGERED"


def test_mark_and_disarm_on_unknown_symbol_are_false_not_crashes():
    a = fresh()
    assert a.disarm("NOSUCH") is False
    assert a.triggered("NOSUCH") is False
    assert a.purge("NOSUCH") is False


def test_purge_hard_removes():
    a = fresh()
    a.arm("TMP", trigger=1)
    assert a.purge("TMP") and "TMP" not in a.load()


# ── robustness: the register must never take the board down ──────────────────
def test_corrupt_store_degrades_to_empty():
    a = fresh()
    with open(a._STORE, "w", encoding="utf-8") as f:
        f.write("{not json")
    assert a.load() == {} and a.active() == {}


def test_non_dict_store_degrades_to_empty():
    a = fresh()
    with open(a._STORE, "w", encoding="utf-8") as f:
        json.dump(["APOLLOHOSP"], f)
    assert a.load() == {}


def test_unparseable_expiry_stays_visible_rather_than_vanishing():
    a = fresh()
    a.arm("WEIRD", trigger=1)
    reg = a.load(); reg["WEIRD"]["expires_on"] = "not-a-date"; a.save(reg)
    assert "WEIRD" in a.active(), "a bad date must not silently drop the name"


def test_numeric_coercion_rejects_junk_without_raising():
    a = fresh()
    r = a.arm("Y", trigger="abc", entry=None, sl="", t1=float("nan"), rr="2.5")
    assert r["trigger"] is None and r["entry"] is None
    assert r["sl"] is None and r["t1"] is None and r["rr"] == 2.5


def test_arm_requires_a_symbol():
    a = fresh()
    for bad in ("", None, "   "):
        try:
            a.arm(bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad!r}")


# ── board contract ───────────────────────────────────────────────────────────
def test_badge_cannot_decide_a_path_on_its_own():
    """ARMED_ARCHETYPE lives in BOTH archetype sets, so the path must come from the
    record — otherwise arming a recovery name would silently re-file it as bull."""
    import gm_trigger_board as b
    assert b.ARMED_ARCHETYPE in b.BULL_ARCHETYPES
    assert b.ARMED_ARCHETYPE in b.RECOVERY_ARCHETYPES


def test_armed_is_structural_so_it_is_not_catalyst_expired():
    """An armed name's thesis persists by definition; treating it as catalyst-scan-
    ONLY would demote it to 'catalyst expired' the moment the catalyst faded."""
    import gm_trigger_board as b
    assert b.ARMED_ARCHETYPE in b.STRUCTURAL_BULL_ARCHETYPES
    assert b.ARMED_ARCHETYPE in b.STRUCTURAL_RECOVERY_ARCHETYPES


def test_canon_matches_the_boards_key_function():
    """If these two ever diverge, armed names silently fail to join the board."""
    import gm_trigger_board as b
    for sym in ("APOLLOHOSP.NS", "NSE:BAJAJ_AUTO", "m&m", "  titan  ", "BAJAJ-AUTO"):
        assert gm_armed.canon(sym) == b._canon_key(sym), sym


if __name__ == "__main__":
    fails = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError as e:
                fails.append(f"{name}: {e or 'assertion failed'}")
            except Exception as e:
                fails.append(f"{name}: {type(e).__name__}: {e}")
    print(f"{len(fails)} failed")
    for f in fails:
        print("  ", f)
    print("PASS" if not fails else "FAIL")
    raise SystemExit(1 if fails else 0)
