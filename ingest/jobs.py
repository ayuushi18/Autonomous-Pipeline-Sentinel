import os
import requests
from dotenv import load_dotenv

load_dotenv()


def fetch():
    r = requests.get(
        'https://api.adzuna.com/v1/api/jobs/us/search/1',
        params={
            'app_id': os.getenv('ADZUNA_APP_ID'),
            'app_key': os.getenv('ADZUNA_APP_KEY'),
            'what': 'data scientist',
            'where': 'austin'
        },
        timeout=15
    )
    r.raise_for_status()
    return r.json()
    
if __name__ == "__main__":
    data = fetch()
    json.dump(data, open('snapshots/jobs_snapshot.json', 'w'))
    print("Saved!")