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
            "rejection_reasons":rejection_reasons,
            "ema_signal":direction,"quality_filter":quality,
            "liquidity_atr_filter":liquid,
            "context_candidate":bool(direction!="WAIT" and context_ok),
            "decision":"OBSERVE_ONLY","orders_enabled":False,
            "note":"No predicted return or realized PnL; do not treat as validated strategy."}

if __name__=="__main__":
    print(json.dumps(observe(),indent=2))
