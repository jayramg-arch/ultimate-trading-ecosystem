"""book_factors.py (11-Oct-2026) - the book's factor model, from PCA on daily returns.

Recommendations 3 and 4 of docs/36_PCA_Study.md:
  3. Rank GO names on PORTFOLIO CONSTRUCTION, not on claimed alpha - the board gets two
     columns: ΔBets (how many independent bets the name would ADD to the current book)
     and Fit (beta · correlation with the book's market factor · the holding it overlaps
     most with).
  4. Measure book risk in FACTOR terms - Risk Shield's open-risk card gets one line:
     independent bets, market-factor share, beta-weighted exposure, and the crowded
     cluster.

Method
  Daily log returns, last WINDOW sessions (250 ≈ one year), from data_provider's 2y daily
  frames - the same frames the board already loads, so the cache serves them. The book's
  correlation matrix is decomposed; "independent bets" is the participation ratio of its
  eigenvalues, (Σλ)² / Σλ², which equals N for N uncorrelated names and 1 for N copies of
  one name. PC1 is signed to correlate positively with the Nifty 500 (it is the market).
  A candidate's ΔBets = participation ratio of the book WITH it, minus the book without
  it. Positive = it diversifies; around 0 = it is one more of what you already own.

Display only. Nothing here gates an order or moves a stop. Streamlit-free.
"""
from __future__ import annotations

import sqlite3
import time

import numpy as np
import pandas as pd

WINDOW = 250
MIN_OBS = 120
BENCH = "^CRSLDX"
_CACHE: dict = {}
_TTL_S = 3600
CLUSTER_R = 0.40          # a candidate this correlated with the PC2 cluster factor 'joins' it


def _closes(sym: str) -> pd.Series | None:
    import data_provider as dp
    try:
        df = dp.fetch_ohlcv(sym, period="2y", interval="1d", use_cache=True, auto_adjust=True)
    except Exception:
        return None
    if df is None or len(df) == 0:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.title)
    if "Close" not in df:
        return None
    s = df["Close"].dropna()
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    return s[~s.index.duplicated(keep="last")]


def _returns(sym: str) -> pd.Series | None:
    """Last WINDOW daily log returns; memoised per process for an hour (three boards a night)."""
    hit = _CACHE.get(("ret", sym))
    if hit and time.time() - hit[0] < _TTL_S:
        return hit[1]
    s = _closes(sym)
    r = None if s is None or len(s) < MIN_OBS + 1 else np.log(s).diff().dropna().iloc[-WINDOW:]
    _CACHE[("ret", sym)] = (time.time(), r)
    return r


def _inr(x: float) -> str:
    """₹ amount in Indian digit grouping (house rule): 1674936 -> 16,74,936."""
    n = int(round(abs(x))); s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:]); head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-" if x < 0 else "") + s


def participation_ratio(corr: np.ndarray) -> float:
    ev = np.clip(np.linalg.eigvalsh(corr), 0, None)
    return float(ev.sum() ** 2 / (ev ** 2).sum()) if ev.sum() > 0 else float("nan")


def open_book() -> dict:
    """{SYMBOL: cost value ₹} for OPEN journal rows, cash-park LIQUID* excluded."""
    from journal_path import JOURNAL_DB
    con = sqlite3.connect(JOURNAL_DB)
    try:
        rows = con.execute("SELECT symbol, quantity, buy_price FROM journal "
                           "WHERE UPPER(status)='OPEN'").fetchall()
    finally:
        con.close()
    book = {}
    for sym, q, px in rows:
        s = str(sym or "").upper().strip()
        if not s or s.startswith("LIQUID"):
            continue
        book[s] = book.get(s, 0.0) + float(q or 0) * float(px or 0)
    return book


