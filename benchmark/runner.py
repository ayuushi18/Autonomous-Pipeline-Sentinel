import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import os
import random
import time

from benchmark.injector import inject, DRIFT_TYPES
from ingest.fingerprints import fingerprint
from ingest.compare import compare
from ingest.values import extract_values
from ingest.value_drift import compare_values

SOURCES = ['jobs', 'govdata', 'transit']
TRIALS = 20
MAX_HISTORY = 8


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def profile(data):
    numbers, nulls = extract_values(data)
    return {'fp': fingerprint(data), 'numbers': numbers, 'nulls': nulls}


def detect(old, new_data):
    new = profile(new_data)
    structure = compare(old['fp'], new['fp'])
    values = compare_values(old['numbers'], new['numbers'], old['nulls'], new['nulls'])
    return structure, values


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


def run_injected(source, data):
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
            structure, values = detect(base, mutated)
            rows.append({
                'source': source,
                'type': drift_type,
                'trial': i,
                'info': info,
                'detected': is_alarm(structure, values),
                'localized': localized(info, structure, values),
            })
    return rows, skipped


def run_clean(source):
    folder = f'snapshots/history/{source}'
    if not os.path.isdir(folder):
        return []
    files = sorted(os.listdir(folder))[-MAX_HISTORY:]
    snapshots = [load_json(f'{folder}/{name}') for name in files]
    snapshots = [s for s in snapshots if s]

    rows = []
    for older, newer in zip(snapshots, snapshots[1:]):
        structure, values = detect(profile(older), newer)
        rows.append({
            'source': source,
            'alarm': is_alarm(structure, values),
            'structure': structure,
            'values': values,
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
        data = load_json(f'snapshots/{source}_snapshot.json')
        if not data:
            print(f'{source}: snapshot missing or empty, skipping')
            continue
        print(f'Running {source}...')
        rows, skip = run_injected(source, data)
        injected += rows
        skipped[source] = skip
        clean += run_clean(source)

    print()
    print(f'{"Drift type":<14}{"Trials":>8}{"Detected":>10}{"Localized":>11}')
    for drift_type in DRIFT_TYPES:
        rows = [r for r in injected if r['type'] == drift_type]
        n = len(rows)
        found = sum(r['detected'] for r in rows)
        exact = sum(r['localized'] for r in rows)
        print(f'{drift_type:<14}{n:>8}{pct(found, n):>10}{pct(exact, n):>11}')

    print()
    print('Localized % by source:')
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
    for source in SOURCES:
        rows = [r for r in clean if r['source'] == source]
        alarms = sum(r['alarm'] for r in rows)
        print(f'  {source}: {alarms} of {len(rows)} pairs flagged ({pct(alarms, len(rows))})')

    os.makedirs('benchmark', exist_ok=True)
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