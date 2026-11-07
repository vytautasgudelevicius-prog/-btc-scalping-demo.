"""Download aligned Binance public spot 1m archives for transfer research.

Proxy data only, not Kraken execution prices. ETH/EUR and SOL/EUR.
Fail closed on missing data or a contiguous run shorter than seven days.
"""
import csv
import io
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

SYMBOLS = ("ETHEUR", "SOLEUR")
MONTHS = ("2026-08", "2026-09", "2026-10")

def download(symbol):
    bars = []
    for month in MONTHS:
        filename = f"{symbol}-1m-{month}.zip"
        url = f"https://data.binance.vision/data/spot/monthly/klines/{symbol}/1m/{filename}"
        with urllib.request.urlopen(url, timeout=90) as response:
            blob = response.read()
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            with archive.open(filename.replace(".zip",".csv")) as file:
                for row in csv.reader(io.TextIOWrapper(file)):
                    stamp = int(row[0])
                    minute = int(stamp/(1_000_000 if stamp>10**14 else 1000)//60)
                    bars.append((minute,*row[1:6]))
    bars.sort(key=lambda r:r[0])
    segments, segment = [], []
    for bar in bars:
        if segment and bar[0] != segment[-1][0]+1:
            segments.append(segment)
            segment=[]
        segment.append(bar)
    if segment:
        segments.append(segment)
    if not segments:
        raise RuntimeError(f"No {symbol} data")
    longest=max(segments,key=len)
    if len(longest)<10080:
        raise RuntimeError(f"{symbol} contiguous coverage < 7 days")
    out=Path(f"research/history_{symbol.lower()}_proxy.csv")
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",newline="") as file:
        writer=csv.writer(file)
        writer.writerow(("timestamp","open","high","low","close","volume"))
        for minute,o,h,l,c,v in longest:
            writer.writerow((datetime.fromtimestamp(minute*60,timezone.utc).isoformat(),o,h,l,c,v))
    print(f"{symbol}: {len(longest)} consecutive bars -> {out}",flush=True)

if __name__=="__main__":
    for symbol in SYMBOLS:
        download(symbol)
