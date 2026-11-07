"""Research-only multi-market transfer learning evaluation.

Input: CSV files in the same OHLCV format as backtest.read_csv.
Fit on chronologically earlier samples of multiple markets; select confidence
threshold on BTC validation; evaluate ONCE on untouched BTC test.
Never creates exchange orders or changes production bot.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.train_direction import examples, fit, score

def evaluate(btc_rows, other_markets):
    btc = examples(btc_rows)
    if len(btc) < 500:
        raise ValueError("Need at least 500 labeled BTC 5m candles")
    a, b = int(len(btc)*.6), int(len(btc)*.8)
    btc_train, validation, test = btc[:a], btc[a:b], btc[b:]
    if not other_markets:
        raise ValueError("Supply at least one independent training market")
    pooled = list(btc_train)
    market_counts = {}
    # Anchor all external training to the BTC train/validation calendar boundary.
    # The BTC dataset is required to be contiguous and UTC aligned.
    btc_cutoff = btc_rows[239 + 5*a][0]
    for name, rows in other_markets.items():
        eligible_rows = [row for row in rows if row[0] < btc_cutoff]
        sample = examples(eligible_rows)
        if len(sample) < 500:
            raise ValueError(f"{name}: fewer than 500 eligible training candles")
        pooled.extend(sample)
        market_counts[name] = len(sample)
    baseline = fit(btc_train)
    transfer = fit(pooled)
    thresholds = (.5,.55,.6,.65,.7,.75)
    def select(model):
        candidates = [(score(model,validation,t),t) for t in thresholds]
        eligible = [(s,t) for s,t in candidates if s["signals"]>=30]
        return max(eligible,key=lambda x:(x[0]["accuracy_pct"],x[0]["signals"]))[1] if eligible else .5
    base_t, trans_t = select(baseline), select(transfer)
    return {
        "btc_only": {"threshold":base_t,"validation":score(baseline,validation,base_t),"test":score(baseline,test,base_t)},
        "multi_market": {"threshold":trans_t,"validation":score(transfer,validation,trans_t),"test":score(transfer,test,trans_t)},
        "training_samples": {"btc":len(btc_train),**market_counts},
        "warning": "Research only; other-market labels end before BTC validation cutoff. Directional accuracy excludes fees and is not profitability."
    }

if __name__=="__main__":
    if len(sys.argv)<3 or len(sys.argv[2:])%2:
        raise SystemExit("Usage: python research/train_multimarket.py BTC.csv ETH ETH.csv [SOL SOL.csv ...]")
    btc=read_csv(sys.argv[1])
    markets={sys.argv[i]:read_csv(sys.argv[i+1]) for i in range(2,len(sys.argv),2)}
    print(json.dumps(evaluate(btc,markets),indent=2))
