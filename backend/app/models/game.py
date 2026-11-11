from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Coordinates:
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not -90 <= self.latitude <= 90:
            raise ValueError("Latitude must be between -90 and 90")

        if not -180 <= self.longitude <= 180:
            raise ValueError("Longitude must be between -180 and 180")


@dataclass(frozen=True)
class Guess:
    coordinates: Coordinates
    distance_km: float
    score: int


@dataclass
class Round:
    round_id: int
    game_id: int
    round_number: int
    # TODO i don't think that we need this field
    panorama_id: str
    correct_coordinates: Coordinates

    guess: Guess | None = None

    @property
    def is_completed(self) -> bool:
        return self.guess is not None


@dataclass
class Game:
    game_id: int
    user_id: int
    rounds_total: int
    started_at: datetime

    finished_at: datetime | None = None
    total_score: int = 0

    location_id: int | None = None

    @property
    def is_finished(self) -> bool:
        return self.finished_at is not None

 
@dataclass
class User:
    user_id: int
    tg_id: int
    username: str
    total_score: int


@dataclass(frozen=True)
class Location:
    location_id: int
    name: str
    west_lon: float
    east_lon: float
    south_lat: float
    north_lat: float
