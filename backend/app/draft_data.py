"""
Snake draft engine. In-memory only (no database) - state lives for the
life of the server process.

Single draft at a time, shared by everyone hitting the server - simplest
possible setup for one person using the app. If multiple people load the
site simultaneously they'd see the same draft. Revisit multi-draft
support (keyed by ID) later if that becomes a real need.
"""
import random
from collections import defaultdict

from .players_data import load_players

DRAFT_STATE = None  # reset by calling create_draft()

# Every draftable position group, used to initialize each team's counters.
# TE folds into WR at the source (see players_data.py) so it's not listed
# separately here.
ALL_POSITION_GROUPS = ["QB", "RB", "WR", "DL", "LB", "DB"]

# Static keepers - these players are auto-assigned at their pick number
# before any live drafting happens at that pick. Keyed by pick_number
# (not team), so whichever team's snake-order turn lands on that pick
# gets the keeper - live drafting still starts at pick 1 and proceeds
# normally, these picks just get silently filled when the draft reaches
# them instead of being offered up for a real choice.
KEEPERS = {
    13: "9226",  # De'Von Achane
    14: "9221",  # Jahmyr Gibbs
}


def _find_player_by_id(player_id: str):
    return next((p for p in load_players() if p["player_id"] == player_id), None)


def _apply_keepers(state: dict):
    """
    Inserts keeper picks directly into state, immediately at draft
    creation - this reserves those players from pick 1 onward so no
    bot/human can draft them before their designated pick number.
    Does NOT touch current_pick_number - live drafting still starts
    at pick 1; _advance_bots() skips over these pick numbers when the
    sequential counter reaches them.
    """
    for pick_number, player_id in KEEPERS.items():
        player = _find_player_by_id(player_id)
        if player is None:
            continue  # keeper player not found in the pool - skip silently

        team_slot = team_for_pick(pick_number, state["num_teams"])
        team = next((t for t in state["teams"] if t["slot"] == team_slot), None)
        if team is None:
            continue  # pick_number falls outside num_teams - skip silently

        pick = {
            "pick_number": pick_number,
            "team_slot": team["slot"],
            "player_id": player["player_id"],
            "player_name": player["name"],
            "position": player["position"],
            "team": player["team"]
        }
        state["picks"].append(pick)
        state["drafted_player_ids"].add(player["player_id"])
        team["roster"].append(pick)
        team["position_counts"][player["position_group"]] = (
            team["position_counts"].get(player["position_group"], 0) + 1
        )


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
            "position_counts": {pos: 0 for pos in ALL_POSITION_GROUPS},
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

    _apply_keepers(DRAFT_STATE)
    _advance_bots(DRAFT_STATE)
    return get_state()


def get_state():
    if DRAFT_STATE is None:
        return None
    # `drafted_player_ids` is a set, not JSON-serializable - omit it from output
    return {k: v for k, v in DRAFT_STATE.items() if k != "drafted_player_ids"}


def _current_team(state: dict):
    slot = team_for_pick(state["current_pick_number"], state["num_teams"])
    return next(t for t in state["teams"] if t["slot"] == slot)


def _available_players(state: dict):
    all_players = load_players()
    drafted = state["drafted_player_ids"]
    return [p for p in all_players if p["player_id"] not in drafted]


def _record_pick(state: dict, team: dict, player: dict):
    pick = {
        "pick_number": state["current_pick_number"],
        "team_slot": team["slot"],
        "player_id": player["player_id"],
        "player_name": player["name"],
        "position": player["position"],
        "team": player["team"]
    }
    state["picks"].append(pick)
    state["drafted_player_ids"].add(player["player_id"])
    team["roster"].append(pick)
    team["position_counts"][player["position_group"]] = (
        team["position_counts"].get(player["position_group"], 0) + 1
    )

    state["current_pick_number"] += 1
    total_picks = state["rounds"] * state["num_teams"]
    if state["current_pick_number"] > total_picks:
        state["status"] = "complete"


# Hard cap on how many players a team can draft at each position group.
# A position hitting its limit is completely excluded from bot
# consideration - not just deprioritized.
POSITION_LIMITS = {
    "QB": 2,
    "RB": 10,
    "WR": 10,   # TE players are folded into WR at the source (players_data.py)
    "DL": 2,
    "LB": 2,
    "DB": 2,
}


def _need_count(counts: dict, position: str) -> int:
    """How many players a team already has at this position."""
    return counts.get(position, 0)


