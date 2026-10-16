import json

import pandas as pd
import streamlit as st

from ingest.explainer import template_explanation

ACTION_LABELS = {
    'patch_applied': 'Patch applied',
    'patch_rejected': 'Patch rejected',
    'no_action': 'No action',
}


def _safe(text):
    return text.replace('$', '\\$')


def _card(label, value, sub, tone=''):
    return (f'<div class="card"><div class="label">{label}</div>'
            f'<div class="value {tone}">{value}</div>'
            f'<div class="sub">{sub}</div></div>')


def _load(path, origin):
    entries = []
    if not path.exists():
        return entries
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        entry['origin'] = origin
        entries.append(entry)
    return entries


def _explanation(entry):
    saved = entry.get('explanation')
    if isinstance(saved, dict) and saved.get('text'):
        return saved['text'], saved.get('by', 'template')
    try:
        return template_explanation(entry), 'template'
    except (KeyError, TypeError):
        return 'No explanation was recorded for this decision.', 'none'


def render_log(data_dir):
    st.write('Every decision the healer makes is recorded with its validation checks '
             'and a plain-English explanation. The code makes the decision; the '
             'explanation only narrates it.')

    live = _load(data_dir / 'heal_log.jsonl', 'Live feeds')
    tests = _load(data_dir / 'test_heal_log.jsonl', 'Injected test')

    include_tests = st.toggle(
        'Include decisions from injected tests', value=True,
        help='These come from scripted tests where renames were injected on purpose.')
    entries = live + (tests if include_tests else [])

    if not entries:
        st.info('No decisions recorded yet. Run the pipeline or python test_heal.py, '
                'then python dashboard/make_demo_data.py to refresh this tab.')
        return

    entries.sort(key=lambda e: e.get('time', ''), reverse=True)

    counts = {key: sum(e.get('action') == key for e in entries)
              for key in ACTION_LABELS}
    c1, c2, c3 = st.columns(3)
    c1.markdown(_card('Patches applied', counts['patch_applied'],
                      'validated, then fixed', 'good'), unsafe_allow_html=True)
    c2.markdown(_card('Patches rejected', counts['patch_rejected'],
                      'failed validation, left unchanged', 'warn'),
                unsafe_allow_html=True)
    c3.markdown(_card('No action', counts['no_action'],
                      'no confident rename found', 'accent'), unsafe_allow_html=True)

    live_actions = {e.get('action') for e in live}
    if include_tests and not (live_actions & {'patch_applied', 'patch_rejected'}):
        st.caption('No real field rename has happened on the live feeds so far, so '
                   'applied and rejected decisions come from injected tests.')

    st.write('')
    sources = sorted({e.get('source', '?') for e in entries})
    col_a, col_b = st.columns(2)
    pick_sources = col_a.multiselect('Feed', sources, default=sources)
    pick_actions = col_b.multiselect('Decision', list(ACTION_LABELS.values()),
                                     default=list(ACTION_LABELS.values()))
    wanted = {key for key, label in ACTION_LABELS.items() if label in pick_actions}
    shown = [e for e in entries
             if e.get('source', '?') in pick_sources and e.get('action') in wanted]

    if not shown:
        st.caption('No decisions match these filters.')
        return

    rows = []
    for e in shown:
        text, by = _explanation(e)
        rows.append({
            'Time': e.get('time', ''),
            'Origin': e['origin'],
            'Feed': e.get('source', ''),
            'Decision': ACTION_LABELS.get(e.get('action'), e.get('action')),
            'Explained by': by,
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True)

    st.write('')
    st.subheader('Details')
    for e in shown[:20]:
        text, by = _explanation(e)
        decision = ACTION_LABELS.get(e.get('action'), e.get('action'))
        label = f"{e.get('time', '')}  ·  {e.get('source', '')}  ·  {decision}  ·  {e['origin']}"
        with st.expander(label):
            st.markdown(_safe(text))
            st.caption(f'Explanation written by: {by}')

            patch = e.get('patch')
            if patch and patch.get('renames'):
                st.markdown('**Proposed renames**')
                st.dataframe(pd.DataFrame(patch['renames']), hide_index=True)

            checks = e.get('checks')
            if checks:
                st.markdown('**Validation checks**')
                st.dataframe(pd.DataFrame({
                    'Check': list(checks),
                    'Passed': ['✅' if ok else '❌' for ok in checks.values()],
                }), hide_index=True)

            if e.get('action') == 'no_action':
                st.markdown('**Fields that changed**')
                st.json({'added': e.get('added', []),
                         'removed': e.get('removed', [])})

    if len(shown) > 20:
        st.caption(f'Showing the 20 most recent of {len(shown)} decisions.')