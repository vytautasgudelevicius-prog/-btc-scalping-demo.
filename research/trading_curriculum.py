"""Trading curriculum as deterministic, auditable market-reading gates.

Educational research only. No exchange credentials, orders or production writes.
Each lesson is a testable rule, not a claim of profitable prediction.
"""
from statistics import mean
from research.candles import aggregate, atr_pct, candle_features, price_action_context

LESSONS = (
    "OHLCV integrity", "completed candles only", "candlestick body and wicks",
    "support and resistance", "breakout confirmation", "multi-timeframe trend",
    "volatility regimes", "volume confirmation", "risk/reward after costs",
    "position sizing", "no-trade conditions", "lookahead prevention",
)

def trading_lesson_report(rows, fee_per_side=.008, spread_bps=5,
                          slippage_bps=2, stop_pct=.012, target_pct=.03):
    """Read completed UTC 1m bars and return evidence and a conservative decision.

    Costs are modeled on notional; no actual execution or win probability.
    """
    result = {"decision": "WAIT", "lessons": list(LESSONS), "checks": {}}
    if len(rows) < 240:
        result["reason"] = "insufficient_history"
        return result
    if any((b[0]-a[0]).total_seconds() != 60 for a,b in zip(rows[-240:],rows[-239:])):
        result["reason"] = "missing_or_duplicate_minutes"
        return result
    for row in rows[-240:]:
        candle_features(row)  # raises on invalid OHLCV
    minute = int(rows[-1][0].timestamp()) // 60
    if minute % 5 != 4:
        result["reason"] = "unfinished_5m_candle"
        return result
    m5, m15 = aggregate(rows[-240:],5), aggregate(rows[-240:],15)
    if len(m5)<22 or len(m15)<8:
        result["reason"] = "incomplete_timeframes"
        return result
    context = price_action_context(m5)
    volatility = atr_pct(m5)
    trend = m15[-1][4]/m15[-8][4]-1
    baseline = mean(r[5] for r in m5[-21:-1])
    volume_ratio = m5[-1][5]/baseline if baseline>0 else 0
    roundtrip_cost_pct = 2*fee_per_side + (spread_bps+2*slippage_bps)/10000
    net_target_pct = target_pct-roundtrip_cost_pct
    net_stop_pct = stop_pct+roundtrip_cost_pct
    breakeven_win_rate = net_stop_pct/(net_stop_pct+net_target_pct) if net_target_pct>0 else None
    result["checks"] = {
        "context": context["location"], "pattern": context["pattern"],
        "breakout_confirmed": context["confirmation"],
        "trend_15m_pct": round(trend*100,4),
        "atr_5m_pct": round(volatility*100,4) if volatility is not None else None,
        "volume_ratio": round(volume_ratio,4),
        "roundtrip_cost_pct": round(roundtrip_cost_pct*100,4),
        "net_target_pct": round(net_target_pct*100,4),
        "net_stop_pct": round(net_stop_pct*100,4),
        "breakeven_win_rate_pct": round(breakeven_win_rate*100,2) if breakeven_win_rate is not None else None,
    }
    if net_target_pct<=0:
        result["reason"] = "costs_exceed_target"
    elif volatility is None or not .0005<=volatility<=.02:
        result["reason"] = "volatility_regime"
    elif volume_ratio<1.2:
        result["reason"] = "insufficient_volume"
    elif not context["confirmation"]:
        result["reason"] = "no_confirmed_breakout"
    elif context["location"]=="ABOVE_RESISTANCE" and trend>.003:
        result["decision"],result["reason"]="LONG_CANDIDATE","trend_volume_breakout"
    elif context["location"]=="BELOW_SUPPORT" and trend<-.003:
        result["decision"],result["reason"]="SHORT_CANDIDATE","trend_volume_breakout"
    else:
        result["reason"]="higher_timeframe_disagreement"
    return result
