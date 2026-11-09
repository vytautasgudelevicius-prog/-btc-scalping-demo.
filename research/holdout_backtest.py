"""Fixed-parameter chronological holdout; no tuning on holdout."""
import argparse,json,tempfile
from pathlib import Path
from research.forward_fill_backtest import run

def evaluate(path,fee=.0005,slip=.0002,stop=.0025,rr=1.5):
    rows=Path(path).read_text(encoding='utf-8').splitlines()
    if len(rows)<10000:raise ValueError('At least 10000 historical minutes required')
    cut=int(len(rows)*.7)
    boundary=json.loads(rows[cut])['timestamp_utc'][:10]
    while cut<len(rows) and json.loads(rows[cut])['timestamp_utc'].startswith(boundary):cut+=1
    if cut>=len(rows):raise ValueError('Holdout is empty')
    with tempfile.TemporaryDirectory() as folder:
        result={}
        for name,part in [('development',rows[:cut]),('untouched_holdout',rows[cut:])]:
            file=Path(folder)/(name+'.jsonl');file.write_text('\n'.join(part)+'\n',encoding='utf-8')
            summary=run(file,fee=fee,slip=slip,stop_pct=stop,rr=rr)
            summary.pop('trades',None)
            result[name]=summary
    result['fixed_parameters']={'fee_one_way':fee,'slippage_one_way':slip,'min_stop_pct':stop*100,'net_rr':rr}
    result['limitations']='Hypothetical commission tier and synthetic spread. Holdout untouched by strategy tuning; no proof of future returns.'
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('snapshots');x=a.parse_args()
    print(json.dumps(evaluate(x.snapshots),indent=2))
