"""Research-only leveraged paper trade simulator; no exchange connectivity.

Simplified isolated-margin model with explicit funding, fees, slippage,
maintenance margin and liquidation. This is not an exchange liquidation engine.
"""
from dataclasses import dataclass
from math import isfinite

@dataclass(frozen=True)
class LeverageTrade:
    side: int
    entry: float
    exit: float
    leverage: float
    margin_eur: float
    fee_per_side: float = .0008
    spread_bps: float = 5
    slippage_bps: float = 2
    funding_rate: float = 0.0
    maintenance_margin_rate: float = .005
    adverse_extreme: float | None = None

def simulate(trade: LeverageTrade):
    if trade.side not in (-1, 1):
        raise ValueError("side must be LONG (+1) or SHORT (-1)")
    values=(trade.entry,trade.exit,trade.leverage,trade.margin_eur,
            trade.fee_per_side,trade.spread_bps,trade.slippage_bps,
            trade.funding_rate,trade.maintenance_margin_rate)
    if not all(isfinite(v) for v in values):
        raise ValueError("non-finite input")
    if min(trade.entry,trade.exit,trade.leverage,trade.margin_eur)<=0:
        raise ValueError("prices, leverage and margin must be positive")
    if trade.leverage>20:
        raise ValueError("research leverage capped at 20x")
    if min(trade.fee_per_side,trade.spread_bps,trade.slippage_bps,
           trade.maintenance_margin_rate)<0:
        raise ValueError("negative costs")
    if trade.adverse_extreme is not None and (
        not isfinite(trade.adverse_extreme) or trade.adverse_extreme<=0
    ):
        raise ValueError("invalid adverse extreme")
    notional=trade.margin_eur*trade.leverage
    # Round-trip costs on notional, funding charged once per supplied period.
    cost_fraction=2*trade.fee_per_side+(trade.spread_bps+2*trade.slippage_bps)/10000
    total_cost=notional*(cost_fraction+trade.funding_rate)
    gross=notional*trade.side*(trade.exit/trade.entry-1)
    # Approximate isolated margin exhaustion including maintenance and costs.
    liquidation_move=(trade.margin_eur*(1-trade.maintenance_margin_rate)-total_cost)/notional
    liquidation_price=trade.entry*(1-trade.side*liquidation_move)
    adverse=trade.adverse_extreme if trade.adverse_extreme is not None else trade.exit
    liquidated=(adverse<=liquidation_price if trade.side==1 else adverse>=liquidation_price)
    net=-trade.margin_eur if liquidated else max(-trade.margin_eur,gross-total_cost)
    return {
        "side":"LONG" if trade.side==1 else "SHORT",
        "leverage":trade.leverage,
        "notional_eur":round(notional,4),
        "gross_pnl_eur":round(gross,4),
        "total_cost_eur":round(total_cost,4),
        "liquidation_price_approx":round(liquidation_price,6),
        "liquidated":liquidated,
        "net_pnl_eur":round(net,4),
        "ending_margin_eur":round(trade.margin_eur+net,4),
        "note":"Simplified isolated margin research. No exchange orders; intrabar extreme required for reliable liquidation detection.",
    }
