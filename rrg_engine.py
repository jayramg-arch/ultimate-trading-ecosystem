"""
rrg_engine.py — Canonical JdK Relative Rotation Graph (RRG) Engine

Implements the official JdK Relative Rotation Graph math formula:
  1. RS = (Security Close / Benchmark Close)
  2. RS_SMA = Rolling Mean(RS, jdk_length) [Default: 12]
  3. RS_Ratio_Raw = 100.0 + ((RS - RS_SMA) / RS_SMA) * 100.0
  4. RS_Ratio = Rolling Mean(RS_Ratio_Raw, 5) [5-bar smoothing]
  5. RM1 = 100.0 * (RS_Ratio / Shift(RS_Ratio, 1))
  6. RS_Momentum = Rolling Mean(RM1, jdk_length)

Renders an interactive 2D Scatter Plot canvas in Plotly with:
  • 4 Shaded Quadrants (Leading 🟢, Weakening 🟠, Lagging 🔴, Improving 🔵)
  • (100, 100) Baseline Crosshairs
  • Historical Trajectory Tails (Gradient/Opacity fading) showing clockwise rotation
  • Sector & Stock Drill-down capability
"""

from __future__ import annotations

import math
import logging
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import numpy as np
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# UNIVERSE LOADER  (moved here 12-Aug-2026)
#
# It lived in pages/6_rrg.py, and the main app tried to reach it with
#     from pages.6_rrg import load_universe_data
# which is not importable at all - a module name cannot start with a digit, so
# Python raised SyntaxError at line 35 and the ENTIRE app failed to compile.
# importlib would load it but is also wrong here: 6_rrg.py calls
# st.set_page_config() and st.title() at top level, so importing it would render
# the RRG page into whatever page you were on.
#
# It belongs beside the other RRG functions anyway. Both callers import it from
# here now, so there is one definition.
#
# The streamlit cache is applied only if streamlit is importable, so this module
# stays usable from a plain script (validation, cron) with no behaviour change
# in the app.
# ---------------------------------------------------------------------------
try:
    import streamlit as _st
    _cache = _st.cache_data(ttl=600, show_spinner=False)
except Exception:
    def _cache(fn):
        return fn


@_cache
def load_universe_data(symbols: tuple, period: str = "1y", interval: str = "1wk") -> dict:
    """Fetch OHLCV for a tuple of symbols. Keys are stripped of .NS / ^."""
    import data_provider as dp
    data_map = {}
    for sym in symbols:
        try:
            df = dp.fetch_ohlcv(sym, period=period, interval=interval, auto_adjust=True, use_cache=True)
            if df is not None and not df.empty and 'Close' in df.columns:
                data_map[sym.replace('.NS', '').replace('^', '')] = df
        except Exception as exc:
            logger.debug("load_universe_data: %s failed: %s", sym, exc)
    return data_map

# Sector Indices Dictionary
SECTOR_INDICES = {
    'Nifty Bank':           '^NSEBANK',
    'Nifty IT':             '^CNXIT',
    'Nifty Pharma':         '^CNXPHARMA',
    'Nifty Auto':           '^CNXAUTO',
    'Nifty Metal':          '^CNXMETAL',
    'Nifty FMCG':           '^CNXFMCG',
    'Nifty Realty':         '^CNXREALTY',
    'Nifty Energy':         '^CNXENERGY',
    'Nifty Infra':          '^CNXINFRA',
    'Nifty PSE':            '^CNXPSE',
    'Nifty Media':          '^CNXMEDIA',
    'Capital Goods & Def':  '^CNXINFRA',
    'Nifty Fin Svc':        'NIFTY_FIN_SERVICE.NS',
    'Nifty PSU Bank':       '^CNXPSUBANK',
    'Nifty Pvt Bank':       'NIFTY_PVT_BANK.NS',
    'Nifty Services':       '^CNXSERVICE',
    'Nifty Consumption':    '^CNXCONSUM',
    'Nifty Commodities':    '^CNXCMDT',
    'Nifty MNC':            '^CNXMNC',
}

