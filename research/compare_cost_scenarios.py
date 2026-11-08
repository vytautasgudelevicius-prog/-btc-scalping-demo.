"""Compare fixed fee/slippage scenarios without changing the running paper bot.

Requires chronological point-in-time JSONL observations, never future-computed
indicators. This is sensitivity analysis, not parameter optimization or proof.
"""
import argparse
import json
from research.offline_replay import replay


def compare(path):
    scenarios = (
        ("configured", None, None),
        ("fee_0_40pct", 0.004, 0.0002),
        ("fee_0_20pct", 0.002, 0.0002),
        ("fee_0_10pct", 0.001, 0.0002),
        ("higher_slippage", None, 0.001),
    )
    results = {}
    for name, fee, slip in scenarios:
        results[name] = replay(path, fee=fee, slip=slip)
    for result in results.values():
        result["evidence_sufficient"] = result["closed_trades"] >= 100
    return {"scenarios": results,
            "note": "Fixed cost sensitivity only. No claim of optimized or profitable strategy."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshots")
    args = parser.parse_args()
    print(json.dumps(compare(args.snapshots), indent=2))


if __name__ == "__main__":
    main()