# Base weight per position group - multiplies against the need-based
# weight below. 1.0 is neutral. Values above 1.0 make a position more
# likely to be picked overall (all else equal); below 1.0 makes it less
# likely. Tune these to shift the bots' general draft priorities.
POSITION_WEIGHTS = {
    "QB": 0.9,   # QBs score very high under this league's scoring, so bots
                 # would over-draft them without this counterweight
    "RB": 1.5,
    "WR": 1.3,   # includes TE players, folded in at the source
    "DL": 0.1,
    "LB": 0.1,
    "DB": 0.05,
}

# Defensive positions can't be drafted by bots before this round.
DEFENSE_POSITIONS = {"DL", "LB", "DB"}
MIN_DEFENSE_ROUND = 4


def _current_round(state: dict) -> int:
    return (state["current_pick_number"] - 1) // state["num_teams"] + 1


def _choose_bot_player(state: dict, team: dict):
    """
    Weighted-random pick instead of always grabbing the single highest-
    projected player.

    1. WHICH POSITION: weighted by the fixed POSITION_WEIGHTS multiplier
       per position (see above) - a straightforward "how often should
       this position get picked overall" bias. Positions at their
       POSITION_LIMITS cap are excluded entirely (this is what actually
       stops a team from stacking one position - not the weight itself),
       and defense (DL/LB/DB) is excluded entirely before
       MIN_DEFENSE_ROUND. (TE players are folded into WR at the source -
       see players_data.py - so there's no separate TE bucket to weight.)
    2. WHICH PLAYER at that position: picked randomly from the top few
       by points, not always the single #1 - avoids every bot drafting
       the exact same player order.
    """
    available = _available_players(state)
    if not available:
        return None

    by_position = defaultdict(list)
    for p in available:
        by_position[p["position_group"]].append(p)

    counts = team["position_counts"]
    current_round = _current_round(state)

    # exclude any position that's hit its cap
    positions = [
        pos for pos in by_position.keys()
        if _need_count(counts, pos) < POSITION_LIMITS.get(pos, float("inf"))
    ]

    # exclude defense entirely before MIN_DEFENSE_ROUND
    if current_round < MIN_DEFENSE_ROUND:
        positions = [pos for pos in positions if pos not in DEFENSE_POSITIONS]

    if not positions:
        # everything got excluded (caps + defense restriction both hit,
        # or a very early round with nothing else left) - fall back to
        # every available position rather than failing to pick at all
        positions = list(by_position.keys())

    weights = [POSITION_WEIGHTS.get(pos, 1.0) for pos in positions]
    chosen_position = random.choices(positions, weights=weights, k=1)[0]

    candidates = sorted(
            by_position[chosen_position], key=lambda p: p["projected_points"], reverse=True
        )[:3]
    # weight toward the best player at this position, but not exclusively -
    # trimmed to match len(candidates) in case fewer than 3 are left
    candidate_weights = [75, 18, 7][:len(candidates)]
    return random.choices(candidates, weights=candidate_weights, k=1)[0]


def _advance_bots(state: dict):
    """
    Runs bot picks until it's the human's turn or the draft ends.
    Skips over any pick_number already filled by a keeper (see
    _apply_keepers) without re-recording it.
    """
    total_picks = state["rounds"] * state["num_teams"]

    while state["status"] == "active":
        pick_number = state["current_pick_number"]

        if pick_number in KEEPERS:
            # already recorded via _apply_keepers() at draft creation -
            # just advance the counter past it
            state["current_pick_number"] += 1
            if state["current_pick_number"] > total_picks:
                state["status"] = "complete"
            continue

        team = _current_team(state)
        if not team["is_bot"]:
            break

        player = _choose_bot_player(state, team)
        if player is None:
            state["status"] = "complete"
            break

        _record_pick(state, team, player)


def make_human_pick(player_id: str):
    if DRAFT_STATE is None or DRAFT_STATE["status"] != "active":
        raise ValueError("No active draft")

    team = _current_team(DRAFT_STATE)
    if team["is_bot"]:
        raise ValueError("It is not the human's turn")

    player = next((p for p in _available_players(DRAFT_STATE) if p["player_id"] == player_id), None)
    if player is None:
        raise ValueError("Player not found or already drafted")

    _record_pick(DRAFT_STATE, team, player)
    _advance_bots(DRAFT_STATE)
    return get_state()


def reset_draft():
    global DRAFT_STATE
    DRAFT_STATE = None


def available_players(position: str = None, limit: int = 300):
    if DRAFT_STATE is None:
        return []
    players = _available_players(DRAFT_STATE)
    if position:
        players = [p for p in players if p["position_group"] == position]
    return players[:limit]