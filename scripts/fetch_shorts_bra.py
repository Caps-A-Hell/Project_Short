import os
import json
import re
import time
import datetime
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from zoneinfo import ZoneInfo

API_KEY = os.environ["YOUTUBE_API_KEY"]

# --- Impostazioni specifiche per questa lingua/area ---
LANG_CODE = "bra"
LANG_LABEL = "BRA"
REGION_CODES = ["BR"]
ORDERS = ["date"]
MAX_PER_CHANNEL = 3

meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
oggi = datetime.datetime.now(ZoneInfo("America/Sao_Paulo")).date()
query = f"{oggi.day} de {meses[oggi.month - 1]} de {oggi.year}"
data_iso = oggi.strftime("%Y-%m-%d")
json_path = Path(f"{LANG_CODE}-{data_iso}.json")

quota_usata = 0


def api_get(url, costo, tentativi=5):
    global quota_usata
    quota_usata += costo
    attesa = 5
    for tentativo in range(tentativi):
        try:
            with urllib.request.urlopen(url) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and tentativo < tentativi - 1:
                print(f"Errore 429, attendo {attesa}s e riprovo ({tentativo + 1}/{tentativi})...")
                time.sleep(attesa)
                attesa *= 2
            else:
                raise


# --- Ricerca video tramite query testuale, per ciascuna regione e ordinamento ---
video_ids = []
for region in REGION_CODES:
    for order in ORDERS:
        search_url = (
            "https://www.googleapis.com/youtube/v3/search?"
            + urllib.parse.urlencode({
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": 50,
                "order": order,
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
    data = api_get(details_url, costo=1)
    for item in data.get("items", []):
        videos.append(item)


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
        v["_views"] = int(v.get("statistics", {}).get("viewCount", 0))
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

# --- Unione con dati già salvati oggi per questa lingua (se presenti) ---
existing = []
if json_path.exists():
    existing = json.loads(json_path.read_text(encoding="utf-8"))

existing_ids = {item["id"] for item in existing}
nuovi_candidati = [
    {
        "id": v["id"],
        "title": v["snippet"]["title"],
        "channel": v["snippet"]["channelTitle"],
        "channel_id": v["snippet"]["channelId"],
        "thumbnail": v["snippet"]["thumbnails"].get("high", {}).get("url", ""),
        "duration_s": v["_duration_s"],
        "is_vertical": v["_is_vertical"],
        "views": v["_views"],
    }
    for v in filtered if v["id"] not in existing_ids
]

# --- Applica il limite massimo di video per canale, contando anche quelli già esistenti ---
conteggio_canale = {}
for item in existing:
    conteggio_canale[item["channel_id"]] = conteggio_canale.get(item["channel_id"], 0) + 1

nuovi = []
for item in nuovi_candidati:
    cid = item["channel_id"]
    if conteggio_canale.get(cid, 0) >= MAX_PER_CHANNEL:
        continue
    conteggio_canale[cid] = conteggio_canale.get(cid, 0) + 1
    nuovi.append(item)

tutti = existing + nuovi
json_path.write_text(json.dumps(tutti, ensure_ascii=False), encoding="utf-8")


def format_count(n):
    if not n:
        return ""
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{n / 1000:.1f}K"
    return str(n)


cards = ""
for v in tutti:
    vid_id = v["id"]
    title = v["title"]
    channel = v["channel"]
    channel_id = v["channel_id"]
    followers = format_count(channel_info.get(channel_id))
    thumbnail = v["thumbnail"]
    duration_s = v["duration_s"]
    mins, secs = duration_s // 60, duration_s % 60
    dur_str = f"{mins}:{secs:02d}"
    views_str = format_count(v.get("views", 0))
    url = f"https://www.youtube.com/watch?v={vid_id}"
    badge = '<span class="badge">Short verticale</span>' if v["is_vertical"] else ""

    cards += f"""
    <a href="{url}" target="_blank" class="card">
        <div class="thumb">
            <img src="{thumbnail}" alt="{title}" onerror="this.style.display='none'">
            <span class="views">{'👁 ' + views_str if views_str else ''}</span>
            <span class="duration">{dur_str}</span>
            {badge}
        </div>
        <div class="info">
            <p class="title">{title}</p>
            <p class="channel">👤 {channel}{' · ' + followers + ' iscritti' if followers else ''}</p>
        </div>
    </a>"""

html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Shorts {LANG_LABEL} {query}</title>
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
  .views {{ position: absolute; bottom: 4px; left: 4px; background: rgba(0,0,0,0.7); color: #fff; font-size: 9px; padding: 1px 4px; border-radius: 3px; }}
  .badge {{ position: absolute; top: 4px; left: 4px; background: #4ea1ff; color: #000; font-size: 8px; padding: 1px 4px; border-radius: 3px; font-weight: bold; }}
  .info {{ padding: 5px 6px 7px; }}
  .title {{ font-size: 9px; margin: 0 0 3px; line-height: 1.3; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
  .channel {{ font-size: 8px; color: #aaa; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
</style>
</head>
<body>
<a href="index.html" class="back">← Torna all'indice</a>
<h1>Shorts {LANG_LABEL} del {query}</h1>
<p class="count">{len(tutti)} video trovati</p>
<div class="grid">
{cards}
</div>
</body>
</html>"""

Path(f"{LANG_CODE}-{data_iso}.html").write_text(html, encoding="utf-8")
print(f"[{LANG_CODE.upper()}] Totale {len(tutti)} video per '{query}' ({len(nuovi)} nuovi, {len(nuovi_candidati) - len(nuovi)} scartati per limite canale)")
print(f"[{LANG_CODE.upper()}] Quota API stimata usata in questa esecuzione: {quota_usata} unità")
