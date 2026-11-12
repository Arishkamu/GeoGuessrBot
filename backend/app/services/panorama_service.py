import json
import logging
import math
import random
from pathlib import Path

import httpx

import app.database.db as db
from app.models import game

log = logging.getLogger(__name__)

PANORAMAX_API = "https://api.panoramax.xyz/api/search"
PANORAMAX_PICTURE = "https://api.panoramax.xyz/api/pictures/{id}/sd.jpg"

# Panoramax покрывает мир неравномерно: случайная точка в океане или пустыне ничего не вернёт.
# Поэтому раунды берём вокруг городов, где снимков много. Города сгруппированы по странам:
# выбранная на старте страна ограничивает раунды её городами. Список можно расширять.
# bbox страны (west, south, east, north) нужен только чтобы отфильтровать запасные снимки.
COUNTRIES = {
    "FR": {"bbox": [-5.2, 41.3, 9.6, 51.1], "places": [(48.8566, 2.3522), (45.7640, 4.8357), (48.1083, -4.3617), (43.2965, 5.3698), (43.6047, 1.4442), (44.8378, -0.5792), (47.2184, -1.5536), (50.6292, 3.0573)]},
    "DE": {"bbox": [5.9, 47.3, 15.0, 55.1], "places": [(52.5200, 13.4050), (48.1351, 11.5820), (53.5511, 9.9937), (50.9375, 6.9603)]},
    "IT": {"bbox": [6.6, 36.6, 18.5, 47.1], "places": [(41.9028, 12.4964), (45.4642, 9.1900), (40.8518, 14.2681), (43.7696, 11.2558)]},
    "ES": {"bbox": [-9.4, 35.9, 3.4, 43.8], "places": [(40.4168, -3.7038), (41.3874, 2.1686), (37.3891, -5.9845), (39.4699, -0.3763)]},
    "GB": {"bbox": [-8.2, 49.9, 1.8, 58.7], "places": [(51.5074, -0.1278), (53.4808, -2.2426), (55.9533, -3.1883)]},
    "BE": {"bbox": [2.5, 49.5, 6.4, 51.5], "places": [(50.8503, 4.3517), (51.2194, 4.4025)]},
    "NL": {"bbox": [3.3, 50.7, 7.2, 53.6], "places": [(52.3676, 4.9041), (51.9244, 4.4777), (52.0907, 5.1214)]},
    "NO": {"bbox": [4.5, 57.9, 31.1, 71.2], "places": [(59.9139, 10.7522), (60.3913, 5.3221)]},
    "FI": {"bbox": [20.5, 59.8, 31.6, 70.1], "places": [(60.1699, 24.9384), (61.4978, 23.7610)]},
}
ALL_PLACES = [p for c in COUNTRIES.values() for p in c["places"]]


def list_countries() -> list[dict]:
    return [{"code": code, "count": len(c["places"])} for code, c in COUNTRIES.items()]


def ensure_country_location(code: str) -> int:
    """Страна выбирается на старте: храним её как строку в таблице locations (имя = код страны)."""
    country = COUNTRIES.get(code)
    if country is None:
        raise ValueError("для этой страны пока нет снимков")
    west, south, east, north = country["bbox"]
    return db.get_or_create_location(code, west, south, east, north).location_id


# Запасной список снимков (только id и координаты, сами картинки грузятся с Panoramax).
# Создаётся скриптом build_seed.py, нужен на случай, когда поиск Panoramax не отвечает.
SEED_FILE = Path(__file__).with_name("panoramas_seed.json")
_pool: list[tuple[str, float, float]] = []   # (id, lat, lon): всё, что уже находили за время работы


def _remember(items: list[tuple[str, float, float]]) -> None:
    known = {p[0] for p in _pool}
    for it in items:
        if it[0] not in known:
            _pool.append(it)
    del _pool[:-2000]   # не даём списку расти бесконечно


