from fastapi import APIRouter, Depends, HTTPException

from app.models.game import *
from .auth import get_user_by_tg_data
from app.models.router_models import *
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
        "game_id": game.game_id
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
            coordinates=Coordinates(
                latitude=request.latitude,
                longitude=request.longitude,
            ),
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



from app.services.panorama_service import generate_panorama
@router.get("/panoramax/nearby")
def find_panoramax_photos():
    try:
        (panoram_id, _) = generate_panorama()
        return get_image_url(panoram_id)

    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
