import unittest
from datetime import datetime,timedelta,timezone
from research.forex_signal_forecast import forecast_signal

class ForecastTests(unittest.TestCase):
    def test_short_history_waits(self):
        self.assertEqual(forecast_signal([])['status'],'WAIT')

    def test_flat_market_never_claims_signal(self):
        start=datetime(2026,11,2,tzinfo=timezone.utc)
        bars=[(start+timedelta(minutes=i),1.1,1.1,1.1,1.1) for i in range(70)]
        result=forecast_signal(bars)
        self.assertEqual(result['status'],'WAIT')
        self.assertIsNone(result['eta_minutes'])

    def test_forecast_never_places_order(self):
        start=datetime(2026,11,2,tzinfo=timezone.utc)
        bars=[]
        for i in range(100):
            p=1.1+i*.00004
            bars.append((start+timedelta(minutes=i),p,p+.00006,p-.00006,p))
        result=forecast_signal(bars,spread_pips=0,slippage_pips=0,commission_eur_per_100k_side=0)
        self.assertIn(result['status'],('WAIT','WATCH'))
        self.assertFalse(result.get('order_allowed',False))

if __name__=='__main__':
    unittest.main()
