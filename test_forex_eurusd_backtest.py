import unittest
from datetime import datetime, timedelta, timezone
from research.forex_eurusd_backtest import INITIAL_EUR, simulate, scalp_market_gate

class ForexResearchTests(unittest.TestCase):
    def bars(self, count=700, trending=True):
        start=datetime(2026,11,2,0,0,tzinfo=timezone.utc)
        out=[]
        for i in range(count):
            price=1.1+(i*.00003 if trending else 0)
            out.append((start+timedelta(minutes=i),price,price+.00004,price-.00004,price))
        return out

    def test_demo_bankroll(self):
        self.assertEqual(INITIAL_EUR,100.0)

    def test_no_free_profit_on_flat_market(self):
        result=simulate(self.bars(trending=False))
        self.assertEqual(result['trades'],0)
        self.assertEqual(result['net_pnl_eur'],0)

    def test_costs_cannot_improve_net_result(self):
        bars=self.bars()
        cheap=simulate(bars,spread_pips=0,slippage_pips=0,commission_eur_per_100k_side=0)
        costly=simulate(bars,spread_pips=2,slippage_pips=.5,commission_eur_per_100k_side=7)
        self.assertLessEqual(costly['net_pnl_eur'],cheap['net_pnl_eur']+1e-9)

    def test_reject_invalid_history(self):
        with self.assertRaises(ValueError):
            simulate(self.bars(count=50))

    def test_market_gate_rejects_quiet_market(self):
        bars=self.bars(trending=False)
        ok,reason,_=scalp_market_gate(bars,250,spread_pips=1,slippage_pips=.2,commission_eur_per_100k_side=3.5)
        self.assertFalse(ok)
        self.assertEqual(reason,'too_quiet')

    def test_market_gate_rejects_high_costs(self):
        bars=self.bars()
        ok,reason,_=scalp_market_gate(bars,250,spread_pips=20,slippage_pips=2,commission_eur_per_100k_side=10)
        self.assertFalse(ok)
        self.assertEqual(reason,'costs_exceed_volatility_budget')

    def test_market_gate_rejects_stale_data(self):
        bars=self.bars()
        bars[249]=(bars[249][0]-timedelta(minutes=4),*bars[249][1:])
        ok,reason,_=scalp_market_gate(bars,250,spread_pips=0,slippage_pips=0,commission_eur_per_100k_side=0)
        self.assertFalse(ok)
        self.assertEqual(reason,'stale_or_gapped_data')

    def test_reports_risk_controls(self):
        result=simulate(self.bars())
        self.assertEqual(result['max_consecutive_losses'],5)
        self.assertEqual(result['max_simultaneous_positions'],1)
        self.assertEqual(result['initial_capital_eur'],100)

if __name__=='__main__':
    unittest.main()
