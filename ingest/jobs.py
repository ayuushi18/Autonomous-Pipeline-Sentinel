import requests
import json

def fetch():
    r = requests.get('https://api.adzuna.com/v1/api/jobs/us/search/1?app_id=91f4b031&app_key=d7fd736eb5ef8e2db7b9a798a204fcfe&what=data%20scientist&where=austin')
    data = r.json()
    json.dump(data, open('snapshot.json', 'w'))
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    data = fetch()
    json.dump(data, open('snapshots/jobs_snapshot.json', 'w'))
    print("Saved!")