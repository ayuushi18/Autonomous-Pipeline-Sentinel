import json 
from ingest.values import extract_values 

data = json.load(open('snapshots/transit_snapshot.json')) 
numbers, nulls = extract_values(data) 
for path, vals in numbers.items(): 
    print(path, '| count:', len(vals), '| min:', min(vals), '| max:', max(vals)) 