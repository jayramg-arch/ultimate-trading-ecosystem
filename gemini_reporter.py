# gemini_reporter.py — AI Report Generator using Google Gemini 2.5 Flash
# Generates pre-market briefs, post-market summaries, stock analysis reports
# Part of Weinstein Commander Web v4.0 for NSE India
#
# Migrated 19 May 2026 from the deprecated `google.generativeai` package to
# the supported `google.genai` SDK. The old package was emitting a
# "All support for the `google.generativeai` package has ended" FutureWarning
# on every call. The new API uses Client / Client.models.generate_content
# instead of configure() + GenerativeModel(); model id ("gemini-2.5-flash")
# and the .text accessor are unchanged.

import os
import logging
import json
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory response cache: {cache_key: {"result": str, "expires_at": float}}
# ---------------------------------------------------------------------------
_cache: dict = {}
_CACHE_TTL_SECONDS = 600  # 10 minutes

# Module-level Client. The new SDK encourages reusing one Client across calls
# (it holds the API auth + a connection pool). Lazily initialised on first
# use so import remains side-effect-free.
_client = None


def _get_client():
    """Return the cached google.genai.Client, creating it on first call."""
    global _client
    if _client is not None:
        return _client
    from google import genai
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in .env")
    _client = genai.Client(api_key=api_key)
    return _client


def _generate(prompt: str, max_retries: int = 2,
                model: str = "gemini-3.5-flash-lite") -> str:
    """Call Gemini and return the text response.

    Retries up to max_retries times on 429 (rate-limit) errors with
    60-second backoff between attempts.
    """
    client = _get_client()
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model, contents=prompt,
            )
            return (response.text or "").strip()
        except Exception as e:
            if "429" in str(e) and attempt < max_retries:
                wait_sec = 60 * (attempt + 1)          # 60s, then 120s
                logger.warning(
                    "Gemini 429 rate-limit — waiting %ds before retry %d/%d",
                    wait_sec, attempt + 2, max_retries + 1,
                )
                time.sleep(wait_sec)
            else:
                raise


def _clean_snapshot_for_gemini(snapshot: dict) -> dict:
    """
    Strip heavy/noisy fields from a snapshot dict before building the Gemini prompt.
    - Removes 'series' (multi-line pandas string) from every index/commodity entry
    - Converts any DataFrame to a list of dicts (max 10 rows)
    - Drops empty/None values at top level
    - Strips verbose fields from sectors (keep only sector + change_pct)
    - Strips verbose fields from global indices (keep only ltp + change_pct)
    - Returns a cleaned copy ready for json.dumps
    """
    import pandas as pd

    # Fields to drop per section to reduce token use
    _SECTOR_KEEP   = {"sector", "change_pct"}
    _GLOBAL_STRIP  = {"series", "high", "low", "open", "volume", "note",
                      "52w_high", "52w_low", "52w_high_pct", "52w_low_pct"}
    _INDEX_VERBOSE = {"series", "note"}

    def _is_empty(v) -> bool:
        if v is None:
            return True
        if isinstance(v, pd.DataFrame):
            return v.empty
        if isinstance(v, pd.Series):
            return v.empty
        if isinstance(v, (dict, list, str)):
            return len(v) == 0
        return False

    def _strip_series(obj, _depth: int = 0):
        """Recursively remove noisy keys and simplify for JSON/Gemini context."""
        if isinstance(obj, pd.DataFrame):
            if obj.empty:
                return []
            try:
                return obj.head(10).to_dict(orient="records")
            except Exception:
                return []
        if isinstance(obj, pd.Series):
            return obj.tail(5).to_dict()
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if k in ("series",):
                    continue
                if _is_empty(v):
                    continue
                result[k] = _strip_series(v, _depth + 1)
            return result
        if isinstance(obj, list):
            return [_strip_series(i, _depth + 1) for i in obj]
        return obj

    cleaned = _strip_series(snapshot)

    # Slim down sectors list — only keep sector name + change_pct
    if "sectors" in cleaned and isinstance(cleaned["sectors"], list):
        cleaned["sectors"] = [
            {k: v for k, v in s.items() if k in _SECTOR_KEEP}
            for s in cleaned["sectors"]
        ]

    # Slim down global — strip high/low/open/volume noise from nested index dicts
    if "global" in cleaned and isinstance(cleaned["global"], dict):
        for section_key, section_val in cleaned["global"].items():
            if isinstance(section_val, dict):
                for idx_key, idx_val in section_val.items():
                    if isinstance(idx_val, dict):
                        cleaned["global"][section_key][idx_key] = {
                            k: v for k, v in idx_val.items()
                            if k not in _GLOBAL_STRIP
                        }

    return cleaned


