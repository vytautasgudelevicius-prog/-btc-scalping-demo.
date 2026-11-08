"""Read-only Kraken BTC/EUR signal observation. No database or orders.

Run once or periodically to record current market context for forward validation.
"""
import json
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bot import api, PAIR, signal, entry_quality, liquidity_and_atr_ok, FEE, SLIP

def observe(fetch=api):
    ohlc=fetch("OHLC",{"pair":PAIR,"interval":1})
    key=next(k for k in ohlc if k!="last")
    candles=ohlc[key][:-1]
    ticker=fetch("Ticker",{"pair":PAIR})
    quote=next(iter(ticker.values()))
    ask,bid=float(quote["a"][0]),float(quote["b"][0])
    if not (math.isfinite(ask) and math.isfinite(bid) and ask>=bid>0):
        raise ValueError("Invalid Kraken bid/ask; no signal")
    if len(candles)<90:
        raise ValueError("Insufficient completed candles; no signal")
    from datetime import datetime, timezone
    now=datetime.now(timezone.utc).timestamp()
    age=now-int(candles[-1][0])
    if not 0<=age<=180:
        raise ValueError("Stale candles; no signal")
    # Closed 5m and 15m bars only; never use the forming candle.
    structure={}
    for interval in (5,15):
        data=fetch("OHLC",{"pair":PAIR,"interval":interval})
        k=next(k for k in data if k!="last")
        bars=data[k][:-1]
        if len(bars)<30 or not 0<=now-int(bars[-1][0])<=2*interval*60+180:
            raise ValueError("Insufficient or stale structure candles")
        highs_tf=[float(b[2]) for b in bars]
        lows_tf=[float(b[3]) for b in bars]
        closes_tf=[float(b[4]) for b in bars]
        e9=e21=closes_tf[0]
        for price in closes_tf:
            e9=price*0.2+e9*0.8
            e21=price*(2/22)+e21*(20/22)
        recent=bars[-20:]
        volumes=[float(b[6]) for b in recent]
        body=abs(float(bars[-1][4])-float(bars[-1][1]))
        candle_range=max(float(bars[-1][2])-float(bars[-1][3]),1e-9)
        # A breakout that closes back inside the previous completed-bar range
        # is a potential liquidity sweep, not a confirmed continuation.
        prior_high=max(highs_tf[-13:-1])
        prior_low=min(lows_tf[-13:-1])
        last_open=float(bars[-1][1])
        last_close=closes_tf[-1]
        false_break_up=(highs_tf[-1]>prior_high and last_close<prior_high
                        and last_close<last_open)
        false_break_down=(lows_tf[-1]<prior_low and last_close>prior_low
                          and last_close>last_open)
        structure[str(interval)]={"close":closes_tf[-1],"ema9":e9,"ema21":e21,
            "false_break_up":false_break_up,"false_break_down":false_break_down,
            "volume_ratio":volumes[-1]/max(sum(volumes[:-1])/len(volumes[:-1]),1e-9),
            "body_ratio":body/candle_range,
            "upper_wick_ratio":(float(bars[-1][2])-max(float(bars[-1][1]),float(bars[-1][4])))/candle_range,
            "lower_wick_ratio":(min(float(bars[-1][1]),float(bars[-1][4]))-float(bars[-1][3]))/candle_range,
            "higher_lows":min(lows_tf[-6:])>min(lows_tf[-12:-6]),
            "lower_highs":max(highs_tf[-6:])<max(highs_tf[-12:-6]),
            "support":min(lows_tf[-12:-1]),"resistance":max(highs_tf[-12:-1]),
            "previous_support":min(lows_tf[-24:-12]),
            "previous_resistance":max(highs_tf[-24:-12])}
    direction=signal(candles)
    spread_pct=(ask-bid)/ask*100
    cost_pct=(2*(FEE+SLIP))*100+spread_pct
    quality=entry_quality(candles,direction)
    liquid=liquidity_and_atr_ok(candles)
    context_ok=spread_pct<=0.15 and quality and liquid
    highs=[float(x[2]) for x in candles[-60:]]
    lows=[float(x[3]) for x in candles[-60:]]
    closes=[float(x[4]) for x in candles]
    hourly_range_pct=(max(highs)/min(lows)-1)*100
    trend_pct=(closes[-1]/closes[-61]-1)*100
    required_range_pct=(2*(FEE+SLIP)+0.002)*100
    rejection_reasons=[]
    if direction=="WAIT": rejection_reasons.append("NO_EMA_CROSS")
    if hourly_range_pct<required_range_pct: rejection_reasons.append("RANGE_BELOW_COST_GATE")
    if direction=="LONG" and trend_pct<0.2: rejection_reasons.append("TREND_NOT_LONG")
    if direction=="SHORT" and trend_pct>-0.2: rejection_reasons.append("TREND_NOT_SHORT")
    if not liquid: rejection_reasons.append("LIQUIDITY_OR_ATR")
    if spread_pct>0.15: rejection_reasons.append("SPREAD")
    return {"timestamp_utc":datetime.now(timezone.utc).isoformat(),
            "last_completed_candle":datetime.fromtimestamp(int(candles[-1][0]),timezone.utc).isoformat(),
            "pair":"BTC/EUR","bid":bid,"ask":ask,
            "spread_pct":round(spread_pct,5),
            "estimated_roundtrip_cost_pct":round(cost_pct,5),
            "hourly_range_pct":round(hourly_range_pct,4),
            "required_range_pct":round(required_range_pct,4),
            "hourly_trend_pct":round(trend_pct,4),
            "structure":structure,
            "rejection_reasons":rejection_reasons,
            "ema_signal":direction,"quality_filter":quality,
            "liquidity_atr_filter":liquid,
            "context_candidate":bool(direction!="WAIT" and context_ok),
            "decision":"OBSERVE_ONLY","orders_enabled":False,
            "note":"No predicted return or realized PnL; do not treat as validated strategy."}

if __name__=="__main__":
    print(json.dumps(observe(),indent=2))
