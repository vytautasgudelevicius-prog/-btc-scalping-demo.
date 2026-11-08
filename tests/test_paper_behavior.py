"""Behavioral paper signal tests. Synthetic inputs, no market orders."""
import sqlite3
import unittest
from research import isolated_paper_experiment as paper

def snapshot(cost=1.64, hourly=0.3, volume=1.2, target=72000, ts="2026-11-08T10:01:00+00:00"):
    m5={"close":68000,"ema9":68100,"ema21":67900,"volume_ratio":volume,
        "higher_lows":True,"lower_highs":False,"upper_wick_ratio":0.1,
        "lower_wick_ratio":0.1,"false_break_up":False,"false_break_down":False,
        "support":67500,"resistance":69000,"previous_support":67400,"previous_resistance":69100}
    m15={**m5,"support":67000,"resistance":target}
    return {"pair":"BTC/EUR","orders_enabled":False,"decision":"OBSERVE_ONLY",
            "bid":68000.0,"ask":68000.1,"timestamp_utc":ts,
            "last_completed_candle":ts,"hourly_range_pct":hourly,
            "estimated_roundtrip_cost_pct":cost,"spread_pct":0.00015,
            "structure":{"5":m5,"15":m15}}

class BehavioralPaperTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        paper.init(self.db)
    def tearDown(self):
        self.db.close()
    def test_cost_gate_blocks_aligned_trend(self):
        result=paper.tick(self.db,snapshot())
        self.assertEqual(result["open_positions"],0)
        self.assertIn("RANGE_BELOW_125PCT_COST_BUFFER",
                      self.db.execute("SELECT reason FROM decisions").fetchone()[0])
    def test_low_volume_blocks_even_if_cost_passes(self):
        result=paper.tick(self.db,snapshot(hourly=3,volume=.1))
        self.assertEqual(result["open_positions"],0)
        self.assertIn("LOW_VOLUME",self.db.execute("SELECT reason FROM decisions").fetchone()[0])
    def test_net_reward_gate_blocks_unprofitable_target(self):
        result=paper.tick(self.db,snapshot(hourly=3,target=68100))
        self.assertEqual(result["open_positions"],0)
        self.assertEqual(self.db.execute("SELECT eligible FROM decisions").fetchone()[0],1)
    def test_valid_synthetic_signal_opens_only_paper(self):
        result=paper.tick(self.db,snapshot(hourly=3,target=75000))
        self.assertEqual(result["event"],"OPENED")
        self.assertEqual(result["open_positions"],1)
        self.assertIs(result["orders_enabled"],False)
        self.assertIs(result["exchange_credentials_used"],False)
    def test_rejects_live_order_source(self):
        report=snapshot(hourly=3)
        report["orders_enabled"]=True
        with self.assertRaises(ValueError):
            paper.tick(self.db,report)
if __name__=="__main__":
    unittest.main()
