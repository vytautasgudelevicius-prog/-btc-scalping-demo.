"""Read-only profitability sensitivity study from actual forward-settled observations.

No synthetic trades, no live orders, and no relaxation of entry filters.
Usage: python -m research.cost_sensitivity [sqlite_path]
"""
import json
import sqlite3
import sys
from pathlib import Path

# Assumed fee per side and slippage per side. These are hypotheses, not verified rates.
SCENARIOS = {
    "base_0.80pct_fee": (0.008, 0.0002),
    "fee_0.40pct": (0.004, 0.0002),
    "fee_0.20pct": (0.002, 0.0002),
    "fee_0.10pct": (0.001, 0.0002),
    "zero_fee_reference_only": (0.0, 0.0002),
}

def evaluate(rows):
    out = {"settled_samples": len(rows), "sufficient_for_decision": len(rows) >= 100,
           "scenarios": {}, "warning": "Only observed settled candidate fills; no evidence of profitability when sample is small."}
    for name, (fee, slip) in SCENARIOS.items():
        returns = []
        for direction, entry_bid, entry_ask, exit_bid, exit_ask in rows:
            if min(entry_bid, entry_ask, exit_bid, exit_ask) <= 0:
                continue
            if direction == "LONG":
                entry = entry_ask * (1 + slip)
                exit_price = exit_bid * (1 - slip)
                pnl = (exit_price * (1 - fee)) / (entry * (1 + fee)) - 1
            elif direction == "SHORT":
                entry = entry_bid * (1 - slip)
                exit_price = exit_ask * (1 + slip)
                pnl = (entry * (1 - fee) - exit_price * (1 + fee)) / entry
            else:
                continue
            returns.append(pnl * 100)
        out["scenarios"][name] = {
            "samples": len(returns),
            "average_net_pct": round(sum(returns)/len(returns), 6) if returns else None,
            "win_rate_pct": round(100 * sum(x > 0 for x in returns)/len(returns), 2) if returns else None,
            "profitable_samples": sum(x > 0 for x in returns),
        }
    return out

def analyze(db):
    rows = db.execute("""SELECT direction,bid,ask,exit_bid,exit_ask FROM observations
        WHERE candidate=1 AND net_pct IS NOT NULL
        AND exit_bid IS NOT NULL AND exit_ask IS NOT NULL""").fetchall()
    result = evaluate(rows)
    result["observations"] = db.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    result["eligible_candidates"] = db.execute("SELECT COUNT(*) FROM observations WHERE candidate=1").fetchone()[0]
    return result

def main():
    path = Path(sys.argv[1] if len(sys.argv)>1 else "/data/kraken_shadow.sqlite3")
    if not path.is_file():
        raise SystemExit("No forward observation database: " + str(path))
    with sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True) as db:
        print(json.dumps(analyze(db), indent=2))

if __name__ == "__main__":
    main()