# Color System for Quadrants
QUADRANT_COLORS = {
    'Leading':    {'bg': 'rgba(38, 166, 154, 0.12)',  'border': '#26a69a', 'label': '🟢 Leading'},
    'Weakening':  {'bg': 'rgba(255, 179, 0, 0.12)',   'border': '#ffb300', 'label': '🟠 Weakening'},
    'Lagging':    {'bg': 'rgba(239, 83, 80, 0.12)',   'border': '#ef5350', 'label': '🔴 Lagging'},
    'Improving':  {'bg': 'rgba(41, 98, 255, 0.12)',   'border': '#2962ff', 'label': '🔵 Improving'},
}


def calculate_jdk_rrg(
    sec_series: pd.Series,
    bench_series: pd.Series,
    jdk_length: int = 12,
    smooth_length: int = 5
) -> pd.DataFrame:
    """
    Computes JdK RS-Ratio and RS-Momentum series for a single security against a benchmark.
    Returns a DataFrame with columns: ['RS', 'RS_Ratio', 'RS_Momentum', 'Quadrant']
    """
    if sec_series is None or sec_series.empty or bench_series is None or bench_series.empty:
        return pd.DataFrame()

    # Align timestamps
    df = pd.DataFrame({'sec': sec_series, 'bench': bench_series}).dropna()
    if len(df) < (jdk_length + smooth_length + 2):
        return pd.DataFrame()

    # 1. Raw Relative Strength
    rs = df['sec'] / df['bench']

    # 2. RS Moving Average
    rs_sma = rs.rolling(window=jdk_length, min_periods=jdk_length).mean()

    # 3. RS-Ratio Raw (Normalized around 100)
    rs_ratio_raw = 100.0 + ((rs - rs_sma) / rs_sma) * 100.0

    # 4. 5-bar Smoothing
    rs_ratio = rs_ratio_raw.rolling(window=smooth_length, min_periods=smooth_length).mean()

    # 5. Rate of Change of RS-Ratio (RM1)
    rs_ratio_prev = rs_ratio.shift(1)
    rm1 = 100.0 * (rs_ratio / rs_ratio_prev)

    # 6. RS-Momentum (12-period SMA of RM1)
    rs_momentum = rm1.rolling(window=jdk_length, min_periods=jdk_length).mean()

    res = pd.DataFrame({
        'Close': df['sec'],
        'RS': rs,
        'RS_Ratio': rs_ratio,
        'RS_Momentum': rs_momentum
    }, index=df.index).dropna()

    if res.empty:
        return pd.DataFrame()

    # Assign Quadrant
    def get_quadrant(r, m):
        if r >= 100.0 and m >= 100.0:
            return 'Leading'
        elif r >= 100.0 and m < 100.0:
            return 'Weakening'
        elif r < 100.0 and m < 100.0:
            return 'Lagging'
        else:
            return 'Improving'

    res['Quadrant'] = [get_quadrant(r, m) for r, m in zip(res['RS_Ratio'], res['RS_Momentum'])]
    return res


