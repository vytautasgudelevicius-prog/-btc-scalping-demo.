"""Walk-forward evaluation of cost-aware strong BTC signals (research only).

Each fold has disjoint validation/test windows. Thresholds are selected only
on the fold's validation data, never on its test labels.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.train_direction import examples
from research.evaluate_cost_edge import labeled_returns
from research.forecast_expected_value import fit_ridge
from research.strong_signal_backtest import score

def run(rows,fee_per_side=.008,spread_bps=5,slippage_bps=2,folds=3):
    if min(fee_per_side,spread_bps,slippage_bps)<0 or folds<1:
        raise ValueError("Invalid trading costs or folds")
    xs=examples(rows);rets=labeled_returns(rows)
    if len(xs)!=len(rets) or len(xs)<900:
        raise ValueError("Need at least 900 aligned labeled 5m candles")
    data=[(x,ret) for (x,_),(_,ret) in zip(xs,rets)]
    n=len(data);start=n//2;step=(n-start)//(2*folds)
    if step<30:
        raise ValueError("Not enough history for disjoint folds")
    cost=2*fee_per_side+(spread_bps+2*slippage_bps)/10000
    reports=[]
    for fold in range(folds):
        train_end=start+2*fold*step
        validation_end=train_end+step
        test_end=min(n,validation_end+step)
        model=fit_ridge(data[:train_end])
        choices=[]
        for multiple in (1,1.25,1.5,2,3):
            for vol in (0.,.25,.5):
                threshold=cost*multiple
                valid=score(model,data[train_end:validation_end],threshold,cost,vol)
                if valid["trades"]>=30:
                    choices.append((valid["avg_net_pct"],valid["trades"],threshold,vol,valid))
        if not choices:
            reports.append({"fold":fold+1,"decision":"NO_TRADE",
                            "reason":"insufficient_validation_trades",
                            "validation_range":[train_end,validation_end],
                            "test_range":[validation_end,test_end]})
            continue
        _,_,threshold,vol,valid=max(choices,key=lambda c:(c[0],c[1]))
        test=score(model,data[validation_end:test_end],threshold,cost,vol)
        passed=valid["avg_net_pct"]>0 and test["trades"]>=30 and test["avg_net_pct"] is not None and test["avg_net_pct"]>0
        reports.append({"fold":fold+1,"decision":"RESEARCH_ONLY" if passed else "NO_TRADE",
                        "validation_range":[train_end,validation_end],
                        "test_range":[validation_end,test_end],
                        "threshold_pct":round(100*threshold,5),
                        "min_relative_volume":1+vol,"validation":valid,"test":test})
    return {"decision":"RESEARCH_ONLY" if all(f["decision"]=="RESEARCH_ONLY" for f in reports) else "NO_TRADE",
            "cost_roundtrip_pct":round(100*cost,4),"folds":reports,
            "warning":"Research only; no automatic promotion to Railway or exchange execution."}

if __name__=="__main__":
    print(json.dumps(run(read_csv(sys.argv[1])),indent=2))
