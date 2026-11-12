# GeoGuessrBot

## Сборка и запуск

Нужны запущенный Docker Desktop (или Docker Engine с Compose), `cloudflared`
и токен Telegram-бота от @BotFather. Команды выполняются из корня проекта.

1. Заполните `.env`:

2. Соберите и запустите БД, backend и frontend:

   ```bash
   docker compose up --build -d postgres backend front
   ```

   Frontend: http://localhost:8000. Проверка API: http://localhost:8000/api/status.

3. В отдельном терминале запустите HTTPS-туннель:

   ```bash
   cloudflared tunnel --protocol quic --url http://localhost:8000
   ```

   Запишите полученный адрес `https://….trycloudflare.com` в `WEBAPP_URL`
   в `.env`. Оставьте терминал с туннелем открытым.

4. Соберите и запустите бота:

   ```bash
   docker compose up --build -d tg_bot
   ```

   Откройте бота в Telegram, отправьте `/start` и нажмите «Играть».
   После смены адреса туннеля обновите `WEBAPP_URL` и выполните
   `docker compose up -d tg_bot`.
