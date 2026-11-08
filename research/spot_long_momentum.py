"""BTC/EUR spot LONG-only regime research; no leverage, SHORT or orders.
12 months, 4h completed candles, next-open entry, fixed exit, disjoint validation/holdout.
"""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.candles import aggregate

def simulate(bars,start,end,lookback,horizon,threshold,cost):
    i=max(start,lookback+1)
    values=[]
    while i+horizon<end:
        # At decision time only completed bar i and older are visible.
        momentum=bars[i][4]/bars[i-lookback][4]-1
        # LONG only when momentum and slow trend are both positive.
        slow=bars[i][4]/bars[i-2*lookback][4]-1 if i>=2*lookback else 0
        if momentum>threshold and slow>0:
            entry=bars[i+1][1]
            exit_price=bars[i+horizon][4]
            values.append(exit_price/entry-1-cost)
            i+=horizon+1
        else:
            i+=1
    n=len(values)
    return {"trades":n,"avg_net_pct":round(100*sum(values)/n,5) if n else None,
            "win_rate_pct":round(100*sum(x>0 for x in values)/n,2) if n else None,
            "sum_unit_notional_pct":round(100*sum(values),4)}

def run(rows,fee_per_side=.008,spread_bps=5,slippage_bps=2):
    if min(fee_per_side,spread_bps,slippage_bps)<0:
        raise ValueError("Negative costs")
    if any((b[0]-a[0]).total_seconds()!=60 for a,b in zip(rows,rows[1:])):
        raise ValueError("Noncontiguous history")
    bars=aggregate(rows,240)
    if len(bars)<1500:
        raise ValueError("Need 1500+ complete 4h bars")
    a,b=int(.6*len(bars)),int(.8*len(bars))
    cost=2*fee_per_side+(spread_bps+2*slippage_bps)/10000
    results={}
    for lookback in (18,42,84):
        for horizon in (6,12,24,42):
            for threshold in (.01,.03,.05):
                key=f"{lookback}_{horizon}_{threshold}"
                results[key]=simulate(bars,a,b,lookback,horizon,threshold,cost)
    viable=[(v["avg_net_pct"],k) for k,v in results.items()
            if v["trades"]>=8 and v["avg_net_pct"] is not None and v["avg_net_pct"]>0]
    chosen=max(viable)[1] if viable else None
    test=None
    if chosen:
        lookback,horizon,threshold=chosen.split("_")
        test=simulate(bars,b,len(bars),int(lookback),int(horizon),float(threshold),cost)
    passed=bool(test and test["trades"]>=8 and test["avg_net_pct"] is not None and test["avg_net_pct"]>0)
    return {"strategy":"spot_long_only_multiday_momentum","bars":len(bars),
            "roundtrip_cost_pct":round(100*cost,4),
            "validation":results,"selected_on_validation":chosen,"untouched_test":test,
            "decision":"RESEARCH_ONLY" if passed else "NO_TRADE",
            "warning":"Research only. No intrabar stop, equity sizing, maker fill probability, Kraken execution verification, or deployment permission."}

if __name__=="__main__":
    rows=read_csv(sys.argv[1])
    print(json.dumps({name:run(rows,fee_per_side=fee) for name,fee in
                      (("taker_taker",.008),("maker_taker_hypothetical",.006),
                       ("maker_maker_hypothetical",.004))},indent=2))
