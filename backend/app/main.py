from fastapi import FastAPI
from app.core.errors import register_exception_handlers

app = FastAPI(title="Smart Market Watchlist")
register_exception_handlers(app)


@app.get("/health")
async def health():
    return {"status": "ok"}
