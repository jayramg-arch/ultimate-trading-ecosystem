"""portfolio_review.post_checks - the house rules applied to a holding review (31-Oct-2026)."""
import portfolio_review as pr

ROW = {"ltp": 2405.5, "avg": 1613.23, "close": 2405.5, "atr": 71.72, "disaster": 2165.5,
       "thesis": 1952.1, "qty": 58, "budget": 15000.0}


def _rev(ruling, inv, stop):
    return "RECOMMENDATION\nRULING: %s - reason\nTHESIS INTACT - x\nINVALIDATION %s\nSTOP %s\n" % (ruling, inv, stop)


def test_add_on_a_loser_is_overruled(monkeypatch):
    monkeypatch.setattr(pr, "holding_row", lambda s: dict(ROW, ltp=1500.0, close=1500.0))
    rev, out = pr.post_checks("X", _rev("ADD", "Daily close below 1400.00 (zone distal)", "KEEP 1300.00"))
    assert pr.ruling_word(rev) == "HOLD"
    assert any("no averaging down" in o for o in out)


def test_add_blocked_by_exposure_tier(monkeypatch):
    import house_policy
    monkeypatch.setattr(pr, "holding_row", lambda s: ROW)
    monkeypatch.setattr(house_policy, "exposure_status", lambda: {"adds_ok": False, "tier": "BEAR"})
    rev, out = pr.post_checks("X", _rev("ADD", "Daily close below 2250.00 (zone distal)", "KEEP 2165.50"))
    assert pr.ruling_word(rev) == "HOLD"
    assert any("BEAR tier" in o for o in out)


def test_invalidation_equal_to_dhan_stop_is_flagged(monkeypatch):
    monkeypatch.setattr(pr, "holding_row", lambda s: ROW)
    _, out = pr.post_checks("X", _rev("HOLD", "Daily close below 2165.50 (Dhan stop)", "KEEP 2165.50"))
    assert any("is the Dhan stop itself" in o for o in out)


def test_invalidation_never_lowered(monkeypatch):
    monkeypatch.setattr(pr, "holding_row", lambda s: ROW)
    _, out = pr.post_checks("X", _rev("HOLD", "Daily close below 1900.00 (weekly level)", "KEEP 2165.50"))
    assert any("never lowered" in o for o in out)


def test_stop_raise_inside_three_atr_is_flagged(monkeypatch):
    monkeypatch.setattr(pr, "holding_row", lambda s: ROW)
    _, out = pr.post_checks("X", _rev("HOLD", "Daily close below 2250.00 (zone)", "RAISE TO 2300.00 (swing low)"))
    assert any("inside 3 x ATR" in o for o in out)        # close 2405.5 - 3 x 71.72 = 2190.34


def test_drawdown_row_marks_a_broken_level(monkeypatch):
    import sl_board
    row = dict(ROW, symbol="X", thesis=2500.0, plan="Positional", close_src="t")
    monkeypatch.setattr(pr, "holding_row", lambda s: row)
    monkeypatch.setattr(sl_board, "_journal_rows", lambda: {})
    txt = pr.holding_block("X")
    assert "ALREADY THROUGH" in txt
