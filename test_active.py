import unittest
import test_research
from research.active_study import simulate


class ActiveTests(unittest.TestCase):
    def fixture(self, **kwargs):
        return test_research.ResearchTests().fixture(**kwargs)

    def run_case(self, d, variant="active"):
        return simulate(d, int(d.timestamp.iloc[1]), int(d.timestamp.iloc[-1])+60, variant)

    def test_sideways_entries_and_15_min_exit(self):
        d=self.fixture(regime=0, range=0, volume_ratio=0, atr=0)
        _,trades=self.run_case(d)
        self.assertEqual(trades[0]["timestamp"], d.timestamp.iloc[1]+900)
        self.assertEqual(trades[0]["reason"], "time")

    def test_opposite_regime_blocks(self):
        self.assertEqual(self.run_case(self.fixture(regime=-1))[0]["trades"],0)

    def test_five_min_confirmation(self):
        d=self.fixture(trend5=-1)
        self.assertEqual(self.run_case(d,"active_5m")[0]["trades"],0)
        d.trend5=1
        self.assertGreater(self.run_case(d,"active_5m")[0]["trades"],0)

    def test_limit_no_touch_no_fill(self):
        self.assertEqual(self.run_case(self.fixture(),"active_maker")[0]["trades"],0)

    def test_limit_fees_and_short_accounting(self):
        for side in (1,-1):
            d=self.fixture(side=side,high=100.1,low=99.9)
            result,trades=self.run_case(d,"active_maker")
            self.assertGreater(len(trades),0)
            self.assertLess(result["net_pnl"],0)
            self.assertAlmostEqual(result["net_pnl"],sum(t["net_pnl"] for t in trades))


if __name__=="__main__":
    unittest.main()
