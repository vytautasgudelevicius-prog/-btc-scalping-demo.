"""Conservative BTC/EUR 1-minute OHLC paper fills, no exchange orders.

Signal at completed minute t, entry at next minute OPEN (not t close).
Stops take priority if stop and target are both touched in one candle.
Uses synthetic 0.05% spread, adverse slippage, and taker fees each side.
All candles and signals are historical; no future information in entries.
"""
import argparse,json
from datetime import datetime
from research import isolated_paper_experiment as p

def run(path,fee=.0005,slip=.0002,stop_pct=.0025,rr=1.5,max_hold=120):
    reports=[json.loads(s) for s in open(path,encoding="utf-8") if s.strip()]
    if not reports or any("minute_ohlc" not in x for x in reports):
        raise ValueError("Historical completed minute OHLC required")
    trades=[]; rejects={}; pending=None; active=None; equity=1000.; day=None; day_equity=1000.; peak=equity; max_dd=0.
    def reject(k): rejects[k]=rejects.get(k,0)+1
    def close(position,raw,stamp,reason):
        nonlocal equity,active,peak,max_dd
        d=position["direction"]
        exit_px=raw*(1-slip)*(1-.00025) if d=="LONG" else raw*(1+slip)*(1+.00025)
        pnl=(exit_px-position["entry"])*position["qty"] if d=="LONG" else (position["entry"]-exit_px)*position["qty"]
        pnl-=(exit_px+position["entry"])*position["qty"]*fee
        equity+=pnl
        trades.append({"entry_time":position["time"],"exit_time":stamp,"direction":d,"pnl_eur":round(pnl,5),"exit_reason":reason})
        peak=max(peak,equity);max_dd=max(max_dd,(peak-equity)/peak*100)
        active=None
    for i,r in enumerate(reports):
        stamp=r["timestamp_utc"];dte=datetime.fromisoformat(stamp).date()
        if dte!=day:day=dte;day_equity=equity
        candle=r["minute_ohlc"]
        if active:
            active["bars"]+=1
            if active["direction"]=="LONG":
                stop_hit=candle["low"]<=active["stop"]
                target_hit=candle["high"]>=active["target"]
            else:
                stop_hit=candle["high"]>=active["stop"]
                target_hit=candle["low"]<=active["target"]
            if stop_hit:
                # Gap through a stop must fill at the worse opening quote, not at the stop.
                adverse_open=min(active["stop"],candle["open"]) if active["direction"]=="LONG" else max(active["stop"],candle["open"])
                close(active,adverse_open,stamp,"STOP_GAP" if adverse_open!=active["stop"] else "STOP_FIRST")
            elif target_hit:close(active,active["target"],stamp,"TARGET")
            elif active["bars"]>=max_hold:close(active,candle["close"],stamp,"TIMEOUT")
        # Do not open and exit using the same OHLC bar: next-bar open is used.
        if pending and not active:
            signal=pending;pending=None
            if equity<=day_equity*.98:reject("daily_loss_halt");continue
            direction=signal["direction"];op=candle["open"]
            entry=op*(1+slip)*(1+.00025) if direction=="LONG" else op*(1-slip)*(1-.00025)
            structural=signal["structural"]
            stop=min(entry*(1-stop_pct),structural) if direction=="LONG" else max(entry*(1+stop_pct),structural)
            target=signal["target"]
            stop_fill=stop*(1-slip)*(1-.00025) if direction=="LONG" else stop*(1+slip)*(1+.00025)
            target_fill=target*(1-slip)*(1-.00025) if direction=="LONG" else target*(1+slip)*(1+.00025)
            risk=abs(entry-stop_fill)+(entry+stop_fill)*fee
            reward=(target_fill-entry if direction=="LONG" else entry-target_fill)-(entry+target_fill)*fee
            if reward<rr*risk or abs(entry-stop)/entry>.03 or risk<=0:reject("next_open_net_rr");continue
            # Do not claim a next-open entry when the same minute already opened
            # beyond the precomputed profit target (stale signal).
            if (direction=="LONG" and op>=target) or (direction=="SHORT" and op<=target):
                reject("stale_target_at_open");continue
            qty=min(equity*.005/risk,equity/entry)
            if qty<=0:reject("zero_quantity");continue
            active={"direction":direction,"entry":entry,"stop":stop,"target":target,"qty":qty,"time":stamp,"bars":0}
            continue
        if active or pending or i>=len(reports)-1:continue
        m5,m15=r["structure"]["5"],r["structure"]["15"]
        long_ok=m5["ema9"]>m5["ema21"] and m15["ema9"]>m15["ema21"] and m5["close"]>m5["support"] and m15["close"]>m15["support"]
        short_ok=m5["ema9"]<m5["ema21"] and m15["ema9"]<m15["ema21"] and m5["close"]<m5["resistance"] and m15["close"]<m15["resistance"]
        direction="LONG" if long_ok else "SHORT" if short_ok else None
        if not direction:continue
        struct=m5.get("higher_lows",False) if direction=="LONG" else m5.get("lower_highs",False)
        wick=m5.get("upper_wick_ratio",0)>.6 if direction=="LONG" else m5.get("lower_wick_ratio",0)>.6
        false=(m5.get("false_break_up",False) or m15.get("false_break_up",False)) if direction=="LONG" else (m5.get("false_break_down",False) or m15.get("false_break_down",False))
        if not (struct and not wick and not false and m5.get("volume_ratio",0)>=.8 and r["spread_pct"]<=p.MAX_SPREAD_PCT and r["hourly_range_pct"]>=1.25*(200*(fee+slip)+r["spread_pct"])):continue
        pending={"direction":direction,"structural":m5["support"]*(1-.001) if direction=="LONG" else m5["resistance"]*(1+.001),"target":m15["resistance"] if direction=="LONG" else m15["support"]}
    if active:close(active,reports[-1]["minute_ohlc"]["close"],reports[-1]["timestamp_utc"],"END_OF_DATA")
    gains=sum(t["pnl_eur"] for t in trades if t["pnl_eur"]>0)
    losses=sum(t["pnl_eur"] for t in trades if t["pnl_eur"]<0)
    return {"first":reports[0]["timestamp_utc"],"last":reports[-1]["timestamp_utc"],"observations":len(reports),"fee_one_way":fee,"slippage_one_way":slip,"minimum_stop_pct":stop_pct*100,"required_net_rr":rr,"closed_trades":len(trades),"wins":sum(t["pnl_eur"]>0 for t in trades),"net_pnl_eur":round(sum(t["pnl_eur"] for t in trades),4),"equity_eur":round(equity,4),"max_realized_drawdown_pct":round(max_dd,3),"profit_factor":round(gains/abs(losses),3) if losses else None,"rejected":rejects,"trades":trades,"limitations":"Only ~10h rolling Kraken OHLC; synthetic spread, no intrabar sequencing; stop-first conservative, no guarantee of fills or future returns."}

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("snapshots")
    a.add_argument("--fee",type=float,default=.0005)
    a.add_argument("--rr",type=float,default=1.5)
    a.add_argument("--stop",type=float,default=.0025)
    x=a.parse_args()
    print(json.dumps(run(x.snapshots,x.fee,stop_pct=x.stop,rr=x.rr),indent=2))
