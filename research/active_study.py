"""Isolated candle replay; never imports live state or sends orders.
Signals mirror bot.py; fills approximate 15-second bid/ask polling with 1m OHLC.
"""
import argparse, hashlib, json, math
from pathlib import Path
import numpy as np
import pandas as pd

COLS=['timestamp','open','high','low','close','volume','trades']
def read(path, interval):
    d=pd.read_csv(path,header=None,names=COLS)
    if not np.isfinite(d.to_numpy()).all(): raise ValueError('Nonfinite OHLCVT')
    if d.timestamp.duplicated().any() or not d.timestamp.is_monotonic_increasing: raise ValueError('Duplicate/unsorted timestamps')
    if ((d.timestamp%interval)!=0).any(): raise ValueError('Off-grid timestamps')
    if ((d[['open','high','low','close']]<=0).any(axis=1)|(d.volume<0)|(d.high<d[['open','close']].max(axis=1))|(d.low>d[['open','close']].min(axis=1))|(d.high<d.low)).any(): raise ValueError('Invalid OHLCVT')
    return d

def rolling_ema(s,n,w=719):
    e=s.ewm(span=n,adjust=False).mean()
    return e+(1-2/(n+1))**(w-1)*(s.shift(w-1)-e.shift(w-1)).fillna(0)

def features(d,h):
    d=d.copy();c=d.close
    fast,slow=rolling_ema(c,9),rolling_ema(c,21)
    d['signal']=np.select([(fast.shift()<=slow.shift())&(fast>slow),(fast.shift()>=slow.shift())&(fast<slow)],[1,-1],0)
    d['trend']=c/c.shift(60)-1
    d['range']=d.high.rolling(60).max()/d.low.rolling(60).min()-1
    tr=pd.concat([d.high-d.low,(d.high-c.shift()).abs(),(d.low-c.shift()).abs()],axis=1).max(axis=1)
    d['atr']=tr.rolling(14).mean()/c
    d['volume_ratio']=d.volume/d.volume.shift().rolling(30).mean()
    d['continuous']=d.timestamp.diff().eq(60).rolling(90).sum().eq(90)
    f,s=rolling_ema(h.close,50),rolling_ema(h.close,200)
    h=h.copy();h['regime']=np.select([(h.close>f)&(f>s*1.005),(h.close<f)&(f<s*.995)],[1,-1],0)
    h.loc[h.index<209,'regime']=0
    h['strength']=(f/s-1).abs();h['available']=h.timestamp+14400
    # A 4h candle becomes visible only after it closes.
    d['decision']=d.timestamp+60
    d=pd.merge_asof(d,h[['available','regime','strength']],left_on='decision',right_on='available',direction='backward')
    d.loc[d.decision-d.available>14400,'regime']=0
    return d

VARIANTS=['baseline','risk_size','portfolio_risk','atr_stop','atr_target','trend_strength','liquidity','net_reward_risk','cooldown','adverse_pause']
def fill(mid,side,entry,spread,slip):
    sign=side if entry else -side
    return mid*(1+sign*spread/2)*(1+sign*slip)
def net_pnl(side,qty,entry,exit,fee):return side*qty*(exit-entry)-qty*(entry+exit)*fee

