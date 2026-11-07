import unittest
from datetime import datetime,timedelta,timezone
from research.cross_market_context import correlation,cross_market_context

def candles(mult=1.,count=1500):
    t=datetime(2026,1,1,tzinfo=timezone.utc)
    out=[]
    for i in range(count):
        p=100+mult*(i*.01+((i//5)%11)*.1)
        out.append((t+timedelta(minutes=i),p,p+.05,p-.05,p,10.))
    return out

class CrossMarketTests(unittest.TestCase):
    def test_correlation(self):
        self.assertAlmostEqual(correlation([1,2,3],[2,4,6]),1)
        self.assertAlmostEqual(correlation([1,2,3],[6,4,2]),-1)
        self.assertIsNone(correlation([1,1,1],[2,3,4]))
    def test_missing_btc(self):
        self.assertEqual(cross_market_context({"ETH/EUR":candles()})["decision"],"WAIT")
    def test_aligned_markets(self):
        result=cross_market_context({"BTC/EUR":candles(),"ETH/EUR":candles(1.5)},lookback=100)
        self.assertEqual(result["decision"],"WAIT")
        self.assertEqual(result["markets"]["ETH/EUR"]["aligned_candles"],100)
        self.assertIsNotNone(result["markets"]["ETH/EUR"]["correlation"])
    def test_insufficient(self):
        result=cross_market_context({"BTC/EUR":candles(1,50),"SOL/EUR":candles(2,50)})
        self.assertEqual(result["markets"]["SOL/EUR"]["status"],"INSUFFICIENT_ALIGNED_HISTORY")

if __name__=="__main__":unittest.main()
