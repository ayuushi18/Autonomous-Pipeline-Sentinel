import os
import json
from datetime import datetime

try:
    from ingest.rename_finder import find_renames
    from ingest.patcher import build_patch, apply_patch
    from ingest.validator import load_history, validate_patch
    from ingest.explainer import explain
except ImportError:
    from rename_finder import find_renames
    from patcher import build_patch, apply_patch
    from validator import load_history, validate_patch
    from explainer import explain

LOG_PATH = 'logs/heal_log.jsonl'

def log_decision(entry):
    os.makedirs('logs', exist_ok=True)
    entry['time'] = datetime.now().isoformat(timespec='seconds')
    entry['explanation'] = explain(entry)
    with open(LOG_PATH, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def heal(name, data, old_data, old_fp, new_fp, report):
    if not (report['added'] or report['removed']):
        return data, None

    matches = find_renames(report, old_fp, new_fp, old_data, data)
    if not matches:
        decision = {
            'source': name,
            'action': 'no_action',
            'reason': 'no confident rename match',
            'added': report['added'],
            'removed': report['removed'],
        }
        log_decision(decision)
        return data, decision

    patch = build_patch(name, matches)
    history = load_history(name)
    result = validate_patch(patch, data, old_fp, history)

    if result['passed']:
        healed = apply_patch(data, patch)
        decision = {
            'source': name,
            'action': 'patch_applied',
            'patch': patch,
            'checks': result['checks'],
        }
        log_decision(decision)
        return healed, decision

    decision = {
        'source': name,
        'action': 'patch_rejected',
        'patch': patch,
        'checks': result['checks'],
    }
    log_decision(decision)
    return data, decision