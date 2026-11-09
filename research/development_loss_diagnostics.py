"""Read-only development-period loss attribution by trade direction and UTC hour.

This diagnostic does not select parameters or access the independent holdout.
"""
import argparse,json,tempfile
from collections import defaultdict
from pathlib import Path
from research.forward_fill_backtest import run

def diagnose(path):
    rows=Path(path).read_text(encoding='utf-8').splitlines()
    cut=int(len(rows)*.7)
    boundary=json.loads(rows[cut])['timestamp_utc'][:10]
    while cut<len(rows) and json.loads(rows[cut])['timestamp_utc'].startswith(boundary):cut+=1
    with tempfile.TemporaryDirectory() as folder:
        p=Path(folder)/'development.jsonl';p.write_text('\n'.join(rows[:cut])+'\n',encoding='utf-8')
        result=run(p)
    trades=result['trades']
    def group(fn):
        groups=defaultdict(lambda:{'trades':0,'wins':0,'net_pnl_eur':0.,'commission_eur':0.})
        for t in trades:
            x=groups[fn(t)];x['trades']+=1;x['wins']+=int(t['pnl_eur']>0)
            x['net_pnl_eur']+=t['pnl_eur'];x['commission_eur']+=t['commission_eur']
        for x in groups.values():
            x['net_pnl_eur']=round(x['net_pnl_eur'],4)
            x['commission_eur']=round(x['commission_eur'],4)
        return dict(sorted(groups.items()))
    return {'sample':'development_only','trades':len(trades),'by_direction':group(lambda t:t['direction']),
            'by_entry_utc_hour':group(lambda t:t['entry_time'][11:13]),
            'by_exit_reason':group(lambda t:t['exit_reason']),
            'note':'Descriptive diagnostics only. No filters selected, no holdout inspected.'}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('snapshots')
    print(json.dumps(diagnose(a.parse_args().snapshots),indent=2))
