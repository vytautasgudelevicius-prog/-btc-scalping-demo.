"""Create compact, reproducible input subset outside the repository."""
import json,hashlib,zipfile
from pathlib import Path
from study import read,features
root=Path(__file__).resolve().parents[2]/'btc-data'
d,h=read(root/'XBTEUR_1.csv',60),read(root/'XBTEUR_240.csv',14400)
lo,hi=1727740800,1790812800
# Keep 120d warmup, sufficient for the 719 completed 4h bars used by the API.
d=d[d.timestamp.between(lo-120*86400,hi-1)].reset_index(drop=True)
h=h[h.timestamp.between(lo-120*86400,hi-1)].reset_index(drop=True)
# Record observed regime coverage. Regime is known at decision time, not from future returns.
f=features(d,h);q=f[f.timestamp>=lo]
stats={str(k):{'candles':len(v),'ema_crossovers':int(v.signal.ne(0).sum())} for k,v in q.groupby('regime')}
Path('research/regime_coverage.json').write_text(json.dumps(stats,indent=2))
for name,x in [('BTC_EUR_1m.csv',d),('BTC_EUR_4h.csv',h)]:x.to_csv(root/name,index=False,header=False)
print(stats)
print('subset',len(d),len(h))