def book_model(book: dict | None = None, force: bool = False) -> dict:
    """PCA on the book's daily returns. Cached for an hour per process."""
    key = "model"
    if not force and key in _CACHE and time.time() - _CACHE[key][0] < _TTL_S and book is None:
        return _CACHE[key][1]
    book = book if book is not None else open_book()
    rets, skipped = {}, []
    for s in book:
        r = _returns(s)
        (rets.__setitem__(s, r) if r is not None else skipped.append(s))
    bench = _returns(BENCH)
    if len(rets) < 3 or bench is None:
        m = dict(ok=False, reason=f"only {len(rets)} holdings with enough history", skipped=skipped)
        _CACHE[key] = (time.time(), m)
        return m
    R = pd.DataFrame(rets).dropna(how="all").fillna(0.0)
    R = R.loc[R.index.isin(bench.index)]
    b = bench.reindex(R.index).fillna(0.0)
    names = list(R.columns)
    C = np.corrcoef(R.values.T)
    ev, evec = np.linalg.eigh(C)
    o = ev.argsort()[::-1]; ev, evec = ev[o], evec[:, o]
    Z = (R - R.mean()) / R.std().replace(0, 1)
    pc1 = Z.values @ evec[:, 0]
    if np.corrcoef(pc1, b.values)[0, 1] < 0:
        evec[:, 0] *= -1; pc1 = -pc1
    pc2 = Z.values @ evec[:, 1]
    bvar = float(b.var())
    beta = {s: float(np.cov(R[s], b)[0, 1] / bvar) for s in names}
    w = np.array([book.get(s, 0.0) for s in names]); tot = w.sum() or 1.0
    # PC2 cluster: the side of PC2 with the larger total loading, |loading| >= 0.25
    l2 = dict(zip(names, evec[:, 1]))
    pos = sorted([s for s, v in l2.items() if v >= 0.25], key=lambda s: -l2[s])
    neg = sorted([s for s, v in l2.items() if v <= -0.25], key=lambda s: l2[s])
    cluster = pos if sum(l2[s] for s in pos) >= -sum(l2[s] for s in neg) else neg
    if cluster is neg:              # sign PC2 so the crowded cluster's side reads POSITIVE
        pc2 = -pc2
    m = dict(
        ok=True, names=names, skipped=skipped, n=len(names), days=len(R),
        eff_bets=participation_ratio(C), pc1_share=float(ev[0] / ev.sum()),
        pc1_mkt_corr=float(np.corrcoef(pc1, b.values)[0, 1]),
        beta=beta, book_beta=float((w * np.array([beta[s] for s in names])).sum() / tot),
        beta_exposure=float((w * np.array([beta[s] for s in names])).sum()), cost=float(tot),
        cluster=cluster, R=R, pc1=pd.Series(pc1, index=R.index), pc2=pd.Series(pc2, index=R.index),
        bench=b, C=C)
    _CACHE[key] = (time.time(), m)
    return m


def candidate_fit(sym: str, m: dict | None = None) -> dict | None:
    """How a NOT-held name would sit in the book. None when there is no usable history."""
    m = m or book_model()
    if not m.get("ok"):
        return None
    s = str(sym).upper().strip()
    if s in m["names"]:
        return dict(held=True)
    r = _returns(s)
    if r is None:
        return None
    R = m["R"]
    r = r.reindex(R.index)
    if r.notna().sum() < MIN_OBS:
        return None
    r = r.fillna(0.0)
    corr_h = R.corrwith(r)
    top = corr_h.abs().idxmax()
    C2 = np.corrcoef(np.column_stack([R.values, r.values]).T)
    return dict(
        held=False,
        d_bets=participation_ratio(C2) - m["eff_bets"],
        beta=float(np.cov(r, m["bench"])[0, 1] / m["bench"].var()),
        mkt_corr=float(np.corrcoef(r, m["pc1"])[0, 1]),
        cluster_corr=float(np.corrcoef(r, m["pc2"])[0, 1]) if m["cluster"] else float("nan"),
        top_name=str(top), top_corr=float(corr_h[top]))


def fit_text(f: dict | None) -> str:
    if not f:
        return "—"
    if f.get("held"):
        return "held"
    tail = " · ⚠ joins crowded cluster" if f.get("cluster_corr", 0) >= CLUSTER_R else ""
    return (f"β{f['beta']:.2f} · mkt r{f['mkt_corr']:.2f} · most like {f['top_name']} "
            f"r{f['top_corr']:.2f}{tail}")


def annotate_board(df: pd.DataFrame) -> pd.DataFrame:
    """Adds ΔBets and Fit beside Pos. Never raises - a failure leaves the board as it was."""
    if df is None or df.empty or "Symbol" not in df.columns:
        return df
    try:
        m = book_model()
    except Exception:
        return df
    if not m.get("ok"):
        return df
    fits = [candidate_fit(s, m) for s in df["Symbol"]]
    out = df.copy()
    out["ΔBets"] = [round(f["d_bets"], 2) if f and not f.get("held") else np.nan for f in fits]
    out["Fit"] = [fit_text(f) for f in fits]
    cols = [c for c in out.columns if c not in ("ΔBets", "Fit")]
    at = cols.index("Pos") + 1 if "Pos" in cols else len(cols)
    return out[cols[:at] + ["ΔBets", "Fit"] + cols[at:]]


def book_line(capital: float | None = None) -> str:
    """One line for the open-risk card (recommendation 4)."""
    m = book_model()
    if not m.get("ok"):
        return f"Factor view unavailable ({m.get('reason', 'no data')})."
    cap = f" ({m['beta_exposure'] / capital * 100:.0f}% of capital)" if capital else ""
    clus = (" · crowded cluster: " + ", ".join(m["cluster"][:5])) if m["cluster"] else ""
    return (f"{m['n']} holdings act like <b>{m['eff_bets']:.1f} independent bets</b> · market factor "
            f"<b>{m['pc1_share']:.0%}</b> of the book's moves (r {m['pc1_mkt_corr']:+.2f} with Nifty 500) · "
            f"book beta <b>{m['book_beta']:.2f}</b> · beta-weighted exposure ₹{_inr(m['beta_exposure'])}{cap}"
            f"{clus}")


if __name__ == "__main__":
    m = book_model(force=True)
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items()
           if k not in ("R", "pc1", "pc2", "bench", "C", "beta")})
    for s in ("TITAN", "ICICIBANK", "SUNPHARMA", "HDFCBANK"):
        print(s, fit_text(candidate_fit(s, m)), candidate_fit(s, m))
