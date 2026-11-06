"""Count sequential baseline signal gates on development periods only.

This is a signal funnel, not a backtest: portfolio state and execution are
excluded. Never selects parameters or evaluates the consumed holdout.
"""
import argparse
import json
from pathlib import Path

from research.study import features, read


def funnel(d, start, end):
    # Signal is observed at candle close; execution requires the next minute.
    decision = d.timestamp + 60
    mask = decision.ge(start) & decision.lt(end)
    gates = [
        ('crossovers', d.signal.ne(0)),
        ('regime', d.signal.eq(d.regime)),
        ('continuous_data', d.continuous & d.timestamp.shift(-1).eq(decision)),
        ('hour_range_2_14pct', d['range'].ge(.0214)),
        ('directional_hour_trend_0_4pct', (d.signal * d.trend).ge(.004)),
        ('atr_bounds', d.atr.between(.0002, .015)),
        ('volume', d.volume_ratio.ge(.5)),
    ]
    counts = {}
    for name, gate in gates:
        mask &= gate.fillna(False)
        counts[name] = int(mask.sum())
    return counts


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('minute')
    p.add_argument('fourhour')
    p.add_argument('--output', default='research/filter_diagnostics.json')
    a = p.parse_args()
    # Exclude holdout before calculating features, not just from output.
    end = 1775001600
    d, h = read(a.minute, 60), read(a.fourhour, 14400)
    d = features(d[d.timestamp < end].reset_index(drop=True),
                 h[h.timestamp < end].reset_index(drop=True))
    result = {name: funnel(d, start, stop) for name, start, stop in (
        ('train', 1727740800, 1759276800),
        ('validation', 1759276800, end))}
    result['limitations'] = ('Sequential counts depend on gate order; candidates are not trades. '
                            'Portfolio, cooldown, daily limits and execution are excluded. '
                            'No parameter tuning or holdout evaluation.')
    Path(a.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
