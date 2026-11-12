from fastapi import APIRouter, Depends, HTTPException

from app.models.game import *
from app.api.auth import get_user_by_tg_data
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
        rounds_total=ROUNDS_PER_GAME,
        game_total=get_game_total_score(user_id, game_id),
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
        game_total=game.total_score,
        user_total=get_user_total_score(current_user.user_id),
        is_game_finished=game.is_finished,
    )

# POST /api/game/finish
@router.post("/game/finish")
def finish_game(
    game_id: int,
    current_user: User = Depends(get_user_by_tg_data),
):
    try:
        game = finish_user_game(current_user.user_id, game_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "game_id": game.game_id,
        "is_finished": game.is_finished,
        "game_total": game.total_score,
    }

@router.get("/me", response_model=UserScoreResponse)
def get_me(current_user: User = Depends(get_user_by_tg_data)):
    return UserScoreResponse(
        total_score=current_user.total_score,
    )


@router.get("/game/active", response_model=GameStateResponse | None)
def get_active_game(current_user: User = Depends(get_user_by_tg_data)):
    state = get_active_game_state(current_user.user_id)

    if state is None:
        return None

    game, rounds = state
    user_total = get_user_total_score(current_user.user_id)

    history = []
    running_total = 0

    for round_obj in rounds:
        if not round_obj.is_completed:
            continue

        guess = round_obj.guess
        running_total += guess.score

        history.append(
            GuessResponse(
                true_coordinates=CoordinatesResponse(
                    latitude=round_obj.correct_coordinates.latitude,
                    longitude=round_obj.correct_coordinates.longitude,
                ),
                distance_km=guess.distance_km,
                score=guess.score,
                game_total=game.total_score,
                user_total=user_total,
                is_game_finished=False,
            )
        )

    current_round = None

    if rounds:
        last_round = rounds[-1]
        current_round = RoundResponse(
            round_id=last_round.round_id,
            round_no=last_round.round_number,
            rounds_total=ROUNDS_PER_GAME,
            game_total=game.total_score,
            image_url=get_image_url(last_round.panorama_id),
        )

    return GameStateResponse(
        game_id=game.game_id,
        is_finished=game.is_finished,
        game_total=game.total_score,
        rounds_completed=len(history),
        rounds_total=ROUNDS_PER_GAME,
        current_round=current_round,
        history=history,
    )
