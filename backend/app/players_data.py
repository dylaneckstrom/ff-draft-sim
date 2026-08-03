"""
Loads player projections from the local JSON export into memory once at
startup. No database - this is static reference data that doesn't change
per-request, so there's nothing to gain from persisting it to disk beyond
the JSON file itself.
"""
import json
from pathlib import Path
from typing import Optional

PROJECTIONS_FILE = Path(__file__).parent.parent / "player_projections.json"

# Sleeper's real position taxonomy is more granular than standard fantasy
# positions - this maps each raw position onto the bucket you care about.
POSITION_GROUPS = {
    "QB": "QB",
    "RB": "RB",
    "FB": "RB",
    "WR": "WR",
    "TE": "TE",
    "DL": "DL", "DE": "DL", "DT": "DL", "NT": "DL",
    "LB": "LB", "OLB": "LB", "ILB": "LB",
    "DB": "DB", "CB": "DB", "SS": "DB", "FS": "DB", "S": "DB",
}

STAT_FIELDS_BY_GROUP = {
    "QB": ["pass_yd", "pass_td", "pass_int", "pass_cmp", "pass_att", "rush_yd", "rush_td"],
    "RB": ["rush_att", "rush_yd", "rush_td", "rec", "rec_yd", "rec_td"],
    "WR": ["rec", "rec_yd", "rec_td", "rush_att", "rush_yd", "rush_td"],
    "TE": ["rec", "rec_yd", "rec_td", "rush_att", "rush_yd", "rush_td"],
    "DL": ["idp_tkl", "idp_tkl_solo", "idp_tkl_ast", "idp_sack", "idp_ff", "idp_fum_rec", "idp_int", "idp_safe"],
    "LB": ["idp_tkl", "idp_tkl_solo", "idp_tkl_ast", "idp_sack", "idp_int", "idp_ff", "idp_fum_rec"],
    "DB": ["idp_tkl", "idp_tkl_solo", "idp_tkl_ast", "idp_int", "idp_ff", "idp_fum_rec"],
}

# Module-level cache - populated once by load_players(), read by every request.
_players_cache: Optional[list] = None


def load_players() -> list[dict]:
    """
    Reads the JSON file and processes it into a flat list of player dicts.
    Called once at app startup; result is cached in memory for the life
    of the process.
    """
    global _players_cache
    if _players_cache is not None:
        return _players_cache

    with open(PROJECTIONS_FILE, "r", encoding="utf-8") as f:
        raw_entries = json.load(f)

    results = []
    for entry in raw_entries:
        player = entry.get("player") or {}
        raw_position = player.get("position")
        group = POSITION_GROUPS.get(raw_position)
        if group is None:
            continue

        stats = entry.get("stats", {})
        relevant_fields = STAT_FIELDS_BY_GROUP.get(group, [])

        results.append({
            "player_id": entry.get("player_id"),
            "name": f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(),
            "position": raw_position,
            "position_group": group,
            "team": player.get("team"),
            "projected_points": stats.get("pts_ppr") or stats.get("pts_std") or 0,
            "stats": {field: stats.get(field, 0) for field in relevant_fields},
        })

    results.sort(key=lambda p: p["projected_points"], reverse=True)
    _players_cache = results
    return _players_cache