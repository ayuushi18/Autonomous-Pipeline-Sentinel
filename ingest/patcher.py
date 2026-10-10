import copy
from datetime import datetime


def _last(path):
    return path.rsplit('.', 1)[-1]


def build_patch(source_name, matches):
    return {
        'source_name': source_name,
        'created': datetime.now().isoformat(timespec='seconds'),
        'renames': [
            {
                'source': m['to'],
                'target': m['from'],
                'confidence': m['confidence'],
            }
            for m in matches
        ],
    }


def _rename_in(node, path, mapping):
    if isinstance(node, dict):
        for key in list(node.keys()):
            full = f'{path}.{key}'
            _rename_in(node[key], full, mapping)
            if full in mapping and mapping[full] not in node:
                node[mapping[full]] = node.pop(key)
    elif isinstance(node, list):
        for item in node:
            _rename_in(item, f'{path}[]', mapping)


def apply_patch(data, patch):
    mapping = {r['source']: _last(r['target']) for r in patch['renames']}
    fixed = copy.deepcopy(data)
    _rename_in(fixed, '$', mapping)
    return fixed