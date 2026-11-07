import unittest
from research.risk_curriculum import risk_plan

class RiskCurriculumTests(unittest.TestCase):
    def test_unvalidated_signal_waits(self):
        self.assertEqual(risk_plan(equity=1000,entry=100,stop=95,target=120,side="LONG")["reason"],"signal_not_validated")

    def test_costs_block_weak_trade(self):
        result=risk_plan(equity=1000,entry=100,stop=99,target=101,side="LONG",signal_validated=True)
        self.assertEqual(result["decision"],"WAIT")
        self.assertEqual(result["reason"],"insufficient_net_reward_risk")

    def test_position_risk_capped(self):
        result=risk_plan(equity=1000,entry=100,stop=95,target=120,side="LONG",signal_validated=True)
        self.assertEqual(result["decision"],"RESEARCH_CANDIDATE")
        self.assertLessEqual(result["notional"],200)
        self.assertLessEqual(result["worst_case_modeled_loss_eur"],5.0001)

    def test_daily_loss_kill_switch(self):
        result=risk_plan(equity=970,day_start_equity=1000,entry=100,stop=95,target=120,side="LONG",signal_validated=True)
        self.assertEqual(result["reason"],"daily_loss_limit")

    def test_loss_streak_kill_switch(self):
        result=risk_plan(equity=1000,entry=100,stop=95,target=120,side="LONG",signal_validated=True,consecutive_losses=3)
        self.assertEqual(result["reason"],"loss_streak_limit")

    def test_short_geometry(self):
        result=risk_plan(equity=1000,entry=100,stop=95,target=120,side="SHORT",signal_validated=True)
        self.assertEqual(result["reason"],"invalid_stop_target_geometry")

if __name__=="__main__":
    unittest.main()
