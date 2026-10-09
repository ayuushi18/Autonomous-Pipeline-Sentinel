import requests
import json

def fetch():
    r = requests.get(
        'https://data.cdc.gov/resource/45cq-cw4i.json',
        params={'$limit': 100},
        timeout=45
    )
    return r.json()

if __name__ == "__main__":
    data = fetch()
    json.dump(data, open('govdata_snapshot.json', 'w'))
    print("Saved!")