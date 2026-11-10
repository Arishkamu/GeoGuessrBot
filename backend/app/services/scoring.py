from ..models.game import Coordinates, Guess
from math import radians, cos, sin, asin, sqrt, exp, isfinite

EARTH_RADIUS_KM = 6371.0
MAX_SCORE = 5000
SCORE_DISTANCE_SCALE_KM = 1775.0


def calculate_distance(first: Coordinates, second: Coordinates) -> float:
    lat1, lon1 = map(radians, (first.latitude, first.longitude))
    lat2, lon2 = map(radians, (second.latitude, second.longitude))

    dlon = lon2 - lon1
    dlat = lat2 - lat1
    # haversine formula
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    a = max(0.0, min(1.0, a))

    c = 2 * asin(sqrt(a))
    return c * EARTH_RADIUS_KM


def calculate_score(distance_km: float) -> int:
    if distance_km < 0 or not isfinite(distance_km):
        raise ValueError

    return round(MAX_SCORE * exp(-distance_km / SCORE_DISTANCE_SCALE_KM))


def evaluate_guess(correct: Coordinates, guessed: Coordinates) -> Guess:
    distance_km = calculate_distance(correct, guessed)
    score = calculate_score(distance_km)
    return Guess(
        coordinates=guessed,
        distance_km=distance_km,
        score=score,
    )
