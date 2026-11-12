from app.models import game as models
from .scoring import evaluate_guess
import app.database.db as db
from app.services.panorama_service import generate_panorama


ROUNDS_PER_GAME = 5


def get_or_create_user(tg_id: int, username: str | None = None) -> models.User | None:
    return db.get_or_create_user(tg_id=tg_id, username=username)


def create_game(user_id: int, location_id: int | None = None) -> models.Game | None:
    if location_id is not None:
        location = db.get_location_by_id(location_id)
        if location is None:
            raise ValueError("location not found")

    return db.create_game(user_id=user_id, location_id=location_id)


def _get_user_game(user_id: int, game_id: int) -> models.Game:
    game = db.get_game_by_id(game_id)

    if game is None:
        raise ValueError("game not found")

    if game.user_id != user_id:
        raise ValueError("game does not belong to the user")

    return game


def _get_last_round(game_id: int) -> models.Round | None:
    rounds = db.get_rounds_by_game(game_id)

    if not rounds:
        return None

    return rounds[-1]


def get_current_round(user_id: int, game_id: int) -> models.Round | None:
    _get_user_game(user_id, game_id)

    return _get_last_round(game_id)


def next_round(user_id: int, game_id: int) -> models.Round:
    game = _get_user_game(user_id, game_id)

    if game.is_finished:
        raise ValueError("game is already finished")

    last_round = _get_last_round(game_id)

    if last_round is None:
        next_number = 1
    elif not last_round.is_completed:
        return last_round
    else:
        next_number = last_round.round_number + 1

    if next_number > ROUNDS_PER_GAME:
        raise ValueError("round limit exceeded")

    location = None
    if game.location_id is not None:
        location = db.get_location_by_id(game.location_id)
        if location is None:
            raise ValueError("location not found")

    # снимок и его настоящие координаты берём из Panoramax
    result = generate_panorama(game.location_id)
    if result is None:
        raise ValueError("no panorama found")
    panorama_id, correct_coordinates = result

    return db.create_round(
        game_id=game_id,
        round_number=next_number,
        panorama_id=panorama_id,
        correct_coordinates=correct_coordinates,
    )


def submit_guess( user_id: int, game_id: int, round_id: int, coordinates: models.Coordinates) -> tuple[models.Round, models.Game]:
    game = _get_user_game(user_id, game_id)

    if game.is_finished:
        raise ValueError("game is already finished")

    current_round = _get_last_round(game_id)

    if current_round is None:
        raise ValueError("no active round")

    if current_round.round_id != round_id:
        raise ValueError("round is not the current round")

    if current_round.is_completed:
        raise ValueError("round is already completed")

    guess = evaluate_guess(
        correct=current_round.correct_coordinates,
        guessed=coordinates,
    )

    return db.complete_round(
        round_id=round_id,
        guess=guess,
    )


def get_game_result(user_id: int, game_id: int) -> tuple[models.Game, list[models.Round]]:
    game = _get_user_game(user_id, game_id)

    if not game.is_finished:
        raise ValueError("game is not finished yet")

    rounds = db.get_rounds_by_game(game_id)

    return game, rounds

def get_locations() -> list[models.Location]:
    return db.get_all_locations()

def get_game_location(user_id: int, game_id: int) -> models.Location | None:
    game = _get_user_game(user_id, game_id)

    if game.location_id is None:
        return None

    return db.get_location_by_id(location_id=game.location_id)

def get_location_by_id(loc_id: int | None) -> models.Location | None:
    if loc_id is None:
        return None
    return db.get_location_by_id(location_id=loc_id)

def get_user_total_score(user_id: int) -> int:
    return db.get_user_total_score(user_id)


def get_game_total_score(user_id: int, game_id: int) -> int:
    return _get_user_game(user_id, game_id).total_score