def _reorder_for_gemini(cleaned: dict, priority_keys: list) -> dict:
    """
    Return a new dict with priority_keys first, remaining keys after.
    Ensures Gemini sees the most important data before the 16K char cutoff.
    """
    ordered = {}
    for k in priority_keys:
        if k in cleaned:
            ordered[k] = cleaned[k]
    for k, v in cleaned.items():
        if k not in ordered:
            ordered[k] = v
    return ordered


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and time.time() < entry["expires_at"]:
        return entry["result"]
    return None


def _cache_set(key: str, value: str) -> None:
    _cache[key] = {"result": value, "expires_at": time.time() + _CACHE_TTL_SECONDS}


# ---------------------------------------------------------------------------
# Function 1: Pre-Market Brief
# ---------------------------------------------------------------------------
def generate_premarket_brief(snapshot_dict: dict) -> str:
    """Generate a concise pre-market brief (300-400 words)."""
    # Strip volatile timestamp fields before hashing so repeated calls with
    # the same market data hit the cache (avoids unnecessary API round-trips
    # that cause 429 rate-limit errors).
    _VOLATILE = {"generated_at", "fetched_at", "timestamp", "calculated_at"}
    _stable = {k: v for k, v in snapshot_dict.items() if k not in _VOLATILE}
    cache_key = "premarket_" + str(hash(json.dumps(_stable, sort_keys=True, default=str)))
    cached = _cache_get(cache_key)
    if cached:
        return cached
    try:
        cleaned = _clean_snapshot_for_gemini(snapshot_dict)
        # Global pulse is the primary content for pre-market; VIX + FII close second
        cleaned = _reorder_for_gemini(cleaned, [
            "generated_at", "global", "gift_nifty", "india_indices", "vix",
            "fii_dii_last3", "fii_prev_session_cr", "dii_prev_session_cr",
            "sectors", "options", "calendar", "ban_list",
        ])
        context = json.dumps(cleaned, indent=2, default=str)[:16000]
        prompt = f"""You are a senior quant analyst at a Mumbai hedge fund covering NSE India markets.
Write a data-dense pre-market brief based on the data below.

DATA:
{context}

STRICT OUTPUT FORMAT — use exactly these 5 section headers with === delimiters:

=== Global Overnight Pulse ===
List each market with EXACT numbers. Format each line as:
  MARKET: value (±chg%) | brief note
Example:
  S&P 500: 5,204 (+0.3%) | Fed hold rally, tech led
  Gold: $3,285 (+0.8%) | safe haven bid
  DXY: 99.2 (-0.4%) | dollar weakness supports EMs
  US 10Y: 4.31% (-3bps) | yields ease
  Crude: $63.1 (+0.5%) | OPEC output concerns
Include: US indices, Europe/Asia indices, Gold, Crude, DXY, US 10Y yield, USD/INR if available.

=== India-Specific Risk Factors ===
Bullets with EXACT numbers only. Example:
  India VIX: 14.8 (-4.9%) — below 15 = low fear, range-bound likely
  FII: ₹[X]Cr [net buy/sell] prev session (cash market) | DII: ₹[X]Cr [buy/sell]
  GIFT Nifty: [close] ([+/-chg%]) — overnight indication for Nifty
  USD/INR: [value] | [trend]
  Gap open estimate: Nifty ~[X] pts [up/down] based on GIFT Nifty / Dow futures
State actual numbers. If data unavailable, say "data unavailable".

=== Key Levels to Watch ===
Use values from the india_indices block in the DATA. Format:
  Nifty 50: Support [support1] / [support2] | Resistance [resistance1] / [resistance2] | Pivot [pivot]
  BankNifty: Support [support1] / [support2] | Resistance [resistance1] / [resistance2] | Pivot [pivot]
  Volume confirmation level (Nifty): > [vol_avg20] (20D avg) — judge intraday
No explanatory prose — numbers and levels only.

=== Sector in Focus ===
One sector. Format:
  SECTOR: [name] | Bias: [LONG/AVOID] | Reason: [one line with data]
  Key stocks: [2-3 names] | Trigger: [specific price/event]

=== Trading Bias ===
Format exactly:
  BIAS: BULLISH / NEUTRAL / BEARISH (pick one)
  Nifty range today: [X] – [Y]
  Conviction: HIGH / MEDIUM / LOW
  Rationale: [2 sentences max, reference specific numbers from the data above]

RULES:
- Every bullet MUST contain a number from the data — no pure prose sentences
- No paragraphs. Use bullet/colon format throughout
- Plain text only — no asterisks, no markdown, no bold
- If a number is missing from data, write "N/A" not a guess"""
        result = _generate(prompt)
        _cache_set(cache_key, result)
        logger.info("Pre-market brief generated (%d chars)", len(result))
        return result
    except Exception as e:
        logger.error("generate_premarket_brief failed: %s", e)
        return f"Warning: AI report unavailable — Gemini API error: {e}"


