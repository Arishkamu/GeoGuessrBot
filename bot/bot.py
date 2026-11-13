"""Telegram-бот для мини-аппа «GeoGuessr».

Бот делает три вещи:
  1. открывает мини-апп кнопкой «Играть» (/start, /play);
  2. показывает рейтинг (/top), запрашивая его у сервера;
  3. при запуске сам настраивает профиль бота: команды, тексты, кнопку меню.

Запуск:
    pip install aiogram python-dotenv
    export BOT_TOKEN=...                       # токен от @BotFather
    export WEBAPP_URL=https://ваш-домен/       # HTTPS-адрес мини-аппа
    # необязательно:
    export API_URL=https://ваш-домен           # где лежит /api/top (по умолчанию = WEBAPP_URL)
    export APP_LINK=https://t.me/ваш_бот/app   # прямая ссылка на мини-апп, нужна для групп
    python bot.py
"""
import asyncio
import logging
import os
from pathlib import Path

import aiohttp
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)

logging.basicConfig(level=logging.INFO)

# токены берём из .env в корне репозитория; он главнее переменных, заданных в терминале
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip().strip("'\"")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "")
API_URL = (os.environ.get("API_URL") or WEBAPP_URL).rstrip("/")
APP_LINK = os.environ.get("APP_LINK", "")

ABOUT = "Угадай, где сделано фото: отметь точку на карте и набери очки. Играй без ограничений, есть рейтинг."
DESCRIPTION = (
    "GeoGuessr — игра-угадайка для Telegram. Я показываю фото улицы или достопримечательности, "
    "а ты отмечаешь на карте, где оно сделано. Чем ближе твоя точка, тем больше очков: "
    "до 5 000 за раунд.\n\n"
    "• сколько угодно раундов с фото со всего мира\n"
    "• карта прямо в Telegram\n"
    "• разборы после каждого раунда\n"
    "Нажми «Играть» и проверь, насколько хорошо ты знаешь мир."
)
COMMANDS = [
    BotCommand(command="play", description="Начать игру"),
    BotCommand(command="help", description="Как играть"),
]
HELP_TEXT = (
    "Как играть:\n"
    "1. Нажми «Играть» и посмотри на фото.\n"
    "2. Отметь на карте, где оно сделано.\n"
    "3. Получи очки: чем ближе, тем больше. Максимум 5 000 за раунд.\n"
    "4. Нажми «Прислать разбор в чат» и посмотри разбор по раунду.\n\n"
    "5. Играй, сколько хочешь, а когда надоест, нажми «Завершить игру» и посмотри итог.\n\n"
)

dp = Dispatcher()


# ---------- чистые функции (их удобно проверять без Telegram) ----------
def build_play_markup(chat_type: str) -> InlineKeyboardMarkup | None:
    if chat_type == "private":
        button = InlineKeyboardButton(text="Играть", web_app=WebAppInfo(url=WEBAPP_URL))
    elif APP_LINK:
        button = InlineKeyboardButton(text="Играть", url=APP_LINK)
    else:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


# ---------- команды ----------
async def send_play(message: Message):
    markup = build_play_markup(message.chat.type)
    if markup is None:
        await message.answer(
            "В группе игру можно открыть по ссылке на мини-апп. "
            "Её ещё не настроили, поэтому напиши мне в личные сообщения: /play"
        )
        return
    await message.answer("Фото, точка на карте, очки. Начнём?", reply_markup=markup)


@dp.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject):
    await message.answer(
        "Привет! Я показываю фото, а ты угадываешь, где оно сделано: отмечаешь точку на карте "
        "и получаешь очки. Чем ближе, тем больше."
    )
    await send_play(message)


@dp.message(Command("play"))
async def cmd_play(message: Message):
    await send_play(message)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT)


@dp.message(F.text & ~F.text.startswith("/"))
async def any_text(message: Message):
    if message.chat.type == "private":
        await message.answer("Я умею только играть в GeoGuessr. Нажми /play, чтобы начать.")


# ---------- настройка профиля бота при запуске ----------
async def setup_profile(bot: Bot):
    """То, что мы раньше делали руками в @BotFather. Если что-то не прошло, бот всё равно работает."""
    steps = [
        ("команды", bot.set_my_commands(COMMANDS)),
        ("описание", bot.set_my_description(DESCRIPTION)),
        ("о боте", bot.set_my_short_description(ABOUT)),
        ("кнопка меню", bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Играть", web_app=WebAppInfo(url=WEBAPP_URL)))),
    ]
    for name, coro in steps:
        try:
            await coro
        except Exception:
            logging.exception("не удалось настроить: %s", name)


async def main():
    if not BOT_TOKEN or not WEBAPP_URL:
        raise SystemExit("Задай переменные окружения BOT_TOKEN и WEBAPP_URL (HTTPS-адрес мини-аппа).")
    if not WEBAPP_URL.startswith("https://"):
        raise SystemExit("WEBAPP_URL должен начинаться с https:// — Telegram не открывает http-страницы.")
    bot = Bot(BOT_TOKEN)
    await setup_profile(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())