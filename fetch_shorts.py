import os
import json
import re
import datetime
import urllib.request
import urllib.parse
from pathlib import Path

API_KEY = os.environ["YOUTUBE_API_KEY"]

mesi = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
oggi = datetime.date.today()
query = f"{oggi.day} {mesi[oggi.month - 1]} {oggi.year}"
data_iso = oggi.strftime("%Y-%m-%d")
json_path = Path(f"{data_iso}.json")


quota_usata = 0


def api_get(url, costo):
    global quota_usata
    quota_usata += costo
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode())


# --- Ricerca video tramite query testuale ---
search_url = (
    "https://www.googleapis.com/youtube/v3/search?"
    + urllib.parse.urlencode({
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 50,
        "order": "date",
        "key": API_KEY
    })
)

video_ids = []
next_page = ""
for _ in range(4):  # fino a 200 risultati (4 pagine x 50)
    url = search_url + (f"&pageToken={next_page}" if next_page else "")
    data = api_get(url, costo=100)
    for item in data.get("items", []):
        vid = item["id"].get("videoId")
        if vid:
            video_ids.append(vid)
    next_page = data.get("nextPageToken")
    if not next_page:
        break

video_ids = list(dict.fromkeys(video_ids))  # deduplicazione mantenendo ordine

# --- Dettagli dei video (durata, dimensioni, canale) ---
videos = []
for i in range(0, len(video_ids), 50):
    batch = video_ids[i:i + 50]
    details_url = (
        "https://www.googleapis.com/youtube/v3/videos?"
        + urllib.parse.urlencode({
            "part": "snippet,contentDetails",
            "id": ",".join(batch),
            "key": API_KEY
        })
    )
    data = api_get(details_url, costo=1)
    for item in data.get("items", []):
        videos.append(item)


# --- Parsing durata ISO8601 (es. PT1M30S) ---
def parse_duration(d):
    h = re.search(r"(\d+)H", d)
    m = re.search(r"(\d+)M", d)
    s = re.search(r"(\d+)S", d)
    return (int(h.group(1)) if h else 0) * 3600 + (int(m.group(1)) if m else 0) * 60 + (int(s.group(1)) if s else 0)


# --- Filtra solo video <= 3 minuti, raccogli ID canali ---
filtered = []
channel_ids = set()
for v in videos:
    if "contentDetails" not in v or "duration" not in v["contentDetails"]:
        continue
    duration_s = parse_duration(v["contentDetails"]["duration"])
    if duration_s <= 180:
        v["_duration_s"] = duration_s
        thumb = v["snippet"]["thumbnails"].get("maxres") or v["snippet"]["thumbnails"].get("high")
        v["_thumb_w"] = thumb.get("width", 0) if thumb else 0
        v["_thumb_h"] = thumb.get("height", 0) if thumb else 0
        v["_is_vertical"] = v["_thumb_h"] > v["_thumb_w"]
        filtered.append(v)
        channel_ids.add(v["snippet"]["channelId"])

# --- Dettagli canali (iscritti) ---
channel_info = {}
channel_ids = list(channel_ids)
for i in range(0, len(channel_ids), 50):
    batch = channel_ids[i:i + 50]
    ch_url = (
        "https://www.googleapis.com/youtube/v3/channels?"
        + urllib.parse.urlencode({
            "part": "statistics",
            "id": ",".join(batch),
            "key": API_KEY
        })
    )
    data = api_get(ch_url, costo=1)
    for item in data.get("items", []):
        channel_info[item["id"]] = item["statistics"].get("subscriberCount")

# --- Unione con dati già salvati oggi (se presenti, dalla precedente esecuzione) ---
existing = []
if json_path.exists():
    existing = json.loads(json_path.read_text(encoding="utf-8"))

existing_ids = {item["id"] for item in existing}
nuovi = [
    {
        "id": v["id"],
        "title": v["snippet"]["title"],
        "channel": v["snippet"]["channelTitle"],
        "channel_id": v["snippet"]["channelId"],
        "thumbnail": v["snippet"]["thumbnails"].get("high", {}).get("url", ""),
        "duration_s": v["_duration_s"],
        "is_vertical": v["_is_vertical"],
    }
    for v in filtered if v["id"] not in existing_ids
]

