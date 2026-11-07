"""Chronological, cost-aware BTC next-5m return forecast (research only).

A ridge regression forecasts next candle open-to-close return using completed
historical candles. Thresholds are selected on validation only; untouched test
is reported without deploying orders. Predictions are not calibrated intervals.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.train_direction import examples
from research.evaluate_cost_edge import labeled_returns

def fit_ridge(data, epochs=120, rate=.025, l2=.1):
    n=len(data[0][0])
    mu=[sum(x[j] for x,_ in data)/len(data) for j in range(n)]
    std=[max((sum((x[j]-mu[j])**2 for x,_ in data)/len(data))**.5,1e-8) for j in range(n)]
    ys=[y for _,y in data]
    ymean=sum(ys)/len(ys)
    yscale=max((sum((y-ymean)**2 for y in ys)/len(ys))**.5,1e-8)
    weights=[0.]*n
    bias=0.
    for _ in range(epochs):
        gradients=[0.]*n
        gb=0.
        for x,y in data:
            z=[max(-10.,min(10.,(x[j]-mu[j])/std[j])) for j in range(n)]
            error=bias+sum(w*v for w,v in zip(weights,z))-(y-ymean)/yscale
            gb+=error
            for j in range(n):gradients[j]+=error*z[j]
        bias-=rate*gb/len(data)
        weights=[w-rate*(g/len(data)+l2*w) for w,g in zip(weights,gradients)]
    return {"mean":mu,"std":std,"ymean":ymean,"yscale":yscale,
            "weights":weights,"bias":bias}

def predict(model,x):
    z=[max(-10.,min(10.,(v-m)/s)) for v,m,s in zip(x,model["mean"],model["std"])]
    return model["ymean"]+model["yscale"]*(model["bias"]+sum(w*v for w,v in zip(model["weights"],z)))

def assess(model,data,threshold,cost):
    trades=[]
    abs_errors=[]
    for x,ret in data:
        forecast=predict(model,x)
        abs_errors.append(abs(forecast-ret))
        side=1 if forecast>threshold else -1 if forecast< -threshold else 0
        if side:trades.append(side*ret-cost)
    return {
        "samples":len(data),"trades":len(trades),
        "mae_forecast_pct":round(100*sum(abs_errors)/len(abs_errors),5) if abs_errors else None,
        "avg_net_pct":round(100*sum(trades)/len(trades),5) if trades else None,
        "net_wins":sum(t>0 for t in trades),
        "sum_unit_notional_net_pct":round(100*sum(trades),4),
    }

def run(rows,fee_per_side=.008,spread_bps=5,slippage_bps=2):
    samples=examples(rows)
    returns=labeled_returns(rows)
    if len(samples)!=len(returns) or len(samples)<500:
        raise ValueError("Insufficient or mismatched history")
    if min(fee_per_side,spread_bps,slippage_bps)<0:
        raise ValueError("Negative costs")
    data=[(x,ret) for (x,_),(_,ret) in zip(samples,returns)]
    a,b=int(len(data)*.6),int(len(data)*.8)
    model=fit_ridge(data[:a])
    cost=2*fee_per_side+(spread_bps+2*slippage_bps)/10000
    # Require expected absolute move to exceed estimated round-trip costs.
    thresholds=[cost*m for m in (1,1.25,1.5,2,3)]
    ranked=[(assess(model,data[a:b],t,cost),t) for t in thresholds]
    eligible=[(r,t) for r,t in ranked if r["trades"]>=30]
    if not eligible:
        return {"decision":"NO_TRADE","reason":"insufficient_validation_trades",
                "cost_roundtrip_pct":round(100*cost,4)}
    validation,threshold=max(eligible,key=lambda item:item[0]["avg_net_pct"])
    holdout=assess(model,data[b:],threshold,cost)
    positive=validation["avg_net_pct"]>0 and holdout["trades"]>=30 and holdout["avg_net_pct"]>0
    return {
        "method":"ridge_next_5m_return_forecast",
        "forecast_target":"next_5m_open_to_close_return",
        "cost_roundtrip_pct":round(100*cost,4),
        "selected_min_forecast_move_pct":round(100*threshold,5),
        "validation":validation,"untouched_test":holdout,
        "decision":"RESEARCH_ONLY" if positive else "NO_TRADE",
        "warning":"No exchange execution or live orders. Not a calibrated price interval. "
                  "Independent walk-forward and paper forward validation required.",
    }

if __name__=="__main__":
    print(json.dumps(run(read_csv(sys.argv[1])),indent=2))
