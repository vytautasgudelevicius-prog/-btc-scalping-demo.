"""Automated parameter search with chronological validation and untouched holdout.

Research-only. Select candidates on validation; do not optimize on test.
All signals are computed on completed candles and traded next open-to-close.
"""
import json
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.candles import aggregate

CONFIGS = (
    ("trend", 5, 20, 0.0), ("trend", 10, 40, 0.0),
    ("trend", 5, 30, .001), ("trend", 10, 50, .002),
    ("momentum", 6, 0, .002), ("momentum", 12, 0, .004),
    ("momentum", 24, 0, .006), ("momentum", 36, 0, .01),
    ("reversion", 10, 0, .003), ("reversion", 20, 0, .005),
    ("reversion", 30, 0, .008), ("reversion", 40, 0, .012),
    ("breakout", 10, 0, 0.0), ("breakout", 20, 0, 0.0),
    ("breakout", 30, 0, .001), ("breakout", 40, 0, .002),
)

def candidates(candles):
    closes=[c[4] for c in candles]
    prefix=[0.]
    for price in closes:
        prefix.append(prefix[-1]+price)
    highs=[c[2] for c in candles]
    lows=[c[3] for c in candles]
    for kind, fast, slow, threshold in CONFIGS:
        sides=[0]*len(candles)
        for i in range(max(60,fast,slow),len(candles)-1):
            close=closes[i]
            if kind=="trend":
                f=(prefix[i+1]-prefix[i+1-fast])/fast
                s=(prefix[i+1]-prefix[i+1-slow])/slow
                strength=f/s-1 if s else 0
                sides[i]=1 if strength>threshold else -1 if strength< -threshold else 0
            elif kind=="momentum":
                change=close/closes[i-fast]-1 if closes[i-fast] else 0
                sides[i]=1 if change>threshold else -1 if change< -threshold else 0
            elif kind=="reversion":
                avg=(prefix[i+1]-prefix[i+1-fast])/fast
                deviation=close/avg-1 if avg else 0
                sides[i]=-1 if deviation>threshold else 1 if deviation< -threshold else 0
            else:
                upper=max(highs[i-fast:i])
                lower=min(lows[i-fast:i])
                sides[i]=1 if close>upper*(1+threshold) else -1 if close<lower*(1-threshold) else 0
        yield (kind,fast,slow,threshold),sides

def score(candles,sides,lo,hi,cost,allocation=.1):
    equity=1000.
    peak=equity
    max_drawdown=0.
    trades=wins=0
    gross_total=cost_total=0.
    for i in range(max(60,lo),min(hi,len(candles)-1)):
        side=sides[i]
        if not side:
            continue
        nxt=candles[i+1]
        gross=side*(nxt[4]/nxt[1]-1)
        net=gross-cost
        gross_total+=gross
        cost_total+=cost
        equity*=max(0,1+allocation*net)
        peak=max(peak,equity)
        max_drawdown=max(max_drawdown,1-equity/peak)
        trades+=1
        wins+=net>0
    return {"trades":trades,"wins":wins,
            "ending_equity_eur":round(equity,2),
            "capital_growth_pct":round((equity/1000-1)*100,4),
            "max_drawdown_pct":round(max_drawdown*100,4),
            "avg_gross_pct":round(gross_total/trades*100,5) if trades else None,
            "avg_cost_pct":round(cost_total/trades*100,5) if trades else None,
            "avg_net_pct":round((gross_total-cost_total)/trades*100,5) if trades else None}

def optimize(rows,fee_per_side=.008,spread_bps=5,slippage_bps=2,min_trades=30):
    if any((b[0]-a[0]).total_seconds()!=60 for a,b in zip(rows,rows[1:])):
        raise ValueError("Minute history must be contiguous")
    candles=aggregate(rows,5)
    if len(candles)<500:
        raise ValueError("Insufficient history")
    if min(fee_per_side,spread_bps,slippage_bps)<0:
        raise ValueError("Costs must not be negative")
    cost=2*fee_per_side+(spread_bps+2*slippage_bps)/10000
    a,b=int(len(candles)*.6),int(len(candles)*.8)
    evaluated=[]
    for params,sides in candidates(candles):
        validation=score(candles,sides,a,b,cost)
        evaluated.append((params,validation,sides))
    eligible=[item for item in evaluated if item[1]["trades"]>=min_trades]
    # Selection uses validation only; test is evaluated once for the winner.
    winner=max(eligible,key=lambda item:(item[1]["capital_growth_pct"],-item[1]["max_drawdown_pct"])) if eligible else None
    if winner:
        params,validation,sides=winner
        holdout=score(candles,sides,b,len(candles)-1,cost)
        positive=validation["capital_growth_pct"]>0 and holdout["capital_growth_pct"]>0 and holdout["trades"]>=min_trades
    else:
        params=validation=holdout=None
        positive=False
    return {"candidate_count":len(evaluated),"cost_roundtrip_pct":round(cost*100,4),
            "selection":"validation_capital_growth_only","parameters":dict(zip(("family","fast","slow","threshold"),params)) if params else None,
            "validation":validation,"untouched_test":holdout,
            "validation_leaderboard":[{"parameters":dict(zip(("family","fast","slow","threshold"),p)),
                                       "validation":v} for p,v,_ in sorted(evaluated,key=lambda item:item[1]["capital_growth_pct"],reverse=True)[:5]],
            "decision":"RESEARCH_ONLY" if positive else "NO_TRADE",
            "warning":"Research simulation, not a live fill model. Positive holdout still needs independent walk-forward and paper forward validation."}

if __name__=="__main__":
    print(json.dumps(optimize(read_csv(sys.argv[1])),indent=2))
