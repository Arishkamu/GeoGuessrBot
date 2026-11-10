"""
Тест всех функций из модуля db.py (глобальное соединение + новая логика).

Запуск:
    python test_db.py

ВНИМАНИЕ: тест делает reset_db() — УДАЛЯЕТ ВСЕ ТАБЛИЦЫ в базе!
Запускать только на dev-базе.
"""
from __future__ import annotations

import sys
import traceback

import db
from backend.app.models.game import Game, Round, Coordinates, Guess, User

# ---------- helpers ----------

def section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def fail(msg: str) -> None:
    print(f"  ❌ {msg}")


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)
    ok(msg)


# ---------- tests ----------

def main() -> int:
    # ---------- 0. Подготовка схемы ----------
    section("0. Подготовка схемы (reset_db + init_db)")
    try:
        db.reset_db()
    except Exception:
        pass  # Таблиц ещё нет — это нормально
    db.init_db()
    ok("init_db() выполнен")

    # ---------- 1. get_or_create_user ----------
    section("1. get_or_create_user — новый пользователь")
    u1 = db.get_or_create_user(tg_id=1001, username="alice")
    check(isinstance(u1, User), "вернулся объект User")
    alice_id = u1.user_id

    # ---------- 2. create_game ----------
    section("2. create_game")
    g1 = db.create_game(user_id=alice_id)
    check(isinstance(g1, Game), "вернулся объект Game")
    check(g1.total_score == 0, "total_score = 0")
    check(g1.rounds_total == 0, "rounds_total = 0")
    check(g1.is_finished is False, "игра ещё не завершена")
    game1_id = g1.game_id

    # ---------- 3. create_round ----------
    section("3. create_round — создание незавершённого раунда")
    coords1 = Coordinates(latitude=55.75, longitude=37.61)  # Москва
    r1 = db.create_round(
        game_id=game1_id,
        round_number=1,
        panorama_id="pano_abc_123",
        correct_coordinates=coords1
    )
    check(isinstance(r1, Round), "вернулся объект Round")
    check(r1.game_id == game1_id, "game_id совпадает")
    check(r1.round_number == 1, "round_number = 1")
    check(r1.panorama_id == "pano_abc_123", "panorama_id сохранился")
    check(r1.correct_coordinates.latitude == 55.75, "правильная широта")
    check(r1.correct_coordinates.longitude == 37.61, "правильная долгота")
    check(r1.guess is None, "guess = None (игрок ещё не ответил)")
    check(r1.is_completed is False, "is_completed = False")

    # ---------- 4. complete_round ----------
    section("4. complete_round — завершение раунда и обновление счёта")
    guess1 = Guess(
        coordinates=Coordinates(latitude=55.76, longitude=37.62),
        distance_km=1.5,
        score=95
    )
    comp_r1, comp_g1 = db.complete_round(round_id=r1.round_id, guess=guess1)

    check(isinstance(comp_r1, Round), "вернулся объект Round")
    check(isinstance(comp_g1, Game), "вернулся объект Game")
    check(comp_r1.guess is not None, "guess сохранён")
    check(comp_r1.guess.score == 95, "очки раунда = 95")
    check(comp_r1.is_completed is True, "is_completed = True")

    check(comp_g1.rounds_total == 1, "rounds_total в игре = 1")
    check(comp_g1.total_score == 95, "total_score игры = 95")
    check(comp_g1.finished_at is None, "игра НЕ завершена после 1 раунда")

    # ---------- 5. Автоматическое завершение игры после 5 раундов ----------
    section("5. Игра завершается автоматически после 5 раундов")
    current_game = comp_g1

    # Симулируем оставшиеся 4 раунда (со 2-го по 5-й)
    for i in range(2, 6):
        new_coords = Coordinates(latitude=10.0 * i, longitude=20.0 * i)
        new_r = db.create_round(game1_id, round_number=i, panorama_id=f"pano_{i}", correct_coordinates=new_coords)

        # Игрок отвечает на 10 очков
        new_guess = Guess(coordinates=Coordinates(0.0, 0.0), distance_km=100.0, score=10)
        _, current_game = db.complete_round(round_id=new_r.round_id, guess=new_guess)

    # После 5-го раунда игра должна завершиться
    check(current_game.rounds_total == 5, "сыграно ровно 5 раундов")
    check(current_game.total_score == 135, "общий счёт = 95 + (4 * 10) = 135")
    check(current_game.finished_at is not None, "finished_at заполнилось автоматически")
    check(current_game.is_finished is True, "is_finished = True")

    # ---------- 6. get_rounds_by_game ----------
    section("6. get_rounds_by_game")
    rounds = db.get_rounds_by_game(game1_id)
    check(isinstance(rounds, list), "вернулся list")
    check(len(rounds) == 5, "вернулось 5 раундов")
    check(isinstance(rounds[0], Round), "элементы списка — объекты Round")
    check([r.round_number for r in rounds] == [1, 2, 3, 4, 5], "отсортированы по round_number")
    check(rounds[0].guess.score == 95, "первый раунд содержит правильный guess")
    check(rounds[1].guess.score == 10, "второй раунд содержит правильный guess")

    # ---------- 7. get_game_by_id ----------
    section("7. get_game_by_id")
    fetched_game = db.get_game_by_id(game1_id)
    check(fetched_game is not None, "игра найдена")
    check(fetched_game.is_finished is True, "статус завершения сохранён в БД")
    check(fetched_game.total_score == 135, "счёт сохранён в БД")

    # ---------- 8. UNIQUE(game_id, round_number) ----------
    section("8. UNIQUE — защита от дублирования раундов")
    try:
        db.create_round(
            game_id=game1_id,
            round_number=1,  # Пытаемся создать 1-й раунд во второй раз
            panorama_id="duplicate",
            correct_coordinates=Coordinates(0, 0)
        )
    except Exception as e:
        ok(f"дубликат раунда отклонён: {type(e).__name__}")
    else:
        fail("исключения не было — UNIQUE констрейнт не работает!")
        return 1

    # ---------- 9. FK и CASCADE ----------
    section("9. ON DELETE CASCADE — удаление юзера чистит игры и раунды")
    with db.get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE user_id = %s", (alice_id,))

    check(db.get_game_by_id(game1_id) is None, "игра удалена каскадом")
    check(db.get_rounds_by_game(game1_id) == [], "раунды удалены каскадом")

    print(f"\n{'=' * 60}\nВСЁ ОК\n{'=' * 60}")
    return 0


if __name__ == "__main__":
    # 1. Подключаемся к базе ОДИН раз перед началом тестов
    print("Инициализация подключения к БД...")
    db.connect_db()

    exit_code = 1
    try:
        exit_code = main()
    except AssertionError as e:
        print(f"\n❌ ПРОВАЛ: {e}")
        exit_code = 1
    except Exception:
        print("\n❌ Непредвиденная ошибка:")
        traceback.print_exc()
        exit_code = 1
    finally:
        # 2. Гарантированно закрываем соединение, даже если тест упал
        print("\nЗавершение работы, отключение от БД...")
        db.close_db()

    sys.exit(exit_code)
