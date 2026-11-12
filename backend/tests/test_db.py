"""
Тестирование для базы данных через pytest.
Запуск из /backend: pytest tests/test_db.py -v
"""
import pytest
from psycopg.rows import dict_row
from app.models.game import Game, Round, Coordinates, Guess, User, Location
from app.database import db

@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Подключение к БД."""
    db.connect_db()
    yield
    db.close_db()

@pytest.fixture(autouse=True)
def clean_db():
    """Очищает базу перед каждым тестом."""
    db.reset_db()
    db.init_db()
    yield

@pytest.fixture
def test_user():
    """Создает тестового пользователя для каждого теста"""
    return db.get_or_create_user(tg_id=1001, username="user123")

@pytest.fixture
def test_game(test_user):
    """Создает тестовую игру для пользователя"""
    return db.create_game(user_id=test_user.user_id)

def test_get_or_create_user(test_user):
    """Проверка создания пользователя"""
    assert isinstance(test_user, User)
    assert test_user.tg_id == 1001
    assert test_user.username == "user123"
    assert test_user.total_score == 0


def test_create_game(test_game):
    """Проверка создания игры"""
    assert isinstance(test_game, Game)
    assert test_game.total_score == 0
    assert test_game.rounds_total == 0
    assert test_game.is_finished is False


def test_create_and_complete_round(test_game):
    """Проверка создания раунда и его завершения"""
    coords = Coordinates(latitude=55.75, longitude=37.61)
    r1 = db.create_round(
        game_id=test_game.game_id,
        round_number=1,
        panorama_id="pano_abc_123",
        correct_coordinates=coords
    )
    assert isinstance(r1, Round)
    assert r1.panorama_id == "pano_abc_123"
    assert r1.guess is None
    assert r1.is_completed is False

    guess = Guess(
        coordinates=Coordinates(latitude=55.76, longitude=37.62),
        distance_km=1.5,
        score=95
    )
    comp_r1, comp_g1 = db.complete_round(round_id=r1.round_id, guess=guess)
    
    assert comp_r1.is_completed is True
    assert comp_r1.guess.score == 95
    assert comp_g1.rounds_total == 1
    assert comp_g1.total_score == 95
    assert comp_g1.finished_at is None


def test_game_auto_finish_after_5_rounds(test_game):
    """Проверка, что игра завершается автоматически после 5 раундов"""
    current_game = test_game
    
    for i in range(1, 6):
        new_coords = Coordinates(latitude=10.0 * i, longitude=20.0 * i)
        new_r = db.create_round(test_game.game_id, round_number=i, panorama_id=f"pano_{i}", correct_coordinates=new_coords)
        
        new_guess = Guess(coordinates=Coordinates(0.0, 0.0), distance_km=100.0, score=10)
        _, current_game = db.complete_round(round_id=new_r.round_id, guess=new_guess)

    assert current_game.rounds_total == 5
    assert current_game.total_score == 50
    assert current_game.finished_at is not None
    assert current_game.is_finished is True


def test_unique_round_constraint(test_game):
    """Проверка защиты от дублирования раундов"""
    coords = Coordinates(latitude=0, longitude=0)
    db.create_round(test_game.game_id, round_number=1, panorama_id="pano_1", correct_coordinates=coords)
    
    with pytest.raises(Exception) as exc_info:
        db.create_round(test_game.game_id, round_number=1, panorama_id="duplicate", correct_coordinates=coords)
    
    assert "UniqueViolation" in str(exc_info.type) or "unique constraint" in str(exc_info.value).lower()


def test_get_game_by_id(test_game):
    """Проверяем, что get_game_by_id возвращает правильную игру, а для несуществующей — None."""
    found_game = db.get_game_by_id(test_game.game_id)
    
    assert found_game is not None
    assert isinstance(found_game, Game)
    assert found_game.game_id == test_game.game_id
    assert found_game.total_score == test_game.total_score

    missing_game = db.get_game_by_id(999_999)
    assert missing_game is None


def test_get_rounds_by_game(test_game):
    """Проверяем, что get_rounds_by_game возвращает список раундов в правильном порядке."""
    for i in range(1, 4):
        db.create_round(
            game_id=test_game.game_id,
            round_number=i,
            panorama_id=f"pano_{i}",
            correct_coordinates=Coordinates(latitude=10.0 * i, longitude=20.0 * i)
        )
        
    rounds = db.get_rounds_by_game(test_game.game_id)
    
    assert isinstance(rounds, list)
    assert len(rounds) == 3
    
    assert isinstance(rounds[0], Round)
    
    round_numbers = [r.round_number for r in rounds]
    assert round_numbers == [1, 2, 3]
    
    empty_rounds = db.get_rounds_by_game(999_999)
    assert empty_rounds == []

def test_cascade_delete(test_user, test_game):
    """Проверка, что удаление юзера чистит его игры и раунды"""
    db.create_round(test_game.game_id, 1, "pano_x", Coordinates(0, 0))
    
    with db.get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE user_id = %s", (test_user.user_id,))

    assert db.get_game_by_id(test_game.game_id) is None
    assert db.get_rounds_by_game(test_game.game_id) == []


def test_locations_logic(test_user):
    """Проверка добавления и получения локаций"""
    
    with db.get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                INSERT INTO locations (name, west_lon, south_lat, east_lon, north_lat)
                VALUES 
                    ('Paris', 2.224, 48.815, 2.469, 48.902),
                    ('Moscow', 37.3, 55.5, 37.9, 56.0)
            """)
            
            cur.execute("SELECT * FROM locations WHERE name = 'Paris'")
            paris_row = cur.fetchone()
            paris_id = paris_row['location_id']

    locs = db.get_all_locations()
    assert len(locs) == 2

    found_paris = db.get_location_by_id(paris_id)
    assert found_paris is not None
    assert found_paris.name == "Paris"
    
    missing_loc = db.get_location_by_id(999_999)
    assert missing_loc is None

    g_paris = db.create_game(user_id=test_user.user_id, location_id=paris_id)
    game_loc = db.get_game_location_info(g_paris.game_id)
    
    assert game_loc is not None
    assert game_loc.name == "Paris"
    assert game_loc.north_lat == 48.902


