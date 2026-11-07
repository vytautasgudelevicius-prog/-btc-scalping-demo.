import unittest
from unittest.mock import patch
from research.strong_signal_backtest import confirmed_side, score, run

class StrongSignalTests(unittest.TestCase):
    def setUp(self):
        self.bull=[.4,.6,.8,1.,.5,.3,1.2,.7]
        self.bear=[-.4,-.6,-.8,-1.,-.5,-.3,1.2,.7]

    def test_long_and_short_require_confirmation(self):
        self.assertEqual(confirmed_side(self.bull,.025,.016),1)
        self.assertEqual(confirmed_side(self.bear,-.025,.016),-1)

    def test_conflicting_trend_and_weak_volume_wait(self):
        self.assertEqual(confirmed_side([.4,-.1,.8,1.,.5,.3,1.2,.7],.025,.016),0)
        self.assertEqual(confirmed_side(self.bull,.025,.016,.8),0)
        self.assertEqual(confirmed_side(self.bull,.01,.016),0)

    def test_net_profit_subtracts_full_round_trip_cost(self):
        model=object()
        with patch("research.strong_signal_backtest.predict",return_value=.025):
            result=score(model,[(self.bull,.005)],.016,.016)
        self.assertEqual(result["trades"],1)
        self.assertAlmostEqual(result["avg_net_pct"],-1.1)

    def test_rejects_missing_history_and_invalid_cost(self):
        with self.assertRaises(ValueError):
            run([])
        with self.assertRaises(ValueError):
            run([],fee_per_side=-.01)

if __name__=="__main__":
    unittest.main()
