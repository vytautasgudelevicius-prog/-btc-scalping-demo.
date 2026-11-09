"""Development-only entry filter diagnostics. Never select by holdout results."""
import argparse,json
from pathlib import Path
from research.forward_fill_backtest import run

def study(path):
    rows=Path(path).read_text(encoding='utf-8').splitlines()
    cut=int(len(rows)*.7)
    boundary=json.loads(rows[cut])['timestamp_utc'][:10]
    while cut<len(rows) and json.loads(rows[cut])['timestamp_utc'].startswith(boundary):cut+=1
    if cut>=len(rows):raise ValueError('No holdout')
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        dev=Path(d)/'development.jsonl';dev.write_text('\n'.join(rows[:cut])+'\n',encoding='utf-8')
        candidates=[]
        for volume,trend in ((.8,0.),(1.,0.),(1.2,0.),(.8,.02),(.8,.05),(1.,.02),(1.2,.02)):
            s=run(dev,min_volume=volume,min_trend_gap_pct=trend)
            candidates.append({'volume_min':volume,'ema_gap_min_pct':trend,'trades':s['closed_trades'],'wins':s['wins'],'net_pnl_eur':s['net_pnl_eur'],'max_drawdown_pct':s['max_realized_drawdown_pct']})
        eligible=[x for x in candidates if x['trades']>=10 and x['net_pnl_eur']>0]
        chosen=max(eligible,key=lambda x:(x['net_pnl_eur'],-x['max_drawdown_pct'])) if eligible else None
        print(json.dumps({'development_candidates':candidates,'selected_for_holdout':chosen,'policy':'No positive development candidate with >=10 trades means no holdout selection; do not deploy.'},indent=2))
        if chosen:
            hold=Path(d)/'holdout.jsonl';hold.write_text('\n'.join(rows[cut:])+'\n',encoding='utf-8')
            s=run(hold,min_volume=chosen['volume_min'],min_trend_gap_pct=chosen['ema_gap_min_pct'])
            print(json.dumps({'single_independent_holdout':{'trades':s['closed_trades'],'wins':s['wins'],'net_pnl_eur':s['net_pnl_eur'],'max_drawdown_pct':s['max_realized_drawdown_pct']},'deployment_approved':False},indent=2))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('snapshots');study(a.parse_args().snapshots)
