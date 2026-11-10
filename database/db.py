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


@dataclass
class User:
    user_id: int
    tg_id: int
    username: str
    total_score: int


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


@contextmanager
def get_db():
    """Открывает соединение, коммитит при успехе, откатывает при ошибке, закрывает."""
    conn = psycopg.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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
                    round_id     SERIAL PRIMARY KEY,
                    game_id      INTEGER NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
                    round_number INTEGER NOT NULL,
                    points       INTEGER NOT NULL DEFAULT 0
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

def get_or_create_user(tg_id: int, username: str | None = None) -> User | None:
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
            return dict_to_dataclass(row, User)


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


def result_game() -> dict:
    """
    TODO
    По завершении игры, заполняется полная информация о игровой сессии.
    """
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                # TODO
            )
            return cur.fetchone()


def save_round(
        game_id: int,
        round_number: int,
        points: int,
) -> game.Round:
    """Сохраняет завершенный раунд."""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO rounds
                    (game_id, round_number, points)
                VALUES (%s, %s, %s)
                RETURNING *
                """,
                (game_id, round_number, points),
            )
            row = cur.fetchone()

            cur.execute(
                """
                UPDATE games
                SET rounds_total = rounds_total + 1,
                    total_score = total_score + %s
                WHERE game_id = %s
                """,
                (points, game_id),
            )

            return dict_to_dataclass(row, game.Round)


def get_rounds_by_game(game_id: int) -> list[game.Round]:
    """Возвращает все раунды игры, отсортированные по номеру."""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM rounds WHERE game_id = %s ORDER BY round_number",
                (game_id,),
            )
            rows = cur.fetchall()
            return [dict_to_dataclass(row, game.Round) for row in rows]


def get_game_by_id(game_id: int) -> game.Game | None:
    """Возвращает игру по game_id или None, если такой игры нет."""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM games WHERE game_id = %s", (game_id,))
            return dict_to_dataclass(cur.fetchone(), game.Game)
