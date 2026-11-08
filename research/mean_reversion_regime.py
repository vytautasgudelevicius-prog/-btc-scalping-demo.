"""BTC/EUR spot LONG-only volatility-filtered mean reversion research.
Completed 4h bars; enter at next open, fixed horizon exit. Research only.
"""
import json,sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.candles import aggregate

def simulate(bars,start,end,window,z_entry,horizon,fee):
    i=max(start,window+1)
    returns=[]
    while i+horizon<end:
        closes=[b[4] for b in bars[i-window:i]]
        mu=sum(closes)/window
        variance=sum((x-mu)**2 for x in closes)/window
        sigma=math.sqrt(variance)
        z=(bars[i][4]-mu)/sigma if sigma>0 else 0
        # avoid buying downtrends: only long if 30-day regime remains upward
        regime=bars[i][4]>bars[i-180][4] if i>=180 else False
        if z<=-z_entry and regime:
            entry=bars[i+1][1]
            if entry<=0: raise ValueError("Invalid price")
            returns.append(bars[i+horizon][4]/entry-1-fee)
            i+=horizon+1
        else:
            i+=1
    n=len(returns)
    return {"trades":n,"avg_net_pct":round(100*sum(returns)/n,5) if n else None,
            "win_rate_pct":round(100*sum(x>0 for x in returns)/n,2) if n else None}

def run(rows,fee_per_side=.008,spread_bps=5,slippage_bps=2):
    if min(fee_per_side,spread_bps,slippage_bps)<0: raise ValueError("Negative costs")
    if any((b[0]-a[0]).total_seconds()!=60 for a,b in zip(rows,rows[1:])):
        raise ValueError("Noncontiguous history")
    bars=aggregate(rows,240)
    if len(bars)<1500: raise ValueError("Insufficient 4h bars")
    a,b=int(.6*len(bars)),int(.8*len(bars))
    cost=2*fee_per_side+(spread_bps+2*slippage_bps)/10000
    validation={}
    for window in (18,42,84):
        for z in (1.,1.5,2.):
            for horizon in (6,12,24):
                key=f"{window}_{z}_{horizon}"
                validation[key]=simulate(bars,a,b,window,z,horizon,cost)
    eligible=[(v["avg_net_pct"],k) for k,v in validation.items()
              if v["trades"]>=8 and v["avg_net_pct"] is not None and v["avg_net_pct"]>0]
    selected=max(eligible)[1] if eligible else None
    holdout=None
    if selected:
        w,z,h=selected.split("_")
        holdout=simulate(bars,b,len(bars),int(w),float(z),int(h),cost)
    passed=bool(holdout and holdout["trades"]>=8 and holdout["avg_net_pct"] is not None and holdout["avg_net_pct"]>0)
    return {"strategy":"long_only_4h_mean_reversion_uptrend_regime",
            "bars":len(bars),"cost_pct":round(100*cost,4),
            "selected_on_validation":selected,"untouched_holdout":holdout,
            "decision":"RESEARCH_ONLY" if passed else "NO_TRADE",
            "warning":"No portfolio risk, stop execution, Kraken fills, or automatic promotion."}

if __name__=="__main__":
    rows=read_csv(sys.argv[1])
    print(json.dumps({name:run(rows,fee_per_side=fee) for name,fee in
                      (("taker_taker",.008),("maker_taker_hypothetical",.006),
                       ("maker_maker_hypothetical",.004))},indent=2))
