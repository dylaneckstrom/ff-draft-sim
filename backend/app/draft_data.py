"""
Snake draft engine. In-memory only (no database) - state lives for the
life of the server process. Same "load once, keep in memory" pattern as
players_data.py, but this data actually mutates as picks happen.

If you later want the draft to survive a server restart, or support
multiple people picking from different devices, this is the piece that
would move into a database - the shape of DRAFT_STATE below maps
directly onto a Draft/DraftTeam/DraftPick table design.
"""
from .players_data import load_players

DRAFT_STATE = None  # single draft at a time - reset by calling create_draft()


def team_for_pick(pick_number: int, num_teams: int) -> int:
    """
    Snake order: 1..N, then N..1, then 1..N, etc.
    Returns the 1-indexed team slot whose turn it is.
    """
    round_number = (pick_number - 1) // num_teams
    pos_in_round = (pick_number - 1) % num_teams
    if round_number % 2 == 0:
        return pos_in_round + 1
    return num_teams - pos_in_round


def create_draft(num_teams: int = 10, rounds: int = 15, human_slot: int = 1):
    global DRAFT_STATE

    teams = []
    for slot in range(1, num_teams + 1):
        is_bot = slot != human_slot
        teams.append({
            "slot": slot,
            "name": f"Team {slot}" if is_bot else "My Team",
            "is_bot": is_bot,
            "roster": [],
        })

    DRAFT_STATE = {
        "num_teams": num_teams,
        "rounds": rounds,
        "current_pick_number": 1,
        "status": "active",
        "teams": teams,
        "picks": [],  # list of {pick_number, team_slot, player_id, player_name, position}
        "drafted_player_ids": set(),
    }

    _advance_bots()
    return get_state()


def get_state():
    if DRAFT_STATE is None:
        return None
    # `drafted_player_ids` is a set, not JSON-serializable - omit it from output
    state = {k: v for k, v in DRAFT_STATE.items() if k != "drafted_player_ids"}
    return state


def _current_team():
    slot = team_for_pick(DRAFT_STATE["current_pick_number"], DRAFT_STATE["num_teams"])
    return next(t for t in DRAFT_STATE["teams"] if t["slot"] == slot)


def _available_players():
    all_players = load_players()
    drafted = DRAFT_STATE["drafted_player_ids"]
    return [p for p in all_players if p["player_id"] not in drafted]


def _record_pick(team: dict, player: dict):
    pick = {
        "pick_number": DRAFT_STATE["current_pick_number"],
        "team_slot": team["slot"],
        "player_id": player["player_id"],
        "player_name": player["name"],
        "position": player["position"],
    }
    DRAFT_STATE["picks"].append(pick)
    DRAFT_STATE["drafted_player_ids"].add(player["player_id"])
    team["roster"].append(pick)

    DRAFT_STATE["current_pick_number"] += 1
    total_picks = DRAFT_STATE["rounds"] * DRAFT_STATE["num_teams"]
    if DRAFT_STATE["current_pick_number"] > total_picks:
        DRAFT_STATE["status"] = "complete"


def _choose_bot_player():
    """
    Simplest viable strategy: take the highest-projected player left on
    the board. Swap this out for positional-need logic later - it's
    isolated here on purpose so the turn-order code never has to change.
    """
    available = _available_players()
    return available[0] if available else None


def _advance_bots():
    """Runs bot picks until it's the human's turn or the draft ends."""
    while DRAFT_STATE["status"] == "active":
        team = _current_team()
        if not team["is_bot"]:
            break

        player = _choose_bot_player()
        if player is None:
            DRAFT_STATE["status"] = "complete"
            break

        _record_pick(team, player)


def make_human_pick(player_id: str):
    if DRAFT_STATE is None or DRAFT_STATE["status"] != "active":
        raise ValueError("No active draft")

    team = _current_team()
    if team["is_bot"]:
        raise ValueError("It is not the human's turn")

    player = next((p for p in _available_players() if p["player_id"] == player_id), None)
    if player is None:
        raise ValueError("Player not found or already drafted")

    _record_pick(team, player)
    _advance_bots()
    return get_state()


def available_players(position: str = None, limit: int = 300):
    if DRAFT_STATE is None:
        return []
    players = _available_players()
    if position:
        players = [p for p in players if p["position_group"] == position]
    return players[:limit]