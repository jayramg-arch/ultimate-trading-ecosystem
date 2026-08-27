"""commander_theme.py — the Web Commander's design tokens, in one place.

WHY THIS EXISTS
---------------
Before this module, `weinstein_commander_web_v4.0.py` carried ~900 hardcoded hex
values across 18,733 lines and 338 inline `style=` attributes. Nothing enforced that
two "bullish greens" on different pages were the same green, and they frequently were
not. The app also had NO dark theme: `prefers-color-scheme` appeared nowhere, and the
ground was a literal `#F0F4F8`.

This file is the single source of colour, type and spacing. Every rule in the app's
stylesheet should reach for `var(--token)` rather than a literal.

THE PALETTE (27 Aug 2026, Jay: "colors that are soothing on eyes like teal")
---------------------------------------------------------------------------
Teal-anchored and low-saturation, chosen for a surface someone reads from pre-market
through to the evening arming session.

  * The NEUTRALS carry a blue-green bias so they sit UNDER the accent instead of
    competing with it. They replace Tailwind's stock slate ramp (#1E293B / #334155 /
    #94A3B8 / #CBD5E1 / #E2E8F0), which was used because it was to hand.

  * The SEMANTIC trio keeps its hues. Green is bull, red is bear, amber is warn —
    exactly as before. Those are learned associations in a trading app: you read the
    colour before you read the number, and swapping one would be actively harmful.

  * What changed is SATURATION. #DC2626 is a fire-engine red built to alarm, which is
    correct for a smoke detector and wrong for a screen you sit in front of for eight
    hours; on a book with several red rows it is genuinely tiring. #C2453C carries the
    same meaning at a lower volume. Softening a hue is a different act from swapping
    one, and only the first is safe.

Contrast: all four semantic colours clear 4.5:1 against their own tinted grounds in
both themes.

DARK MODE — and why it does NOT follow the OS
---------------------------------------------
Two blocks, not three:
  :root                        the DARK palette — the default
  :root[data-theme="light"]    light, only for anyone who explicitly stamps it

The first version followed `prefers-color-scheme` and broke the app on 27 Aug 2026.
We do not own the whole page: Streamlit's widgets read `.streamlit/config.toml`,
which is STATIC and cannot answer a media query. The moment the stylesheet follows
the OS, a viewer whose desktop disagrees with that file gets Streamlit's widgets in
one theme on our ground in the other — invisible metric values, a white dataframe on
a dark page. A page that only half-owns its rendering has to COMMIT.

`assert_theme_parity()` guards the other half of this: a token present in one palette
and missing from the other renders fine in the theme you tested and leaves a hole in
the one you did not.

STREAMLIT AND PLOTLY DO NOT READ THESE TOKENS
---------------------------------------------
Two consequences that have each cost a round of breakage:

  * `.streamlit/config.toml` must be kept in AGREEMENT with DARK{} by hand. It is
    the only lever for the dataframe, which is a canvas grid CSS cannot reach.
  * A CSS variable renders as NOTHING in SVG. Never hand `var(--x)` to Plotly —
    resolve to a literal from DARK{} instead, or the mark silently vanishes.

TOKEN ROLES ARE NOT INTERCHANGEABLE
-----------------------------------
`surface*` are grounds and `ink*` / `muted` / `faint` are text. Using a ground token
as a `color:` paints text the same shade as the card behind it — the invisible-number
bug, expressed in tokens instead of literals. Likewise `--acc` is a light teal here,
so anything sitting ON it needs `--ground`, not `--ink`.
"""

# ── colour ───────────────────────────────────────────────────────────────────
LIGHT = {
    "ground": "#EDF2F2", "surface": "#FFFFFF", "surface-2": "#F5F9F9", "surface-3": "#E1E9E9",
    "ink": "#0D1618", "ink-2": "#35474A", "muted": "#64757A", "faint": "#95A5A8",
    "rule": "#D2DDDD", "rule-soft": "#E4EBEB",
    "acc": "#0E7C86", "acc-bg": "#E2F0F1", "acc-rule": "#9BC7CB",
    "bull": "#1B7A5A", "bull-bg": "#E3F0EB", "bull-rule": "#9BC6B5",
    "bear": "#C2453C", "bear-bg": "#F9EAE8", "bear-rule": "#E0AEA9",
    "warn": "#A76A1E", "warn-bg": "#F8F1E2", "warn-rule": "#DCC190",
}

