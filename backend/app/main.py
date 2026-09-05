import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.errors import register_exception_handlers
from app.routers import auth, watchlists, stocks

app = FastAPI(title="Smart Market Watchlist")

cors_origins_env = os.environ.get("CORS_ORIGINS", "")
allowed_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]

if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False, # Auth uses Authorization Bearer headers, not cookies
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "Origin"],
    )

register_exception_handlers(app)
app.include_router(auth.router)
app.include_router(watchlists.router)
app.include_router(stocks.router)


@app.get("/health")
async def health():
    return {"status": "ok"}