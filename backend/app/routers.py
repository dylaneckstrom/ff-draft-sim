from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .players_data import load_players
from . import draft_data

# --- players ---------------------------------------------------------

players_router = APIRouter(prefix="/players", tags=["players"])


@players_router.get("")
async def list_players(
    position: Optional[str] = Query(None, description="Filter by position group: QB, RB, WR, DL, LB, DB"),
    limit: int = 300,
):
    players = load_players()

    if position:
        position = position.upper()
        players = [p for p in players if p["position_group"] == position]

    return players[:limit]


# --- draft -------------------------------------------------------------

draft_router = APIRouter(prefix="/draft", tags=["draft"])


class CreateDraftRequest(BaseModel):
    num_teams: int = 14
    rounds: int = 15
    human_slot: int = 1


class MakePickRequest(BaseModel):
    player_id: str


@draft_router.post("")
async def create_draft(req: CreateDraftRequest):
    return draft_data.create_draft(
        num_teams=req.num_teams,
        rounds=req.rounds,
        human_slot=req.human_slot,
    )


@draft_router.get("")
async def get_draft():
    state = draft_data.get_state()
    if state is None:
        raise HTTPException(404, "No draft has been created yet")
    return state


@draft_router.delete("")
async def reset_draft():
    draft_data.reset_draft()
    return {"status": "reset"}


@draft_router.post("/pick")
async def make_pick(req: MakePickRequest):
    try:
        return draft_data.make_human_pick(req.player_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@draft_router.get("/available")
async def get_available(
    position: Optional[str] = Query(None),
    limit: int = 300,
):
    return draft_data.available_players(position=position, limit=limit)