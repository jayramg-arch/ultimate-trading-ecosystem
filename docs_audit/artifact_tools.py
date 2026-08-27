"""Helpers for the 26-Aug-2026 Commander Library audit.

A published artifact comes back wrapped in the frame runtime (<!doctype>, the
preamble <script>, the reset <style>, <body>). Republishing that verbatim would nest
a second wrapper inside the first, so `content()` strips it back to the page body --
the form the Artifact tool expects to be handed.

`facts()` is the point of the exercise: the audit checks pages against values read
from the CODE, never from CLAUDE.md, because the notes are themselves a document that
can drift. Every entry here carries the file it was read from.
"""
import io
import os
import re

TOOLRES = os.path.join(
    os.path.expanduser("~"),
    r".claude\projects\C--Users-jayra-Documents-GeminiVSCode",
    "e9f4697c-8185-40de-b7a3-21917177b2fa", "tool-results")


def saved_path(stub):
    """Newest saved copy whose name contains `stub` (the artifact id fragment)."""
    hits = [f for f in os.listdir(TOOLRES) if stub in f and f.endswith(".html")]
    if not hits:
        raise FileNotFoundError(f"no saved artifact matching {stub!r}")
    hits.sort(key=lambda f: os.path.getmtime(os.path.join(TOOLRES, f)))
    return os.path.join(TOOLRES, hits[-1])


def content(stub):
    """Publishable body of a saved artifact: everything after the runtime wrapper."""
    raw = io.open(saved_path(stub), encoding="utf-8").read()
    i = raw.find("<body>")
    if i == -1:
        raise ValueError("no <body> — wrapper shape changed, check before stripping")
    body = raw[i + len("<body>"):]
    for tail in ("</body></html>", "</body>", "</html>"):
        if body.rstrip().endswith(tail):
            body = body.rstrip()[: -len(tail)]
    return body.strip() + "\n"


def write_page(stub, out_path):
    c = content(stub)
    io.open(out_path, "w", encoding="utf-8").write(c)
    return len(c)


def text_of(html_str):
    """Rough visible text, for claim-hunting."""
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html_str, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t)
