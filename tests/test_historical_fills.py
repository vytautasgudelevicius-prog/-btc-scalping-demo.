"""Regression tests for historical execution: causal entries and conservative exits."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from research.forward_fill_backtest import run

def report(i, op, high, low, close):
    t=datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=i)
    m5={"ema9":102,"ema21":100,"close":100,"support":98,"resistance":110,
        "higher_lows":True,"lower_highs":False,"volume_ratio":2,
        "upper_wick_ratio":0,"lower_wick_ratio":0,"false_break_up":False,"false_break_down":False}
    m15=dict(m5,resistance=110)
    return {"timestamp_utc":t.isoformat(),"minute_ohlc":{"open":op,"high":high,"low":low,"close":close},
            "structure":{"5":m5,"15":m15},"spread_pct":.01,"hourly_range_pct":5}

def simulate(rows,**kw):
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/"candles.jsonl"
        path.write_text("".join(json.dumps(x)+"\n" for x in rows),encoding="utf-8")
        return run(path,fee=0,slip=0,rr=1,**kw)

class HistoricalFillTests(unittest.TestCase):
    def test_entry_not_filled_on_signal_candle(self):
        result=simulate([report(0,100,101,99,100),report(1,100,100,100,100),report(2,100,110,100,110)])
        self.assertEqual(result["closed_trades"],1)
        self.assertEqual(result["trades"][0]["entry_time"],report(1,100,100,100,100)["timestamp_utc"])
        self.assertEqual(result["trades"][0]["exit_reason"],"TARGET")
    def test_stop_precedes_target_within_same_bar(self):
        result=simulate([report(0,100,101,99,100),report(1,100,100,100,100),report(2,100,111,95,100)])
        self.assertEqual(result["trades"][0]["exit_reason"],"STOP_FIRST")
        self.assertLess(result["net_pnl_eur"],0)
    def test_gap_through_stop_is_worse_than_stop_price(self):
        base=[report(0,100,101,99,100),report(1,100,100,100,100)]
        stop=simulate(base+[report(2,100,100,95,95)])
        gap=simulate(base+[report(2,90,91,89,90)])
        self.assertEqual(gap["trades"][0]["exit_reason"],"STOP_GAP")
        self.assertLess(gap["net_pnl_eur"],stop["net_pnl_eur"])
    def test_requires_ohlc(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"r.jsonl"
            path.write_text('{"timestamp_utc":"2026-01-01T00:00:00+00:00"}\n')
            with self.assertRaises(ValueError):run(path)

if __name__=="__main__":unittest.main()
