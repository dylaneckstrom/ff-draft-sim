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
import os
# ... (added near the top with the other imports)

from .players_data import load_players
from .routers import players_router, draft_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    players = load_players()
    print(f"Loaded {len(players)} players into memory")
    yield


app = FastAPI(title="Fantasy Draft App", lifespan=lifespan)

# Comma-separated list of allowed frontend origins, e.g.
# "https://ff-draft-sim.vercel.app,http://localhost:5173"
# Set CORS_ORIGINS in your host's environment variables when deploying -
# no code change or redeploy needed to add/change allowed origins.
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
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