import subprocess
import json
import datetime
from pathlib import Path

# Data di oggi in formato "9 giugno 2026"
mesi = ["gennaio","febbraio","marzo","aprile","maggio","giugno",
        "luglio","agosto","settembre","ottobre","novembre","dicembre"]
oggi = datetime.date.today()
query = f"{oggi.day} {mesi[oggi.month-1]} {oggi.year}"

# Ricerca con yt-dlp
result = subprocess.run([
    "yt-dlp",
    f"ytsearch200:{query}",
    "--match-filter", "duration <= 180",
    "--print", "%(.{id,title,channel,channel_follower_count,duration,thumbnail})j",
    "--no-download",
    "--no-warnings"
], capture_output=True, text=True)
print("STDOUT:", result.stdout[:500])
print("STDERR:", result.stderr[:500])
# Parsing risultati
videos = []
seen = set()
for line in result.stdout.splitlines():
    try:
        v = json.loads(line)
        if v["id"] not in seen:
            seen.add(v["id"])
            videos.append(v)
    except:
        continue

# Generazione HTML
cards = ""
for v in videos:
    vid_id = v.get("id", "")
    title = v.get("title", "")
    channel = v.get("channel", "")
    followers = v.get("channel_follower_count", 0)
    duration = v.get("duration", 0)
    thumbnail = v.get("thumbnail", "")
    url = f"https://www.youtube.com/shorts/{vid_id}"
    mins = int(duration) // 60
    secs = int(duration) % 60
    dur_str = f"{mins}:{secs:02d}"
    if followers and followers >= 1000:
        followers_str = f"{followers/1000:.1f}K iscritti"
    elif followers:
        followers_str = f"{followers} iscritti"
    else:
        followers_str = ""

    cards += f"""
    <a href="{url}" target="_blank" class="card">
        <div class="thumb">
            <img src="{thumbnail}" alt="{title}" onerror="this.style.display='none'">
            <span class="duration">{dur_str}</span>
        </div>
        <div class="info">
            <p class="title">{title}</p>
            <p class="channel">👤 {channel}{' · ' + followers_str if followers_str else ''}</p>
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
  .grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }}
  .card {{ background: #1e1e1e; border-radius: 10px; overflow: hidden; text-decoration: none; color: inherit; display: block; }}
  .thumb {{ position: relative; width: 100%; aspect-ratio: 9/16; background: #333; }}
  .thumb img {{ width: 100%; height: 100%; object-fit: cover; }}
  .duration {{ position: absolute; bottom: 5px; right: 5px; background: rgba(0,0,0,0.7); color: #fff; font-size: 10px; padding: 1px 5px; border-radius: 3px; }}
  .info {{ padding: 6px 8px 10px; }}
  .title {{ font-size: 11px; margin: 0 0 4px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
  .channel {{ font-size: 10px; color: #aaa; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
</style>
</head>
<body>
<h1>Shorts del {query}</h1>
<p class="count">{len(videos)} video trovati</p>
<div class="grid">
{cards}
</div>
</body>
</html>"""

Path("index.html").write_text(html, encoding="utf-8")
print(f"Generati {len(videos)} video per '{query}'")
