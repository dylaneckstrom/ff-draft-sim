"""
Custom league scoring. Maps each raw Sleeper stat field to a point value
per unit. To change scoring, edit SCORING_RULES here - nothing else in
the app needs to change, since players_data.py just calls
calculate_points() and stores the result as projected_points.

Any stat field NOT listed here contributes 0 points (e.g. interceptions
thrown, field goals - not currently scored).
"""

SCORING_RULES = {
    # touchdowns - 100 pts each, regardless of how they're scored
    "pass_td": 100,
    "rush_td": 100,
    "rec_td": 100,

    "rush_att": 1,
    "rec": 5,  # receptions - 5 pts each

    # yardage - 1 pt per yard
    "pass_yd": 1,
    "rush_yd": 1,
    "rec_yd": 1,

    # defense (DL/LB/DB) - idp_tkl is total tackles (solo + assisted
    # combined); using idp_tkl_solo/idp_tkl_ast separately would double-count
    "idp_tkl": 12,
    "idp_sack": 100,
    "idp_int": 75,
    "idp_ff": 50,
}


def calculate_points(stats: dict) -> float:
    """
    stats: a player's raw stat dict (e.g. {"rush_yd": 535, "rush_td": 11, ...})
    Returns total projected points under SCORING_RULES.
    """
    total = 0
    for stat_key, points_per_unit in SCORING_RULES.items():
        total += stats.get(stat_key, 0) * points_per_unit
    return round(total, 1)