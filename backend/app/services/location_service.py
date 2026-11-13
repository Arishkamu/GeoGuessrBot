from .game_service import get_locations

COUNTRIES = {
    "FR": {"bbox": [-5.2, 41.3, 9.6, 51.1], "places": [(48.8566, 2.3522), (45.7640, 4.8357), (48.1083, -4.3617), (43.2965, 5.3698), (43.6047, 1.4442), (44.8378, -0.5792), (47.2184, -1.5536), (50.6292, 3.0573)]},
    # "DE": {"bbox": [5.9, 47.3, 15.0, 55.1], "places": [(52.5200, 13.4050), (48.1351, 11.5820), (53.5511, 9.9937), (50.9375, 6.9603)]},
    # "IT": {"bbox": [6.6, 36.6, 18.5, 47.1], "places": [(41.9028, 12.4964), (45.4642, 9.1900), (40.8518, 14.2681), (43.7696, 11.2558)]},
    # "ES": {"bbox": [-9.4, 35.9, 3.4, 43.8], "places": [(40.4168, -3.7038), (41.3874, 2.1686), (37.3891, -5.9845), (39.4699, -0.3763)]},
    # "GB": {"bbox": [-8.2, 49.9, 1.8, 58.7], "places": [(51.5074, -0.1278), (53.4808, -2.2426), (55.9533, -3.1883)]},
    "BE": {"bbox": [2.5, 49.5, 6.4, 51.5], "places": [(50.8503, 4.3517), (51.2194, 4.4025)]},
    "NL": {"bbox": [3.3, 50.7, 7.2, 53.6], "places": [(52.3676, 4.9041), (51.9244, 4.4777), (52.0907, 5.1214)]},
    # "NO": {"bbox": [4.5, 57.9, 31.1, 71.2], "places": [(59.9139, 10.7522), (60.3913, 5.3221)]},
    # "FI": {"bbox": [20.5, 59.8, 31.6, 70.1], "places": [(60.1699, 24.9384), (61.4978, 23.7610)]},
}
ALL_PLACES = [p for c in COUNTRIES.values() for p in c["places"]]


def list_countries() -> list[dict]:
    return [{"code": code, "count": len(c["places"])} for code, c in COUNTRIES.items()]


COUNTRY_NAME_MAP = {
    "FR": "France",
    "NL": "Netherlands",
    "BE": "Belgium",

    # "DE": "Germany",
    # "IT": "Italy",
    # "ES": "Spain",
    # "GB": "United Kingdom",
    # "NO": "Norway",
    # "FI": "Finland",
}


def get_country_location(country_code: str) -> int:
    country_code = country_code.upper().strip()

    if country_code not in COUNTRIES:
        raise ValueError(f"Unsupported country: {country_code}")

    country_name = COUNTRY_NAME_MAP.get(country_code)

    if not country_name:
        raise ValueError(f"No country name mapping for: {country_code}")

    locations = get_locations()

    for location in locations:
        if location.name.lower() == country_name.lower():
            return location.location_id

    raise ValueError(f"Location '{country_name}' not found in database")