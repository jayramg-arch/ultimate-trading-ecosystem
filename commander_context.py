"""commander_context — the shared per-rerun state every Web Commander page reads (split phase 1).

The router computes broker cash, live holdings, the journal frame and the capital figure
once per rerun, at startup. Pages used to read those as bare module globals, which any page
could silently rebind for every page after it. They now read one FROZEN object, `ctx`:

    ctx.balance  ctx.sys_status  ctx.total_cap  ctx.df_active_global  ctx.df_live_holdings

Frozen means a page cannot reassign a field (`ctx.total_cap = …` raises). The DataFrames
inside are still mutable objects — a page that edits one in place changes it for later
pages exactly as before; freezing the container does not change that behaviour.

Risk %, capital policy and caps are NOT here: those belong to house_policy.py.
tests/test_split_guards.py fails if a converted page goes back to the bare names.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Ctx:
    balance: float            # Dhan available cash (0.0 when the broker call failed)
    sys_status: str           # "SYSTEM ONLINE" / "AUTH EXPIRED" / … from get_dhan_balance()
    total_cap: float          # full equity = cash + deployed (declared capital when Dhan is down)
    total_cap_is_live: bool   # False when total_cap fell back to the declared figure
    df_active_global: pd.DataFrame   # open journal rows, LTP mapped from live holdings
    df_live_holdings: pd.DataFrame   # Dhan holdings with LTP / P&L


# Names a converted page must read through ctx, never bare (guarded by a test).
SHARED_NAMES = ("balance", "sys_status", "total_cap", "df_active_global", "df_live_holdings")
