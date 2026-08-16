"""
Loads player projections from the local JSON export into memory once at
startup. No database - this is static reference data that doesn't change
per-request, so there's nothing to gain from persisting it to disk beyond
the JSON file itself.
"""
import json
from pathlib import Path
from typing import Optional

from .scoring import calculate_points

PROJECTIONS_FILE = Path(__file__).parent.parent / "player_projections.json"

# Sleeper's real position taxonomy is more granular than standard fantasy
# positions - this maps each raw position onto the bucket you care about.
# TE folds directly into WR (not its own group) since this league has no
# separate TE requirement - individual players still show "TE" as their
# raw `position` for display, they just count as WR everywhere else.
POSITION_GROUPS = {
    "QB": "QB",
    "RB": "RB",
    "FB": "RB",
    "WR": "WR",
    "TE": "WR",
    "DL": "DL", "DE": "DL", "DT": "DL", "NT": "DL",
    "LB": "LB", "OLB": "LB", "ILB": "LB",
    "DB": "DB", "CB": "DB", "SS": "DB", "FS": "DB", "S": "DB",
}

STAT_FIELDS_BY_GROUP = {
    "QB": ["pass_yd", "pass_td", "pass_int", "pass_cmp", "pass_att", "rush_yd", "rush_td"],
    "RB": ["rush_att", "rush_yd", "rush_td", "rec", "rec_yd", "rec_td"],
    "WR": ["rec", "rec_yd", "rec_td", "rush_att", "rush_yd", "rush_td"],
    "DL": ["idp_tkl", "idp_tkl_solo", "idp_tkl_ast", "idp_sack", "idp_ff", "idp_fum_rec", "idp_int", "idp_safe"],
    "LB": ["idp_tkl", "idp_tkl_solo", "idp_tkl_ast", "idp_sack", "idp_int", "idp_ff", "idp_fum_rec"],
    "DB": ["idp_tkl", "idp_tkl_solo", "idp_tkl_ast", "idp_int", "idp_ff", "idp_fum_rec"],
}

# Which raw Sleeper ADP field is meaningful per position group. Offensive
# positions use standard-format ADP (adp_std); defensive positions use
# IDP-format ADP (adp_idp) since they're not part of standard non-IDP
# mock drafts. Sleeper uses 999.0 as a placeholder for "no real ADP data" -
# treated as None (unranked) rather than a literal number 999.
ADP_FIELD_BY_GROUP = {
    "QB": "adp_std",
    "RB": "adp_std",
    "WR": "adp_std",
    "DL": "adp_idp",
    "LB": "adp_idp",
    "DB": "adp_idp",
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

        adp_field = ADP_FIELD_BY_GROUP.get(group)
        raw_adp = stats.get(adp_field, 999.0) if adp_field else 999.0
        adp = raw_adp if raw_adp < 999.0 else None  # None = no ADP data (unranked)

        results.append({
            "player_id": entry.get("player_id"),
            "name": f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(),
            "position": raw_position,
            "position_group": group,
            "team": player.get("team"),
            "projected_points": calculate_points(stats),
            "adp": adp,
            "stats": {field: stats.get(field, 0) for field in relevant_fields},
        })

    results.sort(key=lambda p: p["projected_points"], reverse=True)
    _players_cache = results
    return _players_cache