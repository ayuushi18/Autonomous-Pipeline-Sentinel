import os
import json

try:
    from ingest.fingerprints import fingerprint
    from ingest.compare import compare
    from ingest.values import extract_values
    from ingest.value_drift import compare_values
    from ingest.patcher import apply_patch
except ImportError:
    from fingerprints import fingerprint
    from compare import compare
    from values import extract_values
    from value_drift import compare_values
    from patcher import apply_patch


def load_history(name, limit=3):
    folder = f'snapshots/history/{name}'
    if not os.path.isdir(folder):
        return []
    files = sorted(os.listdir(folder))[-limit:]
    history = []
    for filename in files:
        try:
            with open(f'{folder}/{filename}') as f:
                history.append(json.load(f))
        except (OSError, json.JSONDecodeError):
            continue
    return history


def _only(table, targets):
    return {path: value for path, value in table.items() if path in targets}


def validate_patch(patch, new_data, old_fp, history):
    if not history:
        return {'passed': False, 'checks': {}, 'reason': 'no history to validate against'}

    reference = history[-1]
    fixed = apply_patch(new_data, patch)
    sources = {r['source'] for r in patch['renames']}
    targets = {r['target'] for r in patch['renames']}
    checks = {}

    # Check 1: the renamed fields are back where they used to be
    structure = compare(old_fp, fingerprint(fixed))
    checks['structure_restored'] = not (
        sources & set(structure['added'])
        or targets & set(structure['removed'])
        or targets & set(structure['type_changed'])
    )

    # Check 2: values in the renamed fields still look like the old values
    ref_numbers, ref_nulls = extract_values(reference)
    fix_numbers, fix_nulls = extract_values(fixed)
    value_report = compare_values(
        _only(ref_numbers, targets), _only(fix_numbers, targets),
        _only(ref_nulls, targets), _only(fix_nulls, targets),
    )
    checks['values_consistent'] = not (
        value_report['value_shift'] or value_report['null_shift']
    )

    # Check 3: the patch does no harm to old data
    checks['harmless_on_history'] = all(
        apply_patch(old, patch) == old for old in history
    )

    return {
        'passed': all(checks.values()),
        'checks': checks,
        'value_report': value_report,
    }