"""Offline BTC/EUR strategy research. No orders, no network, no production DB writes.

CSV columns: timestamp,open,high,low,close,volume
Timestamp: UTC ISO-8601 or Unix seconds. Candles must be consecutive 1-minute bars.
Usage: python backtest.py history.csv
Results are indicative, not a guarantee; historical fills are approximated.
"""
import csv
import datetime as dt
import json
import sys

FEE = 0.008
SLIP = 0.0002
START = 1000.0
RISK_FRACTION = 0.005
MAX_NOTIONAL = 0.10
STOP = 0.012
TAKE = 0.03
HOLD_BARS = 45
COOLDOWN = 15

def ema(values, n):
    out = []
    value = values[0]
    alpha = 2 / (n + 1)
    for v in values:
        value = alpha * v + (1 - alpha) * value
        out.append(value)
    return out

def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if len(rows) < 250:
        raise ValueError("Need at least 250 1-minute bars")
    data = []
    for row in rows:
        t = row["timestamp"]
        when = dt.datetime.fromtimestamp(float(t), dt.timezone.utc) if t.replace(".", "", 1).isdigit() else dt.datetime.fromisoformat(t.replace("Z", "+00:00"))
        if when.tzinfo is None:
            raise ValueError("Timestamps must include UTC timezone")
        data.append((when, *(float(row[k]) for k in ("open","high","low","close","volume"))))
    for a,b in zip(data,data[1:]):
        if (b[0]-a[0]).total_seconds()!=60:
            raise ValueError("Missing, duplicate, or non-1m bars; no forward-filling")
        if min(a[1:5])<=0 or a[5]<0:
            raise ValueError("Invalid price or volume")
    return data

def evaluate(rows, spread_bps=5):
    closes=[r[4] for r in rows]
    fast,slow=ema(closes,9),ema(closes,21)
    cash=START
    open_pos=None
    last_entry=-COOLDOWN
    trades=[]
    equity_curve=[START]
    # Signals use completed candle i; next-bar open is the earliest possible fill.
    for i in range(220,len(rows)-1):
        _,_,high,low,close,vol=rows[i]
        next_open=rows[i+1][1]
        if open_pos is not None:
            side,entry,qty,fee_in,opened=open_pos
            # Conservative same-bar stop-first when both targets are touched.
            exit_mid=None
            if side==1:
                if low<=entry*(1-STOP): exit_mid=entry*(1-STOP)
                elif high>=entry*(1+TAKE): exit_mid=entry*(1+TAKE)
            else:
                if high>=entry*(1+STOP): exit_mid=entry*(1+STOP)
                elif low<=entry*(1-TAKE): exit_mid=entry*(1-TAKE)
            if exit_mid is None and i-opened>=HOLD_BARS:
                exit_mid=next_open
            if exit_mid is not None:
                execution=exit_mid*(1-side*(spread_bps/20000+SLIP))
                gross=side*(execution-entry)*qty
                fee_out=qty*execution*FEE
                pnl=gross-fee_in-fee_out
                cash+=pnl
                trades.append({"bar":i,"side":"LONG" if side==1 else "SHORT","net_pnl":round(pnl,6)})
                open_pos=None
        if open_pos is None and i-last_entry>=COOLDOWN:
            side=1 if fast[i-1]<=slow[i-1] and fast[i]>slow[i] else (-1 if fast[i-1]>=slow[i-1] and fast[i]<slow[i] else 0)
            if side:
                # Approximate regime/quality gates, not identical to production 4h API gate.
                trend=closes[i]/closes[i-60]-1
                segment=rows[i-59:i+1]
                range_pct=max(r[2] for r in segment)/min(r[3] for r in segment)-1
                avg_vol=sum(r[5] for r in segment[-31:-1])/30
                trs=[max(segment[j][2]-segment[j][3],abs(segment[j][2]-segment[j-1][4]),abs(segment[j][3]-segment[j-1][4])) for j in range(1,60)]
                atr=sum(trs[-14:])/14/closes[i]
                if ((side==1 and trend>=.004) or (side==-1 and trend<=-.004)) and range_pct>=2*(FEE+SLIP)+.005 and .0002<=atr<=.015 and avg_vol>0 and vol>=.5*avg_vol:
                    entry=next_open*(1+side*(spread_bps/20000+SLIP))
                    notional=min(cash*MAX_NOTIONAL,cash*RISK_FRACTION/(STOP+2*FEE+2*SLIP+spread_bps/10000))
                    qty=notional/entry
                    fee_in=notional*FEE
                    open_pos=(side,entry,qty,fee_in,i+1)
                    last_entry=i+1
        # Equity marked to hypothetical close, including exit fee.
        if open_pos:
            side,entry,qty,fee_in,opened=open_pos
            exit_price=close*(1-side*(spread_bps/20000+SLIP))
            marked=cash+side*(exit_price-entry)*qty-fee_in-qty*exit_price*FEE
        else:
            marked=cash
        equity_curve.append(marked)
    peak=START
    drawdown=0
    for value in equity_curve:
        peak=max(peak,value)
        drawdown=max(drawdown,(peak-value)/peak)
    wins=[t["net_pnl"] for t in trades if t["net_pnl"]>0]
    losses=[t["net_pnl"] for t in trades if t["net_pnl"]<0]
    profit_factor=sum(wins)/-sum(losses) if losses else (None if not wins else "inf")
    return {"bars":len(rows),"trades":len(trades),"ending_cash":round(cash,2),
            "realized_net_pnl":round(cash-START,2),
            "win_rate_pct":round(100*len(wins)/len(trades),2) if trades else None,
            "avg_win_eur":round(sum(wins)/len(wins),4) if wins else None,
            "avg_loss_eur":round(sum(losses)/len(losses),4) if losses else None,
            "profit_factor":profit_factor,"max_drawdown_pct":round(drawdown*100,2)}

def main():
    if len(sys.argv)!=2:
        raise SystemExit("Usage: python backtest.py historical_1m.csv")
    data=read_csv(sys.argv[1])
    split=int(len(data)*.7)
    # Warm-up for indicators on holdout without leaking holdout into training.
    print(json.dumps({"in_sample":evaluate(data[:split]),
                      "out_of_sample":evaluate(data[max(0,split-220):]),
                      "caveat":"Simplified 1m proxy; production 4h regime gate not reproduced. Do not use as production validation."},indent=2))
if __name__=="__main__":
    main()
