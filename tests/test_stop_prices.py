"""gtt_auto_shield.stop_prices: Jay's .5 convention (21-Oct-2026) and the exchange tick."""
import gtt_auto_shield as g


def test_half_convention(monkeypatch):
    monkeypatch.setattr(g, "_tick", lambda s: 0.10)
    assert g.stop_prices("X", 1976.86) == (1976.5, 1966.5)
    assert g.stop_prices("X", 1250.44) == (1249.5, 1242.5)     # never above the level asked for
    assert g.stop_prices("X", 1268.5) == (1268.5, 1261.5)
    t, lim = g.stop_prices("X", 100.2)
    assert t == 99.5 and lim <= t - 1.0


def test_coarse_tick_falls_back(monkeypatch):
    monkeypatch.setattr(g, "_tick", lambda s: 1.0)
    t, lim = g.stop_prices("X", 5234.7)
    assert t == 5234.0 and lim < t and lim == int(lim)


def test_target_on_tick(monkeypatch):
    monkeypatch.setattr(g, "_tick", lambda s: 0.05)
    assert g.target_price("X", 1817.03) == 1817.05
