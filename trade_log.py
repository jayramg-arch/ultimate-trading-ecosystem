"""trade_log.py - the reviewer's TAKE pool against the trades actually taken (3-Oct-2026, Jay).

Jay's rule: "I act only on the Reviewer Log. I take a trade if it is a Take-it on the log,
but I'm selective and choose only a few." So the population is every TAKE / TAKE · REDUCED
review (one per symbol + timeframe + trigger bar, review_priority.pick), and the question is
which of them became a real trade and what each side did:

  TAKEN    a Dhan BUY of the same symbol within TAKEN_WINDOW sessions after the review -
           fill price and quantity from Dhan's own trade history (authoritative), slippage
           vs the plan entry, the plan's R unit, and the outcome (open MTM or closed R).
  SKIPPED  a TAKE that was not acted on - its outcome is what S4's plan would have done
           (entry_shadow V_plan, R at 5 / 10 sessions), so "my picks" can be compared with
           "the ones I passed over".
  OFF-LOG  a BUY with no TAKE review in the window before it - a discretionary trade, or one
           taken against a WAIT / PASS (named, if a review exists).

Read-only: Dhan trade history, the journal, the review log, entry_shadow.csv.
Writes reports/trade_log.csv and docs/portal/34_trade_log.html.

    python trade_log.py
"""
from __future__ import annotations

import datetime as dt
import html
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
LOG = os.path.join(HERE, "logs", "ai_review_log.csv")
SHADOW = os.path.join(HERE, "logs", "entry_shadow.csv")
OUT_CSV = os.path.join(HERE, "reports", "trade_log.csv")
OUT_HTML = os.path.join(HERE, "docs", "portal", "34_trade_log.html")
TAKEN_WINDOW = 3          # trading sessions after the review in which a BUY counts as taking it


def _canon(s: str) -> str:
    try:
        from dhan_ohlcv import canonical_nse_symbol
        return (canonical_nse_symbol(str(s)) or str(s)).upper()
    except Exception:
        return re.sub(r"[_]", "-", str(s).upper())


def _sessions_after(d: dt.date, n: int) -> dt.date:
    try:
        import nse_calendar as nc
        out = d
        for _ in range(n):
            out = out + dt.timedelta(days=1)
            while not nc.is_trading_day(out):
                out = out + dt.timedelta(days=1)
        return out
    except Exception:
        return d + dt.timedelta(days=n + 2)


def dhan_buys(since: str) -> pd.DataFrame:
    """Dhan BUY fills since `since`, aggregated per symbol and day."""
    import ai_reconcile_engine as ar
    df = ar.fetch_trade_history()
    if df is None or df.empty:
        return pd.DataFrame(columns=["symbol", "date", "time", "qty", "price"])
    df = df[df["transactionType"].astype(str).str.upper() == "BUY"].copy()
    df["time"] = pd.to_datetime(df["exchangeTime"], errors="coerce")
    df = df[df["time"] >= pd.Timestamp(since)]
    try:
        from dhan_symbols import get_nse_secid_to_symbol
        m = get_nse_secid_to_symbol() or {}
        df["symbol"] = df["securityId"].astype(str).map(lambda x: m.get(x) or m.get(int(x)) if str(x).isdigit() else m.get(x))
    except Exception:
        df["symbol"] = None
    df["symbol"] = df["symbol"].fillna(df["customSymbol"]).map(_canon)
    df["qty"] = pd.to_numeric(df["tradedQuantity"], errors="coerce")
    df["px"] = pd.to_numeric(df["tradedPrice"], errors="coerce")
    df["date"] = df["time"].dt.date
    g = df.groupby(["symbol", "date"]).apply(
        lambda x: pd.Series({"time": x["time"].min(), "qty": x["qty"].sum(),
                             "price": (x["qty"] * x["px"]).sum() / x["qty"].sum()}), include_groups=False)
    return g.reset_index()


def journal_rows() -> pd.DataFrame:
    import sqlite3
    import journal_path as jp
    c = sqlite3.connect(jp.JOURNAL_DB)
    j = pd.read_sql("select symbol, entry_date, buy_price, quantity, status, exit_date, exit_price, stoploss "
                    "from journal", c)
    j["symbol"] = j["symbol"].map(_canon)
    return j


def _last_close(sym: str):
    try:
        import data_provider as dp
        d = dp.fetch_ohlcv(sym, period="1mo", interval="1d", use_cache=True)
        return float(d["Close"].iloc[-1])
    except Exception:
        return None


