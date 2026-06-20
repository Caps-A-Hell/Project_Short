import os
import json
import re
import datetime
import urllib.request
import urllib.parse
from pathlib import Path

API_KEY = os.environ["YOUTUBE_API_KEY"]

# --- Impostazioni specifiche per questa lingua/area ---
LANG_CODE = "rus"
LANG_LABEL = "RUS"
REGION_CODES = ["RU"]

mesi_gen = ["января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря"]
oggi = datetime.date.today()
query = f"{oggi.day} {mesi_gen[oggi.month - 1]} {oggi.year}"
data_iso = oggi.strftime("%Y-%m-%d")
json_path = Path(f"{LANG_CODE}-{data_iso}.json")

quota_usata = 0


def api_get(url, costo):
    global quota_usata
    quota_usata += costo
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode())


# --- Ricerca video tramite query testuale, per ciascuna regione ---
video_ids = []
for region in REGION_CODES:
    search_url = (
        "https://www.googleapis.com/youtube/v3/search?"
        + urllib.parse.urlencode({
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 50,
            "order": "date",
            "regionCode": region,
            "key": API_KEY
        })
    )
    next_page = ""
    for _ in range(4):
        url = search_url + (f"&pageToken={next_page}" if next_page else "")
        data = api_get(url, costo=100)
        for item in data.get("items", []):
            vid = item["id"].get("videoId")
            if vid:
                video_ids.append(vid)
        next_page = data.get("nextPageToken")
        if not next_page:
            break

video_ids = list(dict.fromkeys(video_ids))

# --- Dettagli dei video (durata, dimensioni, canale, visualizzazioni) ---
videos = []
for i in range(0, len(video_ids), 50):
    batch = video_ids[i:i + 50]
    details_url = (
        "https://www.googleapis.com/youtube/v3/videos?"
        + urllib.parse.urlencode({
            "part": "snippet,contentDetails,statistics",
            "id": ",".join(batch),
            "key": API_KEY
        })
    )
    data = api_get(details_url,
