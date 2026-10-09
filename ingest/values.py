def _collect(node, path, numbers, nulls): 
    if isinstance(node, dict): 
        for key, value in node.items(): 
            _collect(value, f"{path}.{key}", numbers, nulls) 
    elif isinstance(node, list): 
        for item in node: 
            _collect(item, f"{path}[]", numbers, nulls) 
    else: 
        counts = nulls.setdefault(path, [0, 0]) 
        counts[1] += 1 
        if node is None: 
            counts[0] += 1 
        elif isinstance(node, (int, float)) and not isinstance(node, bool): 
            numbers.setdefault(path, []).append(node) 

def extract_values(data): 
    numbers = {} 
    nulls = {} 
    _collect(data, "$", numbers, nulls) 
    return numbers, nulls