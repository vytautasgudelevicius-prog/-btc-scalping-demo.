import unittest
from datetime import datetime,timedelta,timezone
from research.auto_optimize import CONFIGS,candidates,optimize,score
from research.candles import aggregate

def history(n=3000,slope=.01):
    start=datetime(2026,1,1,tzinfo=timezone.utc)
    return [(start+timedelta(minutes=i),100+i*slope,100+i*slope+.1,100+i*slope-.1,100+i*slope,10.) for i in range(n)]

class AutoOptimizerTests(unittest.TestCase):
    def test_parameter_search_has_multiple_families(self):
        self.assertEqual(len(CONFIGS),16)
        self.assertEqual(len(set(p[0] for p in CONFIGS)),4)

    def test_future_does_not_change_past_signals(self):
        candles=aggregate(history(),5)
        for (params,signals),(prior_params,prior_signals) in zip(candidates(candles),candidates(candles[:100])):
            self.assertEqual(params,prior_params)
            self.assertEqual(signals[:98],prior_signals[:98])

    def test_flat_market_not_profitable_after_fees(self):
        result=optimize(history(slope=0))
        self.assertEqual(result["decision"],"NO_TRADE")

    def test_zero_costs_not_worse_for_fixed_signal(self):
        candles=aggregate(history(),5)
        _,sides=next(candidates(candles))
        paid=score(candles,sides,350,500,.0169)
        free=score(candles,sides,350,500,0)
        self.assertGreaterEqual(free["ending_equity_eur"],paid["ending_equity_eur"])

    def test_gaps_fail(self):
        data=history()
        data[100]=(data[100][0]+timedelta(minutes=1),*data[100][1:])
        with self.assertRaises(ValueError):optimize(data)

if __name__=="__main__":unittest.main()
