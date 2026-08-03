"""
Base FastAPI app.

Player projections load from a local JSON file into memory once at
startup (see players_data.py) - no database for this static data.
A database will be added later, once we're persisting draft state
(picks, turn order) which actually changes at runtime.

Run with:
    uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .players_data import load_players
from .routers import players_router, draft_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    players = load_players()
    print(f"Loaded {len(players)} players into memory")
    yield


app = FastAPI(title="Fantasy Draft App", lifespan=lifespan)

# Vite's default dev server port. Add your deployed frontend URL here too, later.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players_router)
app.include_router(draft_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"message": "Fantasy Draft API is running"}