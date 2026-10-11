"""market_hmm.py (11-Oct-2026) - is the market CALM or VOLATILE? A Gaussian Hidden Markov
Model on daily index returns. Streamlit-free (the page is commander_pages/market_hmm.py).

What it does
  The market is assumed to switch between K hidden regimes, each with its own mean daily
  return and its own volatility, and to stay in a regime with some probability each day.
  Baum-Welch (EM) fits the regime means, volatilities and the transition matrix to the
  index's daily log returns; the forward pass then gives P(regime | returns up to today).

Two probabilities, and which one to act on
  FILTERED  P(state_t | r_1..r_t)  - uses only data up to that day. This is what you could
            have known at the close; the "today" reading and every decision use it.
  SMOOTHED  P(state_t | r_1..r_T)  - uses the whole window, future included. Cleaner for
            drawing history, but it would NOT have been available live. Display only.
  Note: the model's PARAMETERS are fitted on the whole window, so even the filtered series
  carries mild hindsight in its calibration. It describes regimes; it is not a backtest.

No dependency beyond numpy/pandas (hmmlearn is not installed). States are ordered by
volatility, so state 0 is always the calmest.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

INDEXES = {"Nifty 500": "^CRSLDX", "Nifty 50": "^NSEI", "Nifty Midcap 150": "NIFTYMIDCAP150.NS"}
LABELS = {2: ["CALM", "VOLATILE"], 3: ["CALM", "NORMAL", "VOLATILE"]}


def load_returns(symbol: str = "^CRSLDX", period: str = "5y") -> pd.DataFrame:
    import data_provider as dp
    df = dp.fetch_ohlcv(symbol, period=period, interval="1d", use_cache=True, auto_adjust=True)
    if df is None or len(df) == 0:
        raise RuntimeError(f"no data for {symbol}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.title)[["Close"]].dropna()
    df["ret"] = np.log(df["Close"]).diff()
    return df.dropna()


def _norm_pdf(x, mu, sd):
    return np.exp(-0.5 * ((x[:, None] - mu) / sd) ** 2) / (sd * np.sqrt(2 * np.pi))


def _forward_backward(x, pi, A, mu, sd):
    T, K = len(x), len(mu)
    B = _norm_pdf(x, mu, sd) + 1e-300
    alpha = np.zeros((T, K)); c = np.zeros(T)
    alpha[0] = pi * B[0]; c[0] = alpha[0].sum(); alpha[0] /= c[0]
    for t in range(1, T):
        alpha[t] = (alpha[t - 1] @ A) * B[t]
        c[t] = alpha[t].sum(); alpha[t] /= c[t]
    beta = np.ones((T, K))
    for t in range(T - 2, -1, -1):
        beta[t] = (A @ (B[t + 1] * beta[t + 1])) / c[t + 1]
    gamma = alpha * beta
    gamma /= gamma.sum(1, keepdims=True)
    return alpha, beta, gamma, B, c


def fit(x: np.ndarray, K: int = 2, n_iter: int = 200, n_starts: int = 8, seed: int = 0) -> dict:
    """Baum-Welch with several random starts; keeps the best log-likelihood."""
    rng = np.random.default_rng(seed)
    best = None
    s0 = x.std()
    for _ in range(n_starts):
        mu = rng.normal(x.mean(), s0 * 0.2, K)
        sd = np.sort(s0 * rng.uniform(0.5, 2.0, K))
        A = np.full((K, K), 0.05 / max(K - 1, 1)); np.fill_diagonal(A, 0.95)
        pi = np.full(K, 1.0 / K)
        ll_prev = -np.inf
        for _ in range(n_iter):
            alpha, beta, gamma, B, c = _forward_backward(x, pi, A, mu, sd)
            ll = np.log(c).sum()
            xi = (alpha[:-1, :, None] * A[None] * (B[1:] * beta[1:])[:, None, :]) / c[1:, None, None]
            A = xi.sum(0) / gamma[:-1].sum(0)[:, None]
            A /= A.sum(1, keepdims=True)
            w = gamma.sum(0)
            mu = (gamma * x[:, None]).sum(0) / w
            sd = np.sqrt((gamma * (x[:, None] - mu) ** 2).sum(0) / w)
            sd = np.maximum(sd, 1e-5)
            pi = gamma[0]
            if abs(ll - ll_prev) < 1e-7:
                break
            ll_prev = ll
        if best is None or ll > best["ll"]:
            best = dict(ll=ll, pi=pi, A=A, mu=mu, sd=sd)
    o = np.argsort(best["sd"])                      # state 0 = calmest
    best["mu"], best["sd"], best["pi"] = best["mu"][o], best["sd"][o], best["pi"][o]
    best["A"] = best["A"][np.ix_(o, o)]
    k_par = K * K + 2 * K - 1                       # free parameters (approx.)
    best["bic"] = -2 * best["ll"] + k_par * np.log(len(x))
    return best


def analyse(symbol: str = "^CRSLDX", period: str = "5y", K: int = 2) -> dict:
    df = load_returns(symbol, period)
    x = df["ret"].values
    m = fit(x, K)
    alpha, _, gamma, _, _ = _forward_backward(x, m["pi"], m["A"], m["mu"], m["sd"])
    labels = LABELS.get(K, [f"S{i}" for i in range(K)])
    for i, lab in enumerate(labels):
        df[f"filt_{lab}"] = alpha[:, i]
        df[f"smooth_{lab}"] = gamma[:, i]
    df["state_filt"] = [labels[i] for i in alpha.argmax(1)]
    df["state_smooth"] = [labels[i] for i in gamma.argmax(1)]
    # days in the current (filtered) regime
    s = df["state_filt"].values
    run = 1
    for i in range(len(s) - 2, -1, -1):
        if s[i] != s[-1]:
            break
        run += 1
    # descriptive forward returns by regime (in-sample, uses the CAUSAL label)
    df["fwd20"] = df["Close"].shift(-20) / df["Close"] - 1
    states = []
    for i, lab in enumerate(labels):
        sub = df[df.state_filt == lab]
        states.append(dict(
            state=lab, ann_vol=float(m["sd"][i] * np.sqrt(252)), ann_drift=float(m["mu"][i] * 252),
            stay=float(m["A"][i, i]), exp_days=float(1 / max(1 - m["A"][i, i], 1e-9)),
            share=float((df.state_filt == lab).mean()),
            fwd20_mean=float(sub["fwd20"].mean()) if len(sub) else np.nan,
            fwd20_median=float(sub["fwd20"].median()) if len(sub) else np.nan,
            fwd20_n=int(sub["fwd20"].notna().sum())))
    last = df.iloc[-1]
    return dict(symbol=symbol, K=K, labels=labels, df=df, model=m, states=states,
                today=dict(date=str(df.index[-1].date()), state=last["state_filt"],
                           probs={lab: float(last[f"filt_{lab}"]) for lab in labels},
                           run_days=run, close=float(last["Close"])))


if __name__ == "__main__":
    for k in (2, 3):
        r = analyse(K=k)
        print(f"K={k}  BIC {r['model']['bic']:.0f}  today {r['today']}")
        print(pd.DataFrame(r["states"]).round(4).to_string(index=False))
