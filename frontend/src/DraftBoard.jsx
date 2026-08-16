import { useEffect, useMemo, useState } from "react";

// Set VITE_API_URL in your deployment host's environment variables to
// point at the deployed backend. Falls back to localhost for local dev.
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Number inputs need to allow an empty string as valid transient state
// while the user is editing - forcing Number("") to 0 immediately (and
// feeding that back as the controlled value) causes the classic "stuck
// leading zero" bug: clearing the field re-renders it as "0" instead of
// blank, so the next digit typed lands after that phantom 0 (e.g. "04").
function handleNumberChange(rawValue, setter) {
  if (rawValue === "") {
    setter("");
    return;
  }
  const num = Number(rawValue);
  if (!Number.isNaN(num)) {
    setter(num);
  }
}

// On blur, snap back to a sensible default if the field was left empty
// (or somehow ended up non-numeric) instead of staying blank forever.
function handleNumberBlur(value, setter, fallback) {
  if (value === "" || Number.isNaN(Number(value))) {
    setter(fallback);
  }
}

const POSITION_TABS = ["ALL", "QB", "RB", "WR", "FLEX", "DL", "LB", "DB"];

// Positions that count toward the FLEX filter
const FLEX_POSITIONS = ["RB", "WR"];

// Friendly column labels per position group, matching the raw stat field
// names the backend returns in each player's `stats` object.
const STAT_COLUMNS = {
  QB: [
    { key: "pass_yd", label: "Pass Yd" },
    { key: "pass_td", label: "Pass TD" },
    { key: "pass_int", label: "INT" },
    { key: "rush_yd", label: "Rush Yd" },
    { key: "rush_td", label: "Rush TD" },
  ],
  RB: [
    { key: "rush_att", label: "Att" },
    { key: "rush_yd", label: "Rush Yd" },
    { key: "rush_td", label: "Rush TD" },
    { key: "rec", label: "Rec" },
    { key: "rec_yd", label: "Rec Yd" },
  ],
  WR: [
    { key: "rec", label: "Rec" },
    { key: "rec_yd", label: "Rec Yd" },
    { key: "rec_td", label: "Rec TD" },
    { key: "rush_yd", label: "Rush Yd" },
  ],
  DL: [
    { key: "idp_tkl", label: "Tkl" },
    { key: "idp_sack", label: "Sack" },
    { key: "idp_ff", label: "FF" },
    { key: "idp_fum_rec", label: "FR" },
  ],
  LB: [
    { key: "idp_tkl", label: "Tkl" },
    { key: "idp_sack", label: "Sack" },
    { key: "idp_int", label: "INT" },
    { key: "idp_ff", label: "FF" },
  ],
  DB: [
    { key: "idp_tkl", label: "Tkl" },
    { key: "idp_int", label: "INT" },
    { key: "idp_ff", label: "FF" },
  ],
};

