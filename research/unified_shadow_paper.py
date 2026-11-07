"""One BTC/EUR process: forward shadow evidence plus isolated virtual trades.
Only Kraken public market reads; NEVER submits exchange orders.
"""
import json, os, sqlite3, time
from pathlib import Path
from research.kraken_shadow_observer import observe
from research.kraken_shadow_forward import initialize, settle, record, summary
from research.isolated_paper_experiment import init as paper_init, tick as paper_tick

SHADOW="/data/kraken_shadow.sqlite3"
PAPER="/data/experiment.sqlite3"

def main():
    Path("/data").mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(SHADOW,timeout=30) as shadow, sqlite3.connect(PAPER,timeout=30) as paper:
        initialize(shadow)
        paper_init(paper)
        shadow.execute("CREATE TABLE IF NOT EXISTS signal_diagnostics(candle TEXT PRIMARY KEY, timestamp TEXT, signal TEXT, reasons TEXT, eligible INTEGER)")
        shadow.commit()
        shadow.execute("CREATE TABLE IF NOT EXISTS rejection_audit (candle TEXT PRIMARY KEY, reasons TEXT NOT NULL, eligible INTEGER NOT NULL)")
        shadow.commit()
        while True:
            try:
                report=observe()
                reasons=report.get("rejection_reasons",[])
                shadow.execute("INSERT OR IGNORE INTO rejection_audit(candle,reasons,eligible) VALUES(?,?,?)",
                    (report["last_completed_candle"],json.dumps(reasons),int(report["context_candidate"])))
                shadow.commit()
                audit_rows=shadow.execute("SELECT reasons,eligible FROM rejection_audit").fetchall()
                counts={"candles":len(audit_rows),"eligible":sum(x[1] for x in audit_rows)}
                for raw,_ in audit_rows:
                    for reason in json.loads(raw):
                        counts[reason]=counts.get(reason,0)+1
                settled=settle(shadow,report)
                inserted=record(shadow,report)
                paper_result=paper_tick(paper,report)
                reasons=report.get("rejection_reasons",[])
                shadow.execute("INSERT OR IGNORE INTO signal_diagnostics(candle,timestamp,signal,reasons,eligible) VALUES(?,?,?,?,?)",(report["last_completed_candle"],report["timestamp_utc"],report["ema_signal"],json.dumps(reasons),int(report["context_candidate"])))
                shadow.commit()
                rows=shadow.execute("SELECT reasons,eligible FROM signal_diagnostics").fetchall()
                from collections import Counter
                counts=Counter(reason for encoded,_ in rows for reason in json.loads(encoded))
                diagnostics={"completed_candles":len(rows),"eligible":sum(eligible for _,eligible in rows),"rejections":dict(counts)}
                print(json.dumps({"mode":"UNIFIED_PAPER_ONLY","shadow":{"inserted":inserted,"settled":settled,"latest":report,"summary":summary(shadow)},"paper":paper_result,"rejection_stats":counts,"real_orders_enabled":False}),flush=True)
            except Exception as exc:
                print(json.dumps({"error":str(exc),"real_orders_enabled":False}),flush=True)
            time.sleep(20)
if __name__=="__main__":main()
