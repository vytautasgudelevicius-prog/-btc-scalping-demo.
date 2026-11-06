"""Offline backtest smoke tests. Run: python -m unittest test_backtest.py"""
import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from backtest import read_csv, evaluate

class BacktestTests(unittest.TestCase):
    def make_csv(self, *, missing=False, bad_ohlc=False):
        tmp=tempfile.TemporaryDirectory()
        path=Path(tmp.name)/"candles.csv"
        start=dt.datetime(2026,1,1,tzinfo=dt.timezone.utc)
        with path.open("w",newline="") as f:
            w=csv.writer(f)
            w.writerow(["timestamp","open","high","low","close","volume"])
            for i in range(1000):
                t=start+dt.timedelta(minutes=i+(1 if missing and i>=500 else 0))
                price=50000+i*.01
                high=price+2
                if bad_ohlc and i==999:
                    high=price-1
                w.writerow([t.isoformat(),price,high,price-2,price,1])
        return tmp,path

    def test_flat_market_no_trades(self):
        tmp,path=self.make_csv()
        with tmp:
            rows=read_csv(path)
            result=evaluate(rows)
            self.assertEqual(result["trades"],0)
            self.assertEqual(result["ending_cash"],1000)
            self.assertEqual(result["max_drawdown_pct"],0)

    def test_missing_minute_rejected(self):
        tmp,path=self.make_csv(missing=True)
        with tmp,self.assertRaises(ValueError):
            read_csv(path)

    def test_invalid_last_candle_rejected(self):
        tmp,path=self.make_csv(bad_ohlc=True)
        with tmp,self.assertRaises(ValueError):
            read_csv(path)

    def test_holdout_starts_after_split(self):
        tmp,path=self.make_csv()
        with tmp:
            rows=read_csv(path)
            result=evaluate(rows,start_bar=700)
            self.assertEqual(result["trades"],0)

if __name__=="__main__":
    unittest.main()