# ---------------------------------------------------------------------------
# Function 2: Post-Market Summary
# ---------------------------------------------------------------------------
def generate_postmarket_summary(snapshot_dict: dict) -> str:
    """Generate a post-market EOD summary (300-400 words)."""
    _VOLATILE = {"generated_at", "fetched_at", "timestamp", "calculated_at"}
    _stable = {k: v for k, v in snapshot_dict.items() if k not in _VOLATILE}
    cache_key = "postmarket_" + str(hash(json.dumps(_stable, sort_keys=True, default=str)))
    cached = _cache_get(cache_key)
    if cached:
        return cached
    try:
        cleaned = _clean_snapshot_for_gemini(snapshot_dict)
        # Prioritise India-specific data so it appears before the char cutoff
        cleaned = _reorder_for_gemini(cleaned, [
            "generated_at", "india_indices", "breadth", "mcclellan",
            "top_movers", "fii_dii_last5", "fii_5d_net_cr", "dii_5d_net_cr",
            "fii_dii_fno", "mf_monthly_flows", "sectors", "gift_nifty",
            "corporate_actions", "bulk_deals", "global",
        ])
        context = json.dumps(cleaned, indent=2, default=str)[:16000]
        prompt = f"""You are a senior quant analyst at a Mumbai hedge fund covering NSE India markets.
Write a data-dense end-of-day market summary based on the data below.

DATA:
{context}

STRICT OUTPUT FORMAT — use exactly these 5 section headers with === delimiters:

=== Market Verdict ===
State each index with EXACT close, change, and % vs key MA. Example:
  Nifty 50: [close] ([+/-chg], [+/-chg%]) | [above/below] 200DMA ([200DMA value])
  BankNifty: [close] ([+/-chg%]) | [trend note]
  Nifty Midcap 150: [chg%] | [trend note]
  India VIX: [value] ([+/-chg%]) — [fear level interpretation]
  Day character: [trending/range-bound/reversal] | Volume: [above/below avg]

=== Breadth Analysis ===
EXACT numbers only. Pull from `breadth` and `mcclellan` blocks. Example:
  Advances: [X] | Declines: [Y] | Unchanged: [Z] | A/D Ratio: [X:1]
  Above SMA50: [X]% | Above SMA150: [X]% | Above SMA200: [X]%
  52W Highs: [X] | 52W Lows: [Y] | Net new highs: [+/-Z]
  Stage 2 stocks (N500): [X]% | Regime: [BULL HEALTHY / NEUTRAL / CORRECTION]
  McClellan Oscillator: [oscillator] | Summation Index: [summation] (as of [as_of])

=== Institutional Activity ===
Two distinct data blocks — render BOTH:

CASH MARKET (from `fii_dii_last5`, in ₹Cr):
  FII (cash): ₹[X]Cr [NET BUY/SELL] | gross buy ₹[X]Cr | gross sell ₹[X]Cr
  DII (cash): ₹[X]Cr [NET BUY/SELL] | gross buy ₹[X]Cr | gross sell ₹[X]Cr
  5-day FII cumulative: ₹[fii_5d_net_cr]Cr | 5-day DII cumulative: ₹[dii_5d_net_cr]Cr

F&O PARTICIPANTS (from `fii_dii_fno`, in CONTRACTS — these are participant-wise
contract counts from NSE; do not convert to Cr, contract bias is the
institutional read):
  FII F&O: Net [fii.net] contracts ([fii.bias]) — Idx Fut [fii.idx_fut_net] | Stk Fut [fii.stk_fut_net] | Idx Opt [fii.idx_opt_net] | Stk Opt [fii.stk_opt_net]
  DII F&O: Net [dii.net] contracts ([dii.bias]) — Idx Fut [dii.idx_fut_net] | Stk Fut [dii.stk_fut_net] | Idx Opt [dii.idx_opt_net] | Stk Opt [dii.stk_opt_net]
  As of: [fii_dii_fno.as_of]

DII MF MONTHLY (from `mf_monthly_flows`, in ₹Cr — Equity open-ended only,
AMFI publishes monthly so this lags 2-6 weeks; render only if present):
  DII MF (Equity, [period]): Net inflow ₹[equity_net_inflow_cr]Cr | Sales ₹[equity_sales_cr]Cr | Redemptions ₹[equity_redemptions_cr]Cr | AUM ₹[equity_aum_cr]Cr

  Trend: [net buyer/seller streak across cash + F&O + MF monthly]
  Interpretation: [one line — cross-reference cash flow with F&O positioning and MF monthly direction]

=== Key Movers ===
Use `top_movers` (Nifty 50) and `sectors` blocks. Example:
  Sector outperformer: [best sector] +[X]% | Leader: [top_movers.leader.symbol] +[top_movers.leader.change_pct]%
  Sector laggard: [worst sector] -[X]% | Drag: [top_movers.drag.symbol] [top_movers.drag.change_pct]%
  Bulk/block deal: [stock] — [X] lakh shares @ ₹[price] (buyer/seller) — or "none in feed"
  F&O ban additions/exits: [stocks or "none"]
  Corporate action: [any dividend/split/result from corporate_actions, or "none in feed"]

=== Tomorrow's Watch ===
Pull pivot levels from `india_indices`. Example:
  Nifty: Support [india_indices.Nifty 50.support1] / [support2] | Resistance [resistance1] / [resistance2] | Pivot [pivot]
  BankNifty: Support [india_indices.BankNifty.support1] | Resistance [india_indices.BankNifty.resistance1] | Pivot [pivot]
  Key event: [event name, time IST] — or "none in calendar feed" if calendar empty
  Setup to watch: [sector/index] | Trigger: [breakout/breakdown level based on data above]
  Risk: [one specific risk with level — e.g. "Nifty close below [support2] = bearish continuation"]

RULES:
- Every bullet MUST contain a number — no pure prose sentences
- Use bullet/colon format. No paragraphs.
- Plain text only — no asterisks, no markdown, no bold
- If data is unavailable for a metric, write the metric name followed by "N/A"
- Do NOT invent numbers — use only what is in the DATA section"""
        result = _generate(prompt)
        _cache_set(cache_key, result)
        logger.info("Post-market summary generated (%d chars)", len(result))
        return result
    except Exception as e:
        logger.error("generate_postmarket_summary failed: %s", e)
        return f"Warning: AI report unavailable — Gemini API error: {e}"


