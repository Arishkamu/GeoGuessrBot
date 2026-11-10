from __future__ import annotations

import os
import psycopg
from psycopg.rows import dict_row
from contextlib import contextmanager

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "Переменная окружения DATABASE_URL не задана. "
        "Создайте файл .env"
    )

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


#Основные 5 функций

def get_or_create_user(tg_id: int, username: str | None = None) -> dict:
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
            return cur.fetchone()

def create_game(user_id: int) -> dict:
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
            return cur.fetchone()

def save_round(
    game_id: int,
    round_number: int,
    points: int,
) -> dict:
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
            return cur.fetchone()


def get_rounds_by_game(game_id: int) -> list[dict]:
    """Возвращает все раунды игры, отсортированные по номеру."""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM rounds WHERE game_id = %s ORDER BY round_number",
                (game_id,),
            )
            return cur.fetchall()


def get_game_by_id(game_id: int) -> dict | None:
    """Возвращает игру по game_id или None, если такой игры нет."""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM games WHERE game_id = %s", (game_id,))
            return cur.fetchone()
