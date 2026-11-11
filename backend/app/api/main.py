from fastapi import FastAPI


import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import router
from app.database.db import init_db, connect_db

load_dotenv()

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

app = FastAPI(title="Telegram Mini App API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers

connect_db()
init_db()
app.include_router(router)