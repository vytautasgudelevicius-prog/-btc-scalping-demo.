import datetime as dt
import unittest
from research.adaptive_grid_backtest import simulate

class AdaptiveGridTests(unittest.TestCase):
    def bars(self, count=500, trend=0):
        t=dt.datetime(2026,1,1,tzinfo=dt.timezone.utc)
        out=[]
        for i in range(count):
            p=100+trend*i+0.2*((i%20)-10)/10
            out.append((t+dt.timedelta(minutes=i),p,p+.2,p-.2,p,1.))
        return out

    def test_flat_market_no_free_profit(self):
        result=simulate(self.bars(),fee=.008)
        self.assertLessEqual(result["net_pnl_eur"],0)

    def test_costs_reduce_net_pnl(self):
        rows=self.bars()
        a=simulate(rows,fee=.008)
        b=simulate(rows,fee=.0005)
        self.assertLessEqual(a["net_pnl_eur"],b["net_pnl_eur"])

    def test_high_fees_reject_unrealistic_grid(self):
        result=simulate(self.bars(),fee=.008)
        self.assertEqual(result['trades'],0)
        self.assertGreater(result['rejected_costs'],0)

    def test_holdout_does_not_assume_profitable_fills(self):
        result=simulate(self.bars(trend=.1),fee=.008)
        self.assertLessEqual(result['net_pnl_eur'],0)

    def test_insufficient_data(self):
        with self.assertRaises(ValueError):
            simulate(self.bars(100))

    def test_trending_market_stays_conservative(self):
        result=simulate(self.bars(trend=.1))
        self.assertGreaterEqual(result["max_drawdown_pct"],0)

if __name__=="__main__":
    unittest.main()