def compute_rrg_info(
    v: float, 
    m: float, 
    vt: float, 
    mt: float
) -> Tuple[str, str, str, str, int, bool]:
    """
    Exact Python implementation of Pine Script v67.4 f_rrg_info().
    Inputs:
      v  = Centered RS-Ratio (RS_Ratio - 100.0)
      m  = Centered RS-Momentum (RS_Momentum - 100.0)
      vt = Trailing Centered RS-Ratio (N bars ago)
      mt = Trailing Centered RS-Momentum (N bars ago)
      
    Returns:
      (arrow_emoji, trajectory_str, current_quadrant, next_quadrant, score_bonus, is_tradeable)
    """
    dv = v - vt
    dm = m - mt

    # Current Quadrant
    if v >= 0.0 and m >= 0.0:
        cur = "LEADING"
    elif v >= 0.0 and m < 0.0:
        cur = "WEAKENING"
    elif v < 0.0 and m < 0.0:
        cur = "LAGGING"
    else:
        cur = "IMPROVING"

    # Predictive Next Quadrant (Threshold velocity = 0.3)
    nxt = cur
    if cur == "LEADING":
        if dm < -0.3:
            nxt = "WEAKENING"
        elif dv < -0.3 and dm < 0.3:
            nxt = "IMPROVING"
    elif cur == "WEAKENING":
        if dv < -0.3:
            nxt = "LAGGING"
        elif dm > 0.3 and dv > -0.3:
            nxt = "LEADING"
    elif cur == "LAGGING":
        if dm > 0.3:
            nxt = "IMPROVING"
        elif dv > 0.3 and dm > -0.3:
            nxt = "WEAKENING"
    else: # IMPROVING
        if dv > 0.3:
            nxt = "LEADING"
        elif dm < -0.3 and dv < 0.3:
            nxt = "LAGGING"

    # Rotational Vector Arrow Emoji
    if dv > 0.3:
        arrow = "↗️" if dm > 0.3 else ("↘️" if dm < -0.3 else "➡️")
    elif dv < -0.3:
        arrow = "↖️" if dm > 0.3 else ("↙️" if dm < -0.3 else "⬅️")
    else:
        arrow = "⬆️" if dm > 0.3 else ("⬇️" if dm < -0.3 else "•")

    # Trajectory String
    traj = f"{cur} (stable)" if nxt == cur else f"{cur} → {nxt}"

    # Score: Only LEADING earns +2 bonus
    sc = 2 if cur == "LEADING" else 0

    # Tradeable Gate (Cell-level positive alpha combinations ONLY)
    # Rejects cliff-edge LEADING -> WEAKENING and WEAKENING -> LAGGING
    tr = (
        (cur == "LEADING" and nxt in ["LEADING", "IMPROVING"]) or
        (cur == "IMPROVING" and nxt == "LEADING") or
        (cur == "LAGGING" and nxt == "IMPROVING") or
        (cur == "WEAKENING" and nxt == "LEADING")
    )

    return arrow, traj, cur, nxt, sc, tr


