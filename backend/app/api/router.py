from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from app.models.game import *
from app.api.auth import get_user_by_tg_data, get_location_id
from app.models.router_models import *
from app.services.game_service import *
from app.services.panorama_service import get_image_url
from app.services.location_service import list_countries
from app.services.review import prefetch_image, send_round_review


router = APIRouter(prefix="/api", tags=["Game"])

@router.get("/status")
def get_status():
    return {"status": "ok"}


# GET /api/countries
@router.get("/countries")
def get_countries_list():
    return list_countries()


# POST /api/game/start
@router.post("/game/start")
def start_game(
    location_id: int | None = Depends(get_location_id),
    current_user: User = Depends(get_user_by_tg_data),
):
    try:
        game = create_game(current_user.user_id, location_id)
    except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
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
        rounds_total=ROUNDS_PER_GAME,
        game_total=get_game_total_score(user_id, game_id),
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
        round_obj.guess.coordinates.latitude,
        round_obj.guess.coordinates.longitude,
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
