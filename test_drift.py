import json
import copy
from ingest.values import extract_values
from ingest.value_drift import compare_values

data = json.load(open('snapshots/jobs_snapshot.json'))
old_n, old_nulls = extract_values(data)

print('Test 0 (same data):', compare_values(old_n, old_n, old_nulls, old_nulls))

fake = copy.deepcopy(data)
for job in fake['results']:
    for key in ('salary_min', 'salary_max'):
        if job.get(key) is not None:
            job[key] *= 1000
n, nl = extract_values(fake)
print('Test A (units changed):', compare_values(old_n, n, old_nulls, nl))

fake = copy.deepcopy(data)
for job in fake['results']:
    job['salary_min'] = None
n, nl = extract_values(fake)
print('Test B (salary empty):', compare_values(old_n, n, old_nulls, nl))