"""Cost-aware strong-signal confirmation on completed candles; offline research only.

The eight feature values come from train_direction.examples. No future labels
are used for a signal; thresholds are selected on validation, not test.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.train_direction import examples
from research.evaluate_cost_edge import labeled_returns
from research.forecast_expected_value import fit_ridge, predict

def confirmed_side(x, forecast, threshold, volume_min=0.0):
    """Combine learned return forecast, multi-horizon momentum, candle location and volume."""
    if len(x) != 8 or abs(forecast) <= threshold:
        return 0
    side = 1 if forecast > 0 else -1
    # Feature positions: 5m, 15m, 60m, 180m momentum; candle body,
    # close location, range, 5m volume versus prior hour.
    if not (side*x[0] > 0 and side*x[1] > 0 and side*x[2] > 0):
        return 0
    if not (side*x[4] > 0 and side*x[5] > 0):
        return 0
    if x[7] < volume_min:
        return 0
    return side

def score(model, data, threshold, cost, volume_min=0.0, confirmed=True):
    returns=[]
    for x,actual in data:
        forecast=predict(model,x)
        side=confirmed_side(x,forecast,threshold,volume_min) if confirmed else (
            1 if forecast>threshold else -1 if forecast< -threshold else 0)
        if side:
            returns.append(side*actual-cost)
    return {"trades":len(returns),
            "avg_net_pct":round(100*sum(returns)/len(returns),5) if returns else None,
            "sum_unit_notional_net_pct":round(100*sum(returns),4),
            "win_rate_pct":round(100*sum(v>0 for v in returns)/len(returns),2) if returns else None}

def run(rows, fee_per_side=.008, spread_bps=5, slippage_bps=2):
    if min(fee_per_side,spread_bps,slippage_bps)<0:
        raise ValueError("Negative trading costs")
    xs=examples(rows)
    rets=labeled_returns(rows)
    if len(xs)!=len(rets) or len(xs)<500:
        raise ValueError("Insufficient or mismatched historical candles")
    data=[(x,ret) for (x,_),(_,ret) in zip(xs,rets)]
    a,b=int(len(data)*.6),int(len(data)*.8)
    cost=2*fee_per_side+(spread_bps+2*slippage_bps)/10000
    model=fit_ridge(data[:a])
    candidates=[]
    for multiplier in (1,1.25,1.5,2,3):
        for volume_min in (0.,.25,.5):
            threshold=cost*multiplier
            valid=score(model,data[a:b],threshold,cost,volume_min)
            if valid["trades"]>=30:
                candidates.append((valid["avg_net_pct"],valid["trades"],threshold,volume_min,valid))
    if not candidates:
        return {"decision":"NO_TRADE","reason":"insufficient_confirmed_validation_trades",
                "cost_roundtrip_pct":round(cost*100,4),"validation":None,"untouched_test":None}
    _,_,threshold,volume_min,valid=max(candidates,key=lambda t:(t[0],t[1]))
    test=score(model,data[b:],threshold,cost,volume_min)
    baseline=score(model,data[b:],threshold,cost,confirmed=False)
    positive=(valid["avg_net_pct"]>0 and test["trades"]>=30 and
              test["avg_net_pct"] is not None and test["avg_net_pct"]>0)
    return {"decision":"RESEARCH_ONLY" if positive else "NO_TRADE",
            "cost_roundtrip_pct":round(cost*100,4),
            "selected_forecast_threshold_pct":round(threshold*100,5),
            "selected_min_relative_volume":1+volume_min,
            "validation":valid,"untouched_test":test,"baseline_same_threshold_test":baseline,
            "warning":"Historical proxy candles and estimated costs only. No live orders, "
                      "no proof of profitability; walk-forward and forward paper validation required."}

if __name__=="__main__":
    print(json.dumps(run(read_csv(sys.argv[1])),indent=2))
