"""Research-only market regime classifier from completed 5-minute candles.

Descriptive features, not proof of trading edge or live execution instructions.
"""
from statistics import mean
from research.candles import aggregate, atr_pct

def classify_regime(rows, *, lookback=24):
    """Classify the most recent completed 5m period; no future candles used."""
    result={"regime":"UNKNOWN","decision":"WAIT"}
    if len(rows)<max(lookback+15,40)*5:
        return {**result,"reason":"insufficient_history"}
    minutes=[int(r[0].timestamp())//60 for r in rows]
    if any(b-a!=1 for a,b in zip(minutes,minutes[1:])):
        return {**result,"reason":"non_contiguous_minutes"}
    if minutes[-1]%5!=4:
        return {**result,"reason":"unfinished_candle"}
    candles=aggregate(rows,5)
    if len(candles)<lookback+15:
        return {**result,"reason":"insufficient_complete_candles"}
    recent=candles[-lookback:]
    volatility=atr_pct(candles)
    if volatility is None or volatility<=0:
        return {**result,"reason":"invalid_volatility"}
    start=recent[0][1]
    end=recent[-1][4]
    if start<=0:
        return {**result,"reason":"invalid_price"}
    move=(end/start)-1
    avg_volume=mean(c[5] for c in recent[:-1])
    volume_ratio=recent[-1][5]/avg_volume if avg_volume>0 else 0
    trend_strength=abs(move)/(volatility*(lookback**.5))
    if volatility>.015:
        regime="HIGH_VOLATILITY"
    elif volatility<.0005:
        regime="LOW_VOLATILITY"
    elif trend_strength>=1.5:
        regime="UPTREND" if move>0 else "DOWNTREND"
    else:
        regime="RANGE"
    return {"regime":regime,"decision":"WAIT","reason":"research_classification_only",
            "return_pct":round(move*100,4),"atr_pct":round(volatility*100,4),
            "trend_strength":round(trend_strength,4),"volume_ratio":round(volume_ratio,4)}
