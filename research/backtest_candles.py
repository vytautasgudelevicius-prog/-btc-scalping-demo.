"""Offline, research-only multi-timeframe signal backtest.

Run: python research/backtest_candles.py history.csv
Requires consecutive, completed 1-minute BTC/EUR candles. No live orders.
Signals are evaluated on completed 5m bars, execution at NEXT 1m open.
Fees, half-spread and slippage charged on both sides.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.candles import research_signal

START = 1000.0
FEE = .008
SLIPPAGE = .0002
SPREAD_BPS = 5
NOTIONAL_FRACTION = .10
STOP_PCT = .012
TARGET_PCT = .03
MAX_HOLD_MINUTES = 60
COOLDOWN_MINUTES = 15


def simulate(rows, start_index, fee=FEE, spread_bps=SPREAD_BPS):
    cash, position, trades, last_exit = START, None, [], -COOLDOWN_MINUTES
    friction = spread_bps / 20000 + SLIPPAGE
    # A signal at completed bar i is filled at open of bar i+1.\n    # Limit indicator input to 240 recent bars to avoid quadratic work on months of data.
    # The 5m decision boundary is minute 4, 9, 14... UTC.
    for i in range(max(start_index, 180), len(rows) - 1):
        current, nxt = rows[i], rows[i + 1]
        if position is not None:
            side, entry, qty, entry_fee, opened = position
            # Intrabar exit uses conservative stop-first convention.
            stop = entry * (1 - side * STOP_PCT)
            target = entry * (1 + side * TARGET_PCT)
            stop_hit = current[3] <= stop if side == 1 else current[2] >= stop
            target_hit = current[2] >= target if side == 1 else current[3] <= target
            # A gap beyond the stop cannot fill at the more favorable stop price.\n            gap_open = current[1]\n            if stop_hit:\n                exit_mid = min(stop, gap_open) if side == 1 else max(stop, gap_open)\n            elif target_hit:\n                exit_mid = target\n            else:\n                exit_mid = None
            if exit_mid is None and i - opened >= MAX_HOLD_MINUTES:
                exit_mid = nxt[1]
            if exit_mid is not None:
                exit_price = exit_mid * (1 - side * friction)
                pnl = side * (exit_price - entry) * qty - entry_fee - qty * exit_price * fee
                cash += pnl
                trades.append(pnl)
                position = None
                last_exit = i
        if position is not None or i - last_exit < COOLDOWN_MINUTES:
            continue
        # The signal only changes when the 5m bar closes.
        minute = int(current[0].timestamp()) // 60
        if minute % 5 != 4:
            continue
        result = research_signal(rows[max(0, i - 239):i+1])
        direction = result["signal"]
        if direction not in ("LONG", "SHORT"):
            continue
        side = 1 if direction == "LONG" else -1
        entry = nxt[1] * (1 + side * friction)
        notional = min(cash * NOTIONAL_FRACTION, cash * .005 / (STOP_PCT + 2*fee + 2*friction))
        if notional <= 0:
            break
        qty = notional / entry
        position = (side, entry, qty, notional * fee, i + 1)
    # Unclosed trades are not silently counted as realized profit.
    if position is not None:
        side, entry, qty, entry_fee, opened = position
        exit_price = rows[-1][4] * (1 - side * friction)
        pnl = side * (exit_price - entry) * qty - entry_fee - qty * exit_price * fee
        cash += pnl
        trades.append(pnl)
    wins = [p for p in trades if p > 0]
    losses = [p for p in trades if p < 0]
    return {"trades": len(trades), "wins": len(wins),
            "net_pnl_eur": round(cash - START, 4),
            "win_rate_pct": round(100 * len(wins) / len(trades), 2) if trades else None,
            "profit_factor": round(sum(wins) / -sum(losses), 4) if losses else None}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python research/backtest_candles.py history.csv")
    rows = read_csv(sys.argv[1])
    if len(rows) < 10080:
        raise ValueError("At least 7 days (10080) of consecutive 1m candles required; longer periods strongly preferred")
    split = int(len(rows) * .6)
    scenarios = {}
    for name, fee, spread in (("taker_80bps", .008, 5),
                              ("taker_wide_80bps", .008, 15),
                              ("maker_idealized_40bps", .004, 5)):
        scenarios[name] = {"train": simulate(rows[:split], 180, fee, spread),
                           "holdout": simulate(rows, split, fee, spread)}
    print(json.dumps({"strategy": "candle_multitimeframe_research",
                      "scenarios": scenarios,
                      "warning": "No production parity or guaranteed fills; maker fills idealized."}, indent=2))


if __name__ == "__main__":
    main()
