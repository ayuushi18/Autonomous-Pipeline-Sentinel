import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DRIFT_ORDER = ['rename', 'remove', 'type_change', 'unit_scale', 'null_out']
SOURCES = ['jobs', 'govdata', 'transit']
SCENARIOS = ['suffix', 'prefix', 'case', 'opaque', 'rename+scale']
PLAIN = ('suffix', 'prefix', 'case', 'opaque')


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def rate(k, n):
    if n == 0:
        return 'n/a'
    lo, hi = wilson(k, n)
    return f'{100 * k / n:.0f}% ({100 * lo:.0f}-{100 * hi:.0f}%)'


def simple(k, n):
    return f'{100 * k / n:.0f}%' if n else 'n/a'


def main():
    results = json.load(open(ROOT / 'results.json'))
    heal = json.load(open(ROOT / 'heal_results.json'))
    injected = results['injected']
    clean = results['clean']
    skipped = results.get('skipped', {})

    lines = []
    add = lines.append

    add('# PipelineSentinel benchmark results')
    add('')
    add('All drift in these tests is synthetic: a script breaks copies of real '
        'snapshots in ways whose correct answer is known. False-alarm numbers use '
        'real consecutive snapshots with nothing injected.')
    add('')

    add('## 1. Drift detection (injected drift)')
    add('')
    add('| Drift type | Trials | Detected | Localized to the exact field |')
    add('|---|---|---|---|')
    for kind in DRIFT_ORDER:
        rows = [r for r in injected if r['type'] == kind]
        n = len(rows)
        found = sum(r['detected'] for r in rows)
        exact = sum(r['localized'] for r in rows)
        add(f'| {kind} | {n} | {rate(found, n)} | {rate(exact, n)} |')
    add('')
    add('Values in brackets are 95% Wilson confidence intervals. Trials reuse the '
        'same base snapshots, so the intervals are optimistic.')
    for source, kinds in skipped.items():
        if kinds:
            add('')
            add(f'No eligible field in {source} for: {", ".join(kinds)}.')
    add('')

    add('## 2. False alarms on real consecutive snapshots')
    add('')
    add('| Source | Snapshot pairs | Raw alarms | With noise filter |')
    add('|---|---|---|---|')
    for source in SOURCES:
        rows = [r for r in clean if r['source'] == source]
        n = len(rows)
        raw = sum(r['alarm_before'] for r in rows)
        tuned = sum(r['alarm_after'] for r in rows)
        add(f'| {source} | {n} | {raw} ({simple(raw, n)}) | {tuned} ({simple(tuned, n)}) |')
    add('')
    add('Small samples. Treat these as indicative, not precise.')
    add('')

    add('## 3. Self-healing (injected renames)')
    add('')
    add('| Scenario | Trials | Healed correctly | Rejected | Missed | Wrong fix |')
    add('|---|---|---|---|---|---|')
    for scenario in SCENARIOS:
        rows = [r for r in heal if r['scenario'] == scenario]
        n = len(rows)
        counts = Counter(r['outcome'] for r in rows)
        add(f'| {scenario} | {n} | {simple(counts["healed_correct"], n)} | '
            f'{simple(counts["rejected"], n)} | {simple(counts["missed"], n)} | '
            f'{simple(counts["healed_wrong"], n)} |')
    plain = [r for r in heal if r['scenario'] in PLAIN]
    healed = sum(r['outcome'] == 'healed_correct' for r in plain)
    unsafe = sum(r['outcome'] == 'healed_wrong' for r in heal)
    add('')
    add(f'- Plain renames healed correctly: **{healed} of {len(plain)}**')
    add(f'- Unsafe patches applied (all scenarios): **{unsafe} of {len(heal)}**')
    add('- In the rename+scale scenario most cases were never matched at all, so '
        'no patch was proposed. Only a few reached the validator.')
    add('')

    add('## Method notes and limitations')
    add('')
    add('- Thresholds were fixed before benchmarking: KS statistic >= 0.5 with '
        'p < 0.01, null-rate jump >= 30 percentage points, baseline window of 10 '
        'snapshots, a field must appear in >= 80% of recent snapshots to count as stable.')
    add('- Two changes were made after seeing benchmark results: the value check '
        'now also requires the mean to move by at least 10%, and the injector skips '
        'flag-like fields (5 or fewer distinct values). Each fixed a specific '
        'weakness found in diagnosis.')
    add('- Injected drift is large (100x or 1000x unit changes, about 60% null-out). '
        'Subtle drift would score lower.')
    add('- Null-rate shifts under 30 percentage points are not flagged by default, '
        'which explains the null_out cases that were detected but not localized.')
    add('- Scale changes in fields that are mostly zeros can be missed, because the '
        'KS statistic is capped by the share of non-zero values.')
    add('- Remaining transit false alarms come from the mix of reporting vehicles '
        'changing and optional fields disappearing, which look the same as real '
        'drift from structure alone.')
    add('- The rename matcher is conservative: when values change along with the '
        'name, it usually proposes nothing.')
    add('- Plain-rename tests keep values identical, which is easier than real life.')
    add('')

    out = ROOT / 'RESULTS.md'
    out.write_text('\n'.join(lines), encoding='utf-8')
    print(f'Wrote {out}')


if __name__ == '__main__':
    main()