"""Multi-strategy research arena: train/validation/test and failure attribution.

This is research only. Models are selected on validation, never test.
Independent 5m next-candle unit-notional returns, not portfolio equity.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.candles import aggregate
from research.compare_strategies import signals

def signal(candles,i,name):
    close=candles[i][4]
    if name in ("trend","mean_reversion","breakout"):
        return signals(candles,i)[name]
    history=candles[:i+1]
    if len(history)<30:return 0
    closes=[c[4] for c in history]
    if name=="momentum":
        return 1 if close>closes[-7]*1.002 else -1 if close<closes[-7]*.998 else 0
    if name=="rsi_reversion":
        diffs=[closes[j]-closes[j-1] for j in range(len(closes)-14,len(closes))]
        gains=sum(max(0,d) for d in diffs)
        losses=sum(max(0,-d) for d in diffs)
        rsi=100*gains/(gains+losses) if gains+losses else 50
        return 1 if rsi<30 else -1 if rsi>70 else 0
    if name=="volatility_breakout":
        previous=history[-21:-1]
        span=max(c[2] for c in previous)-min(c[3] for c in previous)
        if span<=0:return 0
        return 1 if close>max(c[2] for c in previous)+span*.05 else -1 if close<min(c[3] for c in previous)-span*.05 else 0
    raise ValueError("unknown strategy")

STRATEGIES=("trend","mean_reversion","breakout","momentum","rsi_reversion","volatility_breakout")

def evaluate(candles,lo,hi,name,cost):
    trades=[]
    for i in range(max(29,lo),min(hi,len(candles)-1)):
        side=signal(candles,i,name)
        if not side:continue
        nxt=candles[i+1]
        gross=side*(nxt[4]/nxt[1]-1)
        trades.append((gross,gross-cost))
    n=len(trades)
    return {"trades":n,
            "gross_avg_pct":round(100*sum(g for g,_ in trades)/n,5) if n else None,
            "net_avg_pct":round(100*sum(v for _,v in trades)/n,5) if n else None,
            "net_wins":sum(v>0 for _,v in trades),
            "fee_driven_losses":sum(g>0 and v<=0 for g,v in trades),
            "wrong_direction_or_flat":sum(g<=0 for g,_ in trades),
            "total_unit_notional_net_pct":round(100*sum(v for _,v in trades),4)}

def run(rows,fee_per_side=.008,spread_bps=5,slippage_bps=2,min_validation_trades=30):
    if any((b[0]-a[0]).total_seconds()!=60 for a,b in zip(rows,rows[1:])):
        raise ValueError("Noncontiguous minute history")
    candles=aggregate(rows,5)
    if len(candles)<500:raise ValueError("Insufficient 5m history")
    cost=2*fee_per_side+(spread_bps+2*slippage_bps)/10000
    a,b=int(len(candles)*.6),int(len(candles)*.8)
    validation={name:evaluate(candles,a,b,name,cost) for name in STRATEGIES}
    eligible=[(v["net_avg_pct"],name) for name,v in validation.items()
              if v["trades"]>=min_validation_trades and v["net_avg_pct"] is not None]
    selected=max(eligible)[1] if eligible else None
    test={name:evaluate(candles,b,len(candles)-1,name,cost) for name in STRATEGIES}
    chosen=test.get(selected) if selected else None
    return {"method":"multi_strategy_validation_selected_holdout",
            "strategies":list(STRATEGIES),"cost_roundtrip_pct":round(cost*100,4),
            "validation":validation,"selected_on_validation":selected,
            "test":test,"selected_test":chosen,
            "decision":"RESEARCH_ONLY" if chosen and chosen["trades"]>=30 and chosen["net_avg_pct"]>0 else "NO_TRADE",
            "failure_diagnosis":"Compare wrong_direction_or_flat vs fee_driven_losses; do not optimize on holdout.",
            "warning":"No deployment. Requires walk-forward, exchange-specific fees, fills, and paper forward testing."}

if __name__=="__main__":
    print(json.dumps(run(read_csv(sys.argv[1])),indent=2))
