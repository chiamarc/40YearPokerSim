const SUITS = ["♠", "♥", "♦", "♣"];
const RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"];
const RANK_VALUES = Object.fromEntries(RANKS.map((rank, index) => [rank, index + 2]));
const ACE_LOW_VALUE = 1;

const playerCountInput = document.getElementById("player-count");
const potInput = document.getElementById("pot-size");
const callCostInput = document.getElementById("call-cost");
const burnSelect = document.getElementById("burn-enabled");
const maxBetInput = document.getElementById("max-bet");
const maxRaisesInput = document.getElementById("max-raises");
const dealButton = document.getElementById("deal-game");
const nextRoundButton = document.getElementById("next-round");
const simulateButton = document.getElementById("simulate-odds");
const roundLabel = document.getElementById("round-label");
const wildLabel = document.getElementById("wild-label");
const playerHandEl = document.getElementById("player-hand");
const communityEl = document.getElementById("community");
const highWinEl = document.getElementById("high-win");
const lowWinEl = document.getElementById("low-win");
const scoopWinEl = document.getElementById("scoop-win");
const anyWinEl = document.getElementById("any-win");
const recommendationEl = document.getElementById("recommendation");
const evDetailEl = document.getElementById("ev-detail");
const bettingConstraintsEl = document.getElementById("betting-constraints");

let state = null;

const createDeck = () => {
  const deck = [];
  for (const suit of SUITS) {
    for (const rank of RANKS) {
      deck.push({ rank, suit, code: `${rank}${suit}` });
    }
  }
  return deck;
};

const shuffle = (deck) => {
  for (let i = deck.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [deck[i], deck[j]] = [deck[j], deck[i]];
  }
  return deck;
};

const dealCard = (deck) => deck.pop();

const renderCard = (card, isFaceDown = false, isWild = false) => {
  const cardEl = document.createElement("div");
  cardEl.className = `card${isFaceDown ? " face-down" : ""}${isWild ? " wild" : ""}`;
  if (!isFaceDown) {
    cardEl.innerHTML = `<div class="rank">${card.rank}</div><div class="suit">${card.suit}</div>`;
  }
  return cardEl;
};

const rankValue = (rank) => RANK_VALUES[rank];

const rankValueLow = (rank) => (rank === "A" ? ACE_LOW_VALUE : rankValue(rank));

const getCombinations = (array, size) => {
  const results = [];
  const dfs = (start, combo) => {
    if (combo.length === size) {
      results.push([...combo]);
      return;
    }
    for (let i = start; i < array.length; i += 1) {
      combo.push(array[i]);
      dfs(i + 1, combo);
      combo.pop();
    }
  };
  dfs(0, []);
  return results;
};

const isFlushPossible = (cards, wildRanks) => {
  const nonWild = cards.filter((card) => !wildRanks.has(card.rank));
  if (nonWild.length <= 1) {
    return true;
  }
  const suit = nonWild[0].suit;
  return nonWild.every((card) => card.suit === suit);
};

const getStraightHigh = (ranks) => {
  const unique = Array.from(new Set(ranks));
  if (unique.length !== 5) return null;
  const sorted = [...unique].sort((a, b) => a - b);
  const isWheel = sorted[0] === 2 && sorted[1] === 3 && sorted[2] === 4 && sorted[3] === 5 && sorted[4] === 14;
  if (isWheel) return 5;
  const isStraight = sorted[4] - sorted[0] === 4;
  return isStraight ? sorted[4] : null;
};

const compareHigh = (a, b) => {
  for (let i = 0; i < Math.max(a.length, b.length); i += 1) {
    if (a[i] !== b[i]) {
      return a[i] > b[i] ? 1 : -1;
    }
  }
  return 0;
};

const compareLow = (a, b) => {
  for (let i = 0; i < Math.max(a.length, b.length); i += 1) {
    if (a[i] !== b[i]) {
      return a[i] < b[i] ? 1 : -1;
    }
  }
  return 0;
};

