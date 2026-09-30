"""plain_text.py — turn a model's stray LaTeX back into plain text.

30-Sep-2026. The reviewer model (gemini flash-lite) sometimes writes numbers as inline
math — `($\\text{RV } 1.07$)`, `($\\Sigma+6$)`, `($0.0\\times\\text{ ATR}$)` — which the
Reviewer Log and Telegram print raw. The prompt now asks for plain text; this is the
backstop, applied where the model's text enters the system (s4_review.deliberate) AND at
render time in build_review_portal, so reviews already on disk read clean too.
It never edits a number or a word — only math delimiters and TeX commands.
"""
from __future__ import annotations

import re

_SYM = {
    "Sigma": "Σ", "sigma": "σ", "Delta": "Δ", "delta": "δ", "times": "×", "cdot": "·",
    "geq": "≥", "ge": "≥", "leq": "≤", "le": "≤", "neq": "≠", "ne": "≠",
    "approx": "≈", "sim": "~", "pm": "±", "to": "→", "rightarrow": "→",
    "Rightarrow": "⇒", "leftarrow": "←", "uparrow": "↑", "downarrow": "↓",
    "infty": "∞", "alpha": "α", "beta": "β", "mu": "μ", "star": "★", "checkmark": "✓",
    "%": "%", "$": "$", "_": "_", "&": "&", "#": "#",
}
_WRAP = re.compile(r"\\(?:text|textbf|textit|mathrm|mathbf|mathit|operatorname|mbox)\s*\{([^{}]*)\}")
_CMD = re.compile(r"\\([A-Za-z]+|[%$_&#])")
_KNOWN = re.compile(r"\\(" + "|".join(sorted((re.escape(k) for k in _SYM), key=len, reverse=True))
                    + r")(?![A-Za-z])")
_SPACE = re.compile(r"\\(?:[,;:! ]|quad|qquad)")
_MATH = re.compile(r"\$\$(.+?)\$\$|\$([^$\n]{1,200}?)\$")


def _tex(s: str) -> str:
    s = re.sub(r"\\(?:left|right)\s*", "", s)
    s = _SPACE.sub(" ", s)
    s = _KNOWN.sub(lambda m: _SYM[m.group(1)], s)        # symbols BEFORE unwrapping, so
    for _ in range(3):                                   # \Delta\text{OI} cannot fuse
        s = _WRAP.sub(r"\1", s)
    s = _CMD.sub(lambda m: m.group(1), s)                # unknown command -> its name
    s = re.sub(r"\{([^{}]*)\}", r"\1", s)                # bare grouping braces
    return re.sub(r"[ \t]{2,}", " ", s)


def delatex(text: str) -> str:
    """Plain text from a model answer that may contain inline LaTeX."""
    if not text or ("$" not in text and "\\" not in text):
        return text
    # math spans first; a lone '$' outside a matched pair is left alone
    out = _MATH.sub(lambda m: _tex(m.group(1) or m.group(2)).strip(), text)
    if "\\" in out:                                      # TeX commands outside $..$
        out = _KNOWN.sub(lambda m: _SYM[m.group(1)], out)
        out = _WRAP.sub(r"\1", out)
    return out
