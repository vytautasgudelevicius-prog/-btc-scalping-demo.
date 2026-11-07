import unittest
from datetime import datetime,timedelta,timezone
from research.market_regime import classify_regime

def rows(slope=0, count=240):
    start=datetime(2026,1,1,tzinfo=timezone.utc)
    out=[]
    for i in range(count):
        o=100+i*slope
        c=o+slope
        out.append((start+timedelta(minutes=i),o,max(o,c)+.05,min(o,c)-.05,c,10.))
    return out

class MarketRegimeTests(unittest.TestCase):
    def test_no_history(self):
        self.assertEqual(classify_regime(rows(count=10))["reason"],"insufficient_history")

    def test_completed_candles_only(self):
        self.assertEqual(classify_regime(rows(count=239))["reason"],"unfinished_candle")

    def test_uptrend(self):
        self.assertEqual(classify_regime(rows(slope=.08))["regime"],"UPTREND")

    def test_downtrend(self):
        self.assertEqual(classify_regime(rows(slope=-.08))["regime"],"DOWNTREND")

    def test_range(self):
        self.assertEqual(classify_regime(rows())["regime"],"RANGE")

    def test_gap_rejected(self):
        data=rows()
        data[100]=(data[100][0]+timedelta(minutes=1),*data[100][1:])
        self.assertEqual(classify_regime(data)["reason"],"non_contiguous_minutes")

if __name__=="__main__":
    unittest.main()
