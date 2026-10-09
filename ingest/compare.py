def compare(old, new, presence_threshold=0.2):
    added = [p for p in new if p not in old]
    removed = [p for p in old if p not in new]
    type_changed = {}
    presence_shift = {}

    for p in new:
        if p not in old:
            continue

        old_types = set(old[p]["types"])
        new_types = set(new[p]["types"])
        if old_types != new_types:
            type_changed[p] = {"was": sorted(old_types), "now": sorted(new_types)}

        o, n = old[p]["presence"], new[p]["presence"]
        if o is not None and n is not None and abs(o - n) >= presence_threshold:
            presence_shift[p] = {"was": o, "now": n}

    return {
        "added": added,
        "removed": removed,
        "type_changed": type_changed,
        "presence_shift": presence_shift,
    }