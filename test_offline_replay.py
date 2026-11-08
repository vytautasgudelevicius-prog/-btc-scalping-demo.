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

    def test_reject_out_of_order_history(self):
        r = report("2026-11-01T10:00:00+00:00", "2026-11-01T09:59:00+00:00")
        with self.assertRaisesRegex(ValueError, "Non-increasing"):
            self.run_replay([r, r])

    def test_reject_orders_enabled(self):
        r = report("2026-11-01T10:00:00+00:00", "2026-11-01T09:59:00+00:00")
        r["orders_enabled"] = True
        with self.assertRaisesRegex(ValueError, "read-only"):
            self.run_replay([r])

    def test_fee_override_restored(self):
        original = paper.FEE
        r = report("2026-11-01T10:00:00+00:00", "2026-11-01T09:59:00+00:00")
        self.run_replay([r], fee=0.001, slip=0.0)
        self.assertEqual(paper.FEE, original)


if __name__ == "__main__":
    unittest.main()
