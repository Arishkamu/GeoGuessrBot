from pydantic import BaseModel, Field
from enum import Enum



class StartRequest(BaseModel):
    country: str | None = None


class RoundResponse(BaseModel):
    round_id: int
    round_no: int
    rounds_total: int
    game_total: int
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
    game_total: int
    user_total: int
    is_game_finished: bool

class PicType(Enum):
    PHOTO = "photo"
    PANO = "pano"
    BOTH = "both"

class ReviewRequest(BaseModel):
    round_id: int

class UserScoreResponse(BaseModel):
    total_score: int

class GameStateResponse(BaseModel):
    game_id: int
    is_finished: bool
    game_total: int
    rounds_completed: int
    rounds_total: int
    current_round: RoundResponse | None = None
    history: list[GuessResponse]

