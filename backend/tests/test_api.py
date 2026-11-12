"""
Тестирование связи сервера и Базы Данных
Запуск из /backend: pytest tests/test_api.py -v
"""

import pytest
from fastapi.testclient import TestClient
from app.api.main import app
from app.api.auth import get_user_by_tg_data
from app.database import db
from app.models.game import Coordinates

# ==========================================
# 1. ФИКСТУРЫ (Подготовка окружения)
# ==========================================

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(autouse=True)
def override_auth():
    """Подменяет авторизацию Telegram."""
    def mock_get_user():
        return db.get_or_create_user(tg_id=9999, username="integration_tester")
    
    app.dependency_overrides[get_user_by_tg_data] = mock_get_user
    yield
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def clean_db():
    """Очищает базу перед каждым тестом"""
    db.reset_db()
    db.init_db()
    yield


# ==========================================
# 2. ТЕСТЫ
# ==========================================

def test_start_game_and_check_db(client):
    """Проверяет, что POST /api/game/start создает игру в БД"""
    
    response = client.post("/api/game/start")
    assert response.status_code == 200, f"Ошибка API: {response.text}"
    game_id = response.json()["game_id"]

    game = db.get_game_by_id(game_id)
    assert game is not None, "Игра не создалась в БД"
    assert game.total_score == 0, "Счет новой игры должен быть 0"
    assert game.is_finished is False, "Игра не должна быть завершена"

    with db.get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT username FROM users WHERE tg_id = %s", (9999,))
            user_row = cur.fetchone()
            assert user_row[0] == "integration_tester", "Неверный tg_id в БД"


def test_get_round_and_make_guess(client):
    """Проверка полного цикла игры"""
    
    game_id = client.post("/api/game/start").json()["game_id"]

    res_round = client.get(f"/api/round/{game_id}")
    assert res_round.status_code == 200
    round_data = res_round.json()
    round_id = round_data["round_id"]
    assert "image_url" in round_data

    payload = {
        "round_id": round_id,
        "latitude": 55.75,
        "longitude": 37.61
    }
    res_guess = client.post(f"/api/guess/{game_id}", json=payload)
    assert res_guess.status_code == 200, f"Ошибка при guess: {res_guess.text}"
    
    guess_data = res_guess.json()
    assert "score" in guess_data
    assert "distance_km" in guess_data

    # Проверка что очки записались в БД
    game_after = db.get_game_by_id(game_id)
    assert game_after.rounds_total == 1, "В БД не увеличился счетчик раундов!"
    assert game_after.total_score == guess_data["score"], "Очки в БД не совпадают с ответом API"
