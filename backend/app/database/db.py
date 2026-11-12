import os
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import fields

from dotenv import load_dotenv

from app.models import game

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

    return game.Location(
        location_id=row['location_id'],
        name=row['name'],
        west_lon=row['west_lon'],
        south_lat=row['south_lat'],
        east_lon=row['east_lon'],
        north_lat=row['north_lat']
    )


def init_db() -> None:
    """Инициализирует таблицы и индексы, если их нет. Вызывается один раз при старте."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS locations (
                    location_id  SERIAL PRIMARY KEY,
                    name         TEXT UNIQUE NOT NULL,
                    west_lon     FLOAT NOT NULL,
                    south_lat    FLOAT NOT NULL,
                    east_lon     FLOAT NOT NULL,
                    north_lat    FLOAT NOT NULL
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
                SELECT * FROM games
                WHERE user_id = %s AND finished_at IS NULL
                LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()

            if row is None:
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
                WHERE round_id = %s AND guess_lat IS NULL
                RETURNING *
                """,
                (guess.coordinates.latitude, guess.coordinates.longitude, guess.distance_km, guess.score, round_id),
            )
            round_row = cur.fetchone()
            if round_row is None:
                raise ValueError("round is already completed or does not exist")
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

            cur.execute(
                """
                UPDATE users
                SET total_score = total_score + %s
                WHERE user_id = %s
                """,
                (points, game_row["user_id"]),
            )

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


def get_all_locations() -> list[game.Location]:
    """Возвращает список всех локаций"""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM locations ORDER BY name")
            rows = cur.fetchall()
            return [row_to_location(row) for row in rows]


def get_game_location_info(game_id: int) -> game.Location | None:
    """Возвращает локацию и его радиус для конкретной игры.
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

def get_location_by_id(location_id: int) -> game.Location | None:
    """Возвращает локацию по её ID или None, если её не существует."""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM locations WHERE location_id = %s", (location_id,))
            return row_to_location(cur.fetchone())


def get_user_total_score(user_id: int) -> int:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT total_score FROM users WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()

            if row is None:
                raise ValueError("user not found")

            return row[0]

def get_active_game(user_id: int) -> game.Game | None:
    """Возвращает активную игру пользователя или None."""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT * FROM games
                WHERE user_id = %s AND finished_at IS NULL
                LIMIT 1
                """,
                (user_id,),
            )
            return dict_to_dataclass(cur.fetchone(), game.Game)

