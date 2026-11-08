"""Research-only BTC/EUR spot regime strategy vs passive buy-and-hold.
No SHORT, leverage, order placement, or deployment. Completed 4h bars.
Selection uses validation only; holdout is evaluated once.
"""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.candles import aggregate

def simulate(bars,start,end,fast,slow,buffer,cost):
    # One position maximum; only decide using completed candle at i.
    if fast>=slow or min(fast,slow)<1: raise ValueError("Invalid moving averages")
    if not 0<=cost<1: raise ValueError("Invalid cost")
    if end-start<slow+10: raise ValueError("Insufficient segment")
    cash=1.
    units=0.
    trades=0
    closed=0
    entry_value=None
    net_returns=[]
    for i in range(max(start,slow),end-1):
        f=sum(bars[k][4] for k in range(i-fast+1,i+1))/fast
        s=sum(bars[k][4] for k in range(i-slow+1,i+1))/slow
        # Execute on next bar open; split roundtrip costs conservatively.
        px=bars[i+1][1]
        half=cost/2
        if units==0 and f>s*(1+buffer):
            entry_value=cash
            units=cash*(1-half)/px
            cash=0.
            trades+=1
        elif units>0 and f<s*(1-buffer):
            cash=units*px*(1-half)
            units=0.
            closed+=1
            net_returns.append(cash/entry_value-1)
    # Mark-to-market final equity, including hypothetical liquidation costs.
    equity=cash if units==0 else units*bars[end-1][4]*(1-cost/2)
    passive=(bars[end-1][4]/bars[start][1])*(1-cost)
    return {"net_return_pct":round(100*(equity-1),5),
            "buy_hold_net_pct":round(100*(passive-1),5),
            "excess_vs_buy_hold_pct":round(100*(equity-passive),5),
            "entries":trades,"closed_trades":closed,
            "completed_trade_win_rate_pct":round(100*sum(x>0 for x in net_returns)/closed,2) if closed else None}

def run(rows,fee_per_side=.008,spread_bps=5,slippage_bps=2):
    if min(fee_per_side,spread_bps,slippage_bps)<0: raise ValueError("Negative costs")
    if any((b[0]-a[0]).total_seconds()!=60 for a,b in zip(rows,rows[1:])):
        raise ValueError("Noncontiguous 1m history")
    bars=aggregate(rows,240)
    if len(bars)<1500: raise ValueError("Need >=1500 completed 4h bars")
    a,b=int(.6*len(bars)),int(.8*len(bars))
    cost=2*fee_per_side+(spread_bps+2*slippage_bps)/10000
    candidates={}
    for fast in (12,30,60):
        for slow in (90,150,240):
            for buffer in (0,.005,.015):
                key=f"{fast}_{slow}_{buffer}"
                candidates[key]=simulate(bars,a,b,fast,slow,buffer,cost)
    # Selection requires positive total return and outperformance of passive
    # during validation. No tuning on holdout.
    eligible=[(v["excess_vs_buy_hold_pct"],k) for k,v in candidates.items()
              if v["entries"]>=2 and v["net_return_pct"]>0 and v["excess_vs_buy_hold_pct"]>0]
    selected=max(eligible)[1] if eligible else None
    holdout=None
    if selected:
        fast,slow,buffer=selected.split("_")
        holdout=simulate(bars,b,len(bars),int(fast),int(slow),float(buffer),cost)
    passed=bool(holdout and holdout["net_return_pct"]>0 and
                holdout["excess_vs_buy_hold_pct"]>0 and holdout["entries"]>=2)
    return {"strategy":"spot_long_flat_trend_regime","bars":len(bars),
            "roundtrip_cost_pct":round(100*cost,4),
            "validation_candidates":candidates,"selected_on_validation":selected,
            "untouched_holdout":holdout,
            "decision":"RESEARCH_ONLY" if passed else "NO_TRADE",
            "warning":"12 months insufficient for robust multi-regime confidence. No portfolio drawdown, actual Kraken fills, or deployment authorization."}

if __name__=="__main__":
    rows=read_csv(sys.argv[1])
    print(json.dumps({name:run(rows,fee_per_side=fee) for name,fee in
                      (("taker_taker",.008),("maker_taker_hypothetical",.006),
                       ("maker_maker_hypothetical",.004))},indent=2))
