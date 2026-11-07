import unittest
from datetime import datetime,timedelta,timezone
from research.technical_analysis_engine import analyze

def sample(count=15000):
    t=datetime(2026,1,1,tzinfo=timezone.utc)
    return [(t+timedelta(minutes=i),100+i*.001,100+i*.001+.1,
             100+i*.001-.1,100+i*.001+.02,10.) for i in range(count)]

class TechnicalAnalysisTests(unittest.TestCase):
    def test_wait_on_short_history(self):
        self.assertEqual(analyze(sample(10))["decision"],"WAIT")
    def test_no_partial_4h(self):
        self.assertEqual(analyze(sample(15001))["reason"],"unfinished_4h_boundary")
    def test_multiframe_and_no_fake_forecast(self):
        # 15360 minutes = 64 completed 4h candles
        result=analyze(sample(15360))
        self.assertEqual(result["decision"],"WAIT")
        self.assertEqual(set(result["frames"]),{"1m","5m","15m","60m","240m"})
        self.assertTrue(all(frame is not None for frame in result["frames"].values()))
        self.assertIsNone(result["forecast"]["expected_price"])
    def test_gap_rejected(self):
        rows=sample(15360)
        rows[5]=(rows[5][0]+timedelta(minutes=1),*rows[5][1:])
        self.assertEqual(analyze(rows)["reason"],"non_contiguous_history")

if __name__=="__main__":unittest.main()
