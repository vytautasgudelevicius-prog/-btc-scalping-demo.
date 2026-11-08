"""Sensitivity of six-month 4h strategy to Kraken Pro fee tiers.
Research only; maker fills, SHORT borrow and slippage remain assumptions.
"""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.extended_swing_edge import run

def compare(rows):
    tiers={
        "tier1_taker_taker":(.008,.008),
        "tier1_maker_taker":(.004,.008),
        "tier1_maker_maker":(.004,.004),
        "tier2_taker_taker":(.006,.006),
        "tier3_taker_taker":(.0038,.0038),
    }
    result={}
    for name,(entry,exit) in tiers.items():
        report=run(rows,fee_per_side=(entry+exit)/2)
        result[name]={"cost_pct":report["roundtrip_cost_pct"],
                      "validation_selected":report["selected_on_validation"],
                      "untouched_test":report["untouched_test"],
                      "decision":report["decision"]}
    return {"scenarios":result,"decision":"RESEARCH_ONLY",
            "warning":"No automatic DEMO or Railway promotion. Proxy spot history does not validate SHORT fills or financing."}
if __name__=="__main__":
    print(json.dumps(compare(read_csv(sys.argv[1])),indent=2))
