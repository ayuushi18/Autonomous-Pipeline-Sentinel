from difflib import SequenceMatcher


def _last(path):
    return path.rsplit('.', 1)[-1]


def _parent(path):
    return path.rsplit('.', 1)[0] if '.' in path else ''


def _collect(node, path, samples):
    if isinstance(node, dict):
        for key, value in node.items():
            _collect(value, f'{path}.{key}', samples)
    elif isinstance(node, list):
        for item in node:
            _collect(item, f'{path}[]', samples)
    else:
        samples.setdefault(path, set()).add(str(node))


def collect_samples(data):
    samples = {}
    _collect(data, '$', samples)
    return samples


def _name_score(old_path, new_path):
    a = _last(old_path).lower().replace('_', '')
    b = _last(new_path).lower().replace('_', '')
    score = SequenceMatcher(None, a, b).ratio()
    if a in b or b in a:
        score = max(score, 0.8)
    return score


def _type_score(old_fp, new_fp, old_path, new_path):
    a = set(old_fp[old_path]['types'])
    b = set(new_fp[new_path]['types'])
    return len(a & b) / len(a | b)


def _value_score(old_samples, new_samples, old_path, new_path):
    a = old_samples.get(old_path)
    b = new_samples.get(new_path)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_renames(report, old_fp, new_fp, old_data, new_data, min_confidence=0.6):
    old_samples = collect_samples(old_data)
    new_samples = collect_samples(new_data)

    candidates = []
    for old_path in report['removed']:
        for new_path in report['added']:
            if _parent(old_path) != _parent(new_path):
                continue
            name = _name_score(old_path, new_path)
            types = _type_score(old_fp, new_fp, old_path, new_path)
            values = _value_score(old_samples, new_samples, old_path, new_path)
            confidence = 0.4 * name + 0.2 * types + 0.4 * values
            candidates.append({
                'from': old_path,
                'to': new_path,
                'confidence': round(confidence, 3),
                'name_score': round(name, 3),
                'type_score': round(types, 3),
                'value_score': round(values, 3),
            })

    candidates.sort(key=lambda c: c['confidence'], reverse=True)

    matches = []
    used_old = set()
    used_new = set()
    for c in candidates:
        if c['confidence'] < min_confidence:
            break
        if c['from'] in used_old or c['to'] in used_new:
            continue
        matches.append(c)
        used_old.add(c['from'])
        used_new.add(c['to'])
    return matches