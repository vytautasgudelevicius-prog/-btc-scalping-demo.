"""Independent research decision cycle: observe -> assess -> confirm -> risk -> paper verdict.

Fail closed: research output never sends orders or resets production loss limits.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.strong_signal_walk_forward import run as walk_forward
from research.best_scalping_hours import run as hourly

def assess(rows):
    observation={"candles":len(rows),"start_utc":rows[0][0].isoformat(),
                 "end_utc":rows[-1][0].isoformat()}
    wf=walk_forward(rows)
    hours=hourly(rows)
    folds=wf.get("folds",[])
    positive_folds=bool(folds) and all(
        f.get("decision")=="RESEARCH_ONLY" and f.get("test",{}).get("trades",0)>=30
        and (f.get("test",{}).get("avg_net_pct") or 0)>0 for f in folds)
    test=hours.get("untouched_test") or {}
    hour_positive=(hours.get("decision")=="RESEARCH_ONLY"
                   and test.get("trades",0)>=15 and (test.get("avg_net_pct") or 0)>0)
    verified=positive_folds and hour_positive
    return {
        "market_observation":observation,
        "situation_analysis":{"walk_forward":wf,"utc_hour_analysis":hours},
        "signal_confirmation":{"historical_edge_verified":verified,
                               "selected_utc_hours":hours.get("selected_utc_hours",[]) if verified else []},
        "risk_check":{"historical_costs_included":True,
                      "real_time_spread_verified":False,
                      "production_kraken_execution_verified":False,
                      "five_loss_circuit_breaker_must_remain":True},
        "demo_trade":{"decision":"WAIT","orders_enabled":False,
                      "reason":"requires_forward_paper_and_production_execution_validation"
                      if verified else "no_verified_positive_historical_edge"},
        "result_analysis":{"hourly_test":test,
                           "walk_forward_folds":[f.get("test") for f in folds]},
        "strategy_improvement":{"candidate_for_forward_shadow_monitoring":verified,
                                "automatic_strategy_replacement":False},
        "decision":"SHADOW_RESEARCH_ONLY" if verified else "NO_TRADE",
        "warning":"Offline evaluation is not a live signal. No orders, no production DB writes."}

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("Usage: python research/autonomous_decision_cycle.py historical.csv")
    print(json.dumps(assess(read_csv(sys.argv[1])),indent=2))
