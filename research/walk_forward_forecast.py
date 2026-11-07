"""Expanding-window walk-forward forecast verification; research only.

Train exclusively on the past. Select threshold on subsequent validation,
then score a later non-overlapping test. No model updates on test labels.
"""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.train_direction import examples
from research.evaluate_cost_edge import labeled_returns
from research.forecast_expected_value import fit_ridge,assess

def walk_forward(rows, fee_per_side=.008,spread_bps=5,slippage_bps=2,folds=3):
    if min(fee_per_side,spread_bps,slippage_bps)<0 or folds<1:
        raise ValueError("Invalid cost or fold configuration")
    xs=examples(rows);rets=labeled_returns(rows)
    if len(xs)!=len(rets) or len(xs)<900:
        raise ValueError("Need at least 900 aligned labeled 5m candles")
    data=[(x,ret) for (x,_),(_,ret) in zip(xs,rets)]
    n=len(data);cost=2*fee_per_side+(spread_bps+2*slippage_bps)/10000
    start=n//2;step=(n-start)//(folds+1)
    if step<30:raise ValueError("Insufficient data per fold")
    reports=[]
    for fold in range(folds):
        train_end=start+fold*step
        validation_end=train_end+step
        test_end=min(n,validation_end+step)
        model=fit_ridge(data[:train_end])
        candidates=[]
        for multiple in (1,1.25,1.5,2,3):
            threshold=cost*multiple
            valid=assess(model,data[train_end:validation_end],threshold,cost)
            if valid["trades"]>=30:
                candidates.append((valid["avg_net_pct"],threshold,valid))
        if not candidates:
            reports.append({"fold":fold+1,"decision":"NO_TRADE",
                            "reason":"insufficient_validation_trades"})
            continue
        _,threshold,valid=max(candidates,key=lambda item:item[0])
        holdout=assess(model,data[validation_end:test_end],threshold,cost)
        reports.append({"fold":fold+1,"train_samples":train_end,
                        "validation":valid,"test":holdout,
                        "threshold_pct":round(threshold*100,5),
                        "decision":"RESEARCH_ONLY" if valid["avg_net_pct"]>0 and
                        holdout["trades"]>=30 and holdout["avg_net_pct"]>0 else "NO_TRADE"})
    return {"decision":"RESEARCH_ONLY" if reports and all(
                f["decision"]=="RESEARCH_ONLY" for f in reports) else "NO_TRADE",
            "folds":reports,"cost_roundtrip_pct":round(cost*100,4),
            "warning":"Walk-forward results are not live proof. No exchange orders. "
                      "Check calibration, fills, regime changes and out-of-sample decay."}

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("Usage: python research/walk_forward_forecast.py history.csv")
    print(json.dumps(walk_forward(read_csv(sys.argv[1])),indent=2))
