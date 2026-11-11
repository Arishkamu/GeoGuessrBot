import os
import json
import hmac
import hashlib
import time

from urllib.parse import parse_qsl
from dotenv import load_dotenv
from fastapi import HTTPException, Header

# from app.services.game_service import get_or_create_user
from app.models.game import User


def get_user_by_tg_data(authorization: str = Header(...)) -> User:

    if not authorization.startswith("tma "):
        raise HTTPException(status_code=401, detail="Invalid authorization")

    init_data = authorization[4:]
    telegram_user = validate_telegram_init_data(init_data)
    
    if not telegram_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid Telegram initData",
        )

    user = get_or_create_user(
        tg_id=telegram_user["id"],
        username=telegram_user.get("username"),
    )

    if user is None:
        raise HTTPException(
            status_code=500,
            detail="Could not get or create user",
        )

    return User

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

def validate_telegram_init_data(init_data: str) -> dict | None:
    if not BOT_TOKEN or not init_data:
        return None

    try:
        # Parse Telegram initData
        data = dict(parse_qsl(init_data, keep_blank_values=True))

        received_hash = data.pop("hash", None)

        if not received_hash:
            return None

        # Create data-check-string
        data_check_string = "\n".join(
            f"{key}={value}"
            for key, value in sorted(data.items())
        )

        # Generate secret key
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=BOT_TOKEN.encode(),
            digestmod=hashlib.sha256,
        ).digest()

        # Calculate hash
        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()

        # Verify signature
        if not hmac.compare_digest(calculated_hash, received_hash):
            return None

        # Check authentication date (5 minutes)
        auth_date = int(data.get("auth_date", 0))
        current_time = int(time.time())

        if auth_date <= 0 or current_time - auth_date > 300:
            return None

        # Reject timestamps too far in the future
        if auth_date > current_time + 30:
            return None

        # Extract Telegram user
        user_data = data.get("user")

        if not user_data:
            return None

        return json.loads(user_data)

    except (ValueError, TypeError, json.JSONDecodeError):
        return None