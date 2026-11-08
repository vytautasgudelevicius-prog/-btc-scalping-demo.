"""Research-only 4h trend/breakout BTC/EUR, 12-48h holds, strict untouched holdout.
No live/DEMO orders. Binance spot proxy cannot validate executable SHORT fills.
"""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.candles import aggregate
from research.multihour_edge import evaluate

def run(rows, fee_per_side=.008, spread_bps=5, slippage_bps=2):
    if min(fee_per_side,spread_bps,slippage_bps)<0:
        raise ValueError("Negative costs")
    if any((b[0]-a[0]).total_seconds()!=60 for a,b in zip(rows,rows[1:])):
        raise ValueError("Noncontiguous 1m history")
    bars=aggregate(rows,240)
    if len(bars)<500:
        raise ValueError("Need at least 500 completed 4h bars")
    cost=2*fee_per_side+(spread_bps+2*slippage_bps)/10000
    cut1,cut2=int(len(bars)*.6),int(len(bars)*.8)
    validation={}
    for mode in ("trend","breakout"):
        for lookback in (12,36,72):
            for horizon in (3,6,12):
                key=f"{mode}_{lookback}_{horizon}"
                validation[key]=evaluate(bars,cut1,cut2,mode,lookback,horizon,cost)
    candidates=[(v["avg_net_pct"],k) for k,v in validation.items()
                if v["trades"]>=10 and v["longs"]>0 and v["shorts"]>0
                and v["avg_net_pct"] is not None and v["avg_net_pct"]>0]
    chosen=max(candidates)[1] if candidates else None
    test=None
    if chosen:
        mode,lookback,horizon=chosen.rsplit("_",2)
        test=evaluate(bars,cut2,len(bars),mode,int(lookback),int(horizon),cost)
    passed=bool(test and test["trades"]>=10 and test["longs"]>0 and
                test["shorts"]>0 and test["avg_net_pct"]>0)
    return {"method":"four_hour_12_to_48_hour_holdout","completed_4h_bars":len(bars),
            "roundtrip_cost_pct":round(cost*100,4),
            "validation":validation,"selected_on_validation":chosen,
            "untouched_test":test,"decision":"RESEARCH_ONLY" if passed else "NO_TRADE",
            "warning":"Not deployment approval. No intrabar stops, short borrowing/funding, maker fill probability, Kraken fills, or portfolio equity."}

if __name__=="__main__":
    print(json.dumps(run(read_csv(sys.argv[1])),indent=2))
