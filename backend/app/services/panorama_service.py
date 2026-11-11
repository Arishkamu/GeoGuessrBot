
PANORAMAX_API = "https://api.panoramax.xyz/api/search"


def _generate_random_bbox(radius_m: int) -> list[float]:
    latitude = random.uniform(-80, 80)
    longitude = random.uniform(-180, 180)

    lat_delta = radius_m / 111_320
    lon_delta = radius_m / (111_320 * math.cos(math.radians(latitude)))

    return [-4.36170, 48.10831, -4.36210, 48.10897]

# [
#         longitude - lon_delta,
#         latitude - lat_delta,
#         longitude + lon_delta,
#         latitude + lat_delta,
#     ]

def generate_panorama(location_id: int = None, radius_m: int = 500, max_attempts: int = 10) -> tuple[str, game.Coordinates]:
    if location_id is None:
        bbox = _generate_random_bbox(radius_m)
    else:
        location = get_location_by_id(location_id)
        bbox = [location.west_lon, location.east_lon, location.south_lat, location.north_lat]
    return _get_panorama_id(bbox)

def _get_panorama_id(bbox: list[float], limit: int = 50) -> tuple[str, game.Coordinates]:
    response = httpx.get(
        PANORAMAX_API,
        params={
            "bbox": ",".join(map(str, bbox)),
            "limit": limit,
        },
        timeout=20,
    )

    response.raise_for_status()
    data = response.json()
    print(response.request)

    for feature in data.get("features", []):
        coordinates = feature.get("geometry", {}).get("coordinates")
        if not coordinates:
            continue

        assets = feature.get("assets", {})
        for asset in assets.values():
            if "visual" in asset.get("roles", []):
                image_url = asset.get("href")
                break
        if not image_url:
            continue

        return feature.get("id"), game.Coordinates(longitude=coordinates[0], latitude=coordinates[1])

    return None

def get_image_url(panorama_id: str):
    return "https://api.panoramax.xyz/api/pictures/c3353397-ff7b-4e19-b76d-adad778f3113/sd.jpg"
    raise("not implemented yet")

