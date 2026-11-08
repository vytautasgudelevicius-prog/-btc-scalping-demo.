"""Safety and chronological replay checks; no network and no live orders."""
import json
import tempfile
import unittest
from pathlib import Path
from research.offline_replay import replay
from research import isolated_paper_experiment as paper


def report(timestamp, candle):
    base = {
        "close": 100.0, "ema9": 99.0, "ema21": 101.0,
        "support": 95.0, "resistance": 105.0,
        "previous_support": 94.0, "previous_resistance": 106.0,
        "volume_ratio": 1.0, "higher_lows": False,
        "lower_highs": False, "upper_wick_ratio": 0.0,
        "lower_wick_ratio": 0.0,
    }
    return {
        "pair": "BTC/EUR", "orders_enabled": False,
        "decision": "OBSERVE_ONLY", "timestamp_utc": timestamp,
        "last_completed_candle": candle, "bid": 99.0, "ask": 100.0,
        "spread_pct": 0.01, "hourly_range_pct": 0.1,
        "estimated_roundtrip_cost_pct": 1.64,
        "structure": {"5": dict(base), "15": dict(base)}
    }


class ReplayTests(unittest.TestCase):
    def run_replay(self, rows, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshots.jsonl"
            path.write_text("".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")
            return replay(path, **kwargs)

    def test_no_signals_does_not_invent_profit(self):
        rows = [report("2026-11-01T10:00:00+00:00", "2026-11-01T09:59:00+00:00")]
        result = self.run_replay(rows)
        self.assertEqual(result["closed_trades"], 0)
        self.assertEqual(result["net_pnl_eur"], 0)
        self.assertEqual(result["equity_eur"], 1000)
        self.assertEqual(result["max_realized_equity_drawdown_pct"], 0)
        self.assertEqual(result["longest_losing_streak"], 0)
        self.assertIsNone(result["average_net_pnl_per_closed_trade_eur"])
        self.assertEqual(result["first_timestamp"], rows[0]["timestamp_utc"])

    def test_reject_out_of_order_history(self):
        r = report("2026-11-01T10:00:00+00:00", "2026-11-01T09:59:00+00:00")
        with self.assertRaisesRegex(ValueError, "Non-increasing"):
            self.run_replay([r, r])

    def test_reject_orders_enabled(self):
        r = report("2026-11-01T10:00:00+00:00", "2026-11-01T09:59:00+00:00")
        r["orders_enabled"] = True
        with self.assertRaisesRegex(ValueError, "read-only"):
            self.run_replay([r])

    def test_false_breakout_blocks_entry(self):
        import sqlite3
        r = report("2026-11-01T10:00:00+00:00", "2026-11-01T09:59:00+00:00")
        for timeframe in ("5", "15"):
            r["structure"][timeframe].update(
                {"ema9": 102.0, "ema21": 100.0, "close": 103.0,
                 "support": 95.0, "resistance": 140.0,
                 "higher_lows": True})
        r["hourly_range_pct"] = 3.0
        r["structure"]["5"]["false_break_up"] = True
        with sqlite3.connect(":memory:") as db:
            paper.init(db)
            result = paper.tick(db, r)
            self.assertEqual(result["open_positions"], 0)
            reasons = db.execute("SELECT reason FROM decisions").fetchone()[0]
            self.assertIn("FALSE_BREAKOUT", reasons)

    def test_daily_loss_halt_preserves_equity(self):
        import sqlite3
        r = report("2026-11-01T10:00:00+00:00", "2026-11-01T09:59:00+00:00")
        with sqlite3.connect(":memory:") as db:
            paper.init(db)
            paper.put(db, "equity", 950)
            paper.put(db, "day", "2026-11-01")
            paper.put(db, "day_start_equity", 1000)
            db.commit()
            result = paper.tick(db, r)
            self.assertEqual(result["event"], "DAILY_LOSS_HALT")
            self.assertEqual(result["equity_eur"], 950)

    def test_daily_halt_blocks_otherwise_eligible_entry(self):
        import sqlite3
        r = report("2026-11-01T10:00:00+00:00", "2026-11-01T09:59:00+00:00")
        for timeframe in ("5", "15"):
            r["structure"][timeframe].update({
                "ema9": 103.0, "ema21": 100.0, "close": 104.0,
                "support": 98.0, "resistance": 150.0,
                "higher_lows": True, "volume_ratio": 1.5,
            })
        r["hourly_range_pct"] = 4.0
        with sqlite3.connect(":memory:") as db:
            paper.init(db)
            paper.put(db, "equity", 950)
            paper.put(db, "day", "2026-11-01")
            paper.put(db, "day_start_equity", 1000)
            db.commit()
            result = paper.tick(db, r)
            self.assertEqual(result["event"], "DAILY_LOSS_HALT")
            self.assertEqual(result["open_positions"], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM trades").fetchone()[0], 0)

    def test_hourly_aggregation_uses_only_completed_quarters(self):
        from research.build_kraken_replay import hourly_from_fifteen
        bars = [[i * 900, "100", "103", "98", str(100+i), "0", "2"]
                for i in range(7)]
        hourly = hourly_from_fifteen(bars)
        self.assertEqual(len(hourly), 1)
        self.assertEqual(hourly[0][0], 0)
        self.assertEqual(hourly[0][4], "103")
        self.assertEqual(hourly[0][6], 8)

    def test_cost_scenario_changes_entry_gate_without_mutating_input(self):
        r = report("2026-11-01T10:00:00+00:00", "2026-11-01T09:59:00+00:00")
        original_cost = r["estimated_roundtrip_cost_pct"]
        result = self.run_replay([r], fee=0.001, slip=0.0)
        self.assertEqual(result["observations"], 1)
        self.assertEqual(r["estimated_roundtrip_cost_pct"], original_cost)

    def test_hourly_aggregation_rejects_missing_quarter(self):
        from research.build_kraken_replay import hourly_from_fifteen
        bars = [[i * 900, "100", "103", "98", str(100+i), "0", "2"]
                for i in (0, 1, 3, 4)]
        self.assertEqual(hourly_from_fifteen(bars), [])

    def test_hourly_aggregation_does_not_use_incomplete_hour(self):
        from research.build_kraken_replay import hourly_from_fifteen
        bars = [[i * 900, "100", "103", "98", str(100+i), "0", "2"]
                for i in range(3)]
        self.assertEqual(hourly_from_fifteen(bars), [])

    def test_fee_override_restored(self):
        original = paper.FEE
        r = report("2026-11-01T10:00:00+00:00", "2026-11-01T09:59:00+00:00")
        self.run_replay([r], fee=0.001, slip=0.0)
        self.assertEqual(paper.FEE, original)


if __name__ == "__main__":
    unittest.main()
