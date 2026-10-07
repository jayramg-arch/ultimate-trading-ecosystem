"""Chandelier anchored at entry (7-Oct-2026): a young position does not trail off highs
printed before it was bought; an older one is unchanged."""
import numpy as np
import pandas as pd

import risk_common as rc


def _frame():
    idx = pd.bdate_range("2026-06-01", periods=60)
    c = np.r_[np.linspace(100, 130, 40), np.linspace(130, 112, 15), np.linspace(112, 116, 5)]
    return pd.DataFrame({"High": c * 1.01, "Low": c * 0.99, "Close": c}, index=idx)


def test_old_position_unchanged():
    d = _frame()
    a = rc.chandelier_exit(d.High, d.Low, d.Close, setup="POS-BO", swing=False)
    b = rc.chandelier_exit(d.High, d.Low, d.Close, setup="POS-BO", swing=False,
                           entry_date=d.index[0])
    assert a == b and not b[2].endswith("·entry")


def test_young_position_anchors_at_entry():
    d = _frame()
    entry = d.index[-6]                                   # bought on the pullback, 6 bars ago
    pre, _, _ = rc.chandelier_exit(d.High, d.Low, d.Close, setup="POS-BO", swing=False)
    lvl, mult, src = rc.chandelier_exit(d.High, d.Low, d.Close, setup="POS-BO", swing=False,
                                        entry_date=entry)
    assert src.endswith("·entry") and lvl < pre
    since = d.Close[d.index >= entry].max()
    tr = pd.concat([d.High - d.Low, (d.High - d.Close.shift()).abs(),
                    (d.Low - d.Close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 22, adjust=False).mean().iloc[-1]
    assert abs(lvl - (since - atr * mult)) < 1e-9


def test_entry_after_last_bar_uses_last_close():
    d = _frame()
    lvl, mult, src = rc.chandelier_exit(d.High, d.Low, d.Close, setup="POS-BO", swing=False,
                                        entry_date=d.index[-1] + pd.Timedelta(days=1))
    assert src.endswith("·entry") and lvl < d.Close.iloc[-1]


def test_holding_chandelier_reports_anchor():
    idx = pd.bdate_range("2025-06-01", periods=260)
    c = np.r_[np.linspace(100, 160, 240), np.linspace(160, 140, 20)]
    d = pd.DataFrame({"High": c * 1.01, "Low": c * 0.99, "Close": c}, index=idx)
    j = {"setup": "POS-BO", "timeframe": "Positional", "buy_price": 141.0, "stoploss": 120.0}
    old = rc.holding_chandelier(d, j, bear=False)
    new = rc.holding_chandelier(d, {**j, "entry_date": idx[-3]}, bear=False)
    assert not old["anchored"] and new["anchored"] and new["level"] < old["level"]


def test_book_sends_exact_level_for_young_position():
    import tv_push_v67_trail as tv
    rows = [{"symbol": "ABC", "window": 22, "mult": 4.5, "override": None, "anchored": True,
             "level": 123.456},
            {"symbol": "XYZ", "window": 22, "mult": 4.5, "override": None, "anchored": False,
             "level": 99.0}]
    b = tv.book_string(rows)
    assert "ABC=22,4.5000,E123.46" in b and "XYZ=22,4.5000,0" in b
