import requests
import json
from google.transit import gtfs_realtime_pb2
from google.protobuf.json_format import MessageToDict

def fetch():
    r = requests.get('https://data.texas.gov/download/rmk2-acnw/application%2Foctet-stream', timeout=15)
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(r.content)
    return [MessageToDict(entity) for entity in feed.entity]

if __name__ == "__main__":
    data = fetch()
    json.dump(data, open('transit_snapshot.json', 'w'))
    print("Saved!")