def _load_seed() -> None:
    try:
        data = json.loads(SEED_FILE.read_text())
        _remember([(d["id"], d["lat"], d["lon"]) for d in data])
        log.info("загружено %d запасных снимков", len(data))
    except FileNotFoundError:
        pass
    except Exception:
        log.warning("не удалось прочитать %s", SEED_FILE, exc_info=True)


_load_seed()


def _from_pool(bbox: list[float] | None = None) -> tuple[str, game.Coordinates] | None:
    items = _pool
    if bbox:
        west, south, east, north = bbox
        items = [p for p in _pool if south <= p[1] <= north and west <= p[2] <= east]
    if not items:
        return None
    pid, lat, lon = random.choice(items)
    log.warning("Panoramax недоступен, беру снимок из запасного списка: %s", pid)
    return pid, game.Coordinates(latitude=lat, longitude=lon)


def _bbox_around(lat0: float, lon0: float, radius_m: int) -> list[float]:
    """Квадрат вокруг города в формате west, south, east, north. Центр сдвигаем до ~5 км,
    чтобы раунды в одном городе не повторялись."""
    latitude = lat0 + random.uniform(-0.05, 0.05)
    longitude = lon0 + random.uniform(-0.05, 0.05)

    lat_delta = radius_m / 111_320
    lon_delta = radius_m / (111_320 * math.cos(math.radians(latitude)))

    return [
        longitude - lon_delta,
        latitude - lat_delta,
        longitude + lon_delta,
        latitude + lat_delta,
    ]


def generate_panorama(
    location_id: int | None = None,
    radius_m: int = 3000,
    max_attempts: int = 3,
) -> tuple[str, game.Coordinates] | None:
    """Возвращает (id снимка, его настоящие координаты) или None, если ничего не нашли."""
    location = None
    if location_id is not None:
        location = db.get_location_by_id(location_id)
        if location is None:
            raise ValueError("location not found")
    country = COUNTRIES.get(location.name) if location else None
    loc_bbox = [location.west_lon, location.south_lat, location.east_lon, location.north_lat] if location else None

    for attempt in range(max_attempts):
        # если в области пусто, каждая следующая попытка ищет в более широкой (3, 6, 9 км)
        if country:
            bbox = _bbox_around(*random.choice(country["places"]), radius_m * (attempt + 1))
        elif location:
            bbox = loc_bbox   # своя локация команды: границы заданы вручную
        else:
            bbox = _bbox_around(*random.choice(ALL_PLACES), radius_m * (attempt + 1))
        try:
            result = _get_panorama(bbox)
        except httpx.HTTPError as e:
            log.warning("Panoramax не ответил (%s): %r, bbox=%s", type(e).__name__, e, bbox)
            continue
        if result is not None:
            return result
        log.warning("в bbox=%s снимков нет", bbox)
        if location and not country:
            break  # границы локации не меняются, повторять запрос бессмысленно
    return _from_pool(loc_bbox)


def _get_panorama(bbox: list[float], limit: int = 20) -> tuple[str, game.Coordinates] | None:
    response = httpx.get(
        PANORAMAX_API,
        params={"bbox": ",".join(map(str, bbox)), "limit": limit},
        timeout=httpx.Timeout(20, connect=5),
    )
    response.raise_for_status()
    features = response.json().get("features", [])

    found = []
    for feature in features:
        coordinates = (feature.get("geometry") or {}).get("coordinates")
        picture_id = feature.get("id")
        if not coordinates or not picture_id:
            continue
        # GeoJSON хранит координаты как [долгота, широта]
        found.append((picture_id, coordinates[1], coordinates[0]))

    if not found:
        return None
    _remember(found)   # пригодится, если Panoramax позже перестанет отвечать
    picture_id, lat, lon = random.choice(found)  # чтобы не выдавать каждый раз один и тот же снимок
    return picture_id, game.Coordinates(latitude=lat, longitude=lon)


def get_image_url(panorama_id: str) -> str:
    return PANORAMAX_PICTURE.format(id=panorama_id)