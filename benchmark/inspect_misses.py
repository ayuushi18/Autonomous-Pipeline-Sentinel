import json

rows = json.load(open('benchmark/results.json'))['injected']
for r in rows:
    if r['type'] == 'null_out' and not r['localized']:
        print(r['source'], r['info'])