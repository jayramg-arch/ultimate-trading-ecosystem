from plain_text import delatex


def test_jay_example():
    s = (r"volume ($\text{RV } 1.07$) with patterns ($\Sigma+6$) and extension "
         r"($0.0\times\text{ ATR}$). Long Build-up ($+0.8\%$) with R $\geq 2$.")
    assert delatex(s) == ("volume (RV 1.07) with patterns (Σ+6) and extension "
                          "(0.0× ATR). Long Build-up (+0.8%) with R ≥ 2.")


def test_plain_text_untouched():
    s = "Entry ₹1,234.50 · stop 1,200 · T1 1,300 (2.0R) — a lone $ sign stays"
    assert delatex(s) == s


def test_commands_outside_math():
    assert delatex(r"R\geq 2 and \text{VAH}") == "R≥ 2 and VAH"


def test_display_math_and_braces():
    assert delatex(r"$$x \leq 3$$") == "x ≤ 3"
    assert delatex(r"$\Delta\text{OI} = -2.1\%$") == "ΔOI = -2.1%"
