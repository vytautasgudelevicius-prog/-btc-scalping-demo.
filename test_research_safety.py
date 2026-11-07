import unittest
from research.walk_forward_forecast import walk_forward
from research.paper_promotion_gate import paper_candidate

class ResearchSafetyTests(unittest.TestCase):
    def test_walkforward_short_data(self):
        with self.assertRaises(ValueError):walk_forward([])
    def test_unvalidated_never_trades(self):
        result=paper_candidate(forecast_return=.03,expected_price=103,entry=100,
             equity=1000,stop=98,target=106)
        self.assertEqual(result["decision"],"WAIT")
        self.assertFalse(result["orders_enabled"])
    def test_cost_gate(self):
        result=paper_candidate(forecast_return=.001,expected_price=100.1,entry=100,
             equity=1000,stop=98,target=106,validated=True,walk_forward_passed=True)
        self.assertEqual(result["reason"],"forecast_does_not_cover_costs")
    def test_risk_gate(self):
        result=paper_candidate(forecast_return=.04,expected_price=104,entry=100,
             equity=1000,stop=98,target=106,validated=True,walk_forward_passed=True,
             consecutive_losses=4)
        self.assertEqual(result["reason"],"loss_streak_limit")
    def test_paper_only(self):
        result=paper_candidate(forecast_return=.04,expected_price=104,entry=100,
             equity=1000,stop=98,target=110,validated=True,walk_forward_passed=True,
             fee_per_side=.0008)
        self.assertEqual(result["decision"],"PAPER_RESEARCH_CANDIDATE")
        self.assertFalse(result["orders_enabled"])

if __name__=="__main__":unittest.main()