def finish_game(game_id: int) -> game.Game | None:
    """Завершает игру пользователя, сохраняя набранные очки."""
    with get_db() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE games
                SET finished_at = NOW()
                WHERE game_id = %s
                RETURNING *
                """,
                (game_id,),
            )
            row = cur.fetchone()

            return dict_to_dataclass(row, game.Game)



def seed_locations() -> None:
    """Заполняет таблицу locations списком городов и регионов"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO locations (name, west_lon, south_lat, east_lon, north_lat)
                VALUES
                ('Paris, France', 2.079135, 48.676938, 2.625265, 49.036262),
                ('Lyon, France', 4.629670, 45.620270, 5.041730, 45.907730),
                ('Nantes, France', -1.751989, 47.083653, -1.355211, 47.353147),
                ('Strasbourg, France', 7.562027, 48.447636, 7.942173, 48.699164),
                ('Bordeaux, France', -0.781892, 44.694070, -0.376508, 44.981530),
                ('Le Havre, France', -0.058064, 49.386603, 0.273864, 49.602197),
                ('Toulon, France', 5.780307, 43.016403, 6.075693, 43.231997),
                ('Grenoble, France', 5.558801, 45.071720, 5.890199, 45.305280),
                ('Dijon, France', 4.882478, 47.214203, 5.200522, 47.429797),
                ('Tours, France', 0.525561, 47.286303, 0.844039, 47.501897),
                ('Limoges, France', 1.119277, 45.734786, 1.402923, 45.932414),
                ('Besancon, France', 5.878562, 47.138986, 6.169638, 47.336614),
                ('Caen, France', -0.535617, 49.075103, -0.205783, 49.290697),
                ('Brest, France', -4.648433, 48.282603, -4.323767, 48.498197),
                ('Poitiers, France', 0.209706, 46.490369, 0.471094, 46.670031),
                ('Bayonne, France', -1.598626, 43.403069, -1.350974, 43.582731),
                ('Biarritz, France', -1.657645, 43.411335, -1.459555, 43.555065),
                ('Mulhouse, France', 7.202294, 47.660969, 7.469506, 47.840631),
                ('Saint-Malo, France', -2.134476, 48.577435, -1.916924, 48.721165),
                ('Chartres, France', 1.367115, 48.366052, 1.610885, 48.527748),
                ('Fontainebleau, France', 2.566285, 48.314869, 2.836915, 48.494531),
                ('Nancy, France', 6.034705, 48.593286, 6.334095, 48.790914),
                ('Epinal, France', 6.314693, 48.084569, 6.584107, 48.264231),
                ('Belfort, France', 6.742814, 47.557152, 6.982786, 47.718848),
                ('Chamonix, France', 6.753175, 45.842852, 6.985625, 46.004548),
                ('Arles, France', 4.503595, 43.586769, 4.752005, 43.766431),
                ('Montauban, France', 1.230083, 43.927769, 1.479917, 44.107431),
                ('La Roche-sur-Yon, France', -1.557812, 46.580669, -1.295988, 46.760331),
                ('Laval, France', -0.904433, 47.980169, -0.635567, 48.159831),
                ('Saint-Nazaire, France', -2.359336, 47.174686, -2.068064, 47.372314),
                ('Morlaix, France', -3.949799, 48.496552, -3.705401, 48.658248),
                ('Beauvais, France', 1.956392, 49.348652, 2.205008, 49.510348),
                ('Compiegne, France', 2.688012, 49.328069, 2.964188, 49.507731),
                ('Laon, France', 3.495349, 49.483252, 3.744651, 49.644948),
                ('Bourges, France', 2.266882, 46.991169, 2.530718, 47.170831),
                ('Chateauroux, France', 1.558745, 46.721569, 1.821255, 46.901231),
                ('Blois, France', 1.216033, 47.505252, 1.455767, 47.666948),
                ('Amboise, France', 0.876502, 47.341135, 1.088898, 47.484865),
                ('Bastia, France', 9.316449, 42.598486, 9.585351, 42.796114),
                ('Calvi, France', 8.647324, 42.486852, 8.866876, 42.648548),
                ('Saint-Denis (Reunion), France', 55.335024, -20.990097, 55.565776, -20.774503),
                ('Saint-Pierre (Reunion), France', 55.362366, -21.449697, 55.593834, -21.234103),
                ('Brussels, Belgium', 4.138273, 50.715553, 4.565127, 50.985047),
                ('Ghent, Belgium', 3.545908, 50.946503, 3.888892, 51.162097),
                ('Leuven, Belgium', 4.572363, 50.798952, 4.828637, 50.960648),
                ('Mechelen, Belgium', 4.349059, 50.945052, 4.606141, 51.106748),
                ('Amsterdam, Netherlands', 4.683418, 52.232853, 5.124782, 52.502347),
                ('Leiden, Netherlands', 4.365209, 52.079252, 4.628791, 52.240948),
                ('Mannheim, Germany', 8.313888, 49.388686, 8.618112, 49.586314),
                ('Ulm, Germany', 9.852294, 48.311269, 10.122906, 48.490931),
                ('Girona, Spain', 2.700559, 41.889569, 2.942241, 42.069231),
                ('Modena, Italy', 10.798935, 44.557269, 11.051465, 44.736931),
                ('Olomouc, Czechia', 17.112315, 49.503969, 17.389485, 49.683631),
                ('Krakow, Poland', 19.735089, 49.929953, 20.154911, 50.199447),
                ('Szczecin, Poland', 14.356802, 53.311720, 14.748798, 53.545280),
                ('Uppsala, Sweden', 17.460002, 59.768769, 17.817798, 59.948431),
                ('Trondheim, Norway', 10.154095, 63.322703, 10.636105, 63.538297),
                ('Cork, Ireland', -8.650296, 51.790703, -8.300904, 52.006297),
                ('Seattle, United States', -122.585250, 47.435521, -122.078950, 47.776879),
                ('Portland Oregon, United States', -122.896337, 45.362487, -122.460463, 45.667913),
                ('Toronto, Canada', -79.631513, 43.473538, -79.134887, 43.832862),
                ('Rosario, Argentina', -60.811066, -33.078947, -60.489934, -32.809453),
                ('Taipei, Taiwan', 121.377026, 24.862321, 121.753774, 25.203679),
                ('Europe', -25, 34, 45, 71),
                ('Asia', 25, -10, 180, 78),
                ('Africa', -18, -35, 52, 38),
                ('North America', -170, 7, -52, 84),
                ('South America', -82, -56, -34, 13),
                ('Oceania', 110, -50, 180, 0),
                ('Western Europe', -10.0, 36.0, 16.0, 55.0),
                ('Eastern Europe', 16.0, 44.0, 30.0, 55.0),
                ('Northern Europe', 5.0, 55.0, 30.0, 70.0),
                ('Southern Europe', 3.0, 36.0, 25.0, 44.0),
                ('Central Europe', 2.0, 48.0, 16.0, 55.0),
                ('British Isles', -10.0, 50.0, 2.0, 59.0),
                ('Iberian Peninsula', -10.0, 36.0, 3.0, 44.0),
                ('France', -5.0, 44.0, 5.0, 50.0),
                ('Alps', 5.0, 44.0, 15.0, 48.0),
                ('USA', -125.0, 30.0, -66.0, 49.0),
                ('Germany', 5.8, 47.2, 15.0, 55.0),
                ('Italy', 6.6, 35.4, 18.5, 46.1),
                ('Spain', -7.3, 36.0, 3.3, 43.8),
                ('United Kingdom', -6.0, 49.9, 1.7, 60.8),
                ('Japan', 130.0, 24.0, 145.0, 42.5),
                ('Brazil', -70.0, -33.7, -34.7, 0.2),
                ('Russia', 29.6, 50.0, 140.0, 81.8),
                ('Turkey', 26.5, 36.8, 44.8, 41.6),
                ('Australia', 113.1, -43.7, 153.6, -10.6),
                ('South Africa', 16.4, -34.8, 32.8, -22.1)
                ON CONFLICT (name) DO UPDATE SET
                  west_lon  = EXCLUDED.west_lon,
                  south_lat = EXCLUDED.south_lat,
                  east_lon  = EXCLUDED.east_lon,
                  north_lat = EXCLUDED.north_lat;
                """)
