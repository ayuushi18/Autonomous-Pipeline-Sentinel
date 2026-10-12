import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import random
import time

import ingest.healer as healer
from benchmark.injector import inject, _candidates, _try_inject, _apply_at, RENAME_STYLES
from ingest.fingerprints import fingerprint
from ingest.compare import compare

# keep the benchmark out of your real decision log (and off the LLM)
healer.log_decision = lambda entry: None

SOURCES = ['jobs', 'govdata', 'transit']
TRIALS = 10
SCALE = 1000


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def pct(part, whole):
    return f'{100 * part / whole:.0f}%' if whole else 'n/a'


def classify(original, healed, decision):
    action = decision['action'] if decision else 'no_decision'
    if action == 'patch_applied':
        return 'healed_correct' if healed == original else 'healed_wrong'
    if action == 'patch_rejected':
        return 'rejected'
    return 'missed'


def run_heal(name, original, mutated):
    old_fp = fingerprint(original)
    new_fp = fingerprint(mutated)
    report = compare(old_fp, new_fp)
    return healer.heal(name, mutated, original, old_fp, new_fp, report)


def run_plain(source, data):
    rows = []
    for style in RENAME_STYLES:
        for i in range(TRIALS):
            rng = random.Random(f'heal-{source}-{style}-{i}')
            result = inject(data, 'rename', rng, style)
            if result is None:
                break
            mutated, info = result
            healed, decision = run_heal(source, data, mutated)
            rows.append({
                'source': source,
                'scenario': style,
                'outcome': classify(data, healed, decision),
                'info': info,
            })
    return rows


def run_tricky(source, data):
    options = sorted(_candidates(data)['unit_scale'])
    if not options:
        print(f'  {source}: no numeric field for the tricky scenario, skipped')
        return []

    def scale(node, key):
        value = node[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        node[key] = value * SCALE
        return True

    rows = []
    for i in range(TRIALS):
        rng = random.Random(f'heal-tricky-{source}-{i}')
        target = rng.choice(options)
        style = rng.choice(RENAME_STYLES)
        result = _try_inject(data, 'rename', target, rng, style)
        if result is None:
            continue
        mutated, info = result
        _apply_at(mutated, '$', info['new_path'], scale)
        healed, decision = run_heal(source, data, mutated)
        rows.append({
            'source': source,
            'scenario': 'rename+scale',
            'outcome': classify(data, healed, decision),
            'info': info,
        })
    return rows


def summarize(rows, scenarios):
    print(f'{"Scenario":<14}{"Trials":>8}{"Healed":>9}{"Rejected":>10}{"Missed":>8}{"WrongFix":>10}')
    for scenario in scenarios:
        subset = [r for r in rows if r['scenario'] == scenario]
        n = len(subset)
        counts = {
            kind: sum(r['outcome'] == kind for r in subset)
            for kind in ('healed_correct', 'rejected', 'missed', 'healed_wrong')
        }
        print(f'{scenario:<14}{n:>8}{pct(counts["healed_correct"], n):>9}'
              f'{pct(counts["rejected"], n):>10}{pct(counts["missed"], n):>8}'
              f'{pct(counts["healed_wrong"], n):>10}')


def main():
    start = time.time()
    rows = []

    for source in SOURCES:
        data = load_json(f'snapshots/{source}_snapshot.json')
        if not data:
            print(f'{source}: snapshot missing or empty, skipping')
            continue
        print(f'Running {source}...')
        rows += run_plain(source, data)
        rows += run_tricky(source, data)

    print()
    summarize(rows, RENAME_STYLES + ['rename+scale'])

    plain = [r for r in rows if r['scenario'] in RENAME_STYLES]
    healed = sum(r['outcome'] == 'healed_correct' for r in plain)
    unsafe = sum(r['outcome'] == 'healed_wrong' for r in rows)

    print()
    print(f'Plain renames healed correctly: {healed} of {len(plain)} ({pct(healed, len(plain))})')
    print(f'Unsafe patches applied (all scenarios): {unsafe} of {len(rows)}')

    print()
    print('Plain rename heal rate by source:')
    for source in SOURCES:
        subset = [r for r in plain if r['source'] == source]
        ok = sum(r['outcome'] == 'healed_correct' for r in subset)
        print(f'  {source}: {ok} of {len(subset)} ({pct(ok, len(subset))})')

    with open('benchmark/heal_results.json', 'w') as f:
        json.dump(rows, f, indent=2, default=str)
    print()
    print(f'Saved benchmark/heal_results.json ({time.time() - start:.0f}s)')


if __name__ == '__main__':
    main()