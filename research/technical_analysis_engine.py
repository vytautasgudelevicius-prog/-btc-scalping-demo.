"""Integrated multi-timeframe BTC technical-analysis snapshot (research only).

Completed 1m candles only. No trained price forecast, probabilities, exchange
orders, or claims of a profitable trading edge.
"""
from statistics import mean, pstdev
from research.candles import aggregate, candle_features, engulfing, atr_pct, price_action_context
from research.extra_strategies import ema
from research.market_regime import classify_regime

def _rsi(closes, period=14):
    changes=[closes[j]-closes[j-1] for j in range(len(closes)-period,len(closes))]
    gain=sum(max(0,d) for d in changes)
    loss=sum(max(0,-d) for d in changes)
    return 100*gain/(gain+loss) if gain+loss else 50.

def _frame(candles):
    if len(candles)<60:
        return None
    closes=[c[4] for c in candles]
    last=closes[-1]
    e9=ema(closes[-60:],9)
    e21=ema(closes[-60:],21)
    e50=ema(closes[-60:],50)
    mid=mean(closes[-20:])
    std=pstdev(closes[-20:])
    volumes=[c[5] for c in candles[-21:-1]]
    volume_ratio=candles[-1][5]/mean(volumes) if mean(volumes)>0 else None
    typical=[(c[2]+c[3]+c[4])/3 for c in candles[-20:]]
    v=sum(c[5] for c in candles[-20:])
    vwap=sum(p*c[5] for p,c in zip(typical,candles[-20:]))/v if v>0 else None
    macd=ema(closes[-60:],12)-ema(closes[-60:],26)
    macd_previous=ema(closes[-61:-1],12)-ema(closes[-61:-1],26) if len(closes)>=61 else None
    return {
        "last_close":last,
        "ema9":round(e9,6),"ema21":round(e21,6),"ema50":round(e50,6),
        "trend":"UP" if e9>e21>e50 else "DOWN" if e9<e21<e50 else "MIXED",
        "rsi14":round(_rsi(closes),3),
        "macd_line":round(macd,6),
        "macd_previous":round(macd_previous,6) if macd_previous is not None else None,
        "bollinger_upper":round(mid+2*std,6),
        "bollinger_lower":round(mid-2*std,6),
        "atr_pct":round(100*atr_pct(candles),5),
        "vwap20":round(vwap,6) if vwap is not None else None,
        "volume_ratio":round(volume_ratio,4) if volume_ratio is not None else None,
        "candle":candle_features(candles[-1]),
        "engulfing":engulfing(candles[-2],candles[-1]),
        "price_action":price_action_context(candles),
    }

def analyze(rows):
    if len(rows)<240:
        return {"decision":"WAIT","reason":"insufficient_history"}
    minutes=[int(r[0].timestamp())//60 for r in rows]
    if any(b-a!=1 for a,b in zip(minutes,minutes[1:])):
        return {"decision":"WAIT","reason":"non_contiguous_history"}
    if minutes[-1]%240!=239:
        # A 4h frame must be fully closed; no incomplete 4h candle.
        return {"decision":"WAIT","reason":"unfinished_4h_boundary"}
    for r in rows:
        _,o,h,l,c,v=r
        if not (0<l<=min(o,c)<=max(o,c)<=h and v>=0):
            return {"decision":"WAIT","reason":"invalid_ohlcv"}
    frames={}
    for duration in (1,5,15,60,240):
        candles=aggregate(rows,duration)
        frames[f"{duration}m"]=_frame(candles)
    if any(x is None for x in frames.values()):
        return {"decision":"WAIT","reason":"insufficient_multi_timeframe_history",
                "frames":frames}
    regime=classify_regime(rows)
    return {
        "decision":"WAIT",
        "reason":"descriptive_analysis_only_no_calibrated_positive_net_edge",
        "regime":regime,
        "frames":frames,
        "forecast":{"status":"NOT_TRAINED","expected_price":None,
                    "confidence_interval":None,"expected_net_pnl_eur":None},
        "warning":"No order authorization. Train and validate a cost-aware forecast "
                  "on chronological unseen data before using any trading decision.",
    }
