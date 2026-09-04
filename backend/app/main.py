from fastapi import FastAPI
from app.core.errors import register_exception_handlers
from app.routers import auth

app = FastAPI(title="Smart Market Watchlist")
register_exception_handlers(app)
app.include_router(auth.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
