# Где это? — интерфейс мини-аппа на React

Интерфейс Telegram-игры в стиле GeoGuessr: фото на весь экран, карта-карточка, очки, итоги.
Работает внутри Telegram и подстраивается под его тему (светлую и тёмную).

## Запуск

```bash
npm install
npm run dev          # http://localhost:5173
```

Открой `http://localhost:5173/?mock=1`, чтобы поиграть без сервера (демо-режим с тестовыми картинками).
Если сервер игры не отвечает, демо-режим включается сам.

### Открыть из Telegram

Telegram открывает только HTTPS-адреса. Для разработки поднимите туннель:

```bash
cloudflared tunnel --url http://localhost:5173
```

Адрес из вывода (`https://….trycloudflare.com/`) укажите в `WEBAPP_URL` для бота.
Vite уже настроен пускать запросы с адресов туннеля (`allowedHosts: true`).

### Сборка

```bash
npm run build        # результат в папке dist/
```

Папку `dist/` раздаёт сервер игры (например, FastAPI через `StaticFiles(directory="dist", html=True)`)
или любой статический хостинг.

## Структура

```
src/
  main.jsx               точка входа
  App.jsx                собирает экраны, держит просмотр фото
  App.css                все стили (цвета берутся из темы Telegram)
  api.js                 запросы к серверу + демо-режим
  telegram.js            обёртка над Telegram WebApp (тема, haptic, подпись)
  utils.js               форматирование чисел, анимация «набегающих» цифр
  hooks/useGame.js       вся логика игры (старт → раунд → результат → итоги)
  components/
    StartScreen.jsx      стартовый экран
    Photo.jsx            фото на весь экран
    Hud.jsx              раунд и счёт
    MapCard.jsx          карта Leaflet, булавки, линия, раскрытие
    Dock.jsx             кнопка «Угадать» и панель результата
    FinalScreen.jsx      итоги: кольцо, список раундов, рейтинг
    TopList.jsx          рейтинг
```

## Что должен отвечать сервер

| Запрос | Ответ |
|---|---|
| `POST /api/game/start` | `{ round_no, rounds_total: null, token, image_url }` |
| `GET /api/round` | то же |
| `POST /api/guess {token, lat, lon}` | `{ distance_km, score, total, true: {lat, lon}, author, license, source_url, finished }` |
| `POST /api/game/finish {token}` | `{}` (необязательно) |
| `GET /api/top` | `[ { name, best } ]` |

Каждый запрос идёт с заголовком `X-Init-Data` — подписанные данные пользователя от Telegram,
сервер обязан проверять подпись. Правильные координаты отдаются только в ответе на `/api/guess`.
`rounds_total: null` означает игру без ограничения раундов.
