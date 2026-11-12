"""Разбор раунда: отправляем снимок и результат в Claude, ответ шлём игроку сообщением от бота.

Вызывается в фоне из make_guess, поэтому игра не ждёт ответа модели.
Нужны переменные окружения: BOT_TOKEN, ANTHROPIC_API_KEY (необязательно CLAUDE_MODEL).
"""
import base64
import logging
import os
import threading
import time

import httpx

log = logging.getLogger(__name__)

MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-5-5")
CLOSE_ENOUGH_KM = 100        # ближе этого разбор не нужен: игрок почти угадал
MAX_IMAGE_BYTES = 4_500_000  # лимит Claude на одну картинку 5 МБ

SYSTEM = (
    "Ты тренер по GeoGuessr и разбираешь раунд, обращаясь напрямую к игроку на «ты», "
    "от первого лица, как будто пишешь ему в личные сообщения. Тебе дают снимок, настоящее место "
    "и точку, которую поставил игрок. Ответь по-русски ровно в 2 коротких предложениях, "
    "не больше 250 символов: "
    "1) главный признак на снимке, по которому можно было понять настоящее место "
    "(надписи, застройка, растительность, разметка, знаки); "
    "2) в чём ты ошибся: например «Ты поставил точку в …, а на фото …». "
    "Никогда не пиши об игроке в третьем лице («игрок», «он»): только «ты», «твоя точка». "
    "Называй только те признаки, в которых уверен, и опирайся лишь на то, что реально видно на снимке. "
    "Если по снимку трудно понять, скажи одной фразой «по этому кадру трудно сказать». "
    "Без разметки, списков, заголовков и советов на будущее."
)

_client = None
_image_cache: dict[str, tuple[str, str]] = {}   # снимки, скачанные заранее, пока игрок смотрел на панораму


def _warm_up() -> None:
    """Первый вызов reverse_geocoder грузит базу городов несколько секунд: делаем это при старте."""
    try:
        import reverse_geocoder as rg
        rg.search((0.0, 0.0), mode=1)
    except Exception:
        pass


threading.Thread(target=_warm_up, daemon=True).start()


def _anthropic():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], timeout=60)
    return _client


def _place(lat: float, lon: float) -> str:
    """Город и страна по координатам. Если пакет не установлен, показываем сами координаты."""
    try:
        import reverse_geocoder as rg
        r = rg.search((lat, lon), mode=1)[0]
        return f"{r['name']}, {r['cc']}"
    except Exception:
        return f"{lat:.2f}, {lon:.2f}"


def _download_image(url: str) -> tuple[str, str] | None:
    """Скачиваем снимок сами: серверы Claude не всегда успевают забрать его с Panoramax."""
    try:
        r = httpx.get(url, timeout=25, follow_redirects=True)
        r.raise_for_status()
        data = r.content
        if not data or len(data) > MAX_IMAGE_BYTES:
            return None
        media_type = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        if media_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
            media_type = "image/jpeg"
        return media_type, base64.b64encode(data).decode()
    except Exception:
        log.warning("не удалось скачать снимок %s", url, exc_info=True)
        return None


def prefetch_image(url: str) -> None:
    """Скачивает снимок заранее (вызывается при выдаче раунда), чтобы разбор не ждал Panoramax."""
    if url in _image_cache:
        return
    image = _download_image(url)
    if image:
        _image_cache[url] = image
        while len(_image_cache) > 30:                 # не копим память
            _image_cache.pop(next(iter(_image_cache)))


def _get_image(url: str) -> tuple[str, str] | None:
    return _image_cache.pop(url, None) or _download_image(url)


def _ask_claude(image: tuple[str, str] | None, text: str) -> str:
    content = []
    if image:
        media_type, data = image
        content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}})
    content.append({"type": "text", "text": text})
    msg = _anthropic().messages.create(
        model=MODEL,
        max_tokens=2000,     # запас: блок рассуждений модели тоже тратит этот лимит
        system=SYSTEM,
        messages=[{"role": "user", "content": content}],
    )
    # в ответе может быть блок рассуждений перед текстом, берём только текстовые блоки
    answer = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    if not answer:
        raise ValueError("Claude вернул ответ без текста")
    return answer


def make_review(image, true_place, guess_place, distance_km, score) -> str:
    facts = (
        f"Настоящее место: {true_place}. Ты поставил точку: {guess_place}. "
        f"Ошибка: {distance_km:.0f} км. Очки: {score} из 5000."
    )
    if image:
        try:
            return _ask_claude(image, facts)                     # со снимком
        except Exception:
            log.exception("запрос со снимком не прошёл, пробую без снимка")
    try:
        return _ask_claude(None, facts + " Снимок недоступен, объясни по географии.")
    except Exception:
        log.exception("Claude недоступен, отправляю разбор без ИИ")
    return f"Ты промахнулся на {distance_km:.0f} км. Было: {true_place}, ты поставил: {guess_place}."


def send_telegram(chat_id: int, text: str) -> None:
    r = httpx.post(
        f"https://api.telegram.org/bot{os.environ['BOT_TOKEN']}/sendMessage",
        json={"chat_id": chat_id, "text": text[:4000]},       # лимит Telegram 4096 символов
        timeout=15,
    )
    if r.status_code != 200:
        # 403 значит, что игрок не запускал бота или заблокировал его
        log.warning("sendMessage %s: %s", r.status_code, r.text)


def send_telegram_photo(chat_id: int, caption: str, image: tuple[str, str]) -> bool:
    """Отправляет снимок раунда с подписью. Возвращает False, если не вышло (тогда шлём просто текст)."""
    media_type, data = image
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{os.environ['BOT_TOKEN']}/sendPhoto",
            data={"chat_id": chat_id, "caption": caption[:1024]},     # лимит подписи 1024 символа
            files={"photo": ("round.jpg", base64.b64decode(data), media_type)},
            timeout=30,
        )
    except Exception:
        log.warning("sendPhoto не прошёл", exc_info=True)
        return False
    if r.status_code != 200:
        log.warning("sendPhoto %s: %s", r.status_code, r.text)
        return False
    return True


def send_round_review(
    tg_id: int,
    image_url: str,
    true_lat: float, true_lon: float,
    guess_lat: float, guess_lon: float,
    distance_km: float,
    score: int,
    round_number: int,
) -> None:
    """Собирает разбор раунда и отправляет его игроку. Ошибки только пишет в лог, игру не роняет."""
    try:
        t0 = time.monotonic()
        true_place = _place(true_lat, true_lon)
        guess_place = _place(guess_lat, guess_lon)
        t1 = time.monotonic()
        image = _get_image(image_url) if image_url else None   # один раз: и для Claude, и для сообщения
        t2 = time.monotonic()
        head = f"Раунд {round_number}: {score} очков, ошибка {distance_km:.0f} км.\n"
        if distance_km < CLOSE_ENOUGH_KM:
            body = f"Почти точно! Это {true_place}."        # ИИ не вызываем, экономим запрос
        else:
            body = make_review(image, true_place, guess_place, distance_km, score)
        t3 = time.monotonic()
        text = head + "\n" + body
        # снимок + разбор одним сообщением; если фото не отправилось, шлём только текст
        if not (image and send_telegram_photo(tg_id, text, image)):
            send_telegram(tg_id, text)
        t4 = time.monotonic()
        log.warning("разбор раунда за %.1f с: геокод %.1f, снимок %.1f, Claude %.1f, Telegram %.1f",
                    t4 - t0, t1 - t0, t2 - t1, t3 - t2, t4 - t3)
    except Exception:
        log.exception("не удалось отправить разбор раунда")