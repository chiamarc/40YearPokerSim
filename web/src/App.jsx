import React, { useEffect, useMemo, useState } from "react";

const API_BASE = "http://127.0.0.1:8000";

const fetchJson = async (path, options) => {
  const res = await fetch(`${API_BASE}${path}`, options);
  const data = await res.json();
  if (!res.ok) {
    const message = data?.detail || "Request failed";
    throw new Error(message);
  }
  return data;
};

const suitSymbol = (suit) => {
  if (suit === "S") return "♠";
  if (suit === "H") return "♥";
  if (suit === "D") return "♦";
  if (suit === "C") return "♣";
  return suit;
};

const rankLabel = (rank) => rank;

const Hand = ({ hand, index }) => (
  <div className="hand">
    <div className="hand-title">Player {index + 1}</div>
    <div className="card-row">
      {hand.map((card) => (
        <div className="card" key={card.code} data-suit={card.suit}>
          <div className="card-corner top-left">
            <div className="rank">{rankLabel(card.rank)}</div>
            <div className="suit">{suitSymbol(card.suit)}</div>
          </div>
          <div className="card-corner top-right">
            <div className="rank">{rankLabel(card.rank)}</div>
            <div className="suit">{suitSymbol(card.suit)}</div>
          </div>
          <div className="card-center">{suitSymbol(card.suit)}</div>
          <div className="card-corner bottom-left">
            <div className="rank">{rankLabel(card.rank)}</div>
            <div className="suit">{suitSymbol(card.suit)}</div>
          </div>
          <div className="card-corner bottom-right">
            <div className="rank">{rankLabel(card.rank)}</div>
            <div className="suit">{suitSymbol(card.suit)}</div>
          </div>
        </div>
      ))}
    </div>
  </div>
);

export default function App() {
  const [modules, setModules] = useState([]);
  const [moduleId, setModuleId] = useState("");
  const [playerCount, setPlayerCount] = useState(4);
  const [session, setSession] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [acting, setActing] = useState(false);
  const [showNewSession, setShowNewSession] = useState(true);
  const [showMetaGroup, setShowMetaGroup] = useState(true);

  useEffect(() => {
    fetchJson("/modules")
      .then((data) => {
        setModules(data);
        if (data.length) setModuleId(data[0].id);
      })
      .catch((err) => setError(err.message));
  }, []);

  const selectedModule = useMemo(
    () => modules.find((m) => m.id === moduleId),
    [modules, moduleId]
  );

  const createSession = async () => {
    if (!moduleId) return;
    setLoading(true);
    setError("");
    try {
      const data = await fetchJson("/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          module_id: moduleId,
          player_count: Number(playerCount),
        }),
      });
      setSession(data);
      setShowNewSession(false);
      setShowMetaGroup(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const sendAction = async (action, amount = null) => {
    if (!session) return;
    setActing(true);
    setError("");
    try {
      const data = await fetchJson(`/sessions/${session.id}/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          player_index: session.payload.current_actor,
          action,
          amount,
        }),
      });
      setSession(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setActing(false);
    }
  };

  const renderActionButtons = () => {
    if (!session?.payload?.available_actions?.length) return null;
    return (
      <div className="actions">
        <div className="payload-title">Actions</div>
        <div className="action-row">
          {session.payload.available_actions.map((action) => {
            if (action === "bet" || action === "raise") {
              return session.payload.allowed_bets.map((bet) => (
                <button
                  key={`${action}-${bet}`}
                  onClick={() => sendAction(action, bet)}
                  disabled={acting}
                >
                  {action.toUpperCase()} ${bet.toFixed(2)}
                </button>
              ));
            }
            return (
              <button
                key={action}
                onClick={() => sendAction(action)}
                disabled={acting}
              >
                {action.toUpperCase()}
              </button>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="page">
      <header className="header">
        <div>
          <h1>Trainer UI</h1>
          <p>Iteration 3 — Minimal React shell</p>
        </div>
        <div className="status">
          <span>Backend: {API_BASE}</span>
        </div>
      </header>

      <main className="content">
        <section className="panel">
          <div className="panel-header">
            <h2>New Session</h2>
            <button
              className="toggle-button"
              onClick={() => setShowNewSession((prev) => !prev)}
            >
              {showNewSession ? "Hide" : "Show"}
            </button>
          </div>
          {showNewSession && (
            <>
              <div className="controls">
                <label>
                  Module
                  <select
                    value={moduleId}
                    onChange={(event) => setModuleId(event.target.value)}
                  >
                    {modules.map((module) => (
                      <option key={module.id} value={module.id}>
                        {module.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Players
                  <input
                    type="number"
                    min="2"
                    max="8"
                    value={playerCount}
                    onChange={(event) => setPlayerCount(event.target.value)}
                  />
                </label>
                <button onClick={createSession} disabled={loading || !moduleId}>
                  {loading ? "Creating..." : "Create Session"}
                </button>
              </div>
              {selectedModule && (
                <div className="module-info">
                  <div className="module-name">{selectedModule.name}</div>
                  <div className="module-desc">{selectedModule.description}</div>
                </div>
              )}
              {error && <div className="error">{error}</div>}
            </>
          )}
        </section>

        <section className="panel">
          <h2>Session State</h2>
          {!session && <div className="empty">No session yet.</div>}
          {session && (
            <div className="session">
              <div className="meta-group">
                <div className="meta-group-header">
                  <div className="meta-title">Session Meta</div>
                  <button
                    className="toggle-button"
                    onClick={() => setShowMetaGroup((prev) => !prev)}
                  >
                    {showMetaGroup ? "Hide" : "Show"}
                  </button>
                </div>
                {showMetaGroup && (
                  <div className="meta-grid">
                    <div className="meta-box">Session ID: {session.id}</div>
                    <div className="meta-box">Module: {session.module_id}</div>
                    <div className="meta-box">Players: {session.player_count}</div>
                    <div className="meta-box">Dealer: Player {session.payload.dealer_index + 1}</div>
                    <div className="meta-box">Current actor: Player {session.payload.current_actor + 1}</div>
                    <div className="meta-box">Ante: ${session.payload.ante.toFixed(2)}</div>
                  </div>
                )}
              </div>

              <div className="meta-grid">
                <div className="meta-box">Round: {session.payload.round_number}</div>
                <div className="meta-box">Pot: ${session.payload.pot_total.toFixed(2)}</div>
                <div className="meta-box">Bet: ${session.payload.current_bet.toFixed(2)}</div>
                <div className="meta-box">Raises: {session.payload.raises_this_round} / {session.payload.max_raises}</div>
                {session.payload.message && (
                  <div className="meta-box full">Message: {session.payload.message}</div>
                )}
              </div>
              {renderActionButtons()}
              <div className="payload">
                <div className="payload-title">Hands</div>
                <div className="hands-grid">
                  {session.payload.hands?.map((hand, index) => (
                    <div
                      key={index}
                      className={`hand-block${
                        session.payload.dealer_index === index ? " is-dealer" : ""
                      }${
                        session.payload.current_actor === index ? " is-actor" : ""
                      }`}
                    >
                      <Hand hand={hand} index={index} />
                      <div className="hand-meta">
                        {session.payload.hand_ranks?.length
                          ? session.payload.hand_ranks[index]?.label
                          : ""}
                        {session.payload.winners?.includes(index) && (
                          <span className="winner">Winner</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