const evaluateHighFive = (cards, wildRanks) => {
  const wildCards = cards.filter((card) => wildRanks.has(card.rank));
  const baseCards = cards.filter((card) => !wildRanks.has(card.rank));
  const wildCount = wildCards.length;
  const flushPossible = isFlushPossible(cards, wildRanks);
  const rankAssignments = [];

  const dfs = (depth, current) => {
    if (depth === wildCount) {
      rankAssignments.push([...current]);
      return;
    }
    for (const rank of RANKS) {
      current.push(rankValue(rank));
      dfs(depth + 1, current);
      current.pop();
    }
  };

  if (wildCount === 0) {
    rankAssignments.push([]);
  } else {
    dfs(0, []);
  }

  let best = null;

  for (const assignment of rankAssignments) {
    const ranks = baseCards.map((card) => rankValue(card.rank)).concat(assignment);
    const counts = new Map();
    for (const value of ranks) {
      counts.set(value, (counts.get(value) || 0) + 1);
    }
    const countList = [...counts.entries()].sort((a, b) => {
      if (b[1] !== a[1]) return b[1] - a[1];
      return b[0] - a[0];
    });
    const countValues = countList.map((entry) => entry[1]);
    const uniqueRanks = countList.map((entry) => entry[0]);

    const straightHigh = getStraightHigh(ranks);
    const isStraight = straightHigh !== null;
    const isFlush = flushPossible;

    let score = [];

    if (countValues[0] === 5) {
      score = [9, uniqueRanks[0]];
    } else if (isStraight && isFlush) {
      score = [8, straightHigh];
    } else if (countValues[0] === 4) {
      score = [7, uniqueRanks[0], uniqueRanks[1]];
    } else if (countValues[0] === 3 && countValues[1] === 2) {
      score = [6, uniqueRanks[0], uniqueRanks[1]];
    } else if (isFlush) {
      const sorted = [...ranks].sort((a, b) => b - a);
      score = [5, ...sorted];
    } else if (isStraight) {
      score = [4, straightHigh];
    } else if (countValues[0] === 3) {
      const kickers = uniqueRanks.slice(1).sort((a, b) => b - a);
      score = [3, uniqueRanks[0], ...kickers];
    } else if (countValues[0] === 2 && countValues[1] === 2) {
      const pairRanks = uniqueRanks.slice(0, 2).sort((a, b) => b - a);
      score = [2, pairRanks[0], pairRanks[1], uniqueRanks[2]];
    } else if (countValues[0] === 2) {
      const kickers = uniqueRanks.slice(1).sort((a, b) => b - a);
      score = [1, uniqueRanks[0], ...kickers];
    } else {
      const sorted = [...ranks].sort((a, b) => b - a);
      score = [0, ...sorted];
    }

    if (!best || compareHigh(score, best) > 0) {
      best = score;
    }
  }

  return best;
};

const evaluateLowFive = (cards) => {
  const ranks = cards.map((card) => rankValueLow(card.rank)).sort((a, b) => a - b);
  return ranks;
};

const bestHandForPlayer = (hand, communityCards, wildRanks) => {
  const handCombos = getCombinations(hand, 3);
  const communityCombos = getCombinations(communityCards, 2);
  let bestHigh = null;
  let bestLow = null;

  for (const handCombo of handCombos) {
    for (const communityCombo of communityCombos) {
      const cards = [...handCombo, ...communityCombo];
      const highScore = evaluateHighFive(cards, wildRanks);
      const lowScore = evaluateLowFive(cards);

      if (!bestHigh || compareHigh(highScore, bestHigh) > 0) {
        bestHigh = highScore;
      }
      if (!bestLow || compareLow(lowScore, bestLow) > 0) {
        bestLow = lowScore;
      }
    }
  }

  return { bestHigh, bestLow };
};

