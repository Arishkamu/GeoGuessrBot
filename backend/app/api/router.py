from fastapi import APIRouter, Depends, HTTPException

from app.models.game import *
from app.api.auth import get_user_by_tg_data
from app.api.router_models import *
from app.services.game_service import *
from app.services.panorama_service import get_image_url

router = APIRouter(prefix="/api", tags=["Game"])

@router.get("/status")
def get_status():
    return {"status": "ok"}


# POST /api/game/start
@router.post("/game/start")
def start_game(current_user: User = Depends(get_user_by_tg_data)):
    game = create_game(current_user.user_id)
    return {
        "game_id": game.id
    }


# GET /api/round/{game_id}
@router.get("/round/{game_id}", response_model=RoundResponse)
def get_round(
    game_id: int,
    current_user: User = Depends(get_user_by_tg_data),
):
    user_id = current_user.user_id
    round_obj = next_round(user_id, game_id)

    return RoundResponse(
        round_id=round_obj.round_id,
        round_no=round_obj.round_number,
        image_url=get_image_url(round_obj.panorama_id),
    )


# POST /api/guess
@router.post("/guess/{game_id}")
def make_guess(
    request: GuessRequest,
    current_user: User = Depends(get_user_by_tg_data),
):
    round_obj, game = submit_guess(
        user_id=current_user.user_id,
        game_id=request.game_id,
        round_id=request.round_id,
        coordinates=Coordinates(
            latitude=request.latitude,
            longitude=request.longitude,
        ),
    )

    return GuessResponse(
        true_coordinates=CoordinatesResponse(
            latitude=round_obj.true_coordinates.latitude,
            longitude=round_obj.true_coordinates.longitude,
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