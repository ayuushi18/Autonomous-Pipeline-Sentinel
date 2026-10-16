import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / 'demo_data'
OUT.mkdir(exist_ok=True)

for name in ('results.json', 'heal_results.json', 'RESULTS.md'):
    shutil.copy(ROOT / 'benchmark' / name, OUT / name)

govdata = json.load(open(ROOT / 'snapshots' / 'govdata_snapshot.json'))
with open(OUT / 'govdata_sample.json', 'w') as f:
    json.dump(govdata, f)

jobs = json.load(open(ROOT / 'snapshots' / 'jobs_snapshot.json'))
for job in jobs.get('results', []):
    job.pop('redirect_url', None)
    job.pop('adref', None)
with open(OUT / 'jobs_sample.json', 'w') as f:
    json.dump(jobs, f)

transit = json.load(open(ROOT / 'snapshots' / 'transit_snapshot.json'))
with open(OUT / 'transit_sample.json', 'w') as f:
    json.dump(transit[:300], f)

for log_name in ('heal_log.jsonl', 'test_heal_log.jsonl'):
    log = ROOT / 'logs' / log_name
    if log.exists():
        shutil.copy(log, OUT / log_name)
    else:
        print(f'(no {log_name} found, skipping)')

for path in sorted(OUT.iterdir()):
    print(f'{path.name}: {path.stat().st_size / 1024:.0f} KB')