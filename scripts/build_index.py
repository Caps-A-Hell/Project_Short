import re
from pathlib import Path

LANG_INFO = {
    "ita": {"label": "ITA", "flag": "🇮🇹"},
    "esp": {"label": "ESP", "flag": "🇪🇸"},
    "bra": {"label": "BRA", "flag": "🇧🇷"},
    "rus": {"label": "RUS", "flag": "🇷🇺"},
}

pattern = re.compile(r"^(ita|esp|bra|rus)-(\d{4}-\d{2}-\d{2})\.html$")

# --- Raccolta di tutti i file lingua-data presenti ---
trovati = {}
for f in Path(".").glob("*.html"):
    m = pattern.match(f.name)
    if m:
        lang, data = m.group(1), m.group(2)
        trovati.setdefault(data, []).append(lang)

date_ordinate = sorted(trovati.keys(), reverse=True)

blocchi = ""
for data in date_ordinate:
    anno, mese, giorno = data.split("-")
    etichetta = f"{int(giorno)}/{mese}/{anno}"
    pillole = ""
    for lang in sorted(trovati[data]):
        info = LANG_INFO[lang]
        href = f"{lang}-{data}.html"
        pillole += f'<a href="{href}" class="pill"><span class="flag">{info["flag"]}</span>{info["label"]}</a>\n'
    blocchi += f"""
    <div class="day-block">
        <p class="day-label">📅 {etichetta}</p>
        <div class="lang-row">
        {pillole}
        </div>
    </div>"""

index_html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Shorts Feed - Indice</title>
<style>
  body {{ font-family: sans-serif; background: #111; color: #eee; padding: 16px; }}
  h1 {{ font-size: 18px; margin-bottom: 16px; }}
  .day-block {{ margin-bottom: 16px; }}
  .day-label {{ font-size: 14px; font-weight: bold; margin: 0 0 6px; }}
  .lang-row {{ display: flex; gap: 8px; flex-wrap: wrap; }}
  .pill {{ display: flex; align-items: center; gap: 6px; background: #1e1e1e; border-radius: 8px; padding: 6px 12px; font-size: 13px; color: #eee; text-decoration: none; }}
  .flag {{ font-size: 14px; }}
</style>
</head>
<body>
<h1>📅 Shorts Feed - Indice giorni</h1>
{blocchi}
</body>
</html>"""

Path("index.html").write_text(index_html, encoding="utf-8")
print(f"Indice aggiornato con {len(date_ordinate)} date e {sum(len(v) for v in trovati.values())} combinazioni data+lingua")
