from pydantic import BaseModel
from enum import Enum

class RoundResponse(BaseModel):
    round_id: int
    image_url: str


class GuessRequest(BaseModel):
    round_id: int
    latitude: float
    longitude: float

class CoordinatesResponse(BaseModel):
    latitude: float
    longitude: float

class GuessResponse(BaseModel):
    true_coordinates: CoordinatesResponse
    distance_km: float
    score: int
    is_game_finished: bool

class PicType(Enum):
    PHOTO = "photo"
    PANO = "pano"
    BOTH = "both"