def build() -> tuple[pd.DataFrame, dict]:
    import review_priority as rp
    log = pd.read_csv(LOG, dtype=str, keep_default_na=False)
    log = rp.pick(log)
    log["ts"] = pd.to_datetime(log["ts"], errors="coerce")
    ru = log["ai_ruling"].str.upper()
    log["ruling"] = np.where(ru.str.contains("TAKE"), np.where(ru.str.contains("REDUC"), "TAKE·REDUCED", "TAKE"),
                             np.where(ru.str.contains("WAIT"), "WAIT", np.where(ru.str.contains("PASS"), "PASS", "OTHER")))
    log["sym"] = log["symbol"].map(_canon)
    since = (log["ts"].min() - pd.Timedelta(days=1)).date().isoformat() if len(log) else "2026-09-10"
    buys = dhan_buys(since)
    jr = journal_rows()
    sh = pd.read_csv(SHADOW) if os.path.exists(SHADOW) else pd.DataFrame()
    rows, used = [], set()
    take = log[log["ruling"].str.startswith("TAKE")].sort_values("ts")
    for _, r in take.iterrows():
        d0 = r["ts"].date()
        d1 = _sessions_after(d0, TAKEN_WINDOW)
        b = buys[(buys["symbol"] == r["sym"]) & (buys["date"] >= d0) & (buys["date"] <= d1)] if len(buys) else buys
        b = b[b["time"] >= r["ts"]] if len(b) else b
        base = {"review_ts": r["ts"], "symbol": r["sym"], "tf": r["tf"], "tier": int(r["tier"]),
                "ruling": r["ruling"], "plan_entry": pd.to_numeric(r.get("entry"), errors="coerce"),
                "plan_stop": pd.to_numeric(r.get("stop"), errors="coerce"),
                "plan_t1": pd.to_numeric(r.get("t1"), errors="coerce"), "file": r.get("file", "")}
        if len(b):
            f = b.iloc[0]
            used.add((f["symbol"], f["date"]))
            e, s = base["plan_entry"], base["plan_stop"]
            risk = (f["price"] - s) if pd.notna(s) else np.nan
            j = jr[(jr["symbol"] == r["sym"])]
            j = j[pd.to_datetime(j["entry_date"], errors="coerce").dt.date >= d0] if len(j) else j
            status, exit_px = (str(j.iloc[0]["status"]), pd.to_numeric(j.iloc[0]["exit_price"], errors="coerce")) if len(j) else ("OPEN?", np.nan)
            px = exit_px if (status.upper() == "CLOSED" and pd.notna(exit_px)) else _last_close(r["sym"])
            base.update({"state": "TAKEN", "fill_ts": f["time"], "fill_qty": f["qty"], "fill_px": round(f["price"], 2),
                         "slip_pct": round((f["price"] / e - 1) * 100, 2) if pd.notna(e) and e else np.nan,
                         "status": status, "R": round((px - f["price"]) / risk, 2) if (px and risk and risk > 0) else np.nan})
        else:
            o = sh[(sh.get("symbol", pd.Series(dtype=str)).astype(str).map(_canon) == r["sym"]) &
                   (pd.to_datetime(sh.get("ts", pd.Series(dtype=str)), errors="coerce") == r["ts"]) &
                   (sh.get("variant", pd.Series(dtype=str)) == "V_plan")] if len(sh) else pd.DataFrame()
            base.update({"state": "SKIPPED", "status": (o.iloc[0]["status"] if len(o) else "no shadow"),
                         "R5": (o.iloc[0].get("R5") if len(o) else np.nan), "R10": (o.iloc[0].get("R10") if len(o) else np.nan)})
        rows.append(base)
    # OFF-LOG: buys not explained by a TAKE
    for _, f in (buys.iterrows() if len(buys) else []):
        if (f["symbol"], f["date"]) in used:
            continue
        prior = log[(log["sym"] == f["symbol"]) & (log["ts"] <= f["time"])].sort_values("ts")
        last = prior.iloc[-1] if len(prior) else None
        rows.append({"review_ts": (last["ts"] if last is not None else pd.NaT), "symbol": f["symbol"], "state": "OFF-LOG",
                     "ruling": (last["ruling"] if last is not None else "no review"), "fill_ts": f["time"],
                     "fill_qty": f["qty"], "fill_px": round(f["price"], 2)})
    df = pd.DataFrame(rows)
    st = df["state"].value_counts().to_dict() if len(df) else {}
    summ = {"take_pool": int((df["state"].isin(["TAKEN", "SKIPPED"])).sum()) if len(df) else 0,
            "taken": st.get("TAKEN", 0), "skipped": st.get("SKIPPED", 0), "off_log": st.get("OFF-LOG", 0),
            "since": since, "buys": len(buys)}
    if len(df) and "R" in df:
        summ["taken_R"] = float(df.loc[df.state == "TAKEN", "R"].mean()) if (df.state == "TAKEN").any() else None
    for hz in ("R10", "R5"):              # 10 sessions once they exist, 5 until then
        if len(df) and hz in df:
            sk = pd.to_numeric(df.loc[df.state == "SKIPPED", hz], errors="coerce").dropna()
            if len(sk):
                summ["skipped_R"], summ["skipped_R_n"], summ["skipped_hz"] = float(sk.mean()), int(len(sk)), hz
                break
    return df, summ


