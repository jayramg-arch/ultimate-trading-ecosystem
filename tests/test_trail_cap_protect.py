"""The broker trail reads Risk Shield's capital-protection switch (30-Oct-2026).

Before this, gtt_auto_shield trailed on 5.0x while Risk Shield / v67 / the SL Dashboard
showed the 2.5x cap-protect Chandelier, so the resting Dhan stop followed the looser one."""
import json

import numpy as np
import pandas as pd

import gtt_auto_shield as g


def _frame(n=260):
    idx = pd.bdate_range("2025-09-01", periods=n)
    c = pd.Series(np.linspace(100, 200, n), index=idx)
    return pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c, "Volume": 1e5})


def test_chandelier_for_passes_cap_protect(monkeypatch):
    import data_provider
    monkeypatch.setattr(data_provider, "fetch_ohlcv", lambda *a, **k: _frame())
    j = {"timeframe": "Positional", "setup": ""}
    off = g._chandelier_for("X", j, bear=True, cap_protect=False)
    on = g._chandelier_for("X", j, bear=True, cap_protect=True)
    assert on["mult"] == 2.5 and on["src"] == "cap-protect"
    assert off["mult"] != 2.5
    assert on["ce"] > off["ce"]


def test_cap_protect_active_reads_book_nav(monkeypatch):
    import risk_common
    falling = {f"2026-10-{d:02d}": 1.0 - d / 100 for d in range(1, 25)}
    monkeypatch.setattr(risk_common, "book_nav_history", lambda path=None: falling)
    assert g._cap_protect_active() is True
    monkeypatch.setattr(risk_common, "book_nav_history", lambda path=None: {})
    assert g._cap_protect_active() is False


def test_book_nav_ignores_money_moved(tmp_path):
    """A withdrawal is not a drawdown: the 19-Oct-2026 cash move read as -22%."""
    import risk_common
    p = tmp_path / "system_equity.csv"
    rows = ["date,system,mv,cash,equity,flow,nav,n,unclassified,bench"]
    eq = [2000000, 2010000, 1410000, 1420000, 1430000, 1440000]
    fl = [0, 0, -600000, 0, 0, 0]
    for i, (e, f) in enumerate(zip(eq, fl)):
        rows.append(f"2026-10-{i + 1:02d},v1,0,0,{e},{f},1,1,0,1")
        rows.append(f"2026-10-{i + 1:02d},v2,0,0,999,0,1,0,0,1")
    p.write_text("\n".join(rows))
    nav = risk_common.book_nav_history(str(p))
    vals = [nav[k] for k in sorted(nav)]
    assert all(b >= a for a, b in zip(vals, vals[1:]))
    assert risk_common.capital_protection_active(nav) is False
