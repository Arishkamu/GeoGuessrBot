import os
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import fields

from dotenv import load_dotenv

from backend.app.models import game

load_dotenv()

DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT")
DB_NAME = os.getenv("POSTGRES_DB")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

if not all([DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME]):
    raise RuntimeError("Не все переменные окружения POSTGRES_* заданы в .env")

_pool: ConnectionPool | None = None


def connect_db() -> None:
    global _pool
    if _pool is None or _pool.closed:
        pool = ConnectionPool(
            conninfo=DATABASE_URL,
            min_size=2,
            max_size=5,
            open=False,
        )
        try:
            pool.open(wait=True)
        except Exception:
            pool.close()
            raise
        _pool = pool


def close_db() -> None:
    global _pool

    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def get_db() -> Iterator[psycopg.Connection]:
    pool = _pool
    if pool is None:
        raise RuntimeError("Пул соединений закрыт")
    with pool.connection() as conn:
        yield conn


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

def row_to_location(row: dict) -> game.Location | None:
    """Собирает объект Location из плоского словаря БД."""
    if row is None:
        return None

    center_coords = game.Coordinates(
        latitude=row['center_lat'],
        longitude=row['center_lon']
    )

    return game.Location(
        location_id=row['location_id'],
        name=row['name'],
        center=center_coords,
        radius=row['radius']
    )


def init_db() -> None:
    """Инициализирует таблицы и индексы, если их нет. Вызывается один раз при старте."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS locations (
                    location_id  SERIAL PRIMARY KEY,
                    name         TEXT UNIQUE NOT NULL,
                    center_lat   FLOAT NOT NULL,
                    center_lon   FLOAT NOT NULL,
                    radius       FLOAT NOT NULL
                );
                
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
                    total_score  INTEGER NOT NULL DEFAULT 0,
                    location_id  INTEGER REFERENCES locations(location_id) ON DELETE SET NULL
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
                DROP TABLE rounds CASCADE;
                DROP TABLE games CASCADE;
                DROP TABLE users CASCADE;
                DROP TABLE locations CASCADE;
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


def create_game(user_id: int, location_id: int | None = None) -> game.Game | None:
    """Создаёт новую игровую сессию.
    finished_at = NULL означает, что игра ещё активна.
    """
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO games (user_id, location_id) VALUES (%s, %s)
                RETURNING *
                """,
                (user_id, location_id),
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









def add_location(name: str, center: game.Coordinates, radius: float) -> game.Location | None:
    """Добавляет новый город в базу с его центром и радиусом"""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO locations (name, center_lat, center_lon, radius) 
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE 
                    SET center_lat = EXCLUDED.center_lat,
                        center_lon = EXCLUDED.center_lon,
                        radius = EXCLUDED.radius
                RETURNING *
                """,
                (name, center.latitude, center.longitude, radius),
            )
            return row_to_location(cur.fetchone())


def get_all_locations() -> list[game.Location]:
    """Возвращает список всех городов"""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM locations ORDER BY name")
            rows = cur.fetchall()
            return [row_to_location(row) for row in rows]


def get_game_location_info(game_id: int) -> game.Location | None:
    """Возвращает город и его радиус для конкретной игры.
    Если игра в стандартном режиме, вернет None"""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT l.* FROM locations l
                JOIN games g ON g.location_id = l.location_id
                WHERE g.game_id = %s
                """,
                (game_id,),
            )
            return row_to_location(cur.fetchone())
