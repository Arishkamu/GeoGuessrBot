"""Собирает запасной список снимков Panoramax (id + координаты) в panoramas_seed.json.
Запуск (когда Panoramax отвечает):  python build_seed.py
Положи результат рядом с panorama_service.py: backend/app/services/panoramas_seed.json
"""
import json
import random
import sys
import time

import httpx

PLACES = [
    (48.8566, 2.3522), (52.5200, 13.4050), (41.9028, 12.4964), (40.4168, -3.7038),
    (51.5074, -0.1278), (50.8503, 4.3517), (52.3676, 4.9041), (48.1351, 11.5820),
    (48.1083, -4.3617), (45.7640, 4.8357), (59.9139, 10.7522), (60.1699, 24.9384),
]
PER_PLACE = 8      # запросов на город
OUT = "panoramas_seed.json"

found = {}
for lat0, lon0 in PLACES:
    for _ in range(PER_PLACE):
        lat = lat0 + random.uniform(-0.04, 0.04)
        lon = lon0 + random.uniform(-0.04, 0.04)
        d = 0.01  # ~1 км: маленькая область отвечает быстрее
        bbox = f"{lon - d},{lat - d},{lon + d},{lat + d}"
        try:
            r = httpx.get("https://api.panoramax.xyz/api/search",
                          params={"bbox": bbox, "limit": 5}, timeout=40)
            r.raise_for_status()
        except Exception as e:
            print("пропуск:", type(e).__name__, bbox, file=sys.stderr)
            continue
        for f in r.json().get("features", []):
            c = (f.get("geometry") or {}).get("coordinates")
            if c and f.get("id"):
                found[f["id"]] = {"id": f["id"], "lat": c[1], "lon": c[0]}
        time.sleep(0.3)
    print(f"({lat0}, {lon0}) всего снимков: {len(found)}")

json.dump(list(found.values()), open(OUT, "w"), ensure_ascii=False)
print("готово:", len(found), "->", OUT)
