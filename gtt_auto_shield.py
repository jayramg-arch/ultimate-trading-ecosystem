import os
import sqlite3
import argparse
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from dhanhq import dhanhq
from dhan_symbols import get_nse_id_map
import time

from dhan_auth import get_dhan_client
# RS-P1 (14-Jul-2026): dhan_helpers imports DhanContext, which does NOT exist in
# the installed dhanhq 2.0.x — that import made THIS WHOLE TOOL crash at launch in
# the app venv (the COMMAND button spawned a script that died on ImportError).
# check_margin is only a pre-flight warning (its call site is already try/except-
# wrapped), so degrade to a no-op instead of dying.
try:
    from dhan_helpers import check_margin
except Exception as _cm_exc:
    _CM_ERR = str(_cm_exc)      # `except..as` names are cleared after the block
    def check_margin(*_a, **_k):
        return {"sufficient": True, "_unavailable": _CM_ERR}

# --- 1. SETUP ---
load_dotenv()
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(_APP_DIR, "trade_journal_v6.db")

# RS-P1 (14-Jul-2026): rotating log so scheduled runs leave a record a human can
# read — console prints vanish when this runs headless from the scheduler.
log = logging.getLogger("gtt_shield")
if not log.handlers:
    try:
        os.makedirs(os.path.join(_APP_DIR, "logs"), exist_ok=True)
        _h = RotatingFileHandler(os.path.join(_APP_DIR, "logs", "gtt_shield.log"),
                                 maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                                          datefmt="%Y-%m-%d %H:%M:%S"))
        log.addHandler(_h)
        log.setLevel(logging.INFO)
    except Exception:
        pass

def connect_dhan():
    try:
        return get_dhan_client()
    except Exception as e:
        print(f"❌ Error connecting to Dhan: {e}")
        log.error(f"connect_dhan failed: {e}")
        return None

def load_journal_data():
    """Returns a dict mapping symbol to SL/Target + the entry-snapshot fields the
    catalyst-aware trail needs (setup, manual_sl_override, custom_ce_mult)."""
    if not os.path.exists(DB_FILE):
        return {}
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql("SELECT symbol, stoploss, target, setup, timeframe, "
                         "manual_sl_override, custom_ce_mult "
                         "FROM journal WHERE status = 'OPEN'", conn)
        conn.close()
        # Normalize keys (Symbol -> data)
        data = {}
        for _, r in df.iterrows():
            sym = str(r['symbol']).strip().upper().replace("NSE:", "").replace("BSE:", "")
            data[sym] = {'SL': r['stoploss'], 'Target': r['target'],
                         'setup': r['setup'],
                         'timeframe': r['timeframe'],
                         'manual_sl': r['manual_sl_override'],
                         'custom_mult': r['custom_ce_mult']}
        return data
    except Exception as e:
        # RS-P1: this was a bare `except: return {}` — a schema/DB error silently
        # yielded an empty map, every holding printed "NOT IN JOURNAL" and NOTHING
        # got shielded, with no error surfaced. Now loud.
        print(f"❌ Journal read FAILED (nothing will be shielded): {e}")
        log.error(f"load_journal_data failed: {e}")
        return {}

