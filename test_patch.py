import json
import copy
from ingest.fingerprints import fingerprint
from ingest.compare import compare
from ingest.rename_finder import find_renames
from ingest.patcher import build_patch, apply_patch

old_data = json.load(open('snapshots/jobs_snapshot.json'))

# Inject two renames to simulate an API change
new_data = copy.deepcopy(old_data)
for job in new_data['results']:
    if 'company' in job and 'display_name' in job['company']:
        job['company']['name'] = job['company'].pop('display_name')
    if 'salary_min' in job:
        job['min_salary'] = job.pop('salary_min')

old_fp = fingerprint(old_data)
new_fp = fingerprint(new_data)
report = compare(old_fp, new_fp)

matches = find_renames(report, old_fp, new_fp, old_data, new_data)
patch = build_patch('jobs', matches)
print('Patch:')
print(json.dumps(patch, indent=2))

fixed = apply_patch(new_data, patch)
after = compare(old_fp, fingerprint(fixed))
print()
print('Drift after patch:', after)
print('Patch restores original data:', fixed == old_data)