import os
import psycopg
from psycopg.rows import dict_row
from contextlib import contextmanager
from dataclasses import dataclass, fields

from dotenv import load_dotenv

from backend.app.models import game

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "Переменная окружения DATABASE_URL не задана. "
        "Создайте файл .env"
    )

_global_conn: psycopg.Connection | None = None


def connect_db() -> None:
    """Открывает соединение с БД. Вызывать при старте бота."""
    global _global_conn
    if _global_conn is None or _global_conn.closed:
        _global_conn = psycopg.connect(DATABASE_URL)
        print("Подключение к базе данных установлено.")


def close_db() -> None:
    """Закрывает соединение. Вызывать при выключении бота."""
    global _global_conn
    if _global_conn is not None and not _global_conn.closed:
        _global_conn.close()
        _global_conn = None
        print("Подключение к базе данных закрыто.")


@contextmanager
def get_db():
    """
    Использует глобальное соединение.
    Делает commit при успехе и rollback при ошибке.
    """
    global _global_conn

    if _global_conn is None or _global_conn.closed:
        connect_db()

    try:
        yield _global_conn
        _global_conn.commit()
    except Exception:
        _global_conn.rollback()
        raise


def dict_to_dataclass(data: dict, cls):
    """Безопасно превращает словарь в датакласс, заполняя отсутствующие поля None."""
    if data is None:
        return None

    class_fields = {f.name for f in fields(cls)}

    filtered_data = {k: v for k, v in data.items() if k in class_fields}

    for field_name in class_fields:
        if field_name not in filtered_data:
            filtered_data[field_name] = None

    return cls(**filtered_data)

def row_to_round(row: dict) -> game.Round | None:
    """Собирает Round из плоского словаря БД."""
    if row is None:
        return None

    correct_coords = game.Coordinates(
        latitude=row['correct_lat'],
        longitude=row['correct_lon']
    )

    guess = None
    if row['guess_lat'] is not None:
        guess_coords = game.Coordinates(
            latitude=row['guess_lat'],
            longitude=row['guess_lon']
        )
        guess = game.Guess(
            coordinates=guess_coords,
            distance_km=row['distance_km'],
            score=row['points']
        )

    return game.Round(
        round_id=row['round_id'],
        game_id=row['game_id'],
        round_number=row['round_number'],
        panorama_id=row['panorama_id'],
        correct_coordinates=correct_coords,
        guess=guess
    )



def init_db() -> None:
    """Инициализирует таблицы и индексы, если их нет. Вызывается один раз при старте."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id      SERIAL PRIMARY KEY,
                    tg_id        BIGINT UNIQUE NOT NULL,
                    username     TEXT,
                    total_score  INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS games (
                    game_id      SERIAL PRIMARY KEY,
                    user_id      INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    rounds_total INTEGER NOT NULL DEFAULT 0,
                    started_at   TIMESTAMP NOT NULL DEFAULT NOW(),
                    finished_at  TIMESTAMP,
                    total_score  INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS rounds (
                    round_id       SERIAL PRIMARY KEY,
                    game_id        INTEGER NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
                    round_number   INTEGER NOT NULL,
                    panorama_id    TEXT NOT NULL,
                    correct_lat    FLOAT NOT NULL,
                    correct_lon    FLOAT NOT NULL,
                    
                    -- Данные для ответа игрока (заполняются позже)
                    guess_lat      FLOAT,
                    guess_lon      FLOAT,
                    distance_km    FLOAT,
                    points         INTEGER NOT NULL DEFAULT 0,
                    
                    UNIQUE(game_id, round_number)
                );

                CREATE INDEX IF NOT EXISTS idx_games_user ON games(user_id);
                CREATE INDEX IF NOT EXISTS idx_rounds_game ON rounds(game_id);
            """)


def reset_db() -> None:
    """Полностью сбрасывает датабазу и удаляет все таблицы."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DROP TABLE users CASCADE;
                DROP TABLE games CASCADE;
                DROP TABLE rounds CASCADE;
            """)


# Основные 5 функций

def get_or_create_user(tg_id: int, username: str | None = None) -> game.User | None:
    """Возвращает пользователя по tg_id, если он уже есть, или создаёт нового, если его нет."""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO users (tg_id, username) VALUES (%s, %s)
                ON CONFLICT (tg_id) DO UPDATE
                    SET username = COALESCE(EXCLUDED.username, users.username)
                RETURNING *
                """,
                (tg_id, username),
            )
            row = cur.fetchone()
            return dict_to_dataclass(row, game.User)


def create_game(user_id: int) -> game.Game | None:
    """Создаёт новую игровую сессию.
    finished_at = NULL означает, что игра ещё активна.
    """
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO games (user_id) VALUES (%s)
                RETURNING *
                """,
                (user_id,),
            )
            row = cur.fetchone()
            return dict_to_dataclass(row, game.Game)

def create_round(
    game_id: int,
    round_number: int,
    panorama_id: str,
    correct_coordinates: game.Coordinates
) -> game.Round:
    """Создаёт незавершённый раунд с guess=None."""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO rounds (game_id, round_number, panorama_id, correct_lat, correct_lon)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
                """,
                (game_id, round_number, panorama_id, correct_coordinates.latitude, correct_coordinates.longitude),
            )
            row = cur.fetchone()
    return row_to_round(row)

def complete_round(
    round_id: int,
    guess: game.Guess
) -> tuple[game.Round, game.Game]:
    """Завершает раунд, обновляет счёт игры и при необходимости завершает игру."""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # 1. Обновляем раунд (записываем ответ игрока)
            cur.execute(
                """
                UPDATE rounds
                SET guess_lat = %s, guess_lon = %s, distance_km = %s, points = %s
                WHERE round_id = %s
                RETURNING *
                """,
                (guess.coordinates.latitude, guess.coordinates.longitude, guess.distance_km, guess.score, round_id),
            )
            round_row = cur.fetchone()
            game_id = round_row['game_id']
            points = guess.score

            # 2. Обновляем счёт игры и кол-во раундов
            cur.execute(
                """
                UPDATE games
                SET total_score = total_score + %s,
                    rounds_total = rounds_total + 1
                WHERE game_id = %s
                RETURNING *
                """,
                (points, game_id),
            )
            game_row = cur.fetchone()

            # 3. Завершаем игру, если сыграно 5 раундов
            if game_row['rounds_total'] >= 5:
                cur.execute(
                    "UPDATE games SET finished_at = NOW() WHERE game_id = %s RETURNING *",
                    (game_id,),
                )
                game_row = cur.fetchone()

    return row_to_round(round_row), dict_to_dataclass(game_row, game.Game)


def get_rounds_by_game(game_id: int) -> list[game.Round]:
    """Возвращает все раунды игры, отсортированные по номеру."""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM rounds WHERE game_id = %s ORDER BY round_number",
                (game_id,),
            )
            rows = cur.fetchall()
            return [row_to_round(row) for row in rows]


def get_game_by_id(game_id: int) -> game.Game | None:
    """Возвращает игру по game_id или None, если такой игры нет."""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM games WHERE game_id = %s", (game_id,))
            return dict_to_dataclass(cur.fetchone(), game.Game)
