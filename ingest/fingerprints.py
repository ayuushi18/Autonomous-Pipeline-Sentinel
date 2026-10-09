def _walk(node, path, stats):
    entry = stats.setdefault(path, {"count": 0, "types": {}})
    entry["count"] += 1

    t = "null" if node is None else type(node).__name__
    entry["types"][t] = entry["types"].get(t, 0) + 1

    if isinstance(node, dict):
        for key, value in node.items():
            _walk(value, f"{path}.{key}", stats)
    elif isinstance(node, list):
        for item in node:
            _walk(item, f"{path}[]", stats)


def _parent(path):
    if path == "$" or path.endswith("[]"):
        return None
    return path.rsplit(".", 1)[0]


def fingerprint(data):
    stats = {}
    _walk(data, "$", stats)

    result = {}
    for path, entry in stats.items():
        total = entry["count"]
        types = {t: round(c / total, 3) for t, c in entry["types"].items()}

        parent = _parent(path)
        if parent is not None and parent in stats:
            presence = round(total / stats[parent]["count"], 3)
        else:
            presence = None

        result[path] = {"types": types, "presence": presence}

    return result