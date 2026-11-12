from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from app.models.game import *
from app.api.auth import get_user_by_tg_data
from app.models.router_models import *
from app.services.game_service import *
from app.services.panorama_service import ensure_country_location, get_image_url, list_countries, generate_picture
from app.services.review import prefetch_image, send_round_review


router = APIRouter(prefix="/api", tags=["Game"])

@router.get("/status")
def get_status():
    return {"status": "ok"}


class StartRequest(BaseModel):
    country: str | None = None


# GET /api/countries
@router.get("/countries")
def get_countries_list():
    return list_countries()


# POST /api/game/start
@router.post("/game/start")
def start_game(
    body: StartRequest | None = None,
    current_user: User = Depends(get_user_by_tg_data),
):
    location_id = None
    if body and body.country:
        try:
            location_id = ensure_country_location(body.country.upper())
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    game = create_game(current_user.user_id, location_id)
    return {
        "game_id": game.game_id
    }


# GET /api/round/{game_id}
@router.get("/round/{game_id}", response_model=RoundResponse)
def get_round(
    game_id: int,
    background: BackgroundTasks,
    current_user: User = Depends(get_user_by_tg_data),
):
    user_id = current_user.user_id
    try:
        round_obj = next_round(user_id, game_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    image_url = get_image_url(round_obj.panorama_id)
    background.add_task(prefetch_image, image_url)

    return RoundResponse(
        round_id=round_obj.round_id,
        round_no=round_obj.round_number,
        image_url=image_url,
    )


# POST /api/guess/{game_id}
@router.post("/guess/{game_id}")
def make_guess(
    game_id: int,
    request: GuessRequest,
    current_user: User = Depends(get_user_by_tg_data),
):
    try:
        round_obj, game = submit_guess(
            user_id=current_user.user_id,
            game_id=game_id,
            round_id=request.round_id,
            coordinates=Coordinates(latitude=request.latitude, longitude=request.longitude),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return GuessResponse(
        true_coordinates=CoordinatesResponse(
            latitude=round_obj.correct_coordinates.latitude,
            longitude=round_obj.correct_coordinates.longitude,
        ),
        distance_km=round_obj.guess.distance_km,
        score=round_obj.guess.score,
        is_game_finished=game.is_finished,
    )


# POST /api/game/finish
@router.post("/game/finish")
def finish_game(
    game_id: int,
    current_user: User = Depends(get_user_by_tg_data),
):
    game, rounds = get_game_result(
        current_user.user_id,
        game_id,
    )

    return {}

class ReviewRequest(BaseModel):
    round_id: int
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

_reviews_sent: set[tuple[int, int]] = set()


# POST /api/review/{game_id}
@router.post("/review/{game_id}")
def request_review(
    game_id: int,
    body: ReviewRequest,
    background: BackgroundTasks,
    current_user: User = Depends(get_user_by_tg_data),
):
    try:
        round_obj = get_completed_round(current_user.user_id, game_id, body.round_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    key = (game_id, body.round_id)
    if key in _reviews_sent:
        return {"status": "already_sent"}
    _reviews_sent.add(key)

    background.add_task(
        send_round_review,
        current_user.tg_id,
        get_image_url(round_obj.panorama_id),
        round_obj.correct_coordinates.latitude, round_obj.correct_coordinates.longitude,
        body.latitude, body.longitude,
        round_obj.guess.distance_km, round_obj.guess.score,
        round_obj.round_number,
    )
    return {"status": "sent"}

@router.get("/panoramax/nearby")
def find_panoramax_photos():
    try:
        (panoram_id, _) = generate_picture()
        return get_image_url(panoram_id)

    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
