import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

import ingest.healer as healer
from benchmark.injector import (RENAME_STYLES, _apply_at, _candidates,
                                _try_inject, inject)
from ingest.compare import compare
from ingest.explainer import template_explanation
from ingest.fingerprints import fingerprint
from ingest.value_drift import compare_values
from ingest.values import extract_values

DATA = Path(__file__).resolve().parent / 'demo_data'

DRIFT_ORDER = ['rename', 'remove', 'type_change', 'unit_scale', 'null_out']
SOURCES = ['jobs', 'govdata', 'transit']
SCENARIOS = ['suffix', 'prefix', 'case', 'opaque', 'rename+scale']

BREAKS = {
    'Rename a field': 'rename',
    'Remove a field': 'remove',
    'Change a field type': 'type_change',
    'Change units (x100 or x1000)': 'unit_scale',
    'Empty out a field': 'null_out',
    'Rename AND secretly change units (tricky)': 'rename+scale',
}

# the live demo must never write logs or call an LLM
healer.log_decision = lambda entry: None

st.set_page_config(page_title='PipelineSentinel', page_icon='🛡️', layout='wide')

CSS = """
<style>
#MainMenu, footer {visibility: hidden;}
.block-container {padding-top: 2rem; max-width: 1100px;}
.hero h1 {font-size: 2.6rem; margin-bottom: 0.2rem; letter-spacing: -0.02em;}
.hero p {color: #8B93A7; font-size: 1.1rem; margin-top: 0;}
.card {background: #161B26; border: 1px solid #232A3A; border-radius: 14px; padding: 1.1rem 1.3rem; height: 100%;}
.card .label {color: #8B93A7; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em;}
.card .value {font-size: 2rem; font-weight: 700; margin: 0.2rem 0;}
.card .sub {color: #8B93A7; font-size: 0.85rem;}
.good {color: #2ECC9A;}
.accent {color: #9D85FF;}
.warn {color: #F5B642;}
.bad {color: #FF6B6B;}
.flow {display: flex; gap: 0.6rem; align-items: stretch; flex-wrap: wrap;}
.step {flex: 1; min-width: 150px; background: #161B26; border: 1px solid #232A3A; border-radius: 12px; padding: 0.9rem 1rem;}
.step b {color: #9D85FF;}
.step span {display: block; color: #8B93A7; font-size: 0.85rem; margin-top: 0.3rem;}
.arrow {align-self: center; color: #4B5468; font-size: 1.4rem;}
.note {border-left: 3px solid #7C5CFF; background: #161B26; padding: 0.7rem 1rem; border-radius: 6px; color: #B6BDD0; font-size: 0.9rem;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def card(label, value, sub, tone=''):
    return (f'<div class="card"><div class="label">{label}</div>'
            f'<div class="value {tone}">{value}</div>'
            f'<div class="sub">{sub}</div></div>')


def pct(part, whole):
    return round(100 * part / whole) if whole else 0


def safe(text):
    return text.replace('$', '\\$')


results = json.load(open(DATA / 'results.json'))
heal = json.load(open(DATA / 'heal_results.json'))
injected = results['injected']
clean = results['clean']

detected = sum(r['detected'] for r in injected)
localized = sum(r['localized'] for r in injected)
plain = [r for r in heal if r['scenario'] in ('suffix', 'prefix', 'case', 'opaque')]
healed_count = sum(r['outcome'] == 'healed_correct' for r in plain)
unsafe = sum(r['outcome'] == 'healed_wrong' for r in heal)
transit = [r for r in clean if r['source'] == 'transit']
alarm_before = pct(sum(r['alarm_before'] for r in transit), len(transit))
alarm_after = pct(sum(r['alarm_after'] for r in transit), len(transit))


def detection_table():
    rows = []
    for kind in DRIFT_ORDER:
        subset = [r for r in injected if r['type'] == kind]
        n = len(subset)
        rows.append({
            'Drift type': kind,
            'Trials': n,
            'Detected %': pct(sum(r['detected'] for r in subset), n),
            'Localized %': pct(sum(r['localized'] for r in subset), n),
        })
    return pd.DataFrame(rows)


def false_alarm_table():
    rows = []
    for source in SOURCES:
        subset = [r for r in clean if r['source'] == source]
        n = len(subset)
        rows.append({
            'Source': source,
            'Pairs': n,
            'Raw alarms %': pct(sum(r['alarm_before'] for r in subset), n),
            'With noise filter %': pct(sum(r['alarm_after'] for r in subset), n),
        })
    return pd.DataFrame(rows)


def heal_table():
    rows = []
    for scenario in SCENARIOS:
        subset = [r for r in heal if r['scenario'] == scenario]
        n = len(subset)
        rows.append({
            'Scenario': scenario,
            'Trials': n,
            'Healed %': pct(sum(r['outcome'] == 'healed_correct' for r in subset), n),
            'Rejected %': pct(sum(r['outcome'] == 'rejected' for r in subset), n),
            'Missed %': pct(sum(r['outcome'] == 'missed' for r in subset), n),
            'Wrong fix %': pct(sum(r['outcome'] == 'healed_wrong' for r in subset), n),
        })
    return pd.DataFrame(rows)


def load_notes():
    path = DATA / 'RESULTS.md'
    if not path.exists():
        return ''
    text = path.read_text(encoding='utf-8')
    marker = '## Method notes and limitations'
    if marker not in text:
        return ''
    return text.split(marker, 1)[1].strip()


def make_tricky(data, rng):
    options = sorted(_candidates(data)['unit_scale'])
    if not options:
        return None
    target = rng.choice(options)
    style = rng.choice(RENAME_STYLES)
    result = _try_inject(data, 'rename', target, rng, style)
    if result is None:
        return None
    mutated, info = result

    def scale(node, key):
        value = node[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        node[key] = value * 1000
        return True

    _apply_at(mutated, '$', info['new_path'], scale)
    info['type'] = 'rename+scale'
    return mutated, info


def any_alarm(structure, values):
    return any([
        structure['added'], structure['removed'], structure['type_changed'],
        structure['presence_shift'], values['value_shift'], values['null_shift'],
    ])


def was_localized(info, structure, values):
    kind = info['type']
    path = info['path']
    if kind in ('rename', 'rename+scale'):
        return info['new_path'] in structure['added'] and path in structure['removed']
    if kind == 'remove':
        return path in structure['removed']
    if kind == 'type_change':
        return path in structure['type_changed']
    if kind == 'unit_scale':
        return path in values['value_shift']
    return path in values['null_shift']


def describe_break(info):
    kind = info['type']
    if kind in ('rename', 'rename+scale'):
        text = f"Renamed `{info['path']}` to `{info['new_path']}`"
        if kind == 'rename+scale':
            text += ' and secretly multiplied its values by 1000'
    elif kind == 'remove':
        text = f"Removed `{info['path']}`"
    elif kind == 'type_change':
        text = f"Changed the type of `{info['path']}`"
    elif kind == 'unit_scale':
        text = f"Multiplied `{info['path']}` by {info['factor']}"
    else:
        text = f"Emptied out about 60% of `{info['path']}`"
    return text


def show_demo(source, kind, style, seed):
    data = json.load(open(DATA / f'{source}_sample.json'))
    rng = random.Random(f'{source}-{kind}-{style}-{seed}')
    if kind == 'rename+scale':
        result = make_tricky(data, rng)
    else:
        result = inject(data, kind, rng, None if style == 'random' else style)
    if result is None:
        st.warning('This feed has no field that fits that kind of break. '
                   'Try another feed or break type.')
        return
    mutated, info = result

    old_fp = fingerprint(data)
    new_fp = fingerprint(mutated)
    structure = compare(old_fp, new_fp)
    old_numbers, old_nulls = extract_values(data)
    new_numbers, new_nulls = extract_values(mutated)
    values = compare_values(old_numbers, new_numbers, old_nulls, new_nulls)

    healer.load_history = lambda name, limit=3: [data]
    healed, decision = healer.heal(source, mutated, data, old_fp, new_fp, structure)

    alarm = any_alarm(structure, values)
    exact = was_localized(info, structure, values)

    if decision is None:
        outcome, tone = 'Flagged for review', 'warn'
        detail = 'Auto-healing only handles renames, so a person is alerted.'
    elif decision['action'] == 'patch_applied':
        identical = healed == data
        outcome = 'Auto-healed' if identical else 'Wrong fix'
        tone = 'good' if identical else 'bad'
        detail = ('Repaired data is identical to the original.' if identical
                  else 'Repaired data differs from the original.')
    elif decision['action'] == 'patch_rejected':
        outcome, tone = 'Patch refused', 'good'
        detail = 'Validation failed, so nothing was changed.'
    else:
        outcome, tone = 'No confident match', 'warn'
        detail = 'Nothing was changed.'

    c1, c2, c3 = st.columns(3)
    c1.markdown(card('Alarm raised', 'Yes' if alarm else 'No',
                     'drift found in the data', 'good' if alarm else 'bad'),
                unsafe_allow_html=True)
    c2.markdown(card('Exact field named', 'Yes' if exact else 'No',
                     'the alarm pointed at the broken field',
                     'good' if exact else 'bad'), unsafe_allow_html=True)
    c3.markdown(card('Outcome', outcome, detail, tone), unsafe_allow_html=True)

    st.write('')
    left, right = st.columns(2)
    with left:
        st.markdown('**What was broken**')
        st.markdown(describe_break(info))
    with right:
        st.markdown('**What PipelineSentinel saw**')
        flagged = {k: v for k, v in {**structure, **values}.items() if v}
        if flagged:
            st.json(flagged)
        else:
            st.write('Nothing flagged.')

    if decision is not None:
        st.markdown('**What it did**')
        st.info(safe(template_explanation(decision)))
        if decision.get('checks'):
            checks = pd.DataFrame({
                'Validation check': list(decision['checks']),
                'Passed': ['✅' if ok else '❌' for ok in decision['checks'].values()],
            })
            st.dataframe(checks, hide_index=True)


st.markdown(
    '<div class="hero"><h1>🛡️ PipelineSentinel</h1>'
    '<p>A self-healing data pipeline that watches live feeds for schema and '
    'value drift, fixes safe renames, and explains every decision.</p></div>',
    unsafe_allow_html=True,
)

tab_overview, tab_try, tab_log, tab_bench = st.tabs(
    ['Overview', 'Try it', 'Decision log', 'Benchmark']
)

with tab_overview:
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(card('Faults detected', f'{detected} / {len(injected)}',
                     f'{pct(localized, len(injected))}% pinned to the exact field',
                     'good'), unsafe_allow_html=True)
    c2.markdown(card('Renames healed', f'{healed_count} / {len(plain)}',
                     'validated before applying', 'good'), unsafe_allow_html=True)
    c3.markdown(card('Unsafe patches', f'{unsafe} / {len(heal)}',
                     'applied across all tests', 'good'), unsafe_allow_html=True)
    c4.markdown(card('Transit false alarms', f'{alarm_before}% → {alarm_after}%',
                     'after learning a noise baseline', 'accent'),
                unsafe_allow_html=True)

    st.write('')
    st.subheader('How it works')
    steps = [
        ('Ingest', 'Pulls 3 live feeds: jobs, open data, transit'),
        ('Fingerprint', 'Maps every field path, type and presence rate'),
        ('Detect', 'Structure drift plus value drift (KS-test)'),
        ('Heal', 'Finds renames, validates, then patches'),
        ('Explain', 'Writes each decision in plain English'),
    ]
    html = '<div class="flow">'
    for i, (title, text) in enumerate(steps):
        html += f'<div class="step"><b>{title}</b><span>{text}</span></div>'
        if i < len(steps) - 1:
            html += '<div class="arrow">→</div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

    st.write('')
    st.markdown(
        '<div class="note">All drift in these numbers is synthetic: real snapshots '
        'were broken on purpose so the correct answer is known. False-alarm figures '
        'use real consecutive snapshots with small samples.</div>',
        unsafe_allow_html=True,
    )
    st.caption('[GitHub repository](https://github.com/ayuushi18/Autonomous-Pipeline-Sentinel)')

with tab_try:
    st.write('Pick a feed and a kind of break. A script damages a small sample of '
             'real data, then the actual detector and healer run on it, live.')
    col_a, col_b, col_c = st.columns(3)
    source = col_a.selectbox('Data feed', SOURCES)
    break_label = col_b.selectbox('What to break', list(BREAKS))
    seed = col_c.number_input('Random seed', min_value=0, max_value=9999, value=7,
                              help='Change it to break a different field.')
    style = 'random'
    if BREAKS[break_label] == 'rename':
        style = st.radio('Rename style', ['random'] + RENAME_STYLES, horizontal=True)

    if st.button('Break it and run PipelineSentinel', type='primary'):
        show_demo(source, BREAKS[break_label], style, int(seed))
    st.caption('The damage is synthetic and the samples are small. The noise baseline '
               'needs a history of snapshots, so it is not applied in this demo.')

with tab_log:
    st.caption('Decision log: built in step 4.')

with tab_bench:
    st.subheader('Drift detection')
    st.caption('Injected faults on copies of real snapshots, 20 trials per source and type. '
               '"Localized" means the alarm named the exact field that was broken.')
    det = detection_table()
    left, right = st.columns(2)
    left.dataframe(det, hide_index=True)
    right.bar_chart(det, x='Drift type', y=['Detected %', 'Localized %'],
                    stack=False, color=['#7C5CFF', '#2ECC9A'])

    st.write('')
    st.subheader('False alarms on real data')
    st.caption('Real consecutive snapshots with nothing injected. Small samples, so '
               'treat these as indicative.')
    fa = false_alarm_table()
    left, right = st.columns(2)
    left.dataframe(fa, hide_index=True)
    right.bar_chart(fa, x='Source', y=['Raw alarms %', 'With noise filter %'],
                    stack=False, color=['#4B5468', '#2ECC9A'])

    st.write('')
    st.subheader('Self-healing')
    st.caption('Injected renames. "Missed" means no confident match, so nothing was '
               'changed. In rename+scale, values were also multiplied by 1000.')
    st.dataframe(heal_table(), hide_index=True)

    notes = load_notes()
    if notes:
        with st.expander('Method notes and limitations'):
            st.markdown(notes)