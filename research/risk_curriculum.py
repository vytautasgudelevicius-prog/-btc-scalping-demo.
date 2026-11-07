"""Auditable research lessons on sizing, costs, risk and no-trade decisions.

Not an exchange order engine. No credentials, deployment or database access.
"""
from math import isfinite

LESSONS = (
    "capital preservation", "fixed fractional position sizing",
    "stop distance", "round-trip fees and spread", "slippage",
    "minimum reward to risk", "maximum notional exposure",
    "daily drawdown kill switch", "consecutive loss kill switch",
    "uncertain signal abstention", "liquidity/spread filter",
    "no-trade on invalid market data",
)

def risk_plan(*, equity, entry, stop, target, side, risk_fraction=.005,
              max_notional_fraction=.2, fee_per_side=.008, spread_bps=5,
              slippage_bps=2, max_spread_bps=20, min_net_rr=1.5,
              day_start_equity=None, max_daily_loss_fraction=.02,
              consecutive_losses=0, max_consecutive_losses=3,
              signal_validated=False):
    result={"decision":"WAIT","quantity":0.0,"notional":0.0,
            "lessons":list(LESSONS)}
    values=(equity,entry,stop,target,risk_fraction,max_notional_fraction,
            fee_per_side,spread_bps,slippage_bps,max_spread_bps,min_net_rr)
    if any(not isfinite(v) for v in values) or equity<=0 or entry<=0 or stop<=0 or target<=0:
        result["reason"]="invalid_market_or_account_data"
        return result
    if side not in ("LONG","SHORT") or not (0<risk_fraction<=.02) or not (0<max_notional_fraction<=1):
        result["reason"]="invalid_risk_configuration"
        return result
    if min(fee_per_side,spread_bps,slippage_bps,max_spread_bps)<0 or min_net_rr<1:
        result["reason"]="invalid_cost_configuration"
        return result
    if day_start_equity is not None:
        if not isfinite(day_start_equity) or day_start_equity<=0:
            result["reason"]="invalid_daily_equity"
            return result
        if equity <= day_start_equity*(1-max_daily_loss_fraction):
            result["reason"]="daily_loss_limit"
            return result
    if consecutive_losses>=max_consecutive_losses:
        result["reason"]="loss_streak_limit"
        return result
    if not signal_validated:
        result["reason"]="signal_not_validated"
        return result
    if spread_bps>max_spread_bps:
        result["reason"]="spread_too_wide"
        return result
    if (side=="LONG" and not stop<entry<target) or (side=="SHORT" and not target<entry<stop):
        result["reason"]="invalid_stop_target_geometry"
        return result
    roundtrip_cost=2*fee_per_side+(spread_bps+2*slippage_bps)/10000
    gross_risk=abs(entry-stop)/entry
    gross_reward=abs(target-entry)/entry
    net_risk=gross_risk+roundtrip_cost
    net_reward=gross_reward-roundtrip_cost
    result["cost_pct"]=round(roundtrip_cost*100,4)
    result["net_reward_risk"]=round(net_reward/net_risk,4) if net_risk else None
    if net_reward<=0 or net_reward/net_risk<min_net_rr:
        result["reason"]="insufficient_net_reward_risk"
        return result
    risk_budget=equity*risk_fraction
    notional=min(risk_budget/net_risk,equity*max_notional_fraction)
    result.update({"decision":"RESEARCH_CANDIDATE","reason":"risk_checks_passed",
                   "quantity":round(notional/entry,10),"notional":round(notional,4),
                   "risk_budget_eur":round(risk_budget,4),
                   "worst_case_modeled_loss_eur":round(notional*net_risk,4)})
    return result
