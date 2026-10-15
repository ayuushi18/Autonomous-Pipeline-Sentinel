import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import os
import random
import time
from collections import Counter

from benchmark.injector import inject, DRIFT_TYPES
from ingest.fingerprints import fingerprint
from ingest.compare import compare
from ingest.values import extract_values
from ingest.value_drift import compare_values
from ingest.baseline import build_baseline, filter_report

SOURCES = ['jobs', 'govdata', 'transit']
TRIALS = 20
MAX_HISTORY = 30
BASELINE_WINDOW = 10
MIN_BASELINE = 3


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def load_snapshots(source):
    folder = f'snapshots/history/{source}'
    if not os.path.isdir(folder):
        return []
    files = sorted(os.listdir(folder))[-MAX_HISTORY:]
    snapshots = [load_json(f'{folder}/{name}') for name in files]
    return [s for s in snapshots if s]


def profile(data):
    numbers, nulls = extract_values(data)
    return {'fp': fingerprint(data), 'numbers': numbers, 'nulls': nulls}


def is_alarm(structure, values):
    return any([
        structure['added'], structure['removed'], structure['type_changed'],
        structure['presence_shift'], values['value_shift'], values['null_shift'],
    ])


def localized(info, structure, values):
    kind = info['type']
    path = info['path']
    if kind == 'rename':
        return info['new_path'] in structure['added'] and path in structure['removed']
    if kind == 'remove':
        return path in structure['removed']
    if kind == 'type_change':
        return path in structure['type_changed']
    if kind == 'unit_scale':
        return path in values['value_shift']
    return path in values['null_shift']


def run_injected(source, data, baseline):
    base = profile(data)
    rows = []
    skipped = []
    for drift_type in DRIFT_TYPES:
        for i in range(TRIALS):
            rng = random.Random(f'{source}-{drift_type}-{i}')
            result = inject(data, drift_type, rng)
            if result is None:
                skipped.append(drift_type)
                break
            mutated, info = result
            new = profile(mutated)
            raw = compare(base['fp'], new['fp'])
            tuned = filter_report(raw, baseline) if baseline else raw
            values = compare_values(base['numbers'], new['numbers'],
                                    base['nulls'], new['nulls'])
            rows.append({
                'source': source,
                'type': drift_type,
                'trial': i,
                'info': info,
                'detected_before': is_alarm(raw, values),
                'localized_before': localized(info, raw, values),
                'detected': is_alarm(tuned, values),
                'localized': localized(info, tuned, values),
            })
    return rows, skipped


def run_clean(source, snapshots):
    profiles = [profile(s) for s in snapshots]
    rows = []
    for i in range(MIN_BASELINE - 1, len(profiles) - 1):
        older = profiles[i]
        newer = profiles[i + 1]
        window = profiles[max(0, i - BASELINE_WINDOW + 1): i + 1]
        baseline = build_baseline([p['fp'] for p in window])

        raw = compare(older['fp'], newer['fp'])
        tuned = filter_report(raw, baseline)
        values = compare_values(older['numbers'], newer['numbers'],
                                older['nulls'], newer['nulls'])

        reasons = [k for k, v in tuned.items() if v] + [k for k, v in values.items() if v]
        rows.append({
            'source': source,
            'alarm_before': is_alarm(raw, values),
            'alarm_after': is_alarm(tuned, values),
            'reasons': reasons,
        })
    return rows


def pct(part, whole):
    return f'{100 * part / whole:.0f}%' if whole else 'n/a'


def main():
    start = time.time()
    injected = []
    clean = []
    skipped = {}

    for source in SOURCES:
        snapshots = load_snapshots(source)
        data = load_json(f'snapshots/{source}_snapshot.json')
        if not data:
            print(f'{source}: snapshot missing or empty, skipping')
            continue
        print(f'Running {source} ({len(snapshots)} history snapshots)...')

        window = snapshots[-BASELINE_WINDOW:]
        baseline = None
        if len(window) >= MIN_BASELINE:
            baseline = build_baseline([fingerprint(s) for s in window])

        rows, skip = run_injected(source, data, baseline)
        injected += rows
        skipped[source] = skip
        clean += run_clean(source, snapshots)

    print()
    print(f'{"Drift type":<14}{"Trials":>8}{"Det.before":>12}{"Det.after":>11}'
          f'{"Loc.before":>12}{"Loc.after":>11}')
    for drift_type in DRIFT_TYPES:
        rows = [r for r in injected if r['type'] == drift_type]
        n = len(rows)
        det_b = sum(r['detected_before'] for r in rows)
        det_a = sum(r['detected'] for r in rows)
        loc_b = sum(r['localized_before'] for r in rows)
        loc_a = sum(r['localized'] for r in rows)
        print(f'{drift_type:<14}{n:>8}{pct(det_b, n):>12}{pct(det_a, n):>11}'
              f'{pct(loc_b, n):>12}{pct(loc_a, n):>11}')

    print()
    print('Localized % by source (after tuning):')
    for source in SOURCES:
        parts = []
        for drift_type in DRIFT_TYPES:
            rows = [r for r in injected
                    if r['source'] == source and r['type'] == drift_type]
            exact = sum(r['localized'] for r in rows)
            parts.append(f'{drift_type}={pct(exact, len(rows))}')
        print(f'  {source}: ' + '  '.join(parts))

    for source, skip in skipped.items():
        if skip:
            print(f'Skipped (no eligible field) in {source}: {", ".join(skip)}')

    print()
    print('False alarms on real consecutive snapshots (no injected drift):')
    print(f'{"Source":<10}{"Pairs":>7}{"Before":>14}{"After":>14}')
    for source in SOURCES:
        rows = [r for r in clean if r['source'] == source]
        n = len(rows)
        before = sum(r['alarm_before'] for r in rows)
        after = sum(r['alarm_after'] for r in rows)
        before_text = f'{before} ({pct(before, n)})'
        after_text = f'{after} ({pct(after, n)})'
        print(f'{source:<10}{n:>7}{before_text:>14}{after_text:>14}')

    print()
    for source in SOURCES:
        counts = Counter(reason for r in clean if r['source'] == source
                         for reason in r['reasons'])
        if counts:
            print(f'Remaining alarms in {source} by type: {dict(counts)}')

    with open('benchmark/results.json', 'w') as f:
        json.dump({
            'trials_per_type': TRIALS,
            'injected': injected,
            'clean': clean,
            'skipped': skipped,
        }, f, indent=2, default=str)

    print()
    print(f'Saved benchmark/results.json ({time.time() - start:.0f}s)')


if __name__ == '__main__':
    main()