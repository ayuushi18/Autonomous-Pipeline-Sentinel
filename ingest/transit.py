import requests
from google.transit import gtfs_realtime_pb2
import json

def fetch():
    r = requests.get('https://data.texas.gov/download/rmk2-acnw/application%2Foctet-stream')
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(r.content)  # note: .content not .json()
    
    # convert to a plain dict/list so it's easy to save/compare
    entities = []
    for entity in feed.entity:
        entities.append(str(entity))  # simple version for now
    return entities

if __name__ == "__main__":
    data = fetch()
    print("Number of entities:", len(data))
    json.dump(data, open('transit_snapshot.json', 'w'))
    print("Saved!")