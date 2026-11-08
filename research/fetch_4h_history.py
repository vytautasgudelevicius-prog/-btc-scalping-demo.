"""Download 36 completed months of Binance BTC/EUR 4h spot candles (Kraken proxy).
Fail closed on gaps, duplicate timestamps, invalid OHLC and insufficient coverage.
"""
import csv,io,os,urllib.request,zipfile
from datetime import datetime,timezone
from pathlib import Path
from research.fetch_proxy_history import completed_months

OUT=Path("research/btceur_4h_36months.csv")
def main():
    months=completed_months(count=int(os.environ.get("BTC_HISTORY_MONTHS","36")))
    rows=[]
    for month in months:
        filename=f"BTCEUR-4h-{month}.zip"
        url="https://data.binance.vision/data/spot/monthly/klines/BTCEUR/4h/"+filename
        with urllib.request.urlopen(url,timeout=90) as response:
            raw=response.read()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            with archive.open(filename.replace(".zip",".csv")) as f:
                for record in csv.reader(io.TextIOWrapper(f)):
                    stamp=int(record[0])
                    seconds=stamp/(1000000 if stamp>10**14 else 1000)
                    timestamp=int(seconds)
                    o,h,l,c,v=map(float,record[1:6])
                    if not (0<l<=min(o,c)<=max(o,c)<=h and v>=0):
                        raise ValueError(f"Invalid OHLCV {month}")
                    rows.append((timestamp,o,h,l,c,v))
        print(f"Fetched {month}",flush=True)
    rows.sort()
    if len(rows)<3500: raise ValueError("Insufficient 4h coverage")
    for a,b in zip(rows,rows[1:]):
        if b[0]-a[0]!=14400: raise ValueError(f"Noncontiguous history at {a[0]} / {b[0]}")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open("w",newline="") as f:
        w=csv.writer(f)
        w.writerow(["timestamp","open","high","low","close","volume"])
        for t,*values in rows:
            w.writerow([datetime.fromtimestamp(t,timezone.utc).isoformat(),*values])
    print(f"Saved {len(rows)} contiguous 4h bars, months={len(months)}",flush=True)
if __name__=="__main__":main()
