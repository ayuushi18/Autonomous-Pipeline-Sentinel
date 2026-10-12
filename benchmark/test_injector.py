import copy
import json
import random

from benchmark.injector import inject, DRIFT_TYPES
from ingest.fingerprints import fingerprint
from ingest.compare import compare

rng = random.Random(42)

for source in ('jobs', 'govdata', 'transit'):
    data = json.load(open(f'snapshots/{source}_snapshot.json'))
    original = copy.deepcopy(data)
    original_fp = fingerprint(data)
    print(f'=== {source} ===')

    for drift_type in DRIFT_TYPES:
        result = inject(data, drift_type, rng)
        if result is None:
            print(f'  {drift_type}: no eligible field in this source')
            continue
        mutated, info = result
        report = compare(original_fp, fingerprint(mutated))
        print(f'  {drift_type}: {info}')
        print('     structure report: added={}, removed={}, type_changed={}'.format(
            len(report['added']), len(report['removed']), len(report['type_changed'])))

    print('  original data untouched:', data == original)
    print()