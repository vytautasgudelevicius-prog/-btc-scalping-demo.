import unittest
from datetime import datetime,timedelta,timezone
from research.strategy_arena import STRATEGIES,signal,run

def history(n=3000,delta=.01):
    start=datetime(2026,1,1,tzinfo=timezone.utc)
    return [(start+timedelta(minutes=i),100+i*delta,100+i*delta+.1,100+i*delta-.1,100+i*delta,10.) for i in range(n)]

class ArenaTests(unittest.TestCase):
    def test_twelve_strategies(self):
        self.assertEqual(len(STRATEGIES),12)

    def test_future_candles_cannot_change_past_signal(self):
        from research.candles import aggregate
        c=aggregate(history(),5)
        for name in STRATEGIES:
            self.assertEqual(signal(c,40,name),signal(c[:41],40,name))

    def test_no_fees_cannot_worsen_net_average(self):
        result=run(history(),fee_per_side=0,spread_bps=0,slippage_bps=0)
        for record in result["test"].values():
            if record["trades"]:
                self.assertAlmostEqual(record["net_avg_pct"],record["gross_avg_pct"])

    def test_gap_rejected(self):
        data=history()
        data[100]=(data[100][0]+timedelta(minutes=1),*data[100][1:])
        with self.assertRaises(ValueError):run(data)

    def test_no_profitable_strategy_is_not_deployed(self):
        result=run(history(delta=0))
        self.assertEqual(result["decision"],"NO_TRADE")

if __name__=="__main__":unittest.main()
