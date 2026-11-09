"""Causal snapshots from official Kraken quarterly OHLCVT BTC/EUR minute CSV ZIP."""
import argparse,csv,io,json,zipfile
from bisect import bisect_right
from datetime import datetime,timezone
from pathlib import Path
from research.build_kraken_replay import structure

def build(archive,output,days=90):
    with zipfile.ZipFile(archive) as z:
        names=[n for n in z.namelist() if n.upper().split('/')[-1] in ('XBTEUR_1.CSV','BTCEUR_1.CSV')]
        if len(names)!=1:raise ValueError(f'Expected exactly one BTC/EUR minute CSV, found {names}')
        with z.open(names[0]) as raw:
            rows=[]
            for line in csv.reader(io.TextIOWrapper(raw,encoding='utf-8-sig')):
                if len(line)<7:continue
                try:r=[int(float(line[0])),*map(float,line[1:7])]
                except ValueError:continue
                rows.append(r)
    rows=sorted({r[0]:r for r in rows}.values())
    if not rows:raise ValueError('No minute data')
    cutoff=rows[-1][0]-(days+3)*86400
    rows=[r for r in rows if r[0]>=cutoff]
    def aggregate(interval):
        groups={}
        for b in rows:groups.setdefault(b[0]//(60*interval)*(60*interval),[]).append(b)
        result=[]
        for t,group in sorted(groups.items()):
            if len(group)!=interval or any(x[0]!=t+j*60 for j,x in enumerate(group)):continue
            result.append([t,group[0][1],max(x[2] for x in group),min(x[3] for x in group),group[-1][4],0,sum(x[6] for x in group)])
        return result
    five=aggregate(5);fifteen=aggregate(15)
    times5=[x[0]+300 for x in five];times15=[x[0]+900 for x in fifteen]
    c5={};c15={};count=0;gaps=0;earliest=rows[-1][0]-days*86400
    with Path(output).open('w',encoding='utf-8') as out:
        for i,b in enumerate(rows):
            if i<60 or b[0]<earliest:continue
            t=b[0]+60;j=bisect_right(times5,t);k=bisect_right(times15,t)
            if j<35 or k<35:continue
            recent=rows[i-59:i+1]
            if any(recent[q+1][0]-recent[q][0]!=60 for q in range(59)):
                gaps+=1;continue
            if j not in c5:c5[j]=structure(five[max(0,j-250):j])
            if k not in c15:c15[k]=structure(fifteen[max(0,k-250):k])
            high=max(x[2] for x in recent);low=min(x[3] for x in recent)
            obj={'timestamp_utc':datetime.fromtimestamp(t,timezone.utc).isoformat(),
                 'minute_ohlc':{'open':b[1],'high':b[2],'low':b[3],'close':b[4]},
                 'structure':{'5':c5[j],'15':c15[k]},
                 'spread_pct':.05,'hourly_range_pct':(high/low-1)*100,
                 'decision':'OBSERVE_ONLY','orders_enabled':False,'data_source':'Kraken official OHLCVT'}
            out.write(json.dumps(obj,separators=(',',':'))+'\n');count+=1
    if count<10000:raise ValueError(f'Insufficient history: {count} observations')
    return {'snapshots':count,'skipped_missing_minute_windows':gaps,'days_requested':days,'output':str(output)}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('archive');a.add_argument('--days',type=int,default=90);a.add_argument('--output',default='/tmp/kraken_bulk_snapshots.jsonl')
    x=a.parse_args();print(json.dumps(build(x.archive,x.output,x.days)))