# ---------------------------------------------------------------------------
# Function 3: Single Stock Analysis
# ---------------------------------------------------------------------------
def generate_stock_analysis(symbol: str, data_dict: dict) -> str:
    """Generate a concise analysis (200-250 words) for a single stock."""
    cache_key = f"stock_{symbol}_" + str(hash(json.dumps(data_dict, sort_keys=True, default=str)))
    cached = _cache_get(cache_key)
    if cached:
        return cached
    try:
        context = json.dumps(data_dict, indent=2, default=str)[:3000]
        prompt = f"""You are a senior analyst at a Mumbai hedge fund.
Analyze the following NSE stock data for {symbol} in 200-250 words.

DATA:
{context}

OUTPUT FORMAT — use exactly these section headers (===):
=== Stage Assessment ===
(Weinstein stage classification and what it implies)

=== Key Levels ===
(Support, resistance, pivot zones based on available data)

=== Risk/Reward ===
(Reward potential vs downside risk — be specific if price data allows)

=== Catalyst ===
(What could drive the move — sector trend, breakout, earnings, etc.)

=== Verdict ===
(Buy / Hold / Avoid — one clear call with one sentence of reasoning)

Rules: Plain text only. No markdown. Be specific. No fluff. 200-250 words total."""
        result = _generate(prompt)
        _cache_set(cache_key, result)
        logger.info("Stock analysis generated for %s (%d chars)", symbol, len(result))
        return result
    except Exception as e:
        logger.error("generate_stock_analysis failed for %s: %s", symbol, e)
        return f"Warning: AI report unavailable — Gemini API error: {e}"


