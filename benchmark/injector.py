import copy
import random
import re

from ingest.fingerprints import fingerprint
from ingest.values import extract_values

DRIFT_TYPES = ['rename', 'remove', 'type_change', 'unit_scale', 'null_out']
RENAME_STYLES = ['suffix', 'prefix', 'case', 'opaque']

LEAF_TYPES = {'str', 'int', 'float', 'bool', 'null'}
NUMBER_TYPES = {'int', 'float'}
IGNORE_WORDS = ('time', 'date', 'created', 'timestamp')
MIN_SAMPLES = 5
MIN_DISTINCT = 5


def _last(path):
    return path.rsplit('.', 1)[-1]


def _parent(path):
    return path.rsplit('.', 1)[0]


def _ignored(path):
    return any(word in _last(path).lower() for word in IGNORE_WORDS)


def _toggle_case(key):
    if '_' in key:
        first, *rest = key.split('_')
        return first + ''.join(part.capitalize() for part in rest)
    if re.search('[A-Z]', key):
        return re.sub(r'(?<!^)(?=[A-Z])', '_', key).lower()
    return key.capitalize()


def _new_key(key, style, rng):
    if style == 'suffix':
        new = key + '_v2'
    elif style == 'prefix':
        new = 'new_' + key
    elif style == 'case':
        new = _toggle_case(key)
    else:
        new = 'f_' + ''.join(rng.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(5))
    return new if new != key else key + '_v2'


def _apply_at(node, path, target, mutate):
    count = 0
    if isinstance(node, dict):
        for key in list(node.keys()):
            full = f'{path}.{key}'
            if full == target:
                if mutate(node, key):
                    count += 1
            else:
                count += _apply_at(node[key], full, target, mutate)
    elif isinstance(node, list):
        for item in node:
            count += _apply_at(item, f'{path}[]', target, mutate)
    return count


def _candidates(data):
    fp = fingerprint(data)
    numbers, nulls = extract_values(data)

    leaf = []
    for path, info in fp.items():
        if path == '$' or path.endswith('[]'):
            continue
        if not set(info['types']) <= LEAF_TYPES:
            continue
        if (info['presence'] or 0) < 0.9:
            continue
        leaf.append(path)

    numeric = []
    for path in leaf:
        types = set(fp[path]['types'])
        if types & NUMBER_TYPES and types <= NUMBER_TYPES | {'null'}:
            numeric.append(path)

    return {
        'rename': leaf,
        'remove': leaf,
        'type_change': [p for p in leaf
                        if set(fp[p]['types']) <= NUMBER_TYPES
                        or set(fp[p]['types']) == {'str'}],
        'unit_scale': [p for p in numeric
                       if not _ignored(p)
                       and len(numbers.get(p, [])) >= MIN_SAMPLES
                       and len(set(numbers[p])) > MIN_DISTINCT],
        'null_out': [p for p in leaf
                     if p in nulls
                     and nulls[p][1] >= MIN_SAMPLES
                     and nulls[p][0] / nulls[p][1] <= 0.2],
    }


def _try_inject(data, drift_type, target, rng, style=None):
    mutated = copy.deepcopy(data)
    info = {'type': drift_type, 'path': target}

    if drift_type == 'rename':
        style = style or rng.choice(RENAME_STYLES)
        new_key = _new_key(_last(target), style, rng)
        info['style'] = style
        info['new_path'] = _parent(target) + '.' + new_key

        def mutate(node, key):
            if new_key in node:
                return False
            node[new_key] = node.pop(key)
            return True

    elif drift_type == 'remove':
        def mutate(node, key):
            node.pop(key)
            return True

    elif drift_type == 'type_change':
        def mutate(node, key):
            value = node[key]
            if isinstance(value, bool):
                return False
            if isinstance(value, (int, float)):
                node[key] = str(value)
                return True
            if isinstance(value, str):
                node[key] = [value]
                return True
            return False

    elif drift_type == 'unit_scale':
        factor = rng.choice([100, 1000])
        info['factor'] = factor

        def mutate(node, key):
            value = node[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return False
            node[key] = value * factor
            return True

    else:
        def mutate(node, key):
            if rng.random() < 0.6:
                node[key] = None
                return True
            return False

    changed = _apply_at(mutated, '$', target, mutate)
    if changed == 0:
        return None
    info['occurrences'] = changed
    return mutated, info


def inject(data, drift_type, rng, style=None):
    options = sorted(_candidates(data)[drift_type])
    for target in rng.sample(options, min(len(options), 10)):
        result = _try_inject(data, drift_type, target, rng, style)
        if result is not None:
            return result
    return None