def simulate(d,start,end,variant='baseline',fee=.008,spread=.0005,slip=.0002):
    active = variant in ('active', 'active_5m', 'active_maker')
    cash=1000.;pos=[];trades=[];peak=1000.;dd=0.;last=-1e20;day=None;day_start=1000.;entries=0;halt=False;curve=[]
    def equity(mid):
        # Exact production marked_equity formula (small fee/slippage cross-term difference from execution).
        amount=sum(p['side']*p['qty'] for p in pos)
        return cash+amount*mid*((1-spread/2)*(1-fee-slip) if amount>=0 else (1+spread/2)*(1+fee+slip))
    def close(p,mid,reason,t):
        nonlocal cash
        price=fill(mid,p['side'],False,spread,slip);cost=p['qty']*price*fee
        cash+=p['side']*p['qty']*price-cost
        net=p['side']*p['qty']*(price-p['entry'])-p['fee']-cost
        trades.append(dict(timestamp=int(t),side=p['side'],net_pnl=net,fees=p['fee']+cost,reason=reason,
                           execution_cost=p['qty']*(abs(p['entry']-p['mid'])+abs(price-mid))))
        pos.remove(p)
    rows=list(d.itertuples(index=False))
    for i in range(1,len(rows)):
        r,prev=rows[i],rows[i-1];t=r.timestamp
        if t<start:continue
        if t>=end:break
        mid=r.open;eq=equity(mid);today=int(t//86400)
        if today!=day:day=today;day_start=eq;entries=0;halt=False
        if variant=='adverse_pause' and eq<day_start*.985:halt=True
        closed=False
        # Exit existing positions before considering the just-completed signal.
        for p in pos[:]:
            quote=mid*(1-p['side']*spread/2);ratio=p['side']*(quote/p['entry']-1)
            reason='stop' if ratio<=-p['stop'] else 'target' if ratio>=p['take'] else 'time' if t-p['opened']>=(900 if active else 2700) else None
            if t-prev.timestamp>60:reason='data_gap'
            if reason:close(p,mid,reason,t);closed=True
        eq=equity(mid);gross=sum(p['qty']*mid*(1-p['side']*spread/2) for p in pos)
        side=int(prev.signal);cool=300 if active else (1800 if variant=='cooldown' else 900)
        ok=(not closed and not halt and eq>=day_start*.97 and len(pos)<3 and entries<(16 if active else 8) and t-last>=cool and side!=0 and (side!=-prev.regime if active else side==prev.regime) and prev.continuous and t-prev.timestamp==60 and spread/(1+spread/2)<=.0015)
        ok=ok and (not pos or pos[0]['side']==side)
        if variant=='active_5m':ok=ok and side==prev.trend5
        if not active:ok=ok and prev.range>=2*(.008+.0002)+.005 and side*prev.trend>=.004 and .0002<=prev.atr<=.015 and prev.volume_ratio>=.5
        if variant=='trend_strength':ok=ok and prev.strength>=.01
        if variant=='liquidity':ok=ok and prev.volume_ratio>=1 and spread<=.0005
        stop=max(.003,min(.02,3*prev.atr)) if variant=='atr_stop' else .012
        take=max(.03,6*prev.atr) if variant=='atr_target' else .03
        if variant=='net_reward_risk':ok=ok and (take-2*fee-spread-2*slip)/(stop+2*fee+spread+2*slip)>=1.5
        if ok:
            budget=min(max(0,eq)*.1,max(0,eq*.3-gross),max(0,cash)*.1)
            risk=stop+2*fee+spread+2*slip
            if variant in ('risk_size','portfolio_risk'):
                budget=min(budget,eq*.0025/risk)
            if variant=='portfolio_risk':
                existing=sum(p['qty']*p['entry']*(p['stop']+2*fee+spread+2*slip) for p in pos)
                budget=min(budget,max(0,eq*.005-existing)/risk)
            if budget>5:
                entry_fee = .004 if variant=='active_maker' else fee
                price = mid*(1-side*spread/2) if variant=='active_maker' else fill(mid,side,True,spread,slip)
                # One-bar post-only limit proxy. A mere touch is insufficient:
                # require 1bp trade-through. Queue/latency remain unobserved.
                filled = (variant!='active_maker' or
                          (r.low<price*(1-.0001) if side==1 else r.high>price*(1+.0001)))
                if filled:
                    qty=budget/(price*(1+entry_fee)) if side==1 else budget/price
                    cost=qty*price*entry_fee;cash-=side*qty*price+cost
                    pos.append(dict(side=side,qty=qty,entry=price,fee=cost,opened=t,stop=stop,take=take,mid=mid));entries+=1;last=t
        # Intrabar execution is a conservative approximation: stop first if both touched.
        for p in pos[:]:
            stop_mid=p['entry']*(1-p['side']*p['stop'])/(1-p['side']*spread/2)
            target_mid=p['entry']*(1+p['side']*p['take'])/(1-p['side']*spread/2)
            stop_hit=r.low<=stop_mid if p['side']==1 else r.high>=stop_mid
            target_hit=r.high>=target_mid if p['side']==1 else r.low<=target_mid
            if stop_hit:close(p,stop_mid,'stop_intrabar',t+59)
            elif target_hit:close(p,target_mid,'target_intrabar',t+59)
        eq=equity(r.close);peak=max(peak,eq);dd=max(dd,(peak-eq)/peak);curve.append((t,eq))
    if curve:
        lastrow=next(r for r in reversed(rows) if start<=r.timestamp<end)
        for p in pos[:]:close(p,lastrow.close,'period_end',lastrow.timestamp+59)
        peak=max(peak,cash);dd=max(dd,(peak-cash)/peak)
    wins=[x['net_pnl'] for x in trades if x['net_pnl']>0];loss=[x['net_pnl'] for x in trades if x['net_pnl']<0]
    result=dict(trades=len(trades),win_rate_pct=100*len(wins)/len(trades) if trades else None,net_pnl=cash-1000,
      profit_factor=sum(wins)/-sum(loss) if loss else None,avg_win=np.mean(wins) if wins else None,avg_loss=np.mean(loss) if loss else None,
      max_drawdown_pct=dd*100,fees=sum(x['fees'] for x in trades),spread_slippage=sum(x['execution_cost'] for x in trades),
      long_trades=sum(x['side']==1 for x in trades),short_trades=sum(x['side']==-1 for x in trades),gap_exits=sum(x['reason']=='data_gap' for x in trades))
    assert math.isclose(sum(x['net_pnl'] for x in trades),cash-1000,abs_tol=1e-7)
    return result,trades

def main():
    p=argparse.ArgumentParser();p.add_argument('minute');p.add_argument('fourhour');p.add_argument('--output',default='research/results.json');a=p.parse_args()
    d,h=read(a.minute,60),read(a.fourhour,14400)
    utc=lambda x:int(pd.Timestamp(x,tz='UTC').timestamp())
    lo,hi=utc('2024-10-01'),utc('2026-10-01')
    d=d[d.timestamp.between(lo-120*86400,hi-1)].reset_index(drop=True);h=h[h.timestamp<hi].reset_index(drop=True)
    q=d[d.timestamp>=lo];delta=q.timestamp.diff().dropna()
    quality=dict(start=str(pd.to_datetime(q.timestamp.iloc[0],unit='s',utc=True)),end=str(pd.to_datetime(q.timestamp.iloc[-1],unit='s',utc=True)),candles=len(q),missing_minutes=int((delta/60-1).sum()),gap_events=int((delta>60).sum()),duplicates=0,four_hour_candles=int(h.timestamp.between(lo,hi-1).sum()),synthetic_candles=0,
                 hashes={str(Path(f).name):hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in (a.minute,a.fourhour)})
    d=features(d,h)
    periods={'train':(lo,utc('2025-10-01')),'validation':(utc('2025-10-01'),utc('2026-04-01')),'holdout':(utc('2026-04-01'),hi)}
    results={};ledger={}
    # Candidate selection uses validation only. Holdout is evaluated once after selection.
    for v in VARIANTS:
        results[v]={}
        for name in ('train','validation'):
            results[v][name],_=simulate(d,*periods[name],v)
        print(v,results[v]['validation'],flush=True)
    eligible=[v for v in VARIANTS[1:] if results[v]['validation']['trades']>=30 and results[v]['validation']['max_drawdown_pct']<=results['baseline']['validation']['max_drawdown_pct']]
    chosen=max(eligible,key=lambda v:results[v]['validation']['net_pnl']) if eligible else 'risk_size'
    for v in ('baseline',chosen):
        results[v]['holdout'],ledger[v]=simulate(d,*periods['holdout'],v)
    sensitivity={}
    for v in ('baseline',chosen):
        sensitivity[v]={}
        for label,fee,spread,slip in [('low',.006,.0002,.0001),('base',.008,.0005,.0002),('stress',.01,.0015,.0005)]:
            sensitivity[v][label],_=simulate(d,*periods['holdout'],v,fee,spread,slip)
    out=dict(quality=quality,periods=periods,variants=results,selected=chosen,selection_eligible=eligible,sensitivity=sensitivity,holdout_trades=ledger,
             deployment_allowed=False,limitation='1m OHLC cannot reproduce historical 15-second bid/ask polling. No observed spreads/order book or short financing. Gaps prevent entries and trigger next-observed-open exits. No exact execution parity.')
    Path(a.output).write_text(json.dumps(out,indent=2,allow_nan=False))
if __name__=='__main__':main()