def summary_line(s: dict) -> str:
    sel = (100.0 * s["taken"] / s["take_pool"]) if s.get("take_pool") else 0
    out = "TAKE pool %d · taken %d (%.0f%%) · off-log buys %d" % (s.get("take_pool", 0), s.get("taken", 0), sel, s.get("off_log", 0))
    if s.get("taken_R") is not None:
        out += " · taken mean R %+.2f" % s["taken_R"]
    if s.get("skipped_R") is not None:
        out += " · skipped TAKEs (S4 plan, %s sessions) %+.2fR n=%d" % (s["skipped_hz"][1:], s["skipped_R"], s["skipped_R_n"])
    return out


def page(df: pd.DataFrame, s: dict) -> str:
    e = html.escape
    css = ("body{font:15px/1.55 Georgia,serif;max-width:1150px;margin:24px auto;padding:0 18px;color:#1d1d1f;background:#fbfaf7}"
           "h1{font:700 30px Archivo,Arial,sans-serif;margin:0 0 6px}h2{font:600 19px Archivo,Arial,sans-serif;margin:26px 0 8px}"
           "table{border-collapse:collapse;width:100%;font:13px 'IBM Plex Mono',monospace}td,th{border-bottom:1px solid #e3e0d8;padding:4px 8px;text-align:left}"
           ".note{background:#f1efe8;padding:10px 14px;border-left:3px solid #b08d2c;margin:12px 0}"
           "@media (prefers-color-scheme:dark){body{background:#16161a;color:#e8e6e1}td,th{border-color:#333}.note{background:#222}}")
    L = ['<meta charset="utf-8"><title>The Trade Log</title><style>%s</style>' % css, "<h1>The Trade Log</h1>",
         "<p>Every TAKE the reviewer gave (one per symbol, timeframe and trigger bar), against what was actually "
         "bought on Dhan within %d sessions. Generated %s.</p>" % (TAKEN_WINDOW, dt.datetime.now().strftime("%d %b %Y %H:%M")),
         '<div class="note"><b>%s</b><br>TAKEN = a Dhan buy followed the TAKE. SKIPPED = not acted on; its R is what '
         "S4's plan would have done. OFF-LOG = a buy with no TAKE before it.</div>" % e(summary_line(s))]
    for state in ("TAKEN", "OFF-LOG", "SKIPPED"):
        g = df[df["state"] == state] if len(df) else df
        L.append("<h2>%s · %d</h2>" % (state, len(g)))
        if not len(g):
            L.append("<p>None.</p>")
            continue
        cols = [c for c in ["review_ts", "symbol", "tf", "tier", "ruling", "plan_entry", "plan_stop", "plan_t1", "fill_ts",
                            "fill_qty", "fill_px", "slip_pct", "status", "R", "R5", "R10"] if c in g.columns]
        L.append("<table><tr>" + "".join("<th>%s</th>" % c for c in cols) + "</tr>")
        for _, r in g.sort_values("review_ts", ascending=False).head(300).iterrows():
            L.append("<tr>" + "".join("<td>%s</td>" % e("" if pd.isna(r.get(c)) else (str(r.get(c))[:16] if "ts" in c else str(r.get(c)))) for c in cols) + "</tr>")
        L.append("</table>")
    return "\n".join(L)


def main() -> int:
    df, s = build()
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    try:
        from io_utils import atomic_write_text
        atomic_write_text(OUT_HTML, page(df, s))
    except Exception:
        open(OUT_HTML, "w", encoding="utf-8").write(page(df, s))
    print("trade log: " + summary_line(s) + "  (Dhan buys since %s: %d)" % (s["since"], s["buys"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
