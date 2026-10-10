import json
import copy
import ingest.healer as healer
from ingest.fingerprints import fingerprint
from ingest.compare import compare

healer.LOG_PATH = 'logs/test_heal_log.jsonl'

old_data = json.load(open('snapshots/jobs_snapshot.json'))
old_fp = fingerprint(old_data)


def run_case(label, new_data):
    new_fp = fingerprint(new_data)
    report = compare(old_fp, new_fp)
    healed, decision = healer.heal('jobs', new_data, old_data, old_fp, new_fp, report)
    print(label, '->', decision['action'] if decision else 'no drift')
    return healed


# Case 1 (injected): two plain renames, should be applied
case1 = copy.deepcopy(old_data)
for job in case1['results']:
    if 'company' in job and 'display_name' in job['company']:
        job['company']['name'] = job['company'].pop('display_name')
    if 'salary_min' in job:
        job['min_salary'] = job.pop('salary_min')
healed = run_case('Case 1 (plain renames)', case1)
print('  structure restored:', fingerprint(healed) == old_fp)

# Case 2 (injected): rename AND values multiplied by 1000, should be rejected
case2 = copy.deepcopy(old_data)
for job in case2['results']:
    if 'salary_min' in job:
        value = job.pop('salary_min')
        job['min_salary'] = value * 1000 if value is not None else None
healed = run_case('Case 2 (rename + 1000x values)', case2)
print('  data left untouched:', healed == case2)

# Case 3: nothing changed
run_case('Case 3 (no change)', copy.deepcopy(old_data))