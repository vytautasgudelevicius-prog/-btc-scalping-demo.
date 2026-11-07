"""BTC-led cross-market research: aligned returns, rolling correlation, relative strength.

Research only. Uses completed timestamp-aligned 5m candles; never places orders.
"""
from math import sqrt
from research.candles import aggregate

def returns_by_close(rows):
    candles=aggregate(rows,5)
    return {int(candles[i][0].timestamp()):candles[i][4]/candles[i-1][4]-1
            for i in range(1,len(candles)) if candles[i-1][4]>0}

def correlation(a,b):
    if len(a)!=len(b) or len(a)<3: return None
    ma=sum(a)/len(a);mb=sum(b)/len(b)
    aa=sum((x-ma)**2 for x in a);bb=sum((y-mb)**2 for y in b)
    if aa<=0 or bb<=0:return None
    return sum((x-ma)*(y-mb) for x,y in zip(a,b))/sqrt(aa*bb)

def cross_market_context(markets,lookback=288):
    if "BTC/EUR" not in markets:
        return {"decision":"WAIT","reason":"missing_btc"}
    if lookback<3:raise ValueError("lookback must be >=3")
    series={name:returns_by_close(rows) for name,rows in markets.items()}
    btc=series["BTC/EUR"]
    results={}
    for name,other in series.items():
        if name=="BTC/EUR":continue
        common=sorted(set(btc)&set(other))
        if len(common)<lookback:
            results[name]={"status":"INSUFFICIENT_ALIGNED_HISTORY"}
            continue
        stamps=common[-lookback:]
        x=[btc[t] for t in stamps];y=[other[t] for t in stamps]
        btc_total=1
        alt_total=1
        for bx,ay in zip(x,y):
            btc_total*=1+bx;alt_total*=1+ay
        corr=correlation(x,y)
        results[name]={"correlation":round(corr,4) if corr is not None else None,
                       "btc_return_pct":round((btc_total-1)*100,4),
                       "alt_return_pct":round((alt_total-1)*100,4),
                       "relative_strength_pct_points":round((alt_total-btc_total)*100,4),
                       "aligned_candles":len(stamps),
                       "status":"DESCRIPTIVE_ONLY"}
    return {"decision":"WAIT","reason":"no_validated_net_edge",
            "lookback_5m_candles":lookback,"markets":results,
            "warning":"Correlation is descriptive, not causal or a price prediction. "
                      "Do not infer live trading permission."}
