"""Weinstein Commander — Pyramid / Trim Manager (standalone page).

Thin wrapper: all logic lives in pyramid_logic.py (shared with the inline
Web Commander page, so the two never drift). This file only owns the standalone
page config, then delegates to render_pyramid_trim().
"""
from __future__ import annotations

import os
import sys

import streamlit as st

st.set_page_config(page_title="Pyramid / Trim — Weinstein Commander",
                   page_icon="⚖️", layout="wide")

# Make the project root importable (this file lives in pages/).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pyramid_logic import render_pyramid_trim

render_pyramid_trim()
