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
        while True:
            try:
                report=observe()
                settled=settle(shadow,report)
                inserted=record(shadow,report)
                paper_result=paper_tick(paper,report)
                print(json.dumps({"mode":"UNIFIED_PAPER_ONLY","shadow":{"inserted":inserted,"settled":settled,"latest":report,"summary":summary(shadow)},"paper":paper_result,"real_orders_enabled":False}),flush=True)
            except Exception as exc:
                print(json.dumps({"error":str(exc),"real_orders_enabled":False}),flush=True)
            time.sleep(20)
if __name__=="__main__":main()