export default function DraftBoard() {
  const [draft, setDraft] = useState(null);
  const [available, setAvailable] = useState([]);
  const [status, setStatus] = useState("checking"); // checking | none | active | error
  const [numTeams, setNumTeams] = useState(14);
  const [rounds, setRounds] = useState(15);
  const [humanSlots, setHumanSlots] = useState([1]); // array of specific slot numbers

  const [positionFilter, setPositionFilter] = useState("ALL");
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState("adp");
  const [sortDir, setSortDir] = useState("asc");

  useEffect(() => {
    fetchDraftState();
  }, []);

  // if numTeams shrinks below a previously-selected human slot, drop it -
  // never leave the list empty though, always keep at least slot 1
  useEffect(() => {
    const max = Number(numTeams) || 14;
    setHumanSlots((prev) => {
      const filtered = prev.filter((s) => s <= max);
      return filtered.length > 0 ? filtered : [1];
    });
  }, [numTeams]);

  function fetchDraftState() {
    fetch(`${API_URL}/draft`)
      .then((res) => {
        if (res.status === 404) {
          setStatus("none");
          return null;
        }
        return res.json();
      })
      .then((data) => {
        if (data) {
          setDraft(data);
          setStatus("active");
          fetchAvailable();
        }
      })
      .catch(() => setStatus("error"));
  }

  function fetchAvailable() {
    // fetch everything and filter/sort client-side, same pattern as the
    // old players grid - avoids a round trip per filter change
    fetch(`${API_URL}/draft/available?limit=1000`)
      .then((res) => res.json())
      .then(setAvailable)
      .catch(() => {});
  }

  function startDraft() {
    fetch(`${API_URL}/draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        num_teams: Number(numTeams) || 14,
        rounds: Number(rounds) || 15,
        human_slots: humanSlots.length > 0 ? humanSlots : [1],
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        setDraft(data);
        setStatus("active");
        fetchAvailable();
      });
  }

  function toggleHumanSlot(slot) {
    setHumanSlots((prev) => {
      if (prev.includes(slot)) {
        // don't allow removing the last selected slot - at least one
        // human team must exist
        if (prev.length === 1) return prev;
        return prev.filter((s) => s !== slot);
      }
      return [...prev, slot].sort((a, b) => a - b);
    });
  }

  function draftPlayer(playerId) {
    fetch(`${API_URL}/draft/pick`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_id: playerId }),
    })
      .then((res) => res.json())
      .then((data) => {
        setDraft(data);
        fetchAvailable();
      });
  }

  function startOver() {
    fetch(`${API_URL}/draft`, { method: "DELETE" }).then(() => {
      setDraft(null);
      setAvailable([]);
      setStatus("none");
    });
  }

  function handleSort(key) {
    if (key === sortKey) {
      setSortDir(sortDir === "desc" ? "asc" : "desc");
    } else {
      setSortKey(key);
      setSortDir(key === "adp" ? "asc" : "desc"); // lower ADP = better, so ascending by default
    }
  }

  function handlePositionChange(pos) {
    setPositionFilter(pos);
    // sort selection (key + direction) intentionally left untouched -
    // switching position tabs shouldn't reset ADP/Points/column sorting
  }

  const columns = positionFilter === "ALL" || positionFilter === "FLEX"
    ? []
    : STAT_COLUMNS[positionFilter] || [];

  const visiblePlayers = useMemo(() => {
    let result = available;

    if (positionFilter === "FLEX") {
      result = result.filter((p) => FLEX_POSITIONS.includes(p.position_group));
    } else if (positionFilter !== "ALL") {
      result = result.filter((p) => p.position_group === positionFilter);
    }

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter((p) => p.name.toLowerCase().includes(q));
    }

    return [...result].sort((a, b) => {
      const getValue = (p) => {
        if (sortKey === "projected_points") return p.projected_points;
        if (sortKey === "adp") return p.adp;
        return p.stats?.[sortKey] ?? 0;
      };
      const aVal = getValue(a);
      const bVal = getValue(b);

      // players with no ADP data (null) always sort to the bottom,
      // regardless of sort direction - "unranked" should never look best
      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;

      return sortDir === "desc" ? bVal - aVal : aVal - bVal;
    });
  }, [available, positionFilter, search, sortKey, sortDir]);

  if (status === "checking") {
    return <div className="app-message">Loading draft...</div>;
  }

  if (status === "error") {
    return (
      <div className="app-message app-message--error">
        Couldn't reach the backend. Is the server running?
      </div>
    );
  }

  if (status === "none") {
    return (
      <div className="draft-setup">
        <h2>Start a Draft</h2>
        <div className="draft-setup-form">
          <label>
            Number of teams
            <input
              type="number"
              min="2"
              max="20"
              value={numTeams}
              onChange={(e) => handleNumberChange(e.target.value, setNumTeams)}
              onBlur={() => handleNumberBlur(numTeams, setNumTeams, 14)}
            />
          </label>
          <label>
            Rounds
            <input
              type="number"
              min="1"
              max="25"
              value={rounds}
              onChange={(e) => handleNumberChange(e.target.value, setRounds)}
              onBlur={() => handleNumberBlur(rounds, setRounds, 15)}
            />
          </label>
          <label>
            Your draft position(s)
            <span className="field-hint">Tap each position you're drafting for</span>
            <div className="slot-picker">
              {Array.from({ length: Number(numTeams) || 14 }, (_, i) => i + 1).map((slot) => (
                <button
                  key={slot}
                  type="button"
                  className={`slot-toggle ${humanSlots.includes(slot) ? "slot-toggle--active" : ""}`}
                  onClick={() => toggleHumanSlot(slot)}
                >
                  {slot}
                </button>
              ))}
            </div>
            <div className="slot-picker-summary">
              Selected: <strong>{[...humanSlots].sort((a, b) => a - b).join(", ")}</strong>
            </div>
          </label>
          <button className="primary-button" onClick={startDraft}>
            Start Draft
          </button>
        </div>
      </div>
    );
  }

  const currentTeamSlot = teamForPick(draft.current_pick_number, draft.num_teams);
  const currentTeam = draft.teams.find((t) => t.slot === currentTeamSlot);
  const isHumanTurn = draft.status === "active" && !currentTeam?.is_bot;

  // Build a lookup: gridPicks[round][teamSlot] = pick. Team columns stay in
  // fixed slot order (1..N) - the left-right/right-left fill pattern each
  // round falls out naturally from snake order, no need to reverse columns.
  const gridPicks = {};
  for (const pick of draft.picks) {
    const round = Math.floor((pick.pick_number - 1) / draft.num_teams) + 1;
    gridPicks[round] = gridPicks[round] || {};
    gridPicks[round][pick.team_slot] = pick;
  }

  return (
    <div className="draft-board">
      <div className="draft-status-bar">
        <span>
          Pick {draft.current_pick_number} of {draft.num_teams * draft.rounds}
        </span>
        <span className={isHumanTurn ? "turn-indicator turn-indicator--you" : "turn-indicator"}>
          {draft.status === "complete"
            ? "Draft complete"
            : isHumanTurn
            ? `${currentTeam?.name}'s turn`
            : `${currentTeam?.name}'s turn`}
        </span>
        <button className="text-button" onClick={startOver}>
          Start Over
        </button>
      </div>

      <div className="draft-grid-wrapper">
        <table className="draft-grid">
          <thead>
            <tr>
              <th className="draft-grid-round-header"></th>
              {draft.teams.map((team) => (
                <th
                  key={team.slot}
                  className={team.slot === currentTeamSlot && draft.status === "active" ? "draft-grid-team--onclock" : ""}
                >
                  {team.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: draft.rounds }, (_, i) => i + 1).map((round) => (
              <tr key={round}>
                <td className="draft-grid-round-header">R{round}</td>
                {draft.teams.map((team) => {
                  const pick = gridPicks[round]?.[team.slot];
                  const pickNumber = (round - 1) * draft.num_teams +
                    (round % 2 === 1 ? team.slot : draft.num_teams - team.slot + 1);
                  const isOnClock = draft.status === "active" && pickNumber === draft.current_pick_number;

                  return (
                    <td
                      key={team.slot}
                      className={`draft-grid-cell ${isOnClock ? "draft-grid-cell--onclock" : ""}`}
                    >
                      {pick ? (
                        <>
                          <div className="draft-grid-player-name">
                            {splitName(pick.player_name).first}
                            <br />
                            {splitName(pick.player_name).last}
                          </div>
                          <span className="position-badge">{pick.position}</span>
                        </>
                      ) : (
                        <span className="draft-grid-empty">
                          {isOnClock ? "on the clock" : ""}
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="controls">
        <div className="position-tabs">
          {POSITION_TABS.map((pos) => (
            <button
              key={pos}
              className={`position-tab ${positionFilter === pos ? "position-tab--active" : ""}`}
              onClick={() => handlePositionChange(pos)}
            >
              {pos}
            </button>
          ))}
        </div>
        <div className="sort-toggle">
          <button
            className={`sort-toggle-option ${sortKey === "adp" ? "sort-toggle-option--active" : ""}`}
            onClick={() => handleSort("adp")}
          >
            ADP
          </button>
          <button
            className={`sort-toggle-option ${sortKey === "projected_points" ? "sort-toggle-option--active" : ""}`}
            onClick={() => handleSort("projected_points")}
          >
            Projected
          </button>
        </div>
        <input
          type="text"
          placeholder="Search players..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="search-input"
        />
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Team</th>
              <th>Pos</th>
              <th className="sortable" onClick={() => handleSort("projected_points")}>
                Proj Pts {sortKey === "projected_points" && (sortDir === "desc" ? "▼" : "▲")}
              </th>
              <th className="sortable" onClick={() => handleSort("adp")}>
                ADP {sortKey === "adp" && (sortDir === "desc" ? "▼" : "▲")}
              </th>
              {columns.map((col) => (
                <th key={col.key} className="sortable" onClick={() => handleSort(col.key)}>
                  {col.label} {sortKey === col.key && (sortDir === "desc" ? "▼" : "▲")}
                </th>
              ))}
              <th></th>
            </tr>
          </thead>
          <tbody>
            {visiblePlayers.map((p) => (
              <tr key={p.player_id}>
                <td className="name-cell">{p.name}</td>
                <td>{p.team || "FA"}</td>
                <td>
                  <span className="position-badge">{p.position}</span>
                </td>
                <td className="num-cell">{p.projected_points?.toFixed(1)}</td>
                <td className="num-cell">{p.adp != null ? p.adp.toFixed(1) : "NR"}</td>
                {columns.map((col) => (
                  <td key={col.key} className="num-cell">
                    {p.stats?.[col.key] ?? "-"}
                  </td>
                ))}
                <td>
                  <button
                    disabled={!isHumanTurn}
                    onClick={() => draftPlayer(p.player_id)}
                    className="draft-button"
                  >
                    Draft
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {visiblePlayers.length === 0 && (
          <div className="empty-state">No players match your filters.</div>
        )}
      </div>
    </div>
  );
}

// Splits "Josh Allen" into { first: "Josh", last: "Allen" }.
// Handles multi-word last names (e.g. "Amon-Ra St. Brown") by treating
// everything after the first word as the last name.
function splitName(fullName) {
  const [first, ...rest] = fullName.split(" ");
  return { first, last: rest.join(" ") };
}

// Mirrors the backend's snake draft order logic (see draft_data.py) so the
// UI can show whose turn it is without waiting on an extra request.
function teamForPick(pickNumber, numTeams) {
  const roundNumber = Math.floor((pickNumber - 1) / numTeams);
  const posInRound = (pickNumber - 1) % numTeams;
  return roundNumber % 2 === 0 ? posInRound + 1 : numTeams - posInRound;
}