"""Discover BTC/EUR UTC hours with historically positive strong-signal net edge.

Research only. Hour selection and forecast threshold use TRAIN/VALIDATION only.
Final chronological test remains untouched. No production order authorization.
"""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.train_direction import examples
from research.evaluate_cost_edge import labeled_returns
from research.forecast_expected_value import fit_ridge,predict
from research.strong_signal_backtest import confirmed_side

def trades_for_hour(model,records,threshold,cost,volume_min=0):
    out={h:[] for h in range(24)}
    for x,ret,hour in records:
        side=confirmed_side(x,predict(model,x),threshold,volume_min)
        if side:
            out[hour].append(side*ret-cost)
    return out

def stats(returns):
    return {"trades":len(returns),
            "avg_net_pct":round(100*sum(returns)/len(returns),5) if returns else None,
            "win_rate_pct":round(100*sum(x>0 for x in returns)/len(returns),2) if returns else None,
            "sum_unit_notional_net_pct":round(100*sum(returns),4)}

def run(rows,fee_per_side=.008,spread_bps=5,slippage_bps=2,
        min_validation_trades=15,min_test_trades=15):
    if min(fee_per_side,spread_bps,slippage_bps)<0 or min(min_validation_trades,min_test_trades)<1:
        raise ValueError("Invalid costs or minimum trades")
    xs=examples(rows);returns=labeled_returns(rows)
    if len(xs)!=len(returns) or len(xs)<900:
        raise ValueError("Insufficient aligned 5m samples")
    # Reconstruct feature anchor indices exactly as train_direction.examples does.
    # Never zip 5m examples against 1m row indices: that mislabels entry hours.
    anchors=[]
    for i in range(239,len(rows)-5,5):
        if int(rows[i][0].timestamp())//60 % 5 != 4:
            continue
        if rows[i+5][4] == rows[i+1][1]:
            continue
        anchors.append(i)
    if len(anchors)!=len(xs):
        raise ValueError('Feature-to-hour alignment failed; no trading approval')
    data=[(x,ret,rows[i+1][0].hour) for (x,_),(_,ret),i in zip(xs,returns,anchors)]
    a,b=int(len(data)*.6),int(len(data)*.8)
    cost=2*fee_per_side+(spread_bps+2*slippage_bps)/10000
    model=fit_ridge([(x,ret) for x,ret,_ in data[:a]])
    candidates=[]
    for multiplier in (1,1.25,1.5,2,3):
        for volume_min in (0.,.25,.5):
            threshold=cost*multiplier
            by_hour=trades_for_hour(model,data[a:b],threshold,cost,volume_min)
            eligible={h:v for h,v in by_hour.items() if len(v)>=min_validation_trades and sum(v)/len(v)>0}
            if eligible:
                # Select hours exclusively on validation. Penalize tiny samples.
                selected=sorted(eligible,key=lambda h:(sum(eligible[h])/len(eligible[h]),len(eligible[h])),reverse=True)[:4]
                validation=[v for h in selected for v in eligible[h]]
                candidates.append((sum(validation)/len(validation),len(validation),threshold,volume_min,selected))
    if not candidates:
        return {"decision":"NO_TRADE","reason":"no_positive_validation_hours_after_costs",
                "cost_roundtrip_pct":round(cost*100,4),"selected_utc_hours":[]}
    _,_,threshold,volume_min,hours=max(candidates,key=lambda x:(x[0],x[1]))
    validation_hours=trades_for_hour(model,data[a:b],threshold,cost,volume_min)
    test_hours=trades_for_hour(model,data[b:],threshold,cost,volume_min)
    validation=[v for h in hours for v in validation_hours[h]]
    test=[v for h in hours for v in test_hours[h]]
    test_stats=stats(test)
    passed=(len(test)>=min_test_trades and test_stats["avg_net_pct"] is not None
            and test_stats["avg_net_pct"]>0)
    return {"decision":"RESEARCH_ONLY" if passed else "NO_TRADE",
            "selected_utc_hours":sorted(hours),
            "cost_roundtrip_pct":round(cost*100,4),
            "selected_forecast_threshold_pct":round(100*threshold,5),
            "selected_min_relative_volume":1+volume_min,
            "validation":stats(validation),"untouched_test":test_stats,
            "test_hour_breakdown":{f"{h:02d}:00 UTC":stats(test_hours[h]) for h in range(24)},
            "warning":"Hour selection is retrospective, UTC and data-source dependent. "
                      "No auto trading authorization. Requires independent walk-forward "
                      "and live forward paper validation."}

if __name__=="__main__":
    print(json.dumps(run(read_csv(sys.argv[1])),indent=2))