const buildCommunityGrid = (communityPairs, revealedPairs, wildRanks) => {
  communityEl.innerHTML = "";
  communityPairs.forEach((pair, index) => {
    const pairEl = document.createElement("div");
    pairEl.className = "community-pair";
    const isRevealed = index < revealedPairs;
    pair.forEach((card) => {
      const isWild = isRevealed && wildRanks.has(card.rank);
      pairEl.appendChild(renderCard(card, !isRevealed, isWild));
    });
    communityEl.appendChild(pairEl);
  });
};

const renderPlayerHand = (hand, wildRanks) => {
  playerHandEl.innerHTML = "";
  hand.forEach((card) => {
    const isWild = wildRanks.has(card.rank);
    playerHandEl.appendChild(renderCard(card, false, isWild));
  });
};

const buildWildRanks = (communityPairs, revealedPairs) => {
  const wildRanks = new Set();
  let lastFaceUp = null;

  for (let i = 0; i < revealedPairs; i += 1) {
    for (const card of communityPairs[i]) {
      if (lastFaceUp && lastFaceUp.rank === "Q") {
        wildRanks.add(card.rank);
      }
      lastFaceUp = card;
    }
  }

  if (lastFaceUp && lastFaceUp.rank === "Q") {
    wildRanks.add("Q");
  }

  return wildRanks;
};

const formatWildRanks = (wildRanks) => {
  if (!wildRanks.size) return "None";
  return [...wildRanks].join(", ");
};

const dealGame = () => {
  const deck = shuffle(createDeck());
  const playerCount = Number(playerCountInput.value || 4);
  const hands = [];

  for (let i = 0; i < playerCount; i += 1) {
    const hand = [];
    for (let j = 0; j < 5; j += 1) {
      hand.push(dealCard(deck));
    }
    hands.push(hand);
  }

  const communityPairs = [];
  for (let i = 0; i < 5; i += 1) {
    communityPairs.push([dealCard(deck), dealCard(deck)]);
  }

  state = {
    deck,
    hands,
    communityPairs,
    revealedPairs: 0,
  };

  updateBoard();
  simulateButton.disabled = false;
  nextRoundButton.disabled = false;
  recommendationEl.textContent = "Run the odds to see your best move.";
  evDetailEl.textContent = "";
  bettingConstraintsEl.textContent = "";
  resetTrainer();
};

const updateBoard = () => {
  if (!state) return;
  const wildRanks = buildWildRanks(state.communityPairs, state.revealedPairs);
  renderPlayerHand(state.hands[0], wildRanks);
  buildCommunityGrid(state.communityPairs, state.revealedPairs, wildRanks);
  roundLabel.textContent = String(state.revealedPairs);
  wildLabel.textContent = formatWildRanks(wildRanks);
};

const resetTrainer = () => {
  highWinEl.textContent = "-";
  lowWinEl.textContent = "-";
  scoopWinEl.textContent = "-";
  anyWinEl.textContent = "-";
};

const revealNextPair = () => {
  if (!state) return;
  if (state.revealedPairs < 5) {
    state.revealedPairs += 1;
  }
  if (state.revealedPairs >= 5) {
    nextRoundButton.disabled = true;
  }
  updateBoard();
};

const drawRemainingCards = (knownCards, count) => {
  const deck = shuffle(createDeck().filter((card) => !knownCards.has(card.code)));
  return deck.slice(0, count);
};

