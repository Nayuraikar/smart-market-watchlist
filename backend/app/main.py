from fastapi import FastAPI

app = FastAPI(title="Smart Market Watchlist")

@app.get("/health")
async def health():
    return {"status": "ok"}
