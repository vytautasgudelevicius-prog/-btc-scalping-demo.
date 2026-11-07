"""Cost-aware 5-minute directional research, not an executable strategy.

Signals use only completed candles. Entry at next 5m open and exit at
that candle's close; round-trip fees, spread and slippage are deducted.
Thresholds are selected on validation only; test remains untouched.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.train_direction import examples, fit, predict

def labeled_returns(rows):
    records=[]
    for i in range(239,len(rows)-5,5):
        if int(rows[i][0].timestamp())//60%5!=4:
            continue
        opening,closing=rows[i+1][1],rows[i+5][4]
        if opening<=0 or closing==opening:
            continue
        records.append((i,(closing/opening)-1))
    return records

def simulate(model, samples, returns, threshold, fee_per_side=.008,
             spread_bps=5, slippage_bps=2):
    if len(samples)!=len(returns):
        raise ValueError("Label and return alignment mismatch")
    cost=2*fee_per_side+(spread_bps+2*slippage_bps)/10000
    trades=[]
    for (x,y),(_,ret) in zip(samples,returns):
        p=predict(model,x)
        side=1 if p>=threshold else (-1 if p<=1-threshold else 0)
        if not side:
            continue
        trades.append(side*ret-cost)
    return {
        "trades":len(trades),
        "total_net_return_pct":round(100*sum(trades),4),
        "avg_net_return_pct":round(100*sum(trades)/len(trades),4) if trades else None,
        "win_rate_pct":round(100*sum(r>0 for r in trades)/len(trades),2) if trades else None,
        "cost_roundtrip_pct":round(cost*100,4),
        "note":"Sum of independent unit-notional returns; not compounded portfolio P&L."
    }

def evaluate(rows):
    samples=examples(rows)
    returns=labeled_returns(rows)
    if len(samples)!=len(returns) or len(samples)<500:
        raise ValueError("Insufficient or mismatched 5m labels")
    a,b=int(len(samples)*.6),int(len(samples)*.8)
    model=fit(samples[:a])
    candidates=[]
    for threshold in (.5,.55,.6,.65,.7,.75,.8,.85,.9):
        result=simulate(model,samples[a:b],returns[a:b],threshold)
        if result["trades"]>=30:
            candidates.append((result["avg_net_return_pct"],threshold))
    if not candidates:
        return {"decision":"NO_TRADE","reason":"insufficient_validation_signals"}
    best_net, selected = max(candidates)
    valid=simulate(model,samples[a:b],returns[a:b],selected)
    test=simulate(model,samples[b:],returns[b:],selected)
    if best_net is None or best_net <= 0:
        decision, reason = "NO_TRADE", "no_positive_validation_edge_after_costs"
    elif test["trades"] < 30:
        decision, reason = "NO_TRADE", "insufficient_test_trades"
    elif test["avg_net_return_pct"] is None or test["avg_net_return_pct"] <= 0:
        decision, reason = "NO_TRADE", "no_positive_test_edge_after_costs"
    else:
        decision, reason = "RESEARCH_ONLY", "positive_historical_edge_requires_robustness_testing"
    return {"selected_threshold":selected,"validation":valid,"test":test,
            "decision":decision,"reason":reason,
            "warning":"No deployment: needs multi-period robustness, realistic fills, and production parity."}

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("Usage: python research/evaluate_cost_edge.py BTC.csv")
    print(json.dumps(evaluate(read_csv(sys.argv[1])),indent=2))