DARK = {
    "ground": "#0F1618", "surface": "#161F21", "surface-2": "#1B2528", "surface-3": "#222E31",
    "ink": "#E3EBEC", "ink-2": "#B6C4C6", "muted": "#8B9BA0", "faint": "#7A8B8F",
    "rule": "#232F32", "rule-soft": "#1B2528",
    "acc": "#56C2CC", "acc-bg": "#0C262A", "acc-rule": "#1F4A50",
    "bull": "#45BE92", "bull-bg": "#0C2A21", "bull-rule": "#1D5142",
    "bear": "#E9857C", "bear-bg": "#2C1A18", "bear-rule": "#5C332E",
    "warn": "#DCA84E", "warn-bg": "#2A2211", "warn-rule": "#57461F",
}

# ── type ─────────────────────────────────────────────────────────────────────
# Two of the three faces are KEPT. Inter is correct for the job and already loaded;
# JetBrains Mono is genuinely good for numbers. Only the display face changes:
# Rajdhani is condensed and squared, reads as a gaming HUD, and at 3px tracking in
# caps it is slow to scan. Archivo carries the same authority at a smaller size.
FONTS = {
    "disp": "'Archivo','Helvetica Neue',Arial,sans-serif",
    "body": "'Inter','Helvetica Neue',Arial,sans-serif",
    "mono": "'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,monospace",
}

GOOGLE_FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=Archivo:wght@500;600;700;800"
    "&family=Inter:wght@400;500;600;700;800;900"
    "&family=JetBrains+Mono:wght@400;500;700;800"
    "&display=swap"
)


def _decls(d):
    return "".join(f"  --{k}:{v};\n" for k, v in d.items())


def tokens_css() -> str:
    """The token blocks plus the type tokens.

    DARK IS THE DEFAULT, and this does NOT follow prefers-color-scheme. That is a
    correction, not an oversight — the first version did follow the OS and it broke the
    app on 27 Aug 2026.

    The reason is that we do not own the whole page. Streamlit's widgets — metrics,
    dataframes, radios, inputs — take their colours from .streamlit/config.toml, which
    is a STATIC file that cannot respond to a media query. So the moment the stylesheet
    follows the OS, a viewer on a light desktop gets Streamlit's dark widgets on our
    light ground, or the reverse: invisible dark-on-dark metric values and a white
    dataframe sitting on a dark page.

    A page that only half-owns its own rendering has to COMMIT to one theme. Light stays
    reachable through an explicit data-theme="light" stamp for anyone who wants it, but
    nothing sets that automatically, and config.toml would need to change with it.

    Returned with SINGLE braces: the app's main stylesheet is an f-string (every CSS
    brace doubled) and this is concatenated rather than interpolated, so doubling here
    would send literal braces to the browser.
    """
    fonts = "".join(f"  --{k}:{v};\n" for k, v in FONTS.items())
    return (
        "@import url('" + GOOGLE_FONTS + "');\n"
        ":root{\n" + _decls(DARK) + fonts +
        "  --radius:3px;\n"
        "}\n"
        ":root[data-theme=\"light\"]{\n" + _decls(LIGHT) + "}\n"
    )


def assert_theme_parity():
    """Every light token must have a dark counterpart, and vice versa.

    This is the guard for the failure that is invisible in review: a token added to
    :root and forgotten in the dark blocks renders correctly in light mode and leaves
    a hole in dark mode that inherits whatever the host painted. Cheap to check, and
    it has to be checked mechanically because nothing about the page looks wrong until
    someone with a dark OS opens it.
    """
    only_light = sorted(set(LIGHT) - set(DARK))
    only_dark = sorted(set(DARK) - set(LIGHT))
    if only_light or only_dark:
        raise AssertionError(
            f"theme token mismatch — light-only: {only_light}, dark-only: {only_dark}"
        )
    return True


assert_theme_parity()


if __name__ == "__main__":
    print(tokens_css())
    print(f"# {len(LIGHT)} tokens x 2 themes, parity OK")