# ---------------------------------------------------------------------------
# Function 4: Weekly Market Report
# ---------------------------------------------------------------------------
def generate_weekly_market_report(data_dict: dict) -> str:
    """Generate a comprehensive weekly market report (500-600 words) for Sunday evening."""
    cache_key = "weekly_" + str(hash(json.dumps(data_dict, sort_keys=True, default=str)))
    cached = _cache_get(cache_key)
    if cached:
        return cached
    try:
        cleaned = _clean_snapshot_for_gemini(data_dict)
        cleaned = _reorder_for_gemini(cleaned, [
            "generated_at", "india_indices", "breadth", "fii_dii_last5",
            "fii_5d_net_cr", "dii_5d_net_cr", "sectors", "global",
        ])
        context = json.dumps(cleaned, indent=2, default=str)[:16000]
        prompt = f"""You are a senior analyst at a Mumbai hedge fund writing the Sunday evening
weekly market letter for institutional clients covering NSE India markets.
Write a comprehensive report of 500-600 words based on the data below.

DATA:
{context}

OUTPUT FORMAT — use exactly these section headers (===):
=== Week in Review ===
(Key index moves, notable events, overall market character)

=== Breadth & Internals ===
(A/D trends, % above SMA50/200, Stage 2 count changes, McClellan if available)

=== Sector Rotation ===
(Which sectors gained/lost leadership, what it implies for next week)

=== FII/DII Activity ===
(Net flows for the week, cumulative trend, institutional intent)

=== Top Setups for Next Week ===
(3-5 actionable stock or index setups with entry context)

=== Risks to Watch ===
(2-3 key macro or market-structure risks that could invalidate the base case)

Rules: Plain text only. No markdown. Institutional tone. 500-600 words total."""
        result = _generate(prompt)
        _cache_set(cache_key, result)
        logger.info("Weekly report generated (%d chars)", len(result))
        return result
    except Exception as e:
        logger.error("generate_weekly_market_report failed: %s", e)
        return f"Warning: AI report unavailable — Gemini API error: {e}"


