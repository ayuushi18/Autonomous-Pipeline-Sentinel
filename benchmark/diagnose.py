import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from collections import Counter

from benchmark.runner import (load_json, load_snapshots, profile,
                              BASELINE_WINDOW, MIN_BASELINE)
from ingest.compare import compare
from ingest.baseline import build_baseline, filter_report
from ingest.value_drift import compare_values
from ingest.values import extract_values

print('PART 1: what still triggers false alarms')
for source in ('transit', 'jobs'):
    profiles = [profile(s) for s in load_snapshots(source)]
    print(f'=== {source} ===')
    for i in range(MIN_BASELINE - 1, len(profiles) - 1):
        older, newer = profiles[i], profiles[i + 1]
        window = profiles[max(0, i - BASELINE_WINDOW + 1): i + 1]
        baseline = build_baseline([p['fp'] for p in window])
        tuned = filter_report(compare(older['fp'], newer['fp']), baseline)
        values = compare_values(older['numbers'], newer['numbers'],
                                older['nulls'], newer['nulls'])
        flagged = {k: v for k, v in {**tuned, **values}.items() if v}
        if flagged:
            print(f'pair {i} -> {i + 1}:')
            for kind, detail in flagged.items():
                print(f'   {kind}: {detail}')

print()
print('PART 2: transit unit_scale misses')
rows = json.load(open('benchmark/results.json'))['injected']
numbers, _ = extract_values(load_json('snapshots/transit_snapshot.json'))
total = Counter()
missed = Counter()
for r in rows:
    if r['type'] == 'unit_scale' and r['source'] == 'transit':
        total[r['info']['path']] += 1
        if not r['localized']:
            missed[r['info']['path']] += 1
for path, n in total.items():
    values = numbers.get(path, [])
    zeros = (sum(v == 0 for v in values) / len(values)) if values else 0
    print(f'{path} | trials {n} | missed {missed[path]} | values {len(values)} | zeros {zeros:.0%}')