def run_auto_shield(auto_yes: bool = False):
    print("="*60)
    print("🛡️ GTT AUTO-SHIELD: COCKPIT MODE")
    print("="*60)

    dhan = connect_dhan()
    if not dhan: return
    
    id_map = get_nse_id_map()
    journal_data = load_journal_data()
    
    print("⏳ Fetching Holdings...")
    resp = dhan.get_holdings()
    if resp.get('status') != 'success':
        print(f"❌ API Error: {resp}")
        return
    
    holdings = resp.get('data', [])
    if not holdings:
        print("⚠️ Portfolio is empty.")
        return

    # Check for GTT orders already active
    print("⏳ Fetching Active GTT Orders...")
    gtt_resp = dhan.get_forever()
    active_gtt_syms = []
    if gtt_resp.get('status') == 'success':
        # RS-P0 (14-Jul-2026): dedup used to count ONLY orderStatus=='ACTIVE' while
        # the Risk Shield page reads 'PENDING' — a live GTT reported as PENDING was
        # invisible here, so the shield would PLACE A DUPLICATE OCO on an already-
        # protected holding. Robust rule: anything NOT in a terminal state is live.
        _TERMINAL = {"TRIGGERED", "CANCELLED", "CANCELED", "EXPIRED", "REJECTED", "CLOSED"}
        for o in gtt_resp.get('data', []):
            if str(o.get('orderStatus', '')).upper() not in _TERMINAL:
                active_gtt_syms.append(o.get('tradingSymbol', '').upper())

    shieldable_list = []
    print(f"\n✅ Found {len(holdings)} holdings. Comparing with Journal...")
    print("-" * 60)
    print(f"{'SYMBOL':<15} {'QTY':<8} {'STATUS':<20}")
    print("-" * 60)

    for h in holdings:
        sym = (h.get('tradingSymbol') or h.get('tradingsymbol')).upper()
        qty = h.get('totalQty') or h.get('quantity') or 0
        if qty <= 0: continue
        
        status_msg = ""
        if sym in active_gtt_syms:
            status_msg = "🟢 PROTECTED (GTT)"
        elif sym in journal_data:
            sl = journal_data[sym]['SL']
            tgt = journal_data[sym]['Target']
            
            # Robust check for NaN or 0
            import math
            has_sl = sl > 0 and not (isinstance(sl, float) and math.isnan(sl))
            has_tgt = tgt > 0 and not (isinstance(tgt, float) and math.isnan(tgt))
            
            if has_sl and has_tgt:
                status_msg = "🟡 READY TO SHIELD"
                shieldable_list.append({
                    'symbol': sym,
                    'qty': qty,
                    'sl': sl,
                    'target': tgt,
                    'exchange': h.get('exchangeSegment', 'NSE_EQ')
                })
            else:
                missing = []
                if not has_sl: missing.append("SL")
                if not has_tgt: missing.append("TGT")
                status_msg = f"🔴 MISSING {(' & '.join(missing)) if missing else 'LEVELS'}"
        else:
            status_msg = "⚪ NOT IN JOURNAL"
            
        print(f"{sym:<15} {qty:<8} {status_msg}")

    if not shieldable_list:
        print("\n✅ All journalled trades are already protected or missing data.")
        if not auto_yes:
            input("\nPress Enter to exit...")
        return

    print("-" * 60)
    confirm = "Y" if auto_yes else input(f"\n🚀 SHIELD ALL {len(shieldable_list)} READY TRADES? (Y/N): ").upper()

    if confirm == 'Y':
        for item in shieldable_list:
            sym = item['symbol']
            sec_id = id_map.get(sym)
            if not sec_id:
                print(f"⚠️ Skipping {sym}: Security ID not found.")
                continue
            
            print(f"📡 Activating OCO for {sym} (Tgt: {item['target']}, SL: {item['sl']})...")
            try:
                # Pre-flight Margin Check (Not strictly required for CNC SELL if holding, but good for validation)
                try:
                    margin_info = check_margin(
                        dhan,
                        security_id=str(sec_id),
                        exchange_segment=dhan.NSE,
                        transaction_type=dhan.SELL,
                        quantity=item['qty'],
                        product_type=dhan.CNC,
                        price=item['target'],
                        trigger_price=item['target']
                    )
                    # We only log for sell side since CNC SELL usually relies on holdings, not cash margin.
                    if not margin_info.get("sufficient", True):
                        print(f"   ⚠️  Warning: Dhan indicates insufficient margin (Shortfall: ₹{margin_info.get('shortfall', 0):.2f}). Attempting anyway since it's a SELL.")
                except Exception as e:
                    pass

                # OCO Order Logic
                res = dhan.place_forever(
                    security_id=str(sec_id),
                    exchange_segment=dhan.NSE,
                    product_type=dhan.CNC,
                    order_type=dhan.LIMIT,
                    transaction_type=dhan.SELL,
                    quantity=item['qty'],
                    # Target Leg
                    price=item['target'],
                    trigger_Price=item['target'],
                    # Stop Leg (OCO)
                    order_flag="OCO",
                    quantity1=item['qty'],
                    price1=item['sl'] * 0.995, # Slight buffer for SL limit
                    trigger_Price1=item['sl']
                )
                if res['status'] == 'success':
                    print(f"   ✅ SHIELD ACTIVE (ID: {res['data']['orderId']})")
                else:
                    print(f"   ❌ FAILED: {res.get('remarks')}")
                time.sleep(0.5) # Anti-throttle
            except Exception as e:
                print(f"   ❌ ERROR: {e}")

    print("\nMission Accomplished.")
    if not auto_yes:
        input("\nPress Enter to exit...")


# ═══════════════════════════════════════════════════════════════════════════════
# RS-P1 (14-Jul-2026) — TRAIL PASS: the audit's biggest finding was that once a
# GTT exists, the broker stop stays FROZEN at the entry SL forever (this tool was
# create-only, and skipped any symbol with an existing GTT). The DNA says ATR
# trailing stops are enforced programmatically — this pass makes that true:
#
#   For every live OCO SL leg, compute the catalyst-aware Chandelier
#   (risk_common — the SAME brain Risk Shield and Pyramid use, journal `setup`
#   drives the POS/WYC/REV/SWG multiplier) and, when the Chandelier is ABOVE the
#   current GTT trigger, modify_forever the SL leg up. TIGHTEN-ONLY — a stop is
#   never loosened. Jay's call: auto-trail, scheduled post-close daily.
# ═══════════════════════════════════════════════════════════════════════════════
_TERMINAL_GTT = {"TRIGGERED", "CANCELLED", "CANCELED", "EXPIRED", "REJECTED", "CLOSED"}
_TIGHTEN_DEADBAND = 1.001          # ignore <0.1% improvements (avoid churn/API spam)


