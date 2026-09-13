#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
gm_evening_headless.py — the Golden Matcher EVENING RUN with no browser.

Runs the Web Commander script in-process through Streamlit's AppTest harness,
navigates to the Trigger Board, presses the same "Evening run" button the window
has (fetch once -> Daily/125m/75m boards -> options bundle), then writes the two
S4 paste strings to gm_bundles/latest.txt (+ a dated copy).

WHY THIS AND NOT A gm_core EXTRACTION: the board builder and everything under it
(gm_evaluate, the loaders, the workflows) live inside the 17k-line app. Moving them
out is the long-term answer; until then this drives the IDENTICAL code path the
button uses, so the headless board and the in-window board cannot drift.

Phase 6 of run_pipeline calls this as a SUBPROCESS (the app starts worker threads
at import; a subprocess with a hard exit is the only way to be sure the pipeline
does not hang on them). Also runnable by hand:

    python gm_evening_headless.py            # full run
    python gm_evening_headless.py --bundles  # no rebuild, just re-emit bundles from the caches

Exit codes: 0 ok · 2 the app raised · 3 boards incomplete · 4 bundle write failed.
"""
import argparse
import datetime as dt
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "weinstein_commander_web_v4.0.py")
OUT_DIR = os.path.join(HERE, "gm_bundles")
RUN_TIMEOUT_S = int(os.getenv("GM_EVENING_TIMEOUT_S", "2400"))   # 40 min ceiling


def write_bundles(opt_bundle: str | None, stamp: str) -> str:
    """Emit gm_bundles/latest.txt from the per-TF caches on disk. The options
    bundle is taken from the run when available (one NSE call per name is not
    something to repeat), else rebuilt."""
    import gm_trigger_board as gtb
    union = gtb.s4_bundle_union()
    if opt_bundle is None:
        opt_bundle = gtb.s4_bundle_options()
    n_opt = len([x for x in (opt_bundle or "").split("=", 1)[-1].split(",") if x.strip()])
    os.makedirs(OUT_DIR, exist_ok=True)
    body = (
        f"# Golden Matcher evening bundles — {stamp}\n"
        f"# Paste line 1 into S4 'GM: ONE-PASTE bundle', line 2 into 'GM: bundle 2 — options OI'.\n"
        f"# union {len(union)} chars · options {n_opt} F&O names / {len(opt_bundle or '')} chars\n\n"
        f"{union}\n\n{opt_bundle or ''}\n"
    )
    latest = os.path.join(OUT_DIR, "latest.txt")
    dated = os.path.join(OUT_DIR, dt.datetime.now().strftime("bundles_%Y%m%d_%H%M.txt"))
    for p in (latest, dated):
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(body)
        os.replace(tmp, p)
    return latest


def run_evening() -> tuple[str, str | None]:
    """Drive the app headlessly. Returns (stamp, options_bundle)."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=RUN_TIMEOUT_S)
    at.query_params["view"] = "gm_window"          # pop-out route: no sidebar, board view free
    at.session_state["page"] = "GOLDEN MATCHER"
    at.session_state["gm_view"] = "📋 Trigger Board"
    at.run(timeout=600)
    if at.exception:
        raise RuntimeError("app raised on load: " + "; ".join(str(e.value) for e in at.exception))
    btn = at.button(key="gm_evening_run")
    if btn is None:
        raise RuntimeError("Evening run button not found — is the Trigger Board view active?")
    t0 = time.time()
    btn.click().run(timeout=RUN_TIMEOUT_S)
    if at.exception:
        raise RuntimeError("app raised during the run: " + "; ".join(str(e.value) for e in at.exception))
    def _ss(key):
        # AppTest's session_state proxy has no .get(): a missing key raises.
        try:
            return at.session_state[key]
        except Exception:
            return None
    stamp = _ss("gm_evening_stamp") or ""
    opt = _ss("_gm_opt_bundle")
    print(f"evening run: {stamp or 'no stamp'} ({int(time.time() - t0)}s)")
    return stamp, opt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundles", action="store_true", help="skip the rebuild; re-emit bundles from the caches")
    args = ap.parse_args()
    os.chdir(HERE)
    if args.bundles:
        stamp = "bundles only · " + dt.datetime.now().strftime("%d %b %H:%M")
        opt = None
    else:
        try:
            stamp, opt = run_evening()
        except Exception as e:
            print(f"FAIL: {e}", file=sys.stderr)
            return 2
        if "boards 3/3" not in stamp:
            print(f"boards incomplete: {stamp}", file=sys.stderr)
            # still write what we have - a partial bundle beats a stale one - but say so
            try:
                write_bundles(opt, stamp + " · PARTIAL")
            except Exception as e:
                print(f"bundle write failed: {e}", file=sys.stderr)
            return 3
    try:
        p = write_bundles(opt, stamp)
    except Exception as e:
        print(f"bundle write failed: {e}", file=sys.stderr)
        return 4
    print(f"bundles -> {os.path.relpath(p, HERE)}")
    return 0


if __name__ == "__main__":
    rc = main()
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(rc)     # the app starts worker threads at import; do not wait on them
