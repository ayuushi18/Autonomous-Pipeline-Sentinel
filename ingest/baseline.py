def build_baseline(fingerprints):
    paths = {}
    for fp in fingerprints:
        for path, info in fp.items():
            entry = paths.setdefault(path, {'seen': 0, 'types': set(), 'presence': []})
            entry['seen'] += 1
            entry['types'].update(info['types'])
            if info['presence'] is not None:
                entry['presence'].append(info['presence'])
    return {'n': len(fingerprints), 'paths': paths}


def filter_report(report, baseline, stable_rate=0.8, margin=0.1):
    n = baseline['n']
    paths = baseline['paths']

    added = [p for p in report['added'] if p not in paths]

    removed = []
    for p in report['removed']:
        entry = paths.get(p)
        if entry is None or entry['seen'] / n >= stable_rate:
            removed.append(p)

    type_changed = {}
    for p, change in report['type_changed'].items():
        entry = paths.get(p)
        known = entry['types'] if entry else set()
        if set(change['now']) - known:
            type_changed[p] = change

    presence_shift = {}
    for p, change in report['presence_shift'].items():
        entry = paths.get(p)
        seen = entry['presence'] if entry else []
        if not seen:
            presence_shift[p] = change
        elif not (min(seen) - margin <= change['now'] <= max(seen) + margin):
            presence_shift[p] = change

    return {
        'added': added,
        'removed': removed,
        'type_changed': type_changed,
        'presence_shift': presence_shift,
    }