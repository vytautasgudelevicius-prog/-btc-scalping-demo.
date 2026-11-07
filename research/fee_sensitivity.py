"""Research-only sensitivity analysis; costs are hypothetical, not exchange quotes.

All candidates are selected on validation, then measured once on untouched
holdout. Never pick a cost scenario using holdout performance.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.auto_optimize import optimize

SCENARIOS = (
    ("low_fee_hypothetical", .0008, 5, 2),
    ("medium_fee_hypothetical", .0026, 5, 2),
    ("current_high_fee_assumption", .008, 5, 2),
)

def compare(rows):
    results = {}
    for name, fee, spread, slip in SCENARIOS:
        result = optimize(rows, fee_per_side=fee, spread_bps=spread,
                          slippage_bps=slip)
        results[name] = {
            "fee_per_side_pct": round(fee * 100, 4),
            "cost_roundtrip_pct": result["cost_roundtrip_pct"],
            "selected_parameters": result["parameters"],
            "validation": result["validation"],
            "untouched_test": result["untouched_test"],
            "decision": result["decision"],
        }
    return {
        "method": "fee_sensitivity_validation_selected",
        "scenarios": results,
        "decision": "RESEARCH_ONLY",
        "warning": "Hypothetical fee scenarios; verify actual venue, order type, "
                   "spread, slippage and fill behavior. Never deploy from this report.",
    }

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python research/fee_sensitivity.py BTC.csv")
    print(json.dumps(compare(read_csv(sys.argv[1])), indent=2))
