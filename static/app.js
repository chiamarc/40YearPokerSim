const state = {
  data: null,
};

const el = (id) => document.getElementById(id);

const playerCountInput = el("player-count");
const highLowInput = el("high-low");
const naturalLowInput = el("natural-low");
const newGameButton = el("new-game");
const revealButton = el("reveal-next");
const simulateButton = el("simulate-odds");
const allActionButton = el("all-action");
const playerHandEl = el("player-hand");
const communityEl = el("community");
const wildLabel = el("wild-label");
const roundLabel = el("round-label");
const dealerLabel = el("dealer-label");
const actorLabel = el("actor-label");
const opponentActionsEl = el("opponent-actions");
const potTotalEl = el("pot-total");
const chipStackEl = el("chip-stack");
const messageEl = el("game-message");
const highWinEl = el("high-win");
const lowWinEl = el("low-win");
const scoopWinEl = el("scoop-win");
const anyWinEl = el("any-win");
const recommendationEl = el("recommendation");
const evDetailEl = el("ev-detail");
const bettingConstraintsEl = el("betting-constraints");
const callButton = el("call-btn");
const foldButton = el("fold-btn");
const betButtons = Array.from(document.querySelectorAll(".bet-btn"));

const postJson = async (url, payload) => {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  const data = await res.json();
  if (!res.ok) throw data;
  return data;
};

const renderCard = (card, faceDown = false, isWild = false) => {
  const cardEl = document.createElement("div");
  cardEl.className = `card${faceDown ? " face-down" : ""}${isWild ? " wild" : ""}`;
  if (!faceDown) {
    cardEl.innerHTML = `<div class="rank">${card.rank}</div><div class="suit">${card.suit}</div>`;
  }
  return cardEl;
};

const renderCommunity = (pairs, revealedPairs, wildRanks) => {
  communityEl.innerHTML = "";
  pairs.forEach((pair, index) => {
    const pairEl = document.createElement("div");
    pairEl.className = "pair";
    const revealed = index < revealedPairs;
    pair.forEach((card) => {
      const isWild = revealed && wildRanks.includes(card.rank);
      pairEl.appendChild(renderCard(card, !revealed, isWild));
    });
    communityEl.appendChild(pairEl);
  });
};

const renderHand = (hand, wildRanks) => {
  playerHandEl.innerHTML = "";
  hand.forEach((card) => {
    const isWild = wildRanks.includes(card.rank);
    playerHandEl.appendChild(renderCard(card, false, isWild));
  });
};

const formatPercent = (value) => `${(value * 100).toFixed(1)}%`;

const renderChips = (pot) => {
  chipStackEl.innerHTML = "";
  const chips = [
    { value: 1.0, cls: "green" },
    { value: 0.25, cls: "blue" },
    { value: 0.1, cls: "red" },
    { value: 0.05, cls: "white" },
  ];
  let remaining = Math.round(pot * 100);
  chips.forEach((chip) => {
    const cents = Math.round(chip.value * 100);
    const count = Math.floor(remaining / cents);
    if (count > 0) {
      for (let i = 0; i < count; i += 1) {
        const chipEl = document.createElement("div");
        chipEl.className = `chip ${chip.cls}`;
        chipEl.textContent = `${Math.round(chip.value * 100)}¢`;
        chipStackEl.appendChild(chipEl);
      }
      remaining -= count * cents;
    }
  });
};

const updateSettingsLock = (locked) => {
  [playerCountInput, highLowInput, naturalLowInput].forEach((input) => {
    input.disabled = locked;
  });
};

const updateTrainerEmpty = () => {
  highWinEl.textContent = "-";
  lowWinEl.textContent = "-";
  scoopWinEl.textContent = "-";
  anyWinEl.textContent = "-";
  recommendationEl.textContent = "Deal a hand to begin.";
  evDetailEl.textContent = "";
  bettingConstraintsEl.textContent = "";
};

const updateActionButtons = (data) => {
  const heroIndex = data.hero_index;
  const actor = data.current_actor;
  const isHeroTurn = actor === heroIndex && !data.game_over && !data.folded[heroIndex];
  betButtons.forEach((btn) => (btn.disabled = !isHeroTurn));
  callButton.disabled = !isHeroTurn;
  foldButton.disabled = !isHeroTurn;

  revealButton.disabled = data.revealed_pairs >= 5 || data.game_over;
  simulateButton.disabled = data.game_over;
  allActionButton.disabled = isHeroTurn || data.game_over;
};

