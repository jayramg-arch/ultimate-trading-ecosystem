"""S5 order flow in the reviewer (12-Oct-2026): flow_read / flow_check / FLOW-GATE, the
fp_div field and the R-CHECK plan parser. FLOW-GATE is the ONE place order flow changes a
ruling, so every one of its five conditions is pinned here."""
import s4_review as r

HEAD = "S4 v11.30 │ core/72 │ 11896ch·17/17 | XYZ │ ATR(125) 60.00 (1.50%) · ATR(D) 110.00 (2.7%)\n"
PANEL = HEAD + (
    "Setup | TREND A │ Breakout\n"
    "Plan | SWING │ Buy-STOP 4210.0 above the trigger bar │ SL 4100.0\n"
    "Entry · SL · T1 · T2 | E 4210.0 │ SL 4100.0 (−2.6%) │ T1 4430.0 (2.0R) │ T2 4650.0 (4.0R)\n")


def _of(verdict="FAILED BREAKOUT", side="resistance", lvl="4,200.00", tf="D", age="1 bar ago"):
    return "ORDER-FLOW READ | %s · %s %s ·%s · %s: buyers who took the break are trapped." % (
        verdict, side, lvl, tf, age)


TAKE = "RULING: TAKE\nDECIDING FACTOR x.\nPLAN   SWING · Buy-stop 4210 · Stop 4100 · T1 4430 (2R) · T2 4650 (4R)\nFLIPS IF y."


def test_flow_read_parses_the_row():
    fr = r.flow_read(PANEL + _of())
    assert fr == {"verdict": "FAILED BREAKOUT", "side": "resistance", "level": 4200.0, "tf": "D", "age": 1}
    assert r.flow_read(PANEL + _of(age="last closed bar"))["age"] == 0
    assert r.flow_read(PANEL) == {}


def test_flow_gate_fires_only_when_all_five_hold():
    fired, txt, log = r.flow_gate(PANEL + _of(), TAKE, held=False)
    assert fired and "OVERRULED: WAIT" in txt and log == "TAKE->WAIT @ 4,200.00"
    # 1. verdict must be FAILED BREAKOUT
    assert not r.flow_gate(PANEL + _of(verdict="CAPPED"), TAKE, False)[0]
    # 2. within the last 2 closed bars
    assert not r.flow_gate(PANEL + _of(age="2 bars ago"), TAKE, False)[0]
    # 3. breakout-type entry: a pullback limit entry with no breakout tag is untouched
    pb = HEAD + "Setup | TREND A │ Pullback\nEntry · SL · T1 · T2 | E 4210.0 │ SL 4100.0 │ T1 4430.0\n"
    rev_pb = TAKE.replace("Buy-stop", "Buy-limit")
    assert not r.flow_gate(pb + _of(), rev_pb, False)[0]
    # 4. the failed level within 0.5 x ATR (30) of the entry
    assert not r.flow_gate(PANEL + _of(lvl="4,100.00"), TAKE, False)[0]
    # 5. holdings are untouched
    assert not r.flow_gate(PANEL + _of(), TAKE, held=True)[0]


def test_flow_gate_never_touches_a_non_take():
    assert not r.flow_gate(PANEL + _of(), TAKE.replace("RULING: TAKE", "RULING: WAIT for a close above 4210"), False)[0]


def test_flow_check_reads_the_level_against_the_plan():
    _, t = r.flow_check(PANEL + _of(verdict="CAPPED", lvl="4,300.00", age="last closed bar"), TAKE)
    assert "FLOW-CHECK" in t and "first test on the way, not the target" in t
    _, t = r.flow_check(PANEL + _of(verdict="DEFENDED", side="support", lvl="4,150.00"), TAKE)
    assert "between stop" in t and "breaks the thesis before the stop fills" in t
    _, t = r.flow_check(PANEL + "ORDER-FLOW READ | none · no order-flow event at a level.", TAKE)
    assert t == ""


def test_fp_div_reads_what_s5_actually_prints():
    txt = "Divergence · VA | BEARISH - new 10b high on WEAKER flow (absorption into strength)"
    assert r.deriv_fields(txt)["fp_div"] == "bearish"


def test_r_check_reads_a_plan_written_on_the_plan_line():
    out = r.r_check("RULING: WAIT\nPLAN   SWING · Buy-limit 52.47 · Stop-Loss 51.09 (-2.6%) · "
                    "T1 55.22 (2.0R) · T2 57.98 (4.0R).\nFLIPS IF x")
    assert out.startswith("R-CHECK") and "entry 52.47" in out and "stop 51.09" in out