const simulateOdds = () => {
  if (!state) return;
  const playerCount = Number(playerCountInput.value || 4);
  const iterations = 400;
  const revealedPairs = state.revealedPairs;
  const knownCommunity = state.communityPairs.slice(0, revealedPairs).flat();
  const unknownPairs = 5 - revealedPairs;
  const heroHand = state.hands[0];
  const knownCards = new Set([...heroHand, ...knownCommunity].map((card) => card.code));

  let highWins = 0;
  let lowWins = 0;
  let scoopWins = 0;
  let anyWins = 0;

  for (let i = 0; i < iterations; i += 1) {
    const unknownCommunity = drawRemainingCards(knownCards, unknownPairs * 2);
    const communityPairs = [];
    for (let j = 0; j < revealedPairs; j += 1) {
      communityPairs.push(state.communityPairs[j]);
    }
    for (let j = 0; j < unknownPairs; j += 1) {
      communityPairs.push([unknownCommunity[j * 2], unknownCommunity[j * 2 + 1]]);
    }

    const updatedKnown = new Set([...knownCards, ...unknownCommunity].map((card) => card.code));
    const opponentHands = [];
    for (let p = 1; p < playerCount; p += 1) {
      const cards = drawRemainingCards(updatedKnown, 5);
      cards.forEach((card) => updatedKnown.add(card.code));
      opponentHands.push(cards);
    }

    const wildRanks = buildWildRanks(communityPairs, 5);
    const fullCommunity = communityPairs.flat();

    const heroBest = bestHandForPlayer(heroHand, fullCommunity, wildRanks);
    const opponents = opponentHands.map((hand) => bestHandForPlayer(hand, fullCommunity, wildRanks));

    let highWinners = [0];
    let lowWinners = [0];

    opponents.forEach((opponent, index) => {
      const playerIndex = index + 1;
      const highCompare = compareHigh(opponent.bestHigh, heroBest.bestHigh);
      if (highCompare > 0) {
        highWinners = [playerIndex];
      } else if (highCompare === 0) {
        highWinners.push(playerIndex);
      }

      const lowCompare = compareLow(opponent.bestLow, heroBest.bestLow);
      if (lowCompare > 0) {
        lowWinners = [playerIndex];
      } else if (lowCompare === 0) {
        lowWinners.push(playerIndex);
      }
    });

    const heroHigh = highWinners.includes(0);
    const heroLow = lowWinners.includes(0);

    if (heroHigh) highWins += 1;
    if (heroLow) lowWins += 1;
    if (heroHigh && heroLow) scoopWins += 1;
    if (heroHigh || heroLow) anyWins += 1;
  }

  const formatPercent = (value) => `${(value * 100).toFixed(1)}%`;

  const highRate = highWins / iterations;
  const lowRate = lowWins / iterations;
  const scoopRate = scoopWins / iterations;
  const anyRate = anyWins / iterations;

  highWinEl.textContent = formatPercent(highRate);
  lowWinEl.textContent = formatPercent(lowRate);
  scoopWinEl.textContent = formatPercent(scoopRate);
  anyWinEl.textContent = formatPercent(anyRate);

  updateRecommendation({ highRate, lowRate, scoopRate, anyRate });
};

const updateRecommendation = ({ highRate, lowRate, scoopRate, anyRate }) => {
  const pot = Number(potInput.value || 0);
  const callCost = Number(callCostInput.value || 0);
  const burnEnabled = burnSelect.value === "yes";
  const isFinalRound = state.revealedPairs >= 5;
  const maxBet = Number(maxBetInput?.value || 0.25);
  const maxRaises = Number(maxRaisesInput?.value || 3);

  const baseWin = anyRate;
  const splitWin = (highRate + lowRate) / 2;
  let expected = pot * splitWin - callCost;

  if (burnEnabled && isFinalRound) {
    const burnPenalty = Math.min(pot / 2, 2);
    expected -= (1 - baseWin) * burnPenalty;
  }

  const decision = expected >= 0 ? "Bet/Call" : "Check/Fold";
  recommendationEl.textContent = `${decision} (EV: $${expected.toFixed(2)})`;
  const burnNote = burnEnabled && isFinalRound ? " (burn applied on final round)" : "";
  evDetailEl.textContent = `EV uses split-pot odds and your call cost${burnNote}.`;
  bettingConstraintsEl.textContent = `Betting caps: max bet/raise $${maxBet.toFixed(2)}, up to ${maxRaises} raises per round. No all-ins.`;
};

const attachHandlers = () => {
  dealButton.addEventListener("click", dealGame);
  nextRoundButton.addEventListener("click", revealNextPair);
  simulateButton.addEventListener("click", simulateOdds);
};

attachHandlers();
