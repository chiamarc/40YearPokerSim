from __future__ import annotations

import random
from dataclasses import dataclass


SUITS = ["S", "H", "D", "C"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
ALLOWED_BETS = [0.05, 0.1, 0.25, 1.0]
ANTE_PER_PLAYER = 0.05
ANTE_PAYER = "dealer_total_once_per_game"
RANK_VALUES = {rank: index + 2 for index, rank in enumerate(RANKS)}
MAX_RAISES = 2


def configure(config: dict) -> None:
    global ALLOWED_BETS, ANTE_PER_PLAYER, ANTE_PAYER, MAX_RAISES
    rules = config.get("betting_rules", {}) if config else {}
    denominations = rules.get("denominations", ALLOWED_BETS)
    max_bet = rules.get("max_bet")
    if max_bet is not None:
        ALLOWED_BETS = [d for d in denominations if d <= max_bet]
    else:
        ALLOWED_BETS = denominations
    MAX_RAISES = int(rules.get("max_raises", MAX_RAISES))
    ANTE_PER_PLAYER = float(rules.get("ante_per_player", ANTE_PER_PLAYER))
    ANTE_PAYER = rules.get("ante_payer", ANTE_PAYER)


@dataclass
class Card:
    rank: str
    suit: str

    def to_dict(self) -> dict:
        return {"rank": self.rank, "suit": self.suit, "code": f"{self.rank}{self.suit}"}


def _deck() -> list[Card]:
    return [Card(rank, suit) for suit in SUITS for rank in RANKS]


def init_state(player_count: int) -> dict:
    return _deal_new_hand(player_count, round_number=1, dealer_index=0)


def _deal_new_hand(player_count: int, round_number: int, dealer_index: int) -> dict:
    deck = _deck()
    random.shuffle(deck)
    hands: list[list[Card]] = []
    for _ in range(player_count):
        hand = [deck.pop() for _ in range(5)]
        hands.append(hand)

    start_index = (dealer_index + 1) % player_count
    pot_total = round(player_count * ANTE_PER_PLAYER, 2)
    contrib = [0.0 for _ in range(player_count)]
    if ANTE_PAYER == "dealer_total_once_per_game":
        contrib[dealer_index] = pot_total

    return {
        "hands": hands,
        "deck_count": len(deck),
        "phase": "betting",
        "current_actor": start_index,
        "dealer_index": dealer_index,
        "start_index": start_index,
        "folded": [False for _ in range(player_count)],
        "last_action": ["" for _ in range(player_count)],
        "pot_total": pot_total,
        "contrib_this_round": contrib,
        "current_bet": 0.0,
        "raises_this_round": 0,
        "pending_players": list(range(player_count)),
        "round_number": round_number,
        "message": "",
    }


def render_payload(state: dict, player_count: int) -> dict:
    return {
        "phase": state["phase"],
        "deck_count": state["deck_count"],
        "hands": [
            [card.to_dict() for card in sorted(hand, key=lambda c: RANK_VALUES[c.rank])]
            for hand in state["hands"]
        ],
        "player_count": player_count,
        "current_actor": state["current_actor"],
        "dealer_index": state["dealer_index"],
        "start_index": state["start_index"],
        "folded": state["folded"],
        "last_action": state["last_action"],
        "pot_total": state["pot_total"],
        "contrib_this_round": state["contrib_this_round"],
        "current_bet": state["current_bet"],
        "raises_this_round": state["raises_this_round"],
        "pending_players": state["pending_players"],
        "round_number": state["round_number"],
        "message": state["message"],
        "allowed_bets": ALLOWED_BETS,
        "max_raises": MAX_RAISES,
        "ante_per_player": ANTE_PER_PLAYER,
        "ante_payer": ANTE_PAYER,
        "winners": state.get("winners", []),
        "hand_ranks": state.get("hand_ranks", []),
        "available_actions": available_actions(state, player_count),
    }


def _active_players(state: dict) -> list[int]:
    return [i for i, folded in enumerate(state["folded"]) if not folded]


def _next_pending_player(state: dict, start_index: int) -> int | None:
    if not state["pending_players"]:
        return None
    player_count = len(state["folded"])
    for offset in range(1, player_count + 1):
        idx = (start_index + offset) % player_count
        if idx in state["pending_players"] and not state["folded"][idx]:
            return idx
    return None


def available_actions(state: dict, player_count: int) -> list[str]:
    if state["phase"] == "showdown":
        return ["next_hand"]
    if state["phase"] != "betting":
        return []
    actor = state["current_actor"]
    if state["folded"][actor]:
        return []

    actions = ["fold"]
    if state["current_bet"] == 0:
        actions.append("check")
        if state["raises_this_round"] < MAX_RAISES:
            actions.append("bet")
    else:
        actions.append("call")
        if state["raises_this_round"] < MAX_RAISES:
            actions.append("raise")
    return actions


def apply_action(state: dict, action: dict, player_count: int) -> dict:
    if state["phase"] == "showdown" and action.get("action") == "next_hand":
        dealer = (state["dealer_index"] + 1) % player_count
        return _deal_new_hand(
            player_count,
            round_number=state["round_number"] + 1,
            dealer_index=dealer,
        )
    if state["phase"] != "betting":
        return state

    player_index = int(action.get("player_index", -1))
    action_type = action.get("action", "")
    amount = float(action.get("amount", 0.0) or 0.0)

    if player_index != state["current_actor"]:
        state["message"] = "Not this player's turn."
        return state
    if state["folded"][player_index]:
        state["message"] = "Player already folded."
        return state

    if action_type == "fold":
        state["folded"][player_index] = True
        state["last_action"][player_index] = "Fold"
        if player_index in state["pending_players"]:
            state["pending_players"].remove(player_index)
    elif action_type in {"check", "call"}:
        call_amount = max(state["current_bet"] - state["contrib_this_round"][player_index], 0.0)
        state["pot_total"] += call_amount
        state["contrib_this_round"][player_index] += call_amount
        state["last_action"][player_index] = "Check" if call_amount == 0 else f"Call {call_amount:.0f}"
        if player_index in state["pending_players"]:
            state["pending_players"].remove(player_index)
    elif action_type in {"bet", "raise"}:
        if amount not in ALLOWED_BETS:
            state["message"] = "Invalid bet amount."
            return state
        if state["raises_this_round"] >= MAX_RAISES:
            state["message"] = "Max raises reached."
            return state
        new_bet = state["current_bet"] + amount if state["current_bet"] else amount
        raise_amount = max(new_bet - state["contrib_this_round"][player_index], 0.0)
        state["pot_total"] += raise_amount
        state["contrib_this_round"][player_index] = new_bet
        state["current_bet"] = new_bet
        if action_type == "raise":
            state["raises_this_round"] += 1
        state["last_action"][player_index] = f"{action_type.capitalize()} {amount:.0f}"
        state["pending_players"] = [i for i in _active_players(state) if i != player_index]
    else:
        state["message"] = "Invalid action."
        return state

    active_players = _active_players(state)
    if len(active_players) <= 1:
        winners = active_players
        state["phase"] = "showdown"
        state["message"] = "Hand ended by folds."
        state["winners"] = winners
        state["hand_ranks"] = _evaluate_all_hands(state["hands"], state["folded"])
        state["pending_players"] = []
        return state

    if not state["pending_players"]:
        state["phase"] = "showdown"
        state["message"] = "Betting complete."
        winners, ranks = _determine_winners(state["hands"], state["folded"])
        state["winners"] = winners
        state["hand_ranks"] = ranks
        return state

    next_actor = _next_pending_player(state, player_index)
    state["current_actor"] = next_actor if next_actor is not None else state["current_actor"]
    return state


def _rank_value(rank: str) -> int:
    return RANK_VALUES[rank]


def _evaluate_hand(hand: list[Card]) -> tuple[int, list[int], str]:
    ranks = [_rank_value(card.rank) for card in hand]
    ranks_sorted = sorted(ranks, reverse=True)
    counts: dict[int, int] = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
    count_list = sorted(counts.items(), key=lambda x: (-x[1], -x[0]))
    count_values = [c for _, c in count_list]
    unique_ranks = [r for r, _ in count_list]

    is_flush = len({card.suit for card in hand}) == 1
    unique_sorted = sorted(set(ranks))
    is_straight = len(unique_sorted) == 5 and unique_sorted[-1] - unique_sorted[0] == 4
    is_wheel = unique_sorted == [2, 3, 4, 5, 14]
    if is_wheel:
        is_straight = True
        straight_high = 5
    else:
        straight_high = unique_sorted[-1] if is_straight else 0

    if is_straight and is_flush:
        return (8, [straight_high], "Straight Flush")
    if count_values[0] == 4:
        return (7, [unique_ranks[0], unique_ranks[1]], "Four of a Kind")
    if count_values[0] == 3 and count_values[1] == 2:
        return (6, [unique_ranks[0], unique_ranks[1]], "Full House")
    if is_flush:
        return (5, ranks_sorted, "Flush")
    if is_straight:
        return (4, [straight_high], "Straight")
    if count_values[0] == 3:
        kickers = sorted(unique_ranks[1:], reverse=True)
        return (3, [unique_ranks[0], *kickers], "Three of a Kind")
    if count_values[0] == 2 and count_values[1] == 2:
        pair_ranks = sorted(unique_ranks[:2], reverse=True)
        return (2, [pair_ranks[0], pair_ranks[1], unique_ranks[2]], "Two Pair")
    if count_values[0] == 2:
        kickers = sorted(unique_ranks[1:], reverse=True)
        return (1, [unique_ranks[0], *kickers], "One Pair")
    return (0, ranks_sorted, "High Card")


def _evaluate_all_hands(hands: list[list[Card]], folded: list[bool]) -> list[dict]:
    results: list[dict] = []
    for idx, hand in enumerate(hands):
        if folded[idx]:
            results.append({"player": idx, "rank": None, "label": "Folded"})
        else:
            rank = _evaluate_hand(hand)
            results.append({"player": idx, "rank": rank[:2], "label": rank[2]})
    return results


def _determine_winners(hands: list[list[Card]], folded: list[bool]) -> tuple[list[int], list[dict]]:
    best: tuple[int, list[int]] | None = None
    winners: list[int] = []
    results: list[dict] = []
    for idx, hand in enumerate(hands):
        if folded[idx]:
            results.append({"player": idx, "rank": None, "label": "Folded"})
            continue
        category, tiebreakers, label = _evaluate_hand(hand)
        results.append({"player": idx, "rank": [category, tiebreakers], "label": label})
        score = (category, tiebreakers)
        if best is None or score > best:
            best = score
            winners = [idx]
        elif score == best:
            winners.append(idx)
    return winners, results