# ---------------------------------------------------------------------------
# Function 4b: Strategic Daily Briefing (long-form, replaces the manual
# "paste Gemini_Analysis_Prompt.txt into the web UI" step in the
# strategic-briefing workflow). Uses Gemini 2.5 Flash directly so the
# briefing markdown is produced end-to-end on the desktop.
# ---------------------------------------------------------------------------
def generate_strategic_briefing(prompt_text: str = None,
                                  prompt_path: str = "Gemini_Analysis_Prompt.txt",
                                  out_path: str = "Strategic_Briefing_AI.md",
                                  max_chars: int = 28000) -> str:
    """Run the daily Strategic Briefing prompt through Gemini 2.5 Flash and
    persist the markdown result.

    Reads ``prompt_path`` if ``prompt_text`` is None, calls Gemini directly,
    writes the response to ``out_path`` (UTF-8 markdown), and returns the
    text. The prompt is the same long-form CIO-briefing prompt that
    ``quant_analyst.generate_gemini_prompt_file()`` already builds — this
    function just closes the loop that previously required pasting it into
    the web UI by hand.

    Failure modes:
      - Missing API key or network error → returns an error-marker string
        starting with "Warning:" and writes the same to disk so the
        workflow can still continue (PDF + email steps don't depend on
        a successful AI run).
      - Prompts longer than ``max_chars`` are truncated with a note so
        token-budget overruns don't silently fail the call.
    """
    if prompt_text is None:
        if not os.path.exists(prompt_path):
            err = f"Warning: prompt file not found at {prompt_path}"
            logger.error(err)
            return err
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read()

    if len(prompt_text) > max_chars:
        logger.warning("Strategic briefing prompt is %d chars — truncating "
                        "to %d to stay under Gemini Flash context budget.",
                        len(prompt_text), max_chars)
        prompt_text = (prompt_text[:max_chars]
                        + "\n\n[Note: prompt truncated at "
                        + f"{max_chars} chars to fit context window.]")

    cache_key = "strategic_briefing_" + str(hash(prompt_text))
    cached = _cache_get(cache_key)
    if cached:
        # Still rewrite the on-disk artefact so the workflow always opens a
        # fresh file even when the in-process cache short-circuited the call.
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(cached)
        except Exception:
            pass
        return cached

    try:
        text = _generate(prompt_text)
    except Exception as e:
        text = (f"Warning: Strategic briefing AI step failed — {e}\n\n"
                 "The rule-based PDF and the raw prompt file are still "
                 "available for manual review.")
        logger.error("generate_strategic_briefing failed: %s", e)

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info("Strategic briefing written to %s (%d chars)", out_path, len(text))
    except Exception as we:
        logger.error("Could not write %s: %s", out_path, we)

    _cache_set(cache_key, text)
    return text


# ---------------------------------------------------------------------------
# Function 5: Monthly Portfolio Review
# ---------------------------------------------------------------------------
def generate_portfolio_review(trades_df, analytics_dict: dict) -> str:
    """Generate a monthly portfolio review (~300 words) from trades and analytics."""
    try:
        trades_summary = trades_df.head(50).to_dict(orient="records") if trades_df is not None else []
    except Exception:
        trades_summary = []
    cache_key = "portfolio_" + str(hash(
        json.dumps({"trades": trades_summary, "analytics": analytics_dict},
                   sort_keys=True, default=str)))
    cached = _cache_get(cache_key)
    if cached:
        return cached
    try:
        context = json.dumps(
            {"trades": trades_summary, "analytics": analytics_dict},
            indent=2, default=str)[:5000]
        prompt = f"""You are a senior portfolio analyst at a Mumbai hedge fund reviewing last month's
trading performance for a systematic NSE India strategy based on Weinstein stage analysis.
Write a clinical, honest monthly review of approximately 300 words.

DATA:
{context}

OUTPUT FORMAT — use exactly these section headers (===):
=== Performance Summary ===
(Win rate, P&L, Sharpe, profit factor — state the numbers, then interpret them)

=== What Worked ===
(Specific trade patterns, sectors, or setups that performed well)

=== What Did Not Work ===
(Honest assessment of losing trades — entry timing, sector choice, sizing)

=== Process Observations ===
(Are the losses from bad luck or process errors? Be specific)

=== Next Month Adjustments ===
(1-3 concrete, actionable changes to improve performance)

Rules: Plain text only. No flattery. Clinical and direct. Approximately 300 words."""
        result = _generate(prompt)
        _cache_set(cache_key, result)
        logger.info("Portfolio review generated (%d chars)", len(result))
        return result
    except Exception as e:
        logger.error("generate_portfolio_review failed: %s", e)
        return f"Warning: AI report unavailable — Gemini API error: {e}"


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Testing Gemini Reporter...")
    test_snap = {
        "generated_at": datetime.now().isoformat(),
        "global": {"indices": {"Nifty 50": {"ltp": 24500, "change_pct": -0.4},
                               "S&P 500":  {"ltp": 5280,  "change_pct":  0.3}}},
        "vix": {"current_vix": 14.2, "percentile": 35},
        "calendar": [{"date": "2026-04-18", "event": "India CPI", "importance": "HIGH"}],
    }
    result = generate_premarket_brief(test_snap)
    print(result[:600])
    print("...\ngemini_reporter.py OK")
