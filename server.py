from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers.auth import router as auth_router
from routers.autotrader import router as autotrader_router
from routers.backtest import router as backtest_router
from routers.chat import router as chat_router
from routers.datasets import router as datasets_router
from routers.experiment import router as experiment_router
from routers.gate import router as gate_router
from routers.live import router as live_router
from routers.meta import router as meta_router
from routers.news import router as news_router
from routers.paper import router as paper_router
from routers.pine import router as pine_router
from routers.presets import router as presets_router
from routers.universe import router as universe_router
from routers.market import router as market_router
from routers.admin import router as admin_router

app = FastAPI(title="TradeBoard API - Pine Long", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev convenience; narrow in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static web assets for remote/mobile use
# Access via: http://<host>:<port>/static/magic.html
STATIC_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=False), name="static")

# Built-in routers
app.include_router(meta_router)
app.include_router(auth_router)
app.include_router(backtest_router)
app.include_router(pine_router)
app.include_router(experiment_router)
app.include_router(live_router)
app.include_router(paper_router)
app.include_router(datasets_router)
app.include_router(autotrader_router)
app.include_router(universe_router)
app.include_router(gate_router)
app.include_router(market_router)

# Existing feature routers
app.include_router(news_router)
app.include_router(chat_router)
app.include_router(presets_router)
app.include_router(admin_router)


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host=host, port=port, reload=False)