def _live_oco_sl_legs(dhan):
    """Parse get_forever() into {SYMBOL: {order_id, sl_trigger, sl_qty}} for live
    OCO SL legs — same leg conventions as the Risk Shield page parser."""
    out = {}
    resp = dhan.get_forever()
    if not (isinstance(resp, dict) and resp.get("status") == "success"):
        print(f"❌ get_forever failed: {resp}")
        log.error(f"trail: get_forever failed: {resp}")
        return None
    for g in (resp.get("data") or []):
        if str(g.get("orderStatus", "")).upper() in _TERMINAL_GTT:
            continue
        if (g.get("transactionType", "") or "").upper() != "SELL":
            continue
        leg = (g.get("legName", "") or "").upper()
        ot = (g.get("orderType", "") or "").upper()
        if not ((ot == "OCO") or leg in ("STOP_LOSS_LEG", "TARGET_LEG")):
            continue
        sym = str(g.get("tradingSymbol", "")).upper().replace("NSE:", "").replace("-EQ", "")
        trigger = float(g.get("triggerPrice", 0) or 0)
        price = float(g.get("price", 0) or 0)
        is_sl = (leg == "STOP_LOSS_LEG") if leg in ("STOP_LOSS_LEG", "TARGET_LEG") else (
            trigger < price if (trigger and price) else True)
        if is_sl and sym and trigger > 0:
            out[sym] = {"order_id": str(g.get("orderId", "")),
                        "sl_trigger": trigger,
                        "sl_qty": int(float(g.get("quantity", 0) or 0))}
    return out


