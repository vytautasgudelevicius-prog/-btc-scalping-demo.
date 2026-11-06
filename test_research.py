import sqlite3, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import bot
from research.study import read, rolling_ema, features, simulate, fill, net_pnl

class ResearchTests(unittest.TestCase):
 def fixture(self,side=1,**change):
  rows=[]
  for i in range(50):
   r=dict(timestamp=1800000000+i*60,open=100.,high=100.01,low=99.99,close=100.,volume=1.,signal=side,regime=side,continuous=True,range=.04,trend=.01*side,atr=.001,volume_ratio=1.,strength=.02)
   r.update(change);rows.append(r)
  return pd.DataFrame(rows)
 def run_case(self,d,**kw):return simulate(d,int(d.timestamp.iloc[1]),int(d.timestamp.iloc[-1])+60,**kw)
 def test_long_flat_costs(self):
  r,t=self.run_case(self.fixture());self.assertGreater(r['trades'],0);self.assertLess(r['net_pnl'],0);self.assertAlmostEqual(r['net_pnl'],sum(x['net_pnl'] for x in t))
 def test_short_flat_costs(self):
  r,t=self.run_case(self.fixture(-1));self.assertGreater(r['short_trades'],0);self.assertLess(r['net_pnl'],0)
 def test_long_stop(self):
  d=self.fixture();d.loc[2:,'low']=97;r,t=self.run_case(d);self.assertEqual(t[0]['reason'],'stop_intrabar');self.assertLess(t[0]['net_pnl'],0)
 def test_short_stop(self):
  d=self.fixture(-1);d.loc[2:,'high']=103;r,t=self.run_case(d);self.assertEqual(t[0]['reason'],'stop_intrabar')
 def test_long_target(self):
  d=self.fixture();d.loc[2:,'high']=105;r,t=self.run_case(d);self.assertEqual(t[0]['reason'],'target_intrabar');self.assertGreater(t[0]['net_pnl'],0)
 def test_short_target(self):
  d=self.fixture(-1);d.loc[2:,'low']=95;r,t=self.run_case(d);self.assertEqual(t[0]['reason'],'target_intrabar');self.assertGreater(t[0]['net_pnl'],0)
 def test_same_bar_stop_first(self):
  d=self.fixture();d.loc[2,'low']=95;d.loc[2,'high']=105;_,t=self.run_case(d);self.assertEqual(t[0]['reason'],'stop_intrabar')
 def test_gap_exit_next_observed_open(self):
  d=self.fixture();d.loc[2:,'timestamp']+=60;d.loc[2,'open']=90;_,t=self.run_case(d);self.assertEqual(t[0]['reason'],'data_gap');self.assertLess(t[0]['net_pnl'],-10)
 def test_time_exit(self):
  _,t=self.run_case(self.fixture());self.assertEqual(t[0]['reason'],'time');self.assertEqual(t[0]['timestamp'],1800000000+46*60)
 def test_end_liquidates(self):
  r,t=self.run_case(self.fixture().iloc[:4]);self.assertEqual(t[-1]['reason'],'period_end');self.assertAlmostEqual(r['net_pnl'],sum(x['net_pnl'] for x in t))
 def test_wide_spread_blocks(self):self.assertEqual(self.run_case(self.fixture(),spread=.002)[0]['trades'],0)
 def test_wrong_regime_blocks(self):self.assertEqual(self.run_case(self.fixture(regime=-1))[0]['trades'],0)
 def test_gap_warmup_blocks(self):self.assertEqual(self.run_case(self.fixture(continuous=False))[0]['trades'],0)
 def test_risk_size_reduces_loss(self):self.assertGreater(self.run_case(self.fixture(),variant='risk_size')[0]['net_pnl'],self.run_case(self.fixture())[0]['net_pnl'])
 def test_formula_both_fees(self):
  self.assertAlmostEqual(net_pnl(1,2,100,110,.008),16.64);self.assertAlmostEqual(net_pnl(-1,2,100,90,.008),16.96)
 def test_rolling_ema_matches_production(self):
  s=pd.Series(np.random.default_rng(9).uniform(90,110,1000))
  for n in (9,21,50,200):self.assertAlmostEqual(rolling_ema(s,n).iloc[-1],bot.ema(s.iloc[-719:].tolist(),n)[-1],places=10)
 def test_features_match_bot_filters(self):
  rng=np.random.default_rng(12);n=900
  close=100*np.exp(np.cumsum(rng.normal(0,.002,n)))
  d=pd.DataFrame(dict(timestamp=1800000000+np.arange(n)*60,open=close,high=close*1.003,low=close*.997,close=close,volume=rng.uniform(.5,2,n),trades=1))
  h=d.iloc[:1].copy();f=features(d,h)
  for i in range(719,900,11):
   cs=[[r.timestamp,r.open,r.high,r.low,r.close,0,r.volume,1] for r in d.iloc[i-718:i+1].itertuples()]
   side={"WAIT":0,"LONG":1,"SHORT":-1}[bot.signal(cs)]
   self.assertEqual(side,f.signal.iloc[i])
   for direction,k in (("LONG",1),("SHORT",-1)):
    self.assertEqual(bot.entry_quality(cs,direction),bool(f.range.iloc[i]>=.0214 and k*f.trend.iloc[i]>=.004))
   self.assertEqual(bot.liquidity_and_atr_ok(cs),bool(.0002<=f.atr.iloc[i]<=.015 and f.volume_ratio.iloc[i]>=.5))
 def test_future_does_not_change_features(self):
  d=self.fixture();d['trades']=1;h=d.iloc[:5].copy();h.timestamp=np.arange(5)*14400+1799900000
  before=features(d,h);d.loc[40:,'close']=999;after=features(d,h)
  pd.testing.assert_frame_equal(before.iloc[:40],after.iloc[:40])
 def test_unclosed_four_hour_not_visible(self):
  d=self.fixture();h=d.iloc[:1].copy();h.timestamp=d.timestamp.iloc[0]
  f=features(d,h);self.assertTrue(f.regime.isna().all())
 def test_migration_preserves_history_idempotently(self):
  db=sqlite3.connect(':memory:');bot.init(db);db.execute("INSERT INTO trades VALUES ('old','BUY',1,100,1,'legacy',1000)");db.execute('UPDATE state SET btc=1,entry=100,opened=10 WHERE id=1');db.commit();bot.init(db);bot.init(db)
  self.assertEqual(len(bot.positions(db)),1);self.assertIsNone(bot.positions(db)[0][4]);self.assertEqual(db.execute('SELECT COUNT(*) FROM trades').fetchone()[0],1)
 def test_unknown_pnl_excluded(self):
  db=sqlite3.connect(':memory:');bot.init(db);self.assertEqual(bot.trade_statistics(db,990)['max_dd'],1.)
 def test_nonfinite_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'d.csv';p.write_text('1800000000,100,101,99,nan,1,1\n')
   with self.assertRaises(ValueError):read(p,60)
 def test_duplicate_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'d.csv';p.write_text('1800000000,100,101,99,100,1,1\n'*2)
   with self.assertRaises(ValueError):read(p,60)
if __name__=='__main__':unittest.main()
