"""Additional completed-candle strategies for the historical arena.

All functions return -1, 0, +1 and never place exchange orders.
"""
from statistics import mean

NAMES=("bollinger_reversion","ema_crossover","donchian_breakout","volume_momentum","macd_trend","stochastic_reversion")

def ema(values,period):
    alpha=2/(period+1)
    result=values[0]
    for v in values[1:]:result=alpha*v+(1-alpha)*result
    return result

def extra_signal(candles,i,name):
    if name not in NAMES:raise ValueError("Unknown strategy")
    if i<55:return 0
    h=candles[:i+1]
    closes=[c[4] for c in h]
    last=closes[-1]
    if name=="bollinger_reversion":
        m=mean(closes[-20:])
        std=(mean((v-m)**2 for v in closes[-20:]))**.5
        return -1 if std and last>m+2*std else 1 if std and last<m-2*std else 0
    if name=="ema_crossover":
        prev=closes[:-1]
        diff=ema(closes[-55:],9)-ema(closes[-55:],21)
        prior=ema(prev[-55:],9)-ema(prev[-55:],21)
        return 1 if prior<=0<diff else -1 if prior>=0>diff else 0
    if name=="donchian_breakout":
        previous=h[-21:-1]
        return 1 if last>max(c[2] for c in previous) else -1 if last<min(c[3] for c in previous) else 0
    if name=="volume_momentum":
        baseline=mean(c[5] for c in h[-21:-1])
        if baseline<=0 or h[-1][5]<baseline*1.5:return 0
        return 1 if last>closes[-5]*1.002 else -1 if last<closes[-5]*.998 else 0
    if name=="macd_trend":
        macd=ema(closes[-55:],12)-ema(closes[-55:],26)
        return 1 if macd>last*.001 else -1 if macd< -last*.001 else 0
    if name=="stochastic_reversion":
        recent=h[-14:]
        high=max(c[2] for c in recent)
        low=min(c[3] for c in recent)
        k=(last-low)/(high-low) if high>low else .5
        return 1 if k<.2 else -1 if k>.8 else 0
    return 0
