"""Fail-closed paper-only promotion gate for research forecasts."""
from math import isfinite
from research.risk_curriculum import risk_plan

def paper_candidate(*, forecast_return, expected_price, entry, equity, stop, target,
                    validated=False, walk_forward_passed=False,
                    day_start_equity=None, consecutive_losses=0,
                    fee_per_side=.008,spread_bps=5,slippage_bps=2):
    result={"decision":"WAIT","reason":"unverified_model_or_risk","orders_enabled":False}
    vals=(forecast_return,expected_price,entry,equity,stop,target)
    if any(not isfinite(v) for v in vals) or min(expected_price,entry,equity,stop,target)<=0:
        return {**result,"reason":"invalid_inputs"}
    if not validated or not walk_forward_passed:
        return {**result,"reason":"model_not_independently_validated"}
    cost=2*fee_per_side+(spread_bps+2*slippage_bps)/10000
    if not isfinite(cost) or cost<0 or abs(forecast_return)<=cost:
        return {**result,"reason":"forecast_does_not_cover_costs"}
    side="LONG" if forecast_return>0 else "SHORT"
    if (side=="LONG" and expected_price<=entry) or (side=="SHORT" and expected_price>=entry):
        return {**result,"reason":"forecast_price_disagrees"}
    risk=risk_plan(equity=equity,entry=entry,stop=stop,target=target,side=side,
                   fee_per_side=fee_per_side,spread_bps=spread_bps,
                   slippage_bps=slippage_bps,signal_validated=True,
                   day_start_equity=day_start_equity,
                   consecutive_losses=consecutive_losses)
    if risk["decision"]!="RESEARCH_CANDIDATE":
        return {**result,"reason":risk.get("reason","risk_rejected"),"risk":risk}
    return {"decision":"PAPER_RESEARCH_CANDIDATE","reason":"research_gates_passed",
            "side":side,"risk":risk,"orders_enabled":False,
            "warning":"No broker/exchange execution; manual research review required."}
