import json
import copy
from ingest.fingerprints import fingerprint
from ingest.compare import compare
from ingest.rename_finder import find_renames
from ingest.patcher import build_patch
from ingest.validator import load_history, validate_patch

old_data = json.load(open('snapshots/jobs_snapshot.json'))
old_fp = fingerprint(old_data)
history = load_history('jobs')
print('History snapshots loaded:', len(history))

# Case 1 (injected): two plain renames
new_data = copy.deepcopy(old_data)
for job in new_data['results']:
    if 'company' in job and 'display_name' in job['company']:
        job['company']['name'] = job['company'].pop('display_name')
    if 'salary_min' in job:
        job['min_salary'] = job.pop('salary_min')

new_fp = fingerprint(new_data)
report = compare(old_fp, new_fp)
matches = find_renames(report, old_fp, new_fp, old_data, new_data)
patch = build_patch('jobs', matches)
result = validate_patch(patch, new_data, old_fp, history)
print('Case 1 (plain renames):', result['passed'], result['checks'])

# Case 2 (injected): rename AND values secretly multiplied by 1000
tricky = copy.deepcopy(old_data)
for job in tricky['results']:
    if 'salary_min' in job:
        value = job.pop('salary_min')
        job['min_salary'] = value * 1000 if value is not None else None

risky_patch = {
    'source_name': 'jobs',
    'renames': [{
        'source': '$.results[].min_salary',
        'target': '$.results[].salary_min',
        'confidence': 0.87,
    }],
}
result = validate_patch(risky_patch, tricky, old_fp, history)
print('Case 2 (rename + 1000x values):', result['passed'], result['checks'])