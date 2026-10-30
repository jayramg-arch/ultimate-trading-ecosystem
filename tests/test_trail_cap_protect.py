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


def test_cap_protect_active_reads_history(monkeypatch, tmp_path):
    falling = {f"2026-10-{d:02d}": 100.0 - d for d in range(1, 25)}
    p = tmp_path / "portfolio_history.json"
    p.write_text(json.dumps(falling))
    real_join = g.os.path.join
    monkeypatch.setattr(g.os.path, "join",
                        lambda *a: str(p) if a[-1] == "portfolio_history.json" else real_join(*a))
    assert g._cap_protect_active() is True
    p.write_text("{}")
    assert g._cap_protect_active() is False