def run_trail_pass(auto_yes: bool = False):
    """Tighten-only Chandelier trail of live GTT SL legs. Never loosens; never
    modifies when the Chandelier sits at/above the last close (that's an EXIT
    signal, not a trail — modifying would fire the order instantly)."""
    print("=" * 60)
    print("🛡️ GTT AUTO-SHIELD — TRAIL PASS (tighten-only)")
    print("=" * 60)
    log.info("trail pass start")

    dhan = connect_dhan()
    if not dhan:
        return
    # Token sanity: one cheap authed call before doing anything
    try:
        _fl = dhan.get_fund_limits()
        if not (isinstance(_fl, dict) and _fl.get("status") == "success"):
            print(f"❌ Token/API check failed — aborting: {_fl}")
            log.error(f"trail: token check failed: {_fl}")
            return
    except Exception as e:
        print(f"❌ Token/API check exception — aborting: {e}")
        log.error(f"trail: token check exception: {e}")
        return

    journal = load_journal_data()
    legs = _live_oco_sl_legs(dhan)
    if legs is None:
        return
    if not legs:
        print("ℹ️ No live OCO SL legs found — nothing to trail. (Run the shield "
              "pass first to place OCOs.)")
        log.info("trail: no live SL legs")
        return

    # Bear regime — same source as Risk Shield/Pyramid (market_regime score ≤ 5).
    bear = False
    try:
        import market_regime as _mr
        _reg = _mr.compute_regime(persist=False) or {}
        bear = float(_reg.get("score", 10)) <= 5
    except Exception as e:
        log.warning(f"trail: regime unavailable (bear=False): {e}")

    import data_provider as _dp
    from risk_common import chandelier_exit

    proposals = []        # (sym, leg, old_sl, new_sl, mult, src, note)
    breached = []
    for sym, leg in sorted(legs.items()):
        j = journal.get(sym, {})
        try:
            df = _dp.fetch_ohlcv(sym, period="1y", interval="1d",
                                 use_cache=True, auto_adjust=True)
            if df is None or len(df) < 22:
                log.warning(f"trail: {sym}: insufficient bars — skipped")
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            c = df["Close"]; h = df["High"]; l = df["Low"]
            ltp = float(c.iloc[-1])
            above200 = bool(len(c) >= 200 and ltp > float(c.rolling(200).mean().iloc[-1]))
            _cm = j.get("custom_mult")
            _cm = float(_cm) if (_cm is not None and not pd.isna(_cm) and float(_cm) > 0) else None
            # Trade-type-aware trail clock: journal Timeframe → 14 swing / 22 pos.
            _tfj = str(j.get("timeframe") or "").lower()
            _swing = True if "swing" in _tfj else (False if "pos" in _tfj else None)
            ch, mult, src = chandelier_exit(h, l, c, setup=str(j.get("setup") or ""),
                                            bear=bear, custom_mult=_cm,
                                            above200=above200, swing=_swing)
            if ch is None:
                continue
            new_sl = ch
            # Manual override acts as a FLOOR (never trail below a hand-set stop).
            _msl = j.get("manual_sl")
            if _msl is not None and not pd.isna(_msl) and float(_msl) > 0:
                new_sl = max(new_sl, float(_msl))
            new_sl = round(float(new_sl), 2)
            if new_sl >= ltp:
                # Stop above price = the position is BELOW its trail → exit signal.
                # Do NOT modify (a SELL trigger ≥ LTP fires instantly = auto-exit,
                # which is order automation we deliberately did not enable).
                breached.append((sym, leg["sl_trigger"], new_sl, ltp))
                log.warning(f"trail: {sym}: Chandelier {new_sl} >= LTP {ltp} — "
                            f"EXIT SIGNAL, not trailed (GTT stays {leg['sl_trigger']})")
                continue
            if new_sl > leg["sl_trigger"] * _TIGHTEN_DEADBAND:
                proposals.append((sym, leg, leg["sl_trigger"], new_sl, mult, src,
                                  f"{'BEAR ' if bear else ''}{src}"))
        except Exception as e:
            print(f"⚠️ {sym}: trail computation failed: {e}")
            log.error(f"trail: {sym}: computation failed: {e}")

    print(f"\n{'SYMBOL':<14}{'GTT SL':>10}{'NEW SL':>10}{'MULT':>6}  SOURCE")
    print("-" * 60)
    for sym, leg, old, new, mult, src, note in proposals:
        print(f"{sym:<14}{old:>10.2f}{new:>10.2f}{mult:>6.1f}  {note}")
    for sym, old, ch, ltp in breached:
        print(f"{sym:<14}{old:>10.2f}{'--':>10}      ⚠ BREACHED: Chandelier {ch} ≥ LTP {ltp} — exit review")
    if not proposals:
        print("✅ No tightenings needed (all GTT stops at/above their Chandelier).")
        log.info(f"trail: 0 proposals, {len(breached)} breached")
        return

    if not auto_yes:
        confirm = input(f"\n🚀 TIGHTEN {len(proposals)} GTT STOP(S)? (Y/N): ").upper()
        if confirm != "Y":
            print("Aborted."); log.info("trail: user aborted")
            return

    done = failed = 0
    for sym, leg, old, new, mult, src, note in proposals:
        try:
            resp = dhan.modify_forever(
                order_id=leg["order_id"],
                order_flag="OCO",
                order_type=dhan.LIMIT,
                leg_name="STOP_LOSS_LEG",
                quantity=leg["sl_qty"],
                price=round(new * 0.995, 2),      # limit buffer, house convention
                trigger_price=new,
                disclosed_quantity=0,
                validity="DAY")
            ok = isinstance(resp, dict) and resp.get("status") == "success"
            if ok:
                done += 1
                print(f"   ✅ {sym}: {old} → {new} ({note})")
                log.info(f"trail: {sym}: {old} -> {new} mult={mult} src={src} "
                         f"order={leg['order_id']}")
                try:      # keep the journal floor in sync (same as Risk Shield tighten)
                    conn = sqlite3.connect(DB_FILE)
                    conn.execute("UPDATE journal SET manual_sl_override=? "
                                 "WHERE symbol=? AND status='OPEN'", (new, sym))
                    conn.commit(); conn.close()
                except Exception as e:
                    log.warning(f"trail: {sym}: journal write-back failed: {e}")
            else:
                failed += 1
                print(f"   ❌ {sym}: {resp.get('remarks') if isinstance(resp, dict) else resp}")
                log.error(f"trail: {sym}: modify failed: {resp}")
            time.sleep(0.5)
        except Exception as e:
            failed += 1
            print(f"   ❌ {sym}: {e}")
            log.error(f"trail: {sym}: modify exception: {e}")

    print(f"\nTrail pass done: {done} tightened, {failed} failed, "
          f"{len(breached)} breached (exit review).")
    log.info(f"trail pass done: {done} ok, {failed} failed, {len(breached)} breached")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="GTT Auto-Shield — place + trail Dhan GTT stops")
    ap.add_argument("--trail", action="store_true",
                    help="Tighten-only Chandelier trail of existing GTT SL legs")
    ap.add_argument("--yes", action="store_true",
                    help="Non-interactive (for the scheduler): skip confirmations")
    args = ap.parse_args()
    if args.trail:
        run_trail_pass(auto_yes=args.yes)
    else:
        run_auto_shield(auto_yes=args.yes)
