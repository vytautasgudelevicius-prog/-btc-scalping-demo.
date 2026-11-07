"""Compare BTC/EUR, ETH/EUR, SOL/EUR independently after costs.

Research only. Never ranks markets as live trade recommendations.
"""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.forecast_expected_value import run

def compare(markets,**kwargs):
    if not markets:raise ValueError("At least one market required")
    results={}
    for symbol,rows in markets.items():
        try:
            results[symbol]=run(rows,**kwargs)
        except (ValueError,ArithmeticError) as exc:
            results[symbol]={"decision":"NO_TRADE","reason":str(exc)}
    qualified=[(name,r) for name,r in results.items()
               if r.get("decision")=="RESEARCH_ONLY" and
               r.get("untouched_test",{}).get("avg_net_pct") is not None]
    qualified.sort(key=lambda item:item[1]["untouched_test"]["avg_net_pct"],reverse=True)
    return {"markets":results,
            "research_ranking":[name for name,_ in qualified],
            "live_decision":"WAIT",
            "warning":"Comparing held-out markets is exploratory, not a validated selection rule. "
                      "Costs are scenario assumptions, not exchange-specific quotes. "
                      "No orders; require walk-forward testing and market-specific fees."}

if __name__=="__main__":
    if len(sys.argv)<3 or len(sys.argv[1:])%2:
        raise SystemExit("Usage: python research/compare_market_forecasts.py BTC/EUR btc.csv ETH/EUR eth.csv ...")
    markets={sys.argv[i]:read_csv(sys.argv[i+1]) for i in range(1,len(sys.argv),2)}
    print(json.dumps(compare(markets),indent=2))
