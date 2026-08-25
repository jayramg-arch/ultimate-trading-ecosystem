#!/usr/bin/env python3
"""HELD MIGRATION — wire the GM's BFF / RFF scores into the S4 panel (item #3).

WHY THIS IS HELD AND NOT ALREADY APPLIED
    The parsing lives in S4Core.fundScore (added 25-Aug-2026). A library body
    compiles separately, so putting it there costs S4 nothing against its
    compiled-token ceiling -- but S4 cannot CALL it until the version carrying
    it is published, and the import must never be bumped to a version that does
    not exist yet (four compile failures in one day were caused by predicting
    the next publish number).

    So: everything else in this round compiles today at import /19. This one
    change waits for the publish.

USAGE
    1. Publish S4Core on TradingView. Note the version number it reports.
    2. python apply_gm_fund_scores.py <version>          e.g.  20
    3. Compile S4, then run BIND_S4_SOURCES.bat, then recreate the GO alerts.

WHAT IT DOES
    * bumps  import jayramg/S4Core/<old>  ->  /<version>
    * adds two paste inputs (BFF scores, RFF scores) beside the existing GM
      Recovery / Pullback list inputs
    * computes both in GLOBAL scope (the v5.9 lesson: state evaluated inside
      `if barstate.islast` runs on one bar and returns garbage)
    * appends them to the Structure basis row -- no new panel row, because a row
      costs several hundred compiled tokens and this file has hit the ceiling
      repeatedly

RENDERING RULE, and it is the point of the whole change
    na is NOT zero. A symbol absent from the pasted list means the GM has not
    scored it; that is a different statement from "scored it and it failed", and
    rendering them the same would turn every unlisted name into a fundamental
    rejection on sight. Absent renders as an em-dash, never a red dot.
        RFF  >= rff_min (4)  green   < 4  red    absent  em-dash
        BFF  present         green   absent      em-dash
    RFF is red-capable because it IS the GM's hard Recovery gate. BFF is
    display-only status in the GM and is never red here either.

Idempotent: re-running detects the inputs are already present and stops.
"""
import io
import re
import sys

PINE = "Section4_Entry_Trigger_v7.2.pine"
GREEN, GREY, RED = "\U0001F7E2", "⚪", "\U0001F534"

INPUTS = (
    'gm_bff_list = input.string("", "GM: BFF scores  (SYM:n, paste from the Golden Matcher)", '
    'group=grpPA, tooltip="The Bull Fundamental Filter score the Golden Matcher computed, '
    'carried across as text because Pine cannot compute it: BFF reads screener.in\'s '
    'compounded-growth table, which no Pine surface can reach.\\n\\nFormat: SYM:n pairs, comma '
    'separated - RELIANCE:7, TECHM:5, CIPLA:6. Spaces, newlines, semicolons and NSE: prefixes '
    'are all tolerated; matching is case-insensitive.\\n\\nA symbol NOT in the list renders as '
    'an em-dash, not a zero - unscored and scored-badly are different facts. DISPLAY ONLY: BFF '
    'never gates anything here, exactly as in the GM."), \n'
    'gm_rff_list = input.string("", "GM: RFF scores  (SYM:n, paste from the Golden Matcher)", '
    'group=grpPA, tooltip="The Recovery Fundamental Fitness score (0-10) from recovery_screener. '
    'Pine CANNOT compute this - TradingView caps request.financial() at five calls per script and '
    'the Capitulation Screener already spends that budget on a two-check RFF Lite. The GM is the '
    'authority; this only carries its answer.\\n\\nFormat: SYM:n pairs - TECHM:6, CIPLA:4.\\n\\n'
    'Coloured against the GM\'s own hard gate (RFF >= 4): below it the name is fundamentally weak '
    'and the GM would reject it, which is worth seeing before you plan the trade. Absent renders '
    'as an em-dash - the GM has not scored it - never as a failure.")'
)


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        print(__doc__)
        print("ERROR: pass the PUBLISHED S4Core version, e.g.  python "
              "apply_gm_fund_scores.py 20")
        return 2
    ver = sys.argv[1]
    src = io.open(PINE, encoding="utf-8").read()

    if "gm_rff_list" in src:
        print("Already applied - gm_rff_list is present. Nothing to do.")
        return 0

    # 1 ── import bump -------------------------------------------------------
    m = re.search(r"^import jayramg/S4Core/(\d+) as core$", src, re.M)
    if not m:
        print("ERROR: could not find the S4Core import line.")
        return 1
    old_ver = m.group(1)
    src = src[:m.start()] + "import jayramg/S4Core/%s as core" % ver + src[m.end():]

    # 2 ── the two paste inputs, beside the existing GM list inputs -----------
    anchor = "gm_rec_list = input.string("
    if src.count(anchor) != 1:
        print("ERROR: gm_rec_list anchor is not unique.")
        return 1
    at = src.index(anchor)
    line_end = src.index("\n", at)
    src = src[:line_end + 1] + INPUTS.replace("), \n", ")\n") + "\n" + src[line_end + 1:]

    # 3 ── global compute (NOT inside the panel block) ------------------------
    gcompute = (
        "// GM FUNDAMENTAL SCORES (item #3). Global scope on purpose - anything computed\n"
        "// inside `if barstate.islast` evaluates on the last bar only, which is how the\n"
        "// v5.9 chop counter came to be garbage. na = the GM has not scored this symbol.\n"
        "float _bffV = core.fundScore(gm_bff_list, syminfo.ticker)\n"
        "float _rffV = core.fundScore(gm_rff_list, syminfo.ticker)\n"
    )
    a2 = 'float atrW_tf = request.security(syminfo.tickerid, "W", ta.atr(14), lookahead=barmerge.lookahead_off)'
    if src.count(a2) != 1:
        print("ERROR: atrW_tf anchor is not unique.")
        return 1
    src = src.replace(a2, gcompute + a2)

    # 4 ── render, appended to Structure basis --------------------------------
    i = src.index("    string _basis  = ")
    j = src.index("\n", i)
    basis = src[i:j]
    if "_mvTxt" not in basis:
        print("ERROR: expected the Minervini append (_mvTxt) on the Structure basis row.")
        return 1
    render = (
        '    // Absent renders em-dash, never a red dot: unscored and scored-badly are\n'
        '    // different facts and the panel must not merge them. RFF is red-capable because\n'
        '    // it is the GM\'s hard Recovery gate; BFF is display-only status in the GM and\n'
        '    // stays that way here.\n'
        '    string _fndTxt = "  ·  RFF " + (na(_rffV) ? "—" : str.tostring(_rffV, "0") '
        '+ (_rffV >= 4 ? " %s" : " %s")) + "  ·  BFF " + (na(_bffV) ? "—" : '
        'str.tostring(_bffV, "0") + " %s")\n' % (GREEN, RED, GREEN)
    )
    src = src[:i] + render + basis + " + _fndTxt" + src[j:]

    io.open(PINE, "w", encoding="utf-8").write(src)
    print("Applied. S4Core import %s -> %s" % (old_ver, ver))
    print("Next: compile S4, run BIND_S4_SOURCES.bat, recreate the GO alerts.")
    print("Then paste the GM's BFF / RFF score lists into the two new inputs")
    print("(Settings -> the same group as the GM Recovery / Pullback lists).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
