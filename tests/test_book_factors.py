"""book_factors (11-Oct-2026): participation ratio, Indian rupee format, board annotation."""
import numpy as np
import pandas as pd

import book_factors as bf


def test_participation_ratio_bounds():
    assert abs(bf.participation_ratio(np.eye(5)) - 5.0) < 1e-9          # 5 independent names
    assert abs(bf.participation_ratio(np.ones((5, 5))) - 1.0) < 1e-9    # 5 copies of one name


def test_inr_grouping():
    assert bf._inr(1674936) == "16,74,936"
    assert bf._inr(999) == "999"
    assert bf._inr(100000) == "1,00,000"


def test_annotate_inserts_after_pos(monkeypatch):
    monkeypatch.setattr(bf, "book_model", lambda *a, **k: {"ok": True})
    fits = {"AAA": {"held": True},
            "BBB": dict(held=False, d_bets=0.31, beta=0.9, mkt_corr=0.4, cluster_corr=0.5,
                        top_name="AAA", top_corr=0.6)}
    monkeypatch.setattr(bf, "candidate_fit", lambda s, m=None: fits.get(s))
    df = pd.DataFrame({"Symbol": ["AAA", "BBB", "CCC"], "Pos": ["x", "", ""], "Loc": [1, 2, 3]})
    out = bf.annotate_board(df)
    assert list(out.columns) == ["Symbol", "Pos", "ΔBets", "Fit", "Loc"]
    assert out.loc[0, "Fit"] == "held" and np.isnan(out.loc[0, "ΔBets"])
    assert out.loc[1, "ΔBets"] == 0.31 and "joins crowded cluster" in out.loc[1, "Fit"]
    assert out.loc[2, "Fit"] == "—"


def test_annotate_never_raises(monkeypatch):
    monkeypatch.setattr(bf, "book_model", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    df = pd.DataFrame({"Symbol": ["AAA"], "Pos": [""]})
    assert bf.annotate_board(df).equals(df)
