"""Research-only net execution accounting; fees, spread and slippage explicitly separated.

Use actual bid/ask where available. The 0.05% scenario is hypothetical,
NOT a claim about Kraken fees. No live orders.
"""
import math


def net_execution(side, quantity, entry_mid, exit_mid, *,
                  fee_per_side, spread_bps=5.0, slippage_bps=2.0):
    vals = (quantity, entry_mid, exit_mid, fee_per_side, spread_bps, slippage_bps)
    if not all(math.isfinite(v) for v in vals) or min(quantity, entry_mid, exit_mid) <= 0:
        raise ValueError("invalid quantity or prices")
    if side not in ("LONG", "SHORT") or min(fee_per_side, spread_bps, slippage_bps) < 0:
        raise ValueError("invalid side or costs")
    half_spread = spread_bps / 20000
    slip = slippage_bps / 10000
    if side == "LONG":
        entry = entry_mid * (1 + half_spread + slip)
        exit_price = exit_mid * (1 - half_spread - slip)
        gross = (exit_price - entry) * quantity
    else:
        entry = entry_mid * (1 - half_spread - slip)
        exit_price = exit_mid * (1 + half_spread + slip)
        gross = (entry - exit_price) * quantity
    entry_fee = entry * quantity * fee_per_side
    exit_fee = exit_price * quantity * fee_per_side
    return {"side": side, "entry_fill": entry, "exit_fill": exit_price,
            "entry_fee_eur": entry_fee, "exit_fee_eur": exit_fee,
            "gross_after_spread_slippage_eur": gross,
            "net_pnl_eur": gross - entry_fee - exit_fee,
            "fee_scenario": fee_per_side}


def compare_cost_scenarios(side, quantity, entry_mid, exit_mid, *,
                           spread_bps=5.0, slippage_bps=2.0):
    return {
        "conservative_0_8pct_each_side": net_execution(
            side, quantity, entry_mid, exit_mid, fee_per_side=.008,
            spread_bps=spread_bps, slippage_bps=slippage_bps),
        "hypothetical_0_05pct_each_side": net_execution(
            side, quantity, entry_mid, exit_mid, fee_per_side=.0005,
            spread_bps=spread_bps, slippage_bps=slippage_bps),
    }
