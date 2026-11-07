"""Compare three simple 5m strategies after costs, on chronological holdout.

Research-only: never sends orders. No parameter tuning on the test segment.
Signals use completed 5m candles; next candle open-to-close return is scored.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.candles import aggregate

def signals(candles, i):
    """Return trend, mean-reversion and breakout sides based on prior closes."""
    history=candles[:i+1]
    if len(history)<25:
        return {"trend":0,"mean_reversion":0,"breakout":0}
    closes=[c[4] for c in history]
    fast=sum(closes[-5:])/5
    slow=sum(closes[-20:])/20
    trend=1 if fast>slow else -1 if fast<slow else 0
    displacement=closes[-1]/slow-1
    reversion=-1 if displacement>.004 else 1 if displacement<-.004 else 0
    prior=history[-21:-1]
    breakout=1 if closes[-1]>max(c[2] for c in prior) else -1 if closes[-1]<min(c[3] for c in prior) else 0
    return {"trend":trend,"mean_reversion":reversion,"breakout":breakout}

def compare(rows, fee_per_side=.008, spread_bps=5, slippage_bps=2):
    if any((b[0]-a[0]).total_seconds()!=60 for a,b in zip(rows,rows[1:])):
        raise ValueError("Noncontiguous input minutes")
    candles=aggregate(rows,5)
    if len(candles)<500:
        raise ValueError("Need at least 500 complete 5m candles")
    cost=2*fee_per_side+(spread_bps+2*slippage_bps)/10000
    split=int(len(candles)*.8)
    result={}
    for name in ("trend","mean_reversion","breakout"):
        returns=[]
        for i in range(max(24,split-1),len(candles)-1):
            side=signals(candles,i)[name]
            if side:
                nxt=candles[i+1]
                returns.append(side*(nxt[4]/nxt[1]-1)-cost)
        result[name]={
            "trades":len(returns),
            "avg_net_return_pct":round(100*sum(returns)/len(returns),4) if returns else None,
            "sum_unit_notional_net_pct":round(100*sum(returns),4),
            "win_rate_pct":round(100*sum(r>0 for r in returns)/len(returns),2) if returns else None,
        }
    eligible=[(v["avg_net_return_pct"],k) for k,v in result.items()
              if v["trades"]>=30 and v["avg_net_return_pct"] is not None and v["avg_net_return_pct"]>0]
    return {"strategies":result,"cost_roundtrip_pct":round(100*cost,4),
            "decision":"RESEARCH_ONLY" if eligible else "NO_TRADE",
            "best_test_strategy_descriptive":max(eligible)[1] if eligible else None,
            "warning":"Test selection is descriptive only; selecting best on test overfits. No deployment without independent forward validation."}

if __name__=="__main__":
    print(json.dumps(compare(read_csv(sys.argv[1])),indent=2))
