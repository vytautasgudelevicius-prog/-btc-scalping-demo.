import unittest
from unittest.mock import patch
from research.kraken_shadow_observer import observe

class KrakenShadowTests(unittest.TestCase):
    def test_invalid_quote_fails_closed(self):
        def fetch(endpoint,params):
            if endpoint=="OHLC":
                return {"XXBTZEUR":[[0,"1","1","1","1","1","1",1]]*100,"last":0}
            return {"XXBTZEUR":{"a":["99"],"b":["100"]}}
        with self.assertRaises(ValueError):
            observe(fetch)
    def test_stale_candles_fail_closed(self):
        def fetch(endpoint,params):
            if endpoint=="OHLC":
                return {"XXBTZEUR":[[0,"1","1","1","1","1","1",1]]*100,"last":0}
            return {"XXBTZEUR":{"a":["101"],"b":["100"]}}
        with self.assertRaises(ValueError):
            observe(fetch)
    @patch("research.kraken_shadow_observer.signal",return_value="LONG")
    @patch("research.kraken_shadow_observer.entry_quality",return_value=True)
    @patch("research.kraken_shadow_observer.liquidity_and_atr_ok",return_value=True)
    def test_good_quote_never_places_order(self,liquid,quality,signal):
        import time
        candle=[int(time.time())-60,"100","101","99","100","100","1",1]
        def fetch(endpoint,params):
            if endpoint=="OHLC":
                return {"XXBTZEUR":[candle]*100,"last":0}
            return {"XXBTZEUR":{"a":["100.01"],"b":["100.00"]}}
        result=observe(fetch)
        self.assertEqual(result["decision"],"OBSERVE_ONLY")
        self.assertFalse(result["orders_enabled"])
        self.assertGreater(result["estimated_roundtrip_cost_pct"],1.64)
if __name__=="__main__":
    unittest.main()
