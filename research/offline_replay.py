"""Offline walk-forward replay of completed BTC/EUR observation snapshots.

Input is timestamp-ordered JSONL of historical *point-in-time* observe() reports.
Do not use retrospectively calculated future indicators; that would leak future data.
Never connects to Kraken or submits orders. Does not modify Railway databases.
"""
import argparse
import json
import math
import sqlite3
from pathlib import Path
from research import isolated_paper_experiment as paper


def replay(path, fee=None, slip=None):
    original_fee, original_slip = paper.FEE, paper.SLIP
    if fee is not None:
        paper.FEE = fee
    if slip is not None:
        paper.SLIP = slip
    try:
        with sqlite3.connect(":memory:") as db:
            paper.init(db)
            previous = None
            first_timestamp = None
            last_timestamp = None
            observations = 0
            peak = paper.INITIAL
            max_drawdown = 0.0
            events = {}
            rejection_counts = {}
            eligible_decisions = 0
            with Path(path).open(encoding="utf-8") as stream:
                for line_no, line in enumerate(stream, 1):
                    if not line.strip():
                        continue
                    report = json.loads(line)
                    stamp = report["timestamp_utc"]
                    if previous is not None and stamp <= previous:
                        raise ValueError(f"Non-increasing timestamp at line {line_no}")
                    previous = stamp
                    if first_timestamp is None:
                        first_timestamp = stamp
                    last_timestamp = stamp
                    if report.get("orders_enabled") is not False:
                        raise ValueError("Historical report must be read-only")
                    if fee is not None or slip is not None:
                        report["estimated_roundtrip_cost_pct"] = 200 * (paper.FEE + paper.SLIP) + float(report["spread_pct"])
                    result = paper.tick(db, report)
                    current_equity = float(paper.get(db, "equity", paper.INITIAL))
                    peak = max(peak, current_equity)
                    max_drawdown = max(max_drawdown, (peak-current_equity)/peak * 100)
                    observations += 1
                    events[result["event"]] = events.get(result["event"], 0) + 1
                    decision = db.execute("SELECT eligible,reason FROM decisions WHERE candle=?", (report["last_completed_candle"],)).fetchone()
                    if decision:
                        eligible_decisions += int(decision[0])
                        for reason in decision[1].split(","):
                            if reason and reason != "ELIGIBLE":
                                rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
            if observations == 0:
                raise ValueError("No historical observations supplied")
            rows = db.execute("SELECT pnl FROM trades WHERE closed IS NOT NULL ORDER BY id").fetchall()
            pnls = [float(x[0]) for x in rows]
            losses = sum(x for x in pnls if x < 0)
            gains = sum(x for x in pnls if x > 0)
            equity = float(paper.get(db, "equity", paper.INITIAL))
            consecutive_losses = 0
            longest_losing_streak = 0
            for pnl in pnls:
                consecutive_losses = consecutive_losses + 1 if pnl < 0 else 0
                longest_losing_streak = max(longest_losing_streak, consecutive_losses)
            return {
                "first_timestamp": first_timestamp,
                "last_timestamp": last_timestamp,
                "observations": observations,
                "closed_trades": len(pnls),
                "open_trades": db.execute("SELECT COUNT(*) FROM trades WHERE closed IS NULL").fetchone()[0],
                "wins": sum(x > 0 for x in pnls),
                "win_rate_pct": round(100 * sum(x > 0 for x in pnls) / len(pnls), 2) if pnls else None,
                "net_pnl_eur": round(sum(pnls), 2),
                "average_net_pnl_per_closed_trade_eur": round(sum(pnls)/len(pnls), 2) if pnls else None,
                "max_realized_equity_drawdown_pct": round(max_drawdown, 3),
                "longest_losing_streak": longest_losing_streak,
                "equity_eur": round(equity, 2),
                "profit_factor": round(gains / abs(losses), 3) if losses else (None if not gains else "infinite"),
                "events": events,
                "eligible_decisions": eligible_decisions,
                "rejection_counts": rejection_counts,
                "warning": "Realized-equity drawdown excludes open unrealized PnL. Offline paper simulation; no guarantee of fills or future profit."
            }
    finally:
        paper.FEE, paper.SLIP = original_fee, original_slip


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshots", help="Point-in-time JSONL reports, in chronological order")
    parser.add_argument("--fee", type=float, default=None, help="One-way fee as fraction (0.008=0.8%)")
    parser.add_argument("--slip", type=float, default=None, help="One-way slippage fraction")
    args = parser.parse_args()
    if args.fee is not None and not 0 <= args.fee < 1:
        parser.error("--fee must be between 0 and 1")
    if args.slip is not None and not 0 <= args.slip < 1:
        parser.error("--slip must be between 0 and 1")
    print(json.dumps(replay(args.snapshots, args.fee, args.slip), indent=2))


if __name__ == "__main__":
    main()