const renderOpponents = (data) => {
  opponentActionsEl.innerHTML = "";
  for (let i = 0; i < data.player_count; i += 1) {
    if (i === data.hero_index) continue;
    const card = document.createElement("div");
    card.className = "opponent-card";
    const label = document.createElement("div");
    label.textContent = `Player ${i + 1}`;
    const actionBtn = document.createElement("button");
    const lastAction = data.last_action[i] || "Action";
    actionBtn.textContent = lastAction.startsWith("Action") ? lastAction : `Action: ${lastAction}`;
    actionBtn.disabled = data.current_actor !== i || data.game_over || data.folded[i];
    actionBtn.addEventListener("click", async () => {
      await triggerOpponentAction(i);
    });
    card.appendChild(label);
    card.appendChild(actionBtn);
    opponentActionsEl.appendChild(card);
  }
};

const renderTrainer = (data) => {
  if (!data.odds) return;
  highWinEl.textContent = formatPercent(data.odds.high);
  lowWinEl.textContent = formatPercent(data.odds.low);
  scoopWinEl.textContent = formatPercent(data.odds.scoop);
  anyWinEl.textContent = formatPercent(data.odds.any);
  recommendationEl.textContent = `${data.recommendation.decision} (EV: $${data.recommendation.ev.toFixed(2)})`;
  evDetailEl.textContent = data.recommendation.detail;
  bettingConstraintsEl.textContent = data.recommendation.betting_constraints;
};

const renderState = (data) => {
  state.data = data;
  updateSettingsLock(true);
  renderHand(data.hands[data.hero_index], data.wild_ranks);
  renderCommunity(data.community_pairs, data.revealed_pairs, data.wild_ranks);
  renderOpponents(data);
  renderChips(data.pot_total);
  wildLabel.textContent = data.wild_ranks.length ? data.wild_ranks.join(", ") : "None";
  roundLabel.textContent = data.round_number;
  dealerLabel.textContent = data.dealer_index + 1;
  actorLabel.textContent = data.game_over ? "-" : data.current_actor + 1;
  potTotalEl.textContent = data.pot_total.toFixed(2);
  messageEl.textContent = data.message || "";
  updateActionButtons(data);
};

const triggerOpponentAction = async (playerIndex) => {
  if (!state.data) return;
  const data = await postJson("/opponent_action", { player_index: playerIndex });
  renderState(data);
};

const handleNewGame = async () => {
  const payload = {
    player_count: Number(playerCountInput.value || 4),
    high_low: highLowInput.checked,
    natural_low: naturalLowInput.checked,
  };
  const data = await postJson("/new_game", payload);
  renderState(data);
  updateSettingsLock(true);
  updateTrainerEmpty();
};

const handleReveal = async () => {
  if (!state.data) return;
  const data = await postJson("/reveal_next", {});
  renderState(data);
};

const handleSimulate = async () => {
  if (!state.data) return;
  const data = await postJson("/simulate", {});
  renderState(data);
  renderTrainer(data);
};

const handleAllAction = async () => {
  const data = await postJson("/all_action", {});
  renderState(data);
};

const handleBet = async (amount) => {
  if (!state.data) return;
  const data = await postJson("/action", {
    player_index: state.data.hero_index,
    action: "raise",
    amount,
  });
  renderState(data);
};

const handleCall = async () => {
  if (!state.data) return;
  const data = await postJson("/action", {
    player_index: state.data.hero_index,
    action: "call",
  });
  renderState(data);
};

const handleFold = async () => {
  if (!state.data) return;
  const data = await postJson("/action", {
    player_index: state.data.hero_index,
    action: "fold",
  });
  renderState(data);
};

const setupToggles = () => {
  document.querySelectorAll(".panel-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.dataset.target);
      target.classList.toggle("hidden");
    });
  });
};

newGameButton.addEventListener("click", handleNewGame);
revealButton.addEventListener("click", handleReveal);
simulateButton.addEventListener("click", handleSimulate);
allActionButton.addEventListener("click", handleAllAction);
callButton.addEventListener("click", handleCall);
foldButton.addEventListener("click", handleFold);
betButtons.forEach((btn) => {
  btn.addEventListener("click", () => handleBet(Number(btn.dataset.amount)));
});

setupToggles();
updateTrainerEmpty();
