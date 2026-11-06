"""Extract BTC/EUR 1m bars from official Kraken OHLCVT ZIP, without loading archive into RAM.

Usage: python import_kraken_archive.py Kraken_OHLCVT_2026Q3.zip output.csv
Kraken files have no header: epoch,open,high,low,close,volume,trades.
No synthetic candles are inserted; backtest.py rejects gaps.
"""
import csv
import io
import sys
import zipfile

def main():
    if len(sys.argv)!=3:
        raise SystemExit("Usage: python import_kraken_archive.py archive.zip output.csv")
    with zipfile.ZipFile(sys.argv[1]) as z:
        matches=[n for n in z.namelist() if n.rsplit("/",1)[-1].upper() in ("XBTEUR_1.CSV","XXBTEUR_1.CSV","BTCEUR_1.CSV")]
        if len(matches)!=1:
            raise RuntimeError("Expected exactly one BTC/EUR 1m CSV; found: "+str(matches))
        with z.open(matches[0]) as src,open(sys.argv[2],"w",newline="",encoding="utf-8") as dst:
            reader=csv.reader(io.TextIOWrapper(src,encoding="utf-8-sig"))
            writer=csv.writer(dst)
            writer.writerow(("timestamp","open","high","low","close","volume"))
            count=0
            for row in reader:
                if len(row)<7:
                    raise ValueError("Invalid Kraken row")
                writer.writerow((row[0],row[1],row[2],row[3],row[4],row[5]))
                count+=1
    print(f"Extracted {count} raw BTC/EUR 1m bars. Validate continuity before testing.")

if __name__=="__main__":
    main()
