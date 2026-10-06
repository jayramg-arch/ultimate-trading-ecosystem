"""Pyramid ladder grace period: entry-day conditions are held off for the first sessions;
the hard exits never are."""
import numpy as np

import pyramid_logic as pl


def _row(**kw):
    base = {"rrg_quadrant": "LEADING", "score_100pt": 50, "stage": 2, "pnl_pct": -1.0,
            "ltp": 100.0, "buy_price": 101.0, "stoploss": 90.0, "atr14": 2.0, "dma50": np.nan,
            "wma30": np.nan, "swing_low": np.nan, "ema20": 99.0, "chandelier": np.nan,
            "timeframe": "Swing", "setup": "SWG-PB", "target": np.nan}
    base.update(kw)
    return base


G = lambda *flags: {"session": 2, "n": 10, "flags": list(flags)}


def test_chandelier_true_at_entry_is_held_off():
    cls, why = pl.classify(_row(chandelier=103.0, grace=G("chandelier")))
    assert cls == "HOLD" and "grace s2/10" in why and "Chandelier" in why
    assert pl.classify(_row(chandelier=103.0))[0] == "EXIT"          # no grace -> exit


def test_condition_not_true_at_entry_still_fires():
    assert pl.classify(_row(chandelier=103.0, grace=G("swing_low")))[0] == "EXIT"


def test_hard_exits_never_held_off():
    g = G("at_sl", "chandelier", "swing_low", "wma30")
    assert pl.classify(_row(pnl_pct=-9.0, grace=g))[0] == "EXIT"
    assert pl.classify(_row(stage=4, grace=g))[0] == "EXIT"
    cls, why = pl.classify(_row(ltp=89.0, grace=g))
    assert cls == "EXIT" and "breached" in why


def test_reduce_rungs_held_off_in_grace():
    cls, why = pl.classify(_row(score_100pt=10, grace=G()))
    assert cls == "HOLD" and "score 10" in why
    assert pl.classify(_row(score_100pt=10))[0] == "REDUCE"


def test_at_sl_tight_stop_held_off():
    r = _row(stoploss=98.0, ltp=100.0, buy_price=100.5)              # 1.0 x ATR away, losing
    assert pl.classify(r)[0] == "EXIT"
    assert pl.classify({**r, "grace": G("at_sl")})[0] == "HOLD"
