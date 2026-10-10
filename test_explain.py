from ingest.explainer import explain, template_explanation

applied = {
    'source': 'jobs',
    'action': 'patch_applied',
    'patch': {'renames': [{
        'source': '$.results[].company.name',
        'target': '$.results[].company.display_name',
        'confidence': 0.92}]},
    'checks': {'structure_restored': True, 'values_consistent': True,
               'harmless_on_history': True},
}

rejected = {
    'source': 'jobs',
    'action': 'patch_rejected',
    'patch': {'renames': [{
        'source': '$.results[].min_salary',
        'target': '$.results[].salary_min',
        'confidence': 0.87}]},
    'checks': {'structure_restored': True, 'values_consistent': False,
               'harmless_on_history': True},
}

no_action = {
    'source': 'transit',
    'action': 'no_action',
    'reason': 'no confident rename match',
    'added': [],
    'removed': ['$[].tripUpdate.stopTimeUpdate[].arrival.uncertainty'],
}

for d in (applied, rejected, no_action):
    print(d['action'])
    print('  template:', template_explanation(d))
    result = explain(d)
    print(f"  {result['by']}:", result['text'])
    print()