import json
import logging
import math
import random
from pathlib import Path

import httpx
from shapely.geometry import shape, Point

import app.database.db as db
from app.models import game
from app.services.game_service import get_locations

log = logging.getLogger(__name__)
from app.models.router_models import PicType

PANORAMAX_API = "https://api.panoramax.xyz/api/search"
PANORAMAX_PICTURE = "https://api.panoramax.xyz/api/pictures/{id}/sd.jpg"

def _in_country(location_name: str | None, point: Point) -> bool:
    if location_name is None or ',' in location_name:
        return True

    with open("countries.geojson", encoding="utf-8") as f:
        countries = json.load(f)

    country = next(
        feature for feature in countries["features"]
        if feature["properties"].get("name") == location_name
    )
    polygon = shape(country["geometry"])
    return polygon.covers(point)


def _generate_random_bbox(bbox_radius_m: int) -> list[float]:
    center = game.Coordinates(latitude=random.uniform(-80, 80), longitude = random.uniform(-180, 180))
    return [
        center.longitude - bbox_radius_m,
        center.latitude - bbox_radius_m,
        center.longitude + bbox_radius_m,
        center.latitude + bbox_radius_m,
    ]


def _location_bbox(location: game.Location) -> list[float]:
    return [location.west_lon, location.south_lat, location.east_lon, location.north_lat]


def generate_picture(location_id: int | None = None, bbox_radius_m: int = 1000, max_attempts: int = 3, pic_type: PicType = PicType.PANO) -> tuple[str, game.Coordinates] | None:
    if location_id is not None:
        location = db.get_location_by_id(location_id)
        if location is None:
                return None
        bbox =  _location_bbox(location)
        return _get_panorama(bbox, location_name=location.name, pic_type=pic_type)

    for _ in range(max_attempts):
        bbox = _generate_random_bbox(bbox_radius_m)
        pano = _get_panorama(bbox, pic_type=pic_type)
        if pano is not None:
            return pano

    location = random.choice(get_locations())
    bbox = _location_bbox(location)
    return(_get_panorama(bbox, pic_type=pic_type))


def _get_panorama(bbox: list[float], limit: int = 50, location_name: str | None = None, pic_type: PicType = PicType.PANO) -> tuple[str, game.Coordinates] | None:
    if (bbox is None):
        return None

    country_name = location_name and ',' in location_name if None else location_name
    params = {
        "bbox": ",".join(map(str, bbox)),
        "limit": limit,
    }
    if pic_type == PicType.PANO:
        params["pic_type"] = "equirectangular"
    elif pic_type == PicType.PHOTO:
        params["pic_type"] = "flat"
    # If BOTH, don't add pic_type

    response = httpx.get(
        PANORAMAX_API,
        params=params,
        timeout=15,
    )

    response.raise_for_status()
    features = response.json().get("features", [])
    random.shuffle(features)

    found = []
    for feature in features:
        coordinates = (feature.get("geometry") or {}).get("coordinates")
        picture_id = feature.get("id")
        if not coordinates or not picture_id:
            continue

        if not _in_country(country_name, coordinates):
            continue

        return picture_id, game.Coordinates(longitude=coordinates[0], latitude=coordinates[1])

    if not found:
        return None
    _remember(found)   # пригодится, если Panoramax позже перестанет отвечать
    picture_id, lat, lon = random.choice(found)  # чтобы не выдавать каждый раз один и тот же снимок
    return picture_id, game.Coordinates(latitude=lat, longitude=lon)


def get_image_url(panorama_id: str) -> str:
    return PANORAMAX_PICTURE.format(id=panorama_id)
