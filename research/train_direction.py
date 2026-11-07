"""Train a simple regularized directional classifier on historical BTC/EUR candles.

Research only: chronological 60/20/20 train/validation/test, no live orders.
Prediction is for next completed 5m candle close versus its open.
No future candle is included in features. Model never modifies production bot.
"""
import json
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest import read_csv

def examples(rows):
    out = []
    # Completed 5m bar at i, next candle occupies i+1..i+5.
    for i in range(239, len(rows)-5, 5):
        if int(rows[i][0].timestamp()) // 60 % 5 != 4:
            continue
        window = rows[i-239:i+1]
        close = window[-1][4]
        if close <= 0:
            continue
        closes = [r[4] for r in window]
        highs = [r[2] for r in window[-30:]]
        lows = [r[3] for r in window[-30:]]
        volumes = [r[5] for r in window]
        recent_vol = sum(volumes[-5:])
        prior_vol = sum(volumes[-65:-5]) / 12
        candle_open = window[-5][1]
        candle_high = max(r[2] for r in window[-5:])
        candle_low = min(r[3] for r in window[-5:])
        spread = max(candle_high-candle_low, 1e-9)
        x = [
            (close/closes[-6]-1)*100,
            (close/closes[-16]-1)*100,
            (close/closes[-61]-1)*100,
            (close/closes[-181]-1)*100,
            (close-candle_open)/spread,
            (close-candle_low)/spread-.5,
            (max(highs)-min(lows))/close*100,
            min(recent_vol/max(prior_vol, 1e-9), 10)-1,
        ]
        nxt_open = rows[i+1][1]
        nxt_close = rows[i+5][4]
        if nxt_close == nxt_open:
            continue
        out.append((x, int(nxt_close > nxt_open)))
    return out

def fit(train, epochs=80, rate=.02, l2=.02):
    # Standardize using training data ONLY.
    n = len(train[0][0])
    mu = [sum(x[j] for x,_ in train)/len(train) for j in range(n)]
    std = [max((sum((x[j]-mu[j])**2 for x,_ in train)/len(train))**.5, 1e-8) for j in range(n)]
    w = [0.] * n
    b = 0.
    for _ in range(epochs):
        gw = [0.] * n
        gb = 0.
        for x,y in train:
            z = sum(w[j]*(x[j]-mu[j])/std[j] for j in range(n)) + b
            p = 1/(1+math.exp(-max(-35,min(35,z))))
            err = p-y
            for j in range(n):
                gw[j] += err*(x[j]-mu[j])/std[j]
            gb += err
        for j in range(n):
            w[j] -= rate*(gw[j]/len(train)+l2*w[j])
        b -= rate*gb/len(train)
    return {"weights":w,"bias":b,"mean":mu,"std":std}

def predict(model,x):
    z = model["bias"]+sum(w*(v-m)/s for w,v,m,s in zip(model["weights"],x,model["mean"],model["std"]))
    return 1/(1+math.exp(-max(-35,min(35,z))))

def score(model, data, threshold):
    total = len(data)
    chosen = [(p,y) for x,y in data for p in [predict(model,x)] if p>=threshold or p<=1-threshold]
    correct = sum((p>=.5)==bool(y) for p,y in chosen)
    return {"samples":total,"signals":len(chosen),"coverage_pct":round(100*len(chosen)/total,2) if total else None,
            "accuracy_pct":round(100*correct/len(chosen),2) if chosen else None,
            "majority_baseline_pct":round(100*max(sum(y for _,y in data),sum(1-y for _,y in data))/total,2) if total else None}

def run(rows):
    data=examples(rows)
    if len(data)<500:
        raise ValueError("At least 500 labeled 5m candles required")
    a,b=int(len(data)*.6),int(len(data)*.8)
    train,valid,test=data[:a],data[a:b],data[b:]
    model=fit(train)
    # Tune only on validation, require >=30 signals to avoid cherry-picking.
    choices=[(score(model,valid,t),t) for t in (.5,.55,.6,.65,.7,.75)]
    eligible=[(s,t) for s,t in choices if s["signals"]>=30]
    threshold=max(eligible,key=lambda item:(item[0]["accuracy_pct"],item[0]["signals"]))[1] if eligible else .5
    return {"method":"regularized_logistic_regression","training_samples":len(train),
            "validation":score(model,valid,threshold),"test":score(model,test,threshold),
            "selected_threshold":threshold,
            "warning":"Research only. Test is held out. Directional accuracy does not imply profitability; fees and spread excluded."}

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("Usage: python research/train_direction.py history.csv")
    rows=read_csv(sys.argv[1])
    print(json.dumps(run(rows),indent=2))
