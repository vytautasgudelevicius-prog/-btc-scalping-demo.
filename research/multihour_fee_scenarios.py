"""Research-only Kraken Pro spot tier-one fee scenarios; maker fills hypothetical."""
import json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.multihour_edge import run

def compare(rows):
    # Spread and slippage are assumptions, not guaranteed executions.
    # maker/maker and maker/taker scenarios assume both legs fill as specified.
    scenarios = {
        "taker_taker_tier1": (.008,.008),
        "maker_taker_tier1": (.004,.008),
        "maker_maker_tier1": (.004,.004),
        "taker_taker_tier2": (.006,.006),
        "taker_taker_tier3": (.0038,.0038),
    }
    results={}
    for name,(entry_fee,exit_fee) in scenarios.items():
        # The strategy runner accepts symmetric fee per side.
        result=run(rows,fee_per_side=(entry_fee+exit_fee)/2,
                   spread_bps=5,slippage_bps=2)
        results[name]={"entry_fee_pct":100*entry_fee,
                       "exit_fee_pct":100*exit_fee,
                       "roundtrip_cost_pct":result["roundtrip_cost_pct"],
                       "selected_on_validation":result["selected_on_validation"],
                       "untouched_test":result["untouched_test"],
                       "decision":result["decision"]}
    return {"method":"kraken_pro_spot_tier_sensitivity",
            "scenarios":results,
            "decision":"RESEARCH_ONLY",
            "warning":"Fee tiers are public schedules, not confirmed account-specific rates. Maker fill probability, adverse selection, margin costs for shorts, and venue execution are NOT modeled. No deployment."}

if __name__=="__main__":
    print(json.dumps(compare(read_csv(sys.argv[1])),indent=2))
