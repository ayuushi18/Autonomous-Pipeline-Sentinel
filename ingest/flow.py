import os
import json
from prefect import flow, task
from jobs import fetch as fetch_jobs
from govdata import fetch as fetch_govdata
from transit import fetch as fetch_transit
from fingerprints import fingerprint
from compare import compare
from datetime import datetime

def save_history(name, data): 
    folder = f'snapshots/history/{name}' 
    os.makedirs(folder, exist_ok=True) 
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S') 
    with open(f'{folder}/{stamp}.json', 'w') as f: 
        json.dump(data, f) 

def process(name, data):
    snap_path = f'snapshots/{name}_snapshot.json'
    fp_path = f'snapshots/{name}_fingerprint.json'
    new_fp = fingerprint(data)

    if os.path.exists(fp_path):
        with open(fp_path) as f:
            old_fp = json.load(f)
        print(f'[{name}] drift report:', compare(old_fp, new_fp))
    else:
        print(f'[{name}] first run, nothing to compare yet')

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