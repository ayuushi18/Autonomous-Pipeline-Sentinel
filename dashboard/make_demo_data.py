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

log = ROOT / 'logs' / 'heal_log.jsonl'
if log.exists():
    shutil.copy(log, OUT / 'heal_log.jsonl')

for path in sorted(OUT.iterdir()):
    print(f'{path.name}: {path.stat().st_size / 1024:.0f} KB')