tutti = existing + nuovi
json_path.write_text(json.dumps(tutti, ensure_ascii=False), encoding="utf-8")


# --- Generazione card HTML ---
def format_followers(n):
    if not n:
        return ""
    n = int(n)
    if n >= 1000:
        return f"{n / 1000:.1f}K iscritti"
    return f"{n} iscritti"


cards = ""
for v in tutti:
    vid_id = v["id"]
    title = v["title"]
    channel = v["channel"]
    channel_id = v["channel_id"]
    followers = format_followers(channel_info.get(channel_id))
    thumbnail = v["thumbnail"]
    duration_s = v["duration_s"]
    mins, secs = duration_s // 60, duration_s % 60
    dur_str = f"{mins}:{secs:02d}"
    url = f"https://www.youtube.com/watch?v={vid_id}"
    badge = '<span class="badge">Short verticale</span>' if v["is_vertical"] else ""

    cards += f"""
    <a href="{url}" target="_blank" class="card">
        <div class="thumb">
            <img src="{thumbnail}" alt="{title}" onerror="this.style.display='none'">
            <span class="duration">{dur_str}</span>
            {badge}
        </div>
        <div class="info">
            <p class="title">{title}</p>
            <p class="channel">👤 {channel}{' · ' + followers if followers else ''}</p>
        </div>
    </a>"""

html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Shorts {query}</title>
<style>
  body {{ font-family: sans-serif; background: #111; color: #eee; padding: 12px; }}
  h1 {{ font-size: 16px; margin-bottom: 4px; }}
  .count {{ font-size: 12px; color: #aaa; margin-bottom: 12px; }}
  .back {{ display: inline-block; margin-bottom: 12px; color: #4ea1ff; text-decoration: none; font-size: 13px; }}
  .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }}
  .card {{ background: #1e1e1e; border-radius: 10px; overflow: hidden; text-decoration: none; color: inherit; display: block; }}
  .thumb {{ position: relative; width: 100%; aspect-ratio: 9/16; background: #333; }}
  .thumb img {{ width: 100%; height: 100%; object-fit: cover; }}
  .duration {{ position: absolute; bottom: 4px; right: 4px; background: rgba(0,0,0,0.7); color: #fff; font-size: 9px; padding: 1px 4px; border-radius: 3px; }}
  .badge {{ position: absolute; top: 4px; left: 4px; background: #4ea1ff; color: #000; font-size: 8px; padding: 1px 4px; border-radius: 3px; font-weight: bold; }}
  .info {{ padding: 5px 6px 7px; }}
  .title {{ font-size: 9px; margin: 0 0 3px; line-height: 1.3; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
  .channel {{ font-size: 8px; color: #aaa; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
</style>
</head>
<body>
<a href="index.html" class="back">← Torna all'indice</a>
<h1>Shorts del {query}</h1>
<p class="count">{len(tutti)} video trovati</p>
<div class="grid">
{cards}
</div>
</body>
</html>"""

Path(f"{data_iso}.html").write_text(html, encoding="utf-8")
print(f"Totale {len(tutti)} video per '{query}' ({len(nuovi)} nuovi)")
print(f"Quota API stimata usata in questa esecuzione: {quota_usata} unità")

# --- Aggiorna pagina indice ---
index_path = Path("index.html")
giorni = sorted(Path(".").glob("????-??-??.html"), reverse=True)

righe = ""
for g in giorni:
    nome_file = g.name
    data_str = g.stem  # es. 2026-06-18
    anno, mese, giorno = data_str.split("-")
    etichetta = f"{int(giorno)} {mesi[int(mese) - 1]} {anno}"
    righe += f'<li><a href="{nome_file}">{etichetta}</a></li>\n'

index_html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Shorts Feed - Indice</title>
<style>
  body {{ font-family: sans-serif; background: #111; color: #eee; padding: 16px; }}
  h1 {{ font-size: 18px; }}
  ul {{ list-style: none; padding: 0; }}
  li {{ margin-bottom: 10px; }}
  a {{ color: #4ea1ff; text-decoration: none; font-size: 15px; }}
</style>
</head>
<body>
<h1>📅 Shorts Feed - Indice giorni</h1>
<ul>
{righe}
</ul>
</body>
</html>"""

index_path.write_text(index_html, encoding="utf-8")
