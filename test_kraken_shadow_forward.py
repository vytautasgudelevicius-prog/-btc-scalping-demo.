import sqlite3
import unittest
from datetime import datetime,timedelta,timezone
from research.kraken_shadow_forward import initialize,record,settle,summary,net_return

def sample(ts,side="LONG",candidate=True):
    return {"last_completed_candle":ts.isoformat(),"timestamp_utc":ts.isoformat(),
            "ema_signal":side,"bid":100.0,"ask":100.1,
            "spread_pct":0.0999,"estimated_roundtrip_cost_pct":1.7399,
            "quality_filter":True,"liquidity_atr_filter":True,
            "context_candidate":candidate}

class ForwardShadowTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        initialize(self.db)
        self.start=datetime(2026,1,1,tzinfo=timezone.utc)
    def tearDown(self):
        self.db.close()
    def test_unique_candle_and_wait_no_trade(self):
        x=sample(self.start,"WAIT",False)
        self.assertEqual(record(self.db,x),1)
        self.assertEqual(record(self.db,x),0)
        self.assertEqual(settle(self.db,sample(self.start+timedelta(minutes=6))),0)
        self.assertEqual(summary(self.db)["settled_candidates"],0)
    def test_five_minute_costs_and_no_deploy(self):
        record(self.db,sample(self.start))
        self.assertEqual(settle(self.db,sample(self.start+timedelta(minutes=4))),0)
        self.assertEqual(settle(self.db,sample(self.start+timedelta(minutes=5))),1)
        result=summary(self.db)
        self.assertEqual(result["settled_candidates"],1)
        self.assertLess(result["avg_net_pct"],-1.6)
        self.assertFalse(result["deployment_authorized"])
    def test_late_quote_not_counted_as_five_minute_pnl(self):
        record(self.db,sample(self.start))
        settle(self.db,sample(self.start+timedelta(hours=1)))
        self.assertEqual(summary(self.db)["settled_candidates"],0)
    def test_short_costs(self):
        gross,net=net_return("SHORT",100,100.1,100,100.1)
        self.assertLess(net,gross)
        self.assertLess(net,-1.6)
if __name__=="__main__":
    unittest.main()
