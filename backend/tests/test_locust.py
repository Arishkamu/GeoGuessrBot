"""
Нагрузочное тестирование через locust

Добавить в .env BOT_TOKEN=...

Запуск (в разных консолях):

py -3.15 -m uvicorn app.api.main:app --reload --port 8000 --env-file ../.env

py -3.15 -m locust -f test_locust.py --host=http://127.0.0.1:8000 
"""

import time
import json
import hmac
import hashlib
import os
from urllib.parse import urlencode
from locust import HttpUser, task, between
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(env_path)

# Для тестирования, BOT_TOKEN должен быть указан в .env, и сервер должен принимать тот же токен
BOT_TOKEN = os.getenv("BOT_TOKEN")
if BOT_TOKEN:
    print(f"\n[DEBUG] Locust использует BOT_TOKEN: {BOT_TOKEN[:5]}...{BOT_TOKEN[-5:]}\n")
else:
    print("\n[ERROR] BOT_TOKEN не найден! Locust будет использовать 'test_token'.\n")
    BOT_TOKEN = "test_token"


def generate_init_data(user_id: int, username: str) -> str:
    """Генерирует подпись для Locust, чтобы сервер пропускал запросы"""
    data = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": user_id, "username": username})
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    data["hash"] = calculated_hash
    return urlencode(data)


class GameUser(HttpUser):
    # Пауза между действиями игрока от 1 до 3 секунд.
    wait_time = between(1, 3)

    def on_start(self):
        # Создание каждого игрока
        self.user_id = int(time.time() * 1000) % 1000000
        self.headers = {"X-Init-Data": generate_init_data(self.user_id, f"player_{self.user_id}")}
        self.game_id = None

    @task(1)
    def start_game(self):
        """Игрок начинает новую игру"""
        with self.client.post("/api/game/start", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                self.game_id = response.json().get("game_id")
            else:
                response.failure(f"Ошибка старта игры: {response.text}")

    @task(3)
    def get_round(self):
        """Игрок запрашивает раунд (выполняется чаще, чем старт)"""
        if self.game_id:
            self.client.get(f"/api/round/{self.game_id}", headers=self.headers)

    @task(1)
    def get_status(self):
        """Проверка, что сервер жив (пинг)"""
        self.client.get("/api/status")
