import json 
from ingest.fingerprints import fingerprint 

data = json.load(open('snapshots/job_snapshot.json')) 
fp = fingerprint(data) 

for path, info in list(fp.items())[:20]: 
    print(path, info) 