def compute_universe_rrg(
    data_dict: Dict[str, pd.DataFrame],
    benchmark_symbol: str = "^CRSLDX",
    jdk_length: int = 12,
    tail_length: int = 6
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    """
    Computes RRG trajectory for all symbols in data_dict against the benchmark
    using the optimized Pine Script v67.4 formula.
    """
    if benchmark_symbol not in data_dict and "^NSEI" in data_dict:
        benchmark_symbol = "^NSEI"

    if benchmark_symbol not in data_dict or data_dict[benchmark_symbol].empty:
        if not data_dict:
            return pd.DataFrame(), {}
        benchmark_symbol = list(data_dict.keys())[0]

    bench_df = data_dict[benchmark_symbol]
    bench_close = bench_df['Close'].dropna() if 'Close' in bench_df.columns else bench_df.iloc[:, 0].dropna()

    summary_rows = []
    tails_dict = {}

    for sym, df in data_dict.items():
        if sym == benchmark_symbol:
            continue
        if df.empty or 'Close' not in df.columns:
            continue

        sec_close = df['Close'].dropna()
        rrg_df = calculate_jdk_rrg(sec_close, bench_close, jdk_length=jdk_length)

        if rrg_df.empty or len(rrg_df) < tail_length:
            continue

        # Extract last N bars for historical tail
        tail_df = rrg_df.tail(tail_length).copy()
        tails_dict[sym] = tail_df

        # Current (Latest bar) stats
        curr = tail_df.iloc[-1]
        prev_tail = tail_df.iloc[-1 - min(tail_length - 1, 4)] # N-bar trailing anchor

        v = curr['RS_Ratio'] - 100.0
        m = curr['RS_Momentum'] - 100.0
        vt = prev_tail['RS_Ratio'] - 100.0
        mt = prev_tail['RS_Momentum'] - 100.0

        # Exact Pine v67.4 RRG Info Evaluation
        arrow, traj, cur_q, nxt_q, rrg_sc, is_tradeable = compute_rrg_info(v, m, vt, mt)

        # Performance Metrics
        recent_chg = ((sec_close.iloc[-1] / sec_close.iloc[-5]) - 1) * 100.0 if len(sec_close) >= 5 else 0.0
        dist_from_center = math.sqrt(v**2 + m**2)

        # Heading degrees
        dx = curr['RS_Ratio'] - prev_tail['RS_Ratio']
        dy = curr['RS_Momentum'] - prev_tail['RS_Momentum']
        heading_deg = (math.degrees(math.atan2(dy, dx)) + 360) % 360

        quad_title = curr['Quadrant']

        summary_rows.append({
            'Symbol':           sym,
            'RS-Ratio':         round(curr['RS_Ratio'], 2),
            'RS-Momentum':      round(curr['RS_Momentum'], 2),
            'Quadrant':         quad_title,
            'Quadrant_Badge':   QUADRANT_COLORS[quad_title]['label'],
            '4W %':             round(recent_chg, 2),
            'Distance':         round(dist_from_center, 2),
            'Heading Deg':      round(heading_deg, 1),
            'Arrow':            arrow,
            'Trajectory':       traj,
            'Next Quadrant':    nxt_q,
            'RRG Score':        rrg_sc,
            'Tradeable Gate':   "✓ BUY OK" if is_tradeable else "✗ WAIT",
            'Is_Tradeable':     is_tradeable,
            'Last_Price':       round(curr['Close'], 2)
        })

    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values(by='Distance', ascending=False)

    return summary_df, tails_dict


def render_rrg_plotly(
    summary_df: pd.DataFrame,
    tails_dict: Dict[str, pd.DataFrame],
    title: str = "Relative Rotation Graph (RRG)",
    tail_length: int = 6,
    selected_symbols: Optional[List[str]] = None
) -> go.Figure:
    """
    Renders an interactive 4-Quadrant Plotly Scatter Chart with trailing rotation tails.
    """
    fig = go.Figure()

    if summary_df.empty:
        fig.update_layout(
            title="No RRG Data Available",
            template="plotly_dark",
            height=600
        )
        return fig

    # Filter symbols if user specified a subset
    if selected_symbols:
        summary_df = summary_df[summary_df['Symbol'].isin(selected_symbols)]

    # Compute plot bounds dynamically around (100, 100)
    max_r = max(abs(summary_df['RS-Ratio'] - 100).max(), 2.5) if not summary_df.empty else 5.0
    max_m = max(abs(summary_df['RS-Momentum'] - 100).max(), 2.5) if not summary_df.empty else 5.0
    bound = max(max_r, max_m) * 1.25

    x_min, x_max = 100.0 - bound, 100.0 + bound
    y_min, y_max = 100.0 - bound, 100.0 + bound

    # ── 1. Quadrant Background Shading ──────────────────────────────────────────
    # Top-Right: Leading (Green)
    fig.add_shape(type="rect", x0=100, y0=100, x1=x_max, y1=y_max,
                  fillcolor="rgba(38, 166, 154, 0.08)", line=dict(width=0), layer="below")
    # Bottom-Right: Weakening (Orange)
    fig.add_shape(type="rect", x0=100, y0=y_min, x1=x_max, y1=100,
                  fillcolor="rgba(255, 179, 0, 0.08)", line=dict(width=0), layer="below")
    # Bottom-Left: Lagging (Red)
    fig.add_shape(type="rect", x0=x_min, y0=y_min, x1=100, y1=100,
                  fillcolor="rgba(239, 83, 80, 0.08)", line=dict(width=0), layer="below")
    # Top-Left: Improving (Blue)
    fig.add_shape(type="rect", x0=x_min, y0=100, x1=100, y1=y_max,
                  fillcolor="rgba(41, 98, 255, 0.08)", line=dict(width=0), layer="below")

    # ── 2. Quadrant Labels ──────────────────────────────────────────────────────
    fig.add_annotation(x=x_max - (bound*0.15), y=y_max - (bound*0.1), text="<b>LEADING</b>",
                       showarrow=False, font=dict(size=14, color="#26a69a"))
    fig.add_annotation(x=x_max - (bound*0.15), y=y_min + (bound*0.1), text="<b>WEAKENING</b>",
                       showarrow=False, font=dict(size=14, color="#ffb300"))
    fig.add_annotation(x=x_min + (bound*0.15), y=y_min + (bound*0.1), text="<b>LAGGING</b>",
                       showarrow=False, font=dict(size=14, color="#ef5350"))
    fig.add_annotation(x=x_min + (bound*0.15), y=y_max - (bound*0.1), text="<b>IMPROVING</b>",
                       showarrow=False, font=dict(size=14, color="#2962ff"))

    # ── 3. Crosshairs at (100, 100) ─────────────────────────────────────────────
    fig.add_hline(y=100.0, line=dict(color="#64748b", width=1.5, dash="dash"))
    fig.add_vline(x=100.0, line=dict(color="#64748b", width=1.5, dash="dash"))

    # Benchmark Center Point
    fig.add_trace(go.Scatter(
        x=[100.0], y=[100.0],
        mode="markers+text",
        marker=dict(size=12, color="#ffffff", symbol="cross"),
        text=["BENCHMARK (100, 100)"],
        textposition="top center",
        name="Benchmark Center",
        hoverinfo="text"
    ))

    # ── 4. Trailing Rotation Tails & Head Markers ────────────────────────────────
    for _, row in summary_df.iterrows():
        sym = row['Symbol']
        quad = row['Quadrant']
        color = QUADRANT_COLORS[quad]['border']

        if sym not in tails_dict:
            continue

        tail_df = tails_dict[sym]
        x_vals = tail_df['RS_Ratio'].tolist()
        y_vals = tail_df['RS_Momentum'].tolist()

        # Draw Trailing Line
        fig.add_trace(go.Scatter(
            x=x_vals,
            y=y_vals,
            mode='lines',
            line=dict(color=color, width=2),
            hoverinfo='none',
            showlegend=False
        ))

        # Draw Fading Tail Dots with Historical Tooltips
        n_dots = len(tail_df)
        dot_sizes = np.linspace(3, 10, n_dots).tolist()
        
        tail_hover_texts = []
        for idx in range(n_dots - 1):
            row_hist = tail_df.iloc[idx]
            dt_str = row_hist.name.strftime('%d %b %Y') if hasattr(row_hist.name, 'strftime') else str(row_hist.name)
            bars_ago = n_dots - 1 - idx
            time_unit = "weeks" if "1wk" in str(tail_df.index.freq) or bars_ago > 1 else "bars"
            
            tail_hover_texts.append(
                f"<b>{sym}</b> ({bars_ago} {time_unit} ago · {dt_str})<br>"
                f"Quadrant: {QUADRANT_COLORS.get(row_hist['Quadrant'], {}).get('label', row_hist['Quadrant'])}<br>"
                f"RS-Ratio: {row_hist['RS_Ratio']:.2f}<br>"
                f"RS-Momentum: {row_hist['RS_Momentum']:.2f}"
            )

        fig.add_trace(go.Scatter(
            x=x_vals[:-1],
            y=y_vals[:-1],
            mode='markers',
            marker=dict(
                size=dot_sizes[:-1], 
                color=color, 
                opacity=0.6,
                line=dict(width=0.5, color='#ffffff')
            ),
            hovertext=tail_hover_texts,
            hoverinfo='text',
            showlegend=False
        ))

        # Draw Current Head Marker (Latest point with text label & arrowhead vector)
        head_x = x_vals[-1]
        head_y = y_vals[-1]
        head_dt = tail_df.index[-1].strftime('%d %b %Y') if hasattr(tail_df.index[-1], 'strftime') else str(tail_df.index[-1])
        
        hover_text = (
            f"<b>{sym}</b> (Current · {head_dt})<br>"
            f"Quadrant: {QUADRANT_COLORS[quad]['label']}<br>"
            f"RS-Ratio: {head_x:.2f}<br>"
            f"RS-Momentum: {head_y:.2f}<br>"
            f"4W Change: {row['4W %']:.1f}%<br>"
            f"Trajectory: {row['Trajectory']}<br>"
            f"Tradeable Gate: {row['Tradeable Gate']}"
        )

        fig.add_trace(go.Scatter(
            x=[head_x],
            y=[head_y],
            mode='markers+text',
            marker=dict(size=12, color=color, symbol='circle', line=dict(color='#ffffff', width=2)),
            text=[f"  <b>{sym}</b>"],
            textposition="top right",
            hovertext=[hover_text],
            hoverinfo="text",
            name=sym
        ))

    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", font=dict(size=18, color="#ffffff")),
        xaxis=dict(
            title="<b>RS-Ratio (Trend) →</b>",
            range=[x_min, x_max],
            gridcolor="#334155",
            zeroline=False
        ),
        yaxis=dict(
            title="<b>RS-Momentum (Acceleration) →</b>",
            range=[y_min, y_max],
            gridcolor="#334155",
            zeroline=False
        ),
        template="plotly_dark",
        paper_bgcolor="#090d16",
        plot_bgcolor="#0f172a",
        height=720,
        showlegend=False,
        margin=dict(l=60, r=60, t=60, b=60)
    )

    return fig
