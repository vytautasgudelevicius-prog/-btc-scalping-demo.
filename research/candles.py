"""Research-only candlestick and market structure features. No orders or I/O.

Rows: (timestamp, open, high, low, close, volume), ascending, completed 1m.
All indicators use only bars available at decision time.
"""
from statistics import mean


def aggregate(rows, minutes):
    """Build completed UTC-aligned multi-minute candles; discard partial buckets."""
    if minutes < 1:
        raise ValueError("minutes must be positive")
    buckets = {}
    for row in rows:
        ts, o, h, l, c, v = row
        minute = int(ts.timestamp()) // 60
        bucket = minute // minutes
        buckets.setdefault(bucket, []).append(row)
    result = []
    for bucket in sorted(buckets):
        group = buckets[bucket]
        if len(group) != minutes:
            continue
        first = int(group[0][0].timestamp()) // 60
        if first != bucket * minutes:
            continue
        if any(int(r[0].timestamp()) // 60 != first + j for j, r in enumerate(group)):
            continue
        result.append((group[0][0], group[0][1], max(r[2] for r in group),
                       min(r[3] for r in group), group[-1][4], sum(r[5] for r in group)))
    return result


def candle_features(row):
    _, o, h, l, c, v = row
    if not (0 < l <= min(o, c) <= max(o, c) <= h and v >= 0):
        raise ValueError("invalid OHLCV")
    span = h - l
    body = abs(c - o)
    upper = h - max(o, c)
    lower = min(o, c) - l
    return {"body_ratio": body / span if span else 0.0,
            "upper_wick_ratio": upper / span if span else 0.0,
            "lower_wick_ratio": lower / span if span else 0.0,
            "close_location": (c - l) / span if span else 0.5,
            "bullish": c > o, "bearish": c < o}


def engulfing(previous, current):
    """Body engulfing is descriptive, not a trading instruction."""
    p, c = candle_features(previous), candle_features(current)
    po, pc, co, cc = previous[1], previous[4], current[1], current[4]
    if p["bearish"] and c["bullish"] and co <= pc and cc >= po:
        return "BULLISH"
    if p["bullish"] and c["bearish"] and co >= pc and cc <= po:
        return "BEARISH"
    return "NONE"


def atr_pct(rows, period=14):
    if len(rows) < period + 1:
        return None
    ranges = [max(rows[i][2] - rows[i][3],
                  abs(rows[i][2] - rows[i-1][4]),
                  abs(rows[i][3] - rows[i-1][4]))
              for i in range(len(rows) - period, len(rows))]
    return mean(ranges) / rows[-1][4] if rows[-1][4] > 0 else None


def breakout(rows, lookback=20):
    """Last completed close versus previous completed highs/lows."""
    if len(rows) < lookback + 1:
        return "NONE"
    previous = rows[-lookback-1:-1]
    last = rows[-1]
    if last[4] > max(r[2] for r in previous):
        return "UP"
    if last[4] < min(r[3] for r in previous):
        return "DOWN"
    return "NONE"


def research_signal(rows):
    """Conservative research label, not validated for profitability."""
    if len(rows) < 121:
        return {"signal": "WAIT", "reason": "insufficient_history"}
    m5 = aggregate(rows, 5)
    m15 = aggregate(rows, 15)
    if len(m5) < 22 or len(m15) < 7:
        return {"signal": "WAIT", "reason": "incomplete_higher_timeframes"}
    trend = m15[-1][4] / m15[-7][4] - 1
    atr = atr_pct(m5)
    if atr is None or atr < .0005 or atr > .02:
        return {"signal": "WAIT", "reason": "volatility"}
    recent_vol = [r[5] for r in m5[-21:-1]]
    if mean(recent_vol) <= 0 or m5[-1][5] < 1.2 * mean(recent_vol):
        return {"signal": "WAIT", "reason": "volume"}
    direction = breakout(m5)
    shape = candle_features(m5[-1])
    if direction == "UP" and trend > .003 and shape["bullish"] and shape["close_location"] > .75:
        return {"signal": "LONG", "reason": "trend_volume_breakout"}
    if direction == "DOWN" and trend < -.003 and shape["bearish"] and shape["close_location"] < .25:
        return {"signal": "SHORT", "reason": "trend_volume_breakout"}
    return {"signal": "WAIT", "reason": "no_confirmation"}
