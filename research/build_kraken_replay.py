"""Fetch Kraken's available completed OHLC history and build causal replay snapshots.

Kraken public OHLC is limited to roughly 720 most recent candles per interval.
This is a short smoke backtest, NOT multi-year historical validation.
No credentials or orders; output contains only point-in-time information.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from bot import api, PAIR, FEE, SLIP


def ema(values, period):
    alpha = 2 / (period + 1)
    result = values[0]
    for value in values:
        result = alpha * value + (1 - alpha) * result
    return result


def structure(bars):
    if len(bars) < 30:
        raise ValueError("Not enough completed candles")
    highs = [float(b[2]) for b in bars]
    lows = [float(b[3]) for b in bars]
    closes = [float(b[4]) for b in bars]
    last = bars[-1]
    op, close, hi, lo = map(float, (last[1], last[4], last[2], last[3]))
    span = max(hi-lo, 1e-9)
    volumes = [float(b[6]) for b in bars[-20:]]
    prev_high, prev_low = max(highs[-13:-1]), min(lows[-13:-1])
    return {
        "close": close, "ema9": ema(closes, 9), "ema21": ema(closes, 21),
        "volume_ratio": volumes[-1] / max(sum(volumes[:-1])/19, 1e-9),
        "body_ratio": abs(close-op)/span,
        "upper_wick_ratio": (hi-max(op,close))/span,
        "lower_wick_ratio": (min(op,close)-lo)/span,
        "higher_lows": min(lows[-6:]) > min(lows[-12:-6]),
        "lower_highs": max(highs[-6:]) < max(highs[-12:-6]),
        "support": min(lows[-12:-1]), "resistance": max(highs[-12:-1]),
        "previous_support": min(lows[-24:-12]),
        "previous_resistance": max(highs[-24:-12]),
        "false_break_up": hi > prev_high and close < prev_high and close < op,
        "false_break_down": lo < prev_low and close > prev_low and close > op,
    }


def completed(interval):
    response = api("OHLC", {"pair": PAIR, "interval": interval})
    key = next(k for k in response if k != "last")
    return response[key][:-1]


def build(output):
    minute, five, fifteen = completed(1), completed(5), completed(15)
    count = 0
    with Path(output).open("w", encoding="utf-8") as out:
        for i in range(90, len(minute)):
            candle = minute[i]
            # A candle at t is only known at t+60 seconds.
            t = int(candle[0]) + 60
            b5 = [b for b in five if int(b[0])+300 <= t]
            b15 = [b for b in fifteen if int(b[0])+900 <= t]
            if len(b5) < 30 or len(b15) < 30:
                continue
            last60 = minute[i-59:i+1]
            high = max(float(b[2]) for b in last60)
            low = min(float(b[3]) for b in last60)
            price = float(candle[4])
            # OHLC lacks historical bid/ask: conservative explicit synthetic spread.
            spread = price * 0.0005
            bid, ask = price-spread/2, price+spread/2
            report = {
                "timestamp_utc": datetime.fromtimestamp(t, timezone.utc).isoformat(),
                "last_completed_candle": datetime.fromtimestamp(int(candle[0]), timezone.utc).isoformat(),
                "pair": "BTC/EUR", "bid": bid, "ask": ask,
                "spread_pct": (ask-bid)/ask*100,
                "estimated_roundtrip_cost_pct": 200*(FEE+SLIP)+(ask-bid)/ask*100,
                "hourly_range_pct": (high/low-1)*100,
                "structure": {"5": structure(b5), "15": structure(b15)},
                "decision": "OBSERVE_ONLY", "orders_enabled": False,
            }
            out.write(json.dumps(report)+"\n")
            count += 1
    if not count:
        raise ValueError("Insufficient overlapping historical OHLC")
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="kraken_replay_snapshots.jsonl")
    args = parser.parse_args()
    print(json.dumps({"snapshots": build(args.output), "output": args.output,
                      "limitations": "Kraken short rolling OHLC, synthetic spread, no intrabar fills"}))


if __name__ == "__main__":
    main()
