import math
import random

import httpx

import app.database.db as db
from app.models import game

PANORAMAX_API = "https://api.panoramax.xyz/api/search"
PANORAMAX_PICTURE = "https://api.panoramax.xyz/api/pictures/{id}/sd.jpg"

# Panoramax покрывает мир неравномерно: случайная точка в океане или пустыне ничего не вернёт.
# Поэтому случайные раунды берём вокруг городов, где снимков много. Список можно расширять.
SEED_PLACES = [
    (48.8566, 2.3522),     # Париж
    (52.5200, 13.4050),    # Берлин
    (41.9028, 12.4964),    # Рим
    (40.4168, -3.7038),    # Мадрид
    (51.5074, -0.1278),    # Лондон
    (50.8503, 4.3517),     # Брюссель
    (52.3676, 4.9041),     # Амстердам
    (48.1351, 11.5820),    # Мюнхен
    (48.1083, -4.3617),    # Бретань
    (45.7640, 4.8357),     # Лион
    (59.9139, 10.7522),    # Осло
    (60.1699, 24.9384),    # Хельсинки
]


def _random_bbox(radius_m: int) -> list[float]:
    """Случайный квадрат вокруг случайного города в формате west, south, east, north."""
    lat0, lon0 = random.choice(SEED_PLACES)
    # сдвигаем центр до ~5 км, чтобы раунды в одном городе не повторялись
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


def _location_bbox(location_id: int) -> list[float]:
    location = db.get_location_by_id(location_id)
    if location is None:
        raise ValueError("location not found")
    # порядок для Panoramax: west, south, east, north
    return [location.west_lon, location.south_lat, location.east_lon, location.north_lat]


def generate_panorama(
    location_id: int | None = None,
    radius_m: int = 3000,
    max_attempts: int = 3,
) -> tuple[str, game.Coordinates] | None:
    """Возвращает (id снимка, его настоящие координаты) или None, если ничего не нашли."""
    for _ in range(max_attempts):
        bbox = _location_bbox(location_id) if location_id is not None else _random_bbox(radius_m)
        try:
            result = _get_panorama(bbox)
        except httpx.HTTPError:
            continue
        if result is not None:
            return result
        if location_id is not None:
            break  # границы локации не меняются, повторять запрос бессмысленно
    return None


def _get_panorama(bbox: list[float], limit: int = 50) -> tuple[str, game.Coordinates] | None:
    response = httpx.get(
        PANORAMAX_API,
        params={"bbox": ",".join(map(str, bbox)), "limit": limit},
        timeout=5,
    )
    response.raise_for_status()
    features = response.json().get("features", [])
    random.shuffle(features)  # чтобы не выдавать каждый раз один и тот же снимок

    for feature in features:
        coordinates = (feature.get("geometry") or {}).get("coordinates")
        picture_id = feature.get("id")
        if not coordinates or not picture_id:
            continue
        # GeoJSON хранит координаты как [долгота, широта]
        return picture_id, game.Coordinates(longitude=coordinates[0], latitude=coordinates[1])

    return None


def get_image_url(panorama_id: str) -> str:
    return PANORAMAX_PICTURE.format(id=panorama_id)