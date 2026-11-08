"""36-month BTC/EUR spot LONG/FLAT Donchian breakout with ATR trailing stop.
No SHORT, leverage, actual orders or deployment. No lookahead: signals use completed bar,
orders execute at following open, intrabar stops at stop or worse gap-open.
"""
import csv,json,math,sys
from datetime import datetime
from pathlib import Path

def load(path):
    with open(path,newline="") as f:
        r=csv.DictReader(f)
        rows=[(datetime.fromisoformat(x["timestamp"]),*(float(x[k]) for k in ("open","high","low","close","volume"))) for x in r]
    if any((b[0]-a[0]).total_seconds()!=14400 for a,b in zip(rows,rows[1:])):
        raise ValueError("4h history has gaps")
    if len(rows)<3500: raise ValueError("Insufficient data")
    return rows

def simulate(rows,start,end,lookback,atr_mult,risk_pct,fee_side=.008,spread_bps=5,slippage_bps=2):
    if min(fee_side,spread_bps,slippage_bps,risk_pct)<0 or risk_pct>1:
        raise ValueError("Invalid cost or risk")
    cash=1.;qty=0.;stop=None;entry_value=None;entries=0;closed=0;wins=0
    peak=1.;max_dd=0.;equity_curve=[]
    friction=(spread_bps/2+slippage_bps)/10000
    # start flat: training bars may be used only to compute indicators
    for i in range(start,end):
        _,o,h,l,c,_=rows[i]
        # Stops already active before current candle: pessimistic gap handling
        if qty>0 and l<=stop:
            sell=min(o,stop)*(1-friction)*(1-fee_side)
            cash+=qty*sell;qty=0.;closed+=1
            wins+=cash>entry_value;stop=None
        # Signal at previous completed close; fill at current open
        if i>start and qty==0 and i>=max(200,lookback+1):
            prev=rows[i-1]
            prior_high=max(x[2] for x in rows[i-lookback-1:i-1])
            trend=sum(x[4] for x in rows[i-201:i-1])/200
            tr=[max(rows[j][2]-rows[j][3],abs(rows[j][2]-rows[j-1][4]),
                    abs(rows[j][3]-rows[j-1][4])) for j in range(i-14,i)]
            atr=sum(tr)/14
            if prev[4]>prior_high and prev[4]>trend and atr>0:
                buy=o*(1+friction)*(1+fee_side)
                # Position fraction bounded by cash and stop distance.
                fraction=min(1.,risk_pct*buy/(atr_mult*atr))
                if fraction>0:
                    entry_value=cash
                    qty=cash*fraction/buy
                    cash*=1-fraction
                    stop=buy-atr_mult*atr
                    entries+=1
        # Stop can trigger on entry candle; pessimistic handling
        if qty>0 and l<=stop:
            sell=min(o,stop)*(1-friction)*(1-fee_side)
            cash+=qty*sell;qty=0.;closed+=1
            wins+=(cash>entry_value);stop=None
        # Update trailing stop after candle completion (effective next bar)
        if qty>0 and i>=15:
            tr=[max(rows[j][2]-rows[j][3],abs(rows[j][2]-rows[j-1][4]),
                    abs(rows[j][3]-rows[j-1][4])) for j in range(i-13,i+1)]
            atr=sum(tr)/14
            stop=max(stop,c-atr_mult*atr)
        equity=cash+qty*c*(1-friction)*(1-fee_side)
        peak=max(peak,equity)
        max_dd=max(max_dd,1-equity/peak)
        equity_curve.append(equity)
    equity=equity_curve[-1]
    passive=(rows[end-1][4]/rows[start][1])*(1-2*fee_side-2*friction)
    return {"net_return_pct":round(100*(equity-1),4),
            "max_drawdown_pct":round(100*max_dd,4),
            "buy_hold_net_pct":round(100*(passive-1),4),
            "buy_hold_max_drawdown_pct":round(100*max(1-rows[j][4]/max(x[4] for x in rows[start:j+1]) for j in range(start,end)),4),
            "entries":entries,"closed":closed,"win_rate_pct":round(100*wins/closed,2) if closed else None}

def run(rows,fee_side=.008):
    a,b=int(.6*len(rows)),int(.8*len(rows))
    validation={}
    for lookback in (20,55,90):
        for atr_mult in (2.5,4.):
            for risk_pct in (.005,.01):
                key=f"{lookback}_{atr_mult}_{risk_pct}"
                validation[key]=simulate(rows,a,b,lookback,atr_mult,risk_pct,fee_side)
    eligible=[(v["net_return_pct"]-v["max_drawdown_pct"]*.5,k)
              for k,v in validation.items() if v["entries"]>=5 and v["net_return_pct"]>0
              and v["max_drawdown_pct"]<=20]
    selected=max(eligible)[1] if eligible else None
    holdout=None
    if selected:
        lb,atr,risk=selected.split("_")
        holdout=simulate(rows,b,len(rows),int(lb),float(atr),float(risk),fee_side)
    passed=bool(holdout and holdout["entries"]>=5 and holdout["net_return_pct"]>0
                and holdout["max_drawdown_pct"]<=20)
    return {"bars":len(rows),"fee_side_pct":fee_side*100,
            "selected_validation":selected,"holdout":holdout,
            "validation":validation,"decision":"RESEARCH_ONLY" if passed else "NO_TRADE",
            "warning":"Proxy data, no exchange fill/latency validation; stop execution is approximated; no deployment."}

if __name__=="__main__":
    rows=load(sys.argv[1])
    print(json.dumps({name:run(rows,fee) for name,fee in
          (("taker_taker",.008),("maker_hypothetical",.004))},indent=2))