def test_create_game_resumes_active_game(test_user):
    """Проверка того что при повторном вызове create_game возвращается активная игра, а не создается новая."""
    game1 = db.create_game(user_id=test_user.user_id)
    assert isinstance(game1, Game)
    
    game2 = db.create_game(user_id=test_user.user_id)
    
    assert game1.game_id == game2.game_id
    
    db.finish_game(game1.game_id)
    game3 = db.create_game(user_id=test_user.user_id)
    
    assert game3.game_id != game1.game_id


def test_complete_round_updates_user_score(test_user, test_game):
    """Проверка, что complete_round обновляет не только счет игры, но и общий счет пользователя."""
    coords = Coordinates(latitude=55.75, longitude=37.61)
    r1 = db.create_round(test_game.game_id, 1, "pano_1", coords)
    
    guess = Guess(coordinates=Coordinates(55.76, 37.62), distance_km=1.5, score=95)
    db.complete_round(round_id=r1.round_id, guess=guess)
    
    user_score = db.get_user_total_score(test_user.user_id)
    assert user_score == 95


def test_complete_round_prevents_double_scoring(test_user, test_game):
    """Проверка защиты от двойного клика"""
    coords = Coordinates(latitude=55.75, longitude=37.61)
    r1 = db.create_round(test_game.game_id, 1, "pano_1", coords)
    
    guess = Guess(coordinates=Coordinates(55.76, 37.62), distance_km=1.5, score=95)
    
    db.complete_round(round_id=r1.round_id, guess=guess)
    
    with pytest.raises(ValueError) as exc_info:
        db.complete_round(round_id=r1.round_id, guess=guess)
    
    assert "round is already completed" in str(exc_info.value)
    
    game = db.get_game_by_id(test_game.game_id)
    assert game.total_score == 95
    assert game.rounds_total == 1


def test_get_active_game_and_finish_game(test_user, test_game):
    """Проверяем получение активной игры и её ручное завершение."""
    active_game = db.get_active_game(test_user.user_id)
    assert active_game is not None
    assert active_game.game_id == test_game.game_id
    
    finished_game = db.finish_game(test_game.game_id)
    assert finished_game is not None
    assert finished_game.is_finished is True
    
    no_active_game = db.get_active_game(test_user.user_id)
    assert no_active_game is None