import os
import json
from prefect import flow, task
from jobs import fetch as fetch_jobs
from govdata import fetch as fetch_govdata
from transit import fetch as fetch_transit
from fingerprints import fingerprint
from compare import compare
from datetime import datetime
from values import extract_values 
from value_drift import compare_values
from healer import heal

def save_history(name, data): 
    folder = f'snapshots/history/{name}' 
    os.makedirs(folder, exist_ok=True) 
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S') 
    with open(f'{folder}/{stamp}.json', 'w') as f: 
        json.dump(data, f) 

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def process(name, data):
    if not data:
        raise ValueError(f'{name} returned empty data')

    snap_path = f'snapshots/{name}_snapshot.json'
    fp_path = f'snapshots/{name}_fingerprint.json'
    new_fp = fingerprint(data)
    old_fp = load_json(fp_path)
    old_data = load_json(snap_path)

    if old_fp:
        report = compare(old_fp, new_fp)
        print(f'[{name}] structure drift:', report)
        if old_data:
            data, decision = heal(name, data, old_data, old_fp, new_fp, report)
            if decision:
                print(f'[{name}] heal decision:', decision['action'])
            if decision and decision['action'] == 'patch_applied':
                new_fp = fingerprint(data)
    else:
        print(f'[{name}] first run, nothing to compare yet')

    if old_data:
        old_numbers, old_nulls = extract_values(old_data)
        new_numbers, new_nulls = extract_values(data)
        print(f'[{name}] value drift:',
              compare_values(old_numbers, new_numbers, old_nulls, new_nulls))

    with open(snap_path, 'w') as f:
        json.dump(data, f)

    save_history(name, data)

    with open(fp_path, 'w') as f:
        json.dump(new_fp, f, indent=2)

@task
def run_jobs():
    try:
        process('jobs', fetch_jobs())
    except Exception as e:
        print('jobs FAILED:', e)


@task
def run_govdata():
    try:
        process('govdata', fetch_govdata())
    except Exception as e:
        print('govdata FAILED:', e)


@task
def run_transit():
    try:
        process('transit', fetch_transit())
    except Exception as e:
        print('transit FAILED:', e)


@flow
def ingestion_flow():
    run_jobs()
    run_govdata()
    run_transit()


if __name__ == "__main__":
    ingestion_flow()