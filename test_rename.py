import json
import copy
from ingest.fingerprints import fingerprint
from ingest.compare import compare
from ingest.rename_finder import find_renames

old_data = json.load(open('snapshots/jobs_snapshot.json'))

new_data = copy.deepcopy(old_data)
for job in new_data['results']:
    if 'company' in job and 'display_name' in job['company']:
        job['company']['name'] = job['company'].pop('display_name')
    if 'salary_min' in job:
        job['min_salary'] = job.pop('salary_min')

old_fp = fingerprint(old_data)
new_fp = fingerprint(new_data)
report = compare(old_fp, new_fp)
print('Added:', report['added'])
print('Removed:', report['removed'])
print()

matches = find_renames(report, old_fp, new_fp, old_data, new_data)
for m in matches:
    print(m)