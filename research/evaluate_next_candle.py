"""Out-of-sample directional evaluation of next_candle_bias, research only.

Usage: python research/evaluate_next_candle.py research/history_btceur_proxy.csv
Predict at completed 5m boundaries, compare with the NEXT 5m candle open/close.
WAIT is excluded from directional accuracy but counted as coverage.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.candles import next_candle_bias

def evaluate(rows, start=None):
    start = max(240, int(len(rows) * .6) if start is None else start)
    counts = {"UP": 0, "DOWN": 0, "WAIT": 0}
    correct = 0
    actual_up = 0
    actual_down = 0
    for i in range(start, len(rows) - 5):
        if int(rows[i][0].timestamp()) // 60 % 5 != 4:
            continue
        decision = next_candle_bias(rows[i - 239:i + 1])["direction"]
        counts[decision] += 1
        if decision == "WAIT":
            continue
        next_open = rows[i + 1][1]
        next_close = rows[i + 5][4]
        if next_close > next_open:
            actual_up += 1
        elif next_close < next_open:
            actual_down += 1
        if (decision == "UP" and next_close > next_open) or (decision == "DOWN" and next_close < next_open):
            correct += 1
    signals = counts["UP"] + counts["DOWN"]
    total = sum(counts.values())
    return {
        "evaluated_5m_boundaries": total, "signals": signals, "up_signals": counts["UP"],
        "down_signals": counts["DOWN"], "wait": counts["WAIT"],
        "coverage_pct": round(100 * signals / total, 2) if total else None,
        "direction_accuracy_pct": round(100 * correct / signals, 2) if signals else None,
        "correct_signals": correct, "actual_up_on_signals": actual_up,
        "actual_down_on_signals": actual_down,
        "warning": "Directional accuracy is not trading profitability; no fees, fills or P&L here."
    }

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python research/evaluate_next_candle.py history.csv")
    rows = read_csv(sys.argv[1])
    if len(rows) < 10080:
        raise ValueError("At least seven contiguous days of 1m candles required")
    print(json.dumps(evaluate(rows), indent=2))
