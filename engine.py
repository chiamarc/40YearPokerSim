from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import random
from typing import Iterable

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
RANK_VALUES = {rank: index + 2 for index, rank in enumerate(RANKS)}
ACE_LOW_VALUE = 1


@dataclass(frozen=True)
class Card:
    rank: str
    suit: str
    code: str


def create_deck() -> list[Card]:
    return [Card(rank, suit, f"{rank}{suit}") for suit in SUITS for rank in RANKS]


def shuffle(deck: list[Card]) -> list[Card]:
    random.shuffle(deck)
    return deck


def rank_value(rank: str) -> int:
    return RANK_VALUES[rank]


def rank_value_low(rank: str) -> int:
    return ACE_LOW_VALUE if rank == "A" else rank_value(rank)


def is_flush_possible(cards: Iterable[Card], wild_ranks: set[str]) -> bool:
    non_wild = [card for card in cards if card.rank not in wild_ranks]
    if len(non_wild) <= 1:
        return True
    suit = non_wild[0].suit
    return all(card.suit == suit for card in non_wild)


def get_straight_high(ranks: list[int]) -> int | None:
    unique = sorted(set(ranks))
    if len(unique) != 5:
        return None
    if unique == [2, 3, 4, 5, 14]:
        return 5
    if unique[-1] - unique[0] == 4:
        return unique[-1]
    return None


def compare_high(a: list[int], b: list[int]) -> int:
    for i in range(max(len(a), len(b))):
        if a[i] != b[i]:
            return 1 if a[i] > b[i] else -1
    return 0


def compare_low(a: list[int], b: list[int]) -> int:
    for i in range(max(len(a), len(b))):
        if a[i] != b[i]:
            return 1 if a[i] < b[i] else -1
    return 0


def evaluate_high_five(cards: list[Card], wild_ranks: set[str]) -> list[int]:
    wild_cards = [card for card in cards if card.rank in wild_ranks]
    base_cards = [card for card in cards if card.rank not in wild_ranks]
    wild_count = len(wild_cards)
    flush_possible = is_flush_possible(cards, wild_ranks)

    rank_assignments: list[list[int]] = [[]]
    if wild_count:
        rank_assignments = []

        def dfs(depth: int, current: list[int]) -> None:
            if depth == wild_count:
                rank_assignments.append(current[:])
                return
            for rank in RANKS:
                current.append(rank_value(rank))
                dfs(depth + 1, current)
                current.pop()

        dfs(0, [])

    best: list[int] | None = None

    for assignment in rank_assignments:
        ranks = [rank_value(card.rank) for card in base_cards] + assignment
        counts: dict[int, int] = {}
        for value in ranks:
            counts[value] = counts.get(value, 0) + 1
        count_list = sorted(counts.items(), key=lambda x: (-x[1], -x[0]))
        count_values = [entry[1] for entry in count_list]
        unique_ranks = [entry[0] for entry in count_list]

        straight_high = get_straight_high(ranks)
        is_straight = straight_high is not None
        is_flush = flush_possible

        if count_values[0] == 5:
            score = [9, unique_ranks[0]]
        elif is_straight and is_flush:
            score = [8, straight_high]
        elif count_values[0] == 4:
            score = [7, unique_ranks[0], unique_ranks[1]]
        elif count_values[0] == 3 and count_values[1] == 2:
            score = [6, unique_ranks[0], unique_ranks[1]]
        elif is_flush:
            score = [5, *sorted(ranks, reverse=True)]
        elif is_straight:
            score = [4, straight_high]
        elif count_values[0] == 3:
            kickers = sorted(unique_ranks[1:], reverse=True)
            score = [3, unique_ranks[0], *kickers]
        elif count_values[0] == 2 and count_values[1] == 2:
            pair_ranks = sorted(unique_ranks[:2], reverse=True)
            score = [2, pair_ranks[0], pair_ranks[1], unique_ranks[2]]
        elif count_values[0] == 2:
            kickers = sorted(unique_ranks[1:], reverse=True)
            score = [1, unique_ranks[0], *kickers]
        else:
            score = [0, *sorted(ranks, reverse=True)]

        if best is None or compare_high(score, best) > 0:
            best = score

    return best or [0]


def evaluate_low_five(cards: list[Card], wild_ranks: set[str], natural_low_enabled: bool) -> list[int]:
    if natural_low_enabled:
        return sorted(rank_value_low(card.rank) for card in cards)

    wild_cards = [card for card in cards if card.rank in wild_ranks]
    base_cards = [card for card in cards if card.rank not in wild_ranks]
    wild_count = len(wild_cards)
    base_values = [rank_value_low(card.rank) for card in base_cards]
    low_values = list(range(1, 14))

    assignments: list[list[int]] = [[]]
    if wild_count:
        assignments = []

        def dfs(depth: int, current: list[int]) -> None:
            if depth == wild_count:
                assignments.append(current[:])
                return
            for value in low_values:
                current.append(value)
                dfs(depth + 1, current)
                current.pop()

        dfs(0, [])

    best: list[int] | None = None
    for assignment in assignments:
        ranks = sorted(base_values + assignment)
        if best is None or compare_low(ranks, best) > 0:
            best = ranks
    return best or sorted(base_values)


def best_hand_for_player(
    hand: list[Card],
    community_cards: list[Card],
    wild_ranks: set[str],
    natural_low_enabled: bool,
) -> dict[str, list[int]]:
    best_high: list[int] | None = None
    best_low: list[int] | None = None
    for hand_combo in combinations(hand, 3):
        for community_combo in combinations(community_cards, 2):
            cards = list(hand_combo) + list(community_combo)
            high_score = evaluate_high_five(cards, wild_ranks)
            low_score = evaluate_low_five(cards, wild_ranks, natural_low_enabled)
            if best_high is None or compare_high(high_score, best_high) > 0:
                best_high = high_score
            if best_low is None or compare_low(low_score, best_low) > 0:
                best_low = low_score

    return {"best_high": best_high or [0], "best_low": best_low or [0]}


def build_wild_ranks(community_pairs: list[list[Card]], revealed_pairs: int) -> set[str]:
    wild_ranks: set[str] = set()
    last_face_up: Card | None = None

    for i in range(revealed_pairs):
        for card in community_pairs[i]:
            if last_face_up and last_face_up.rank == "Q":
                wild_ranks.add(card.rank)
            last_face_up = card

    if last_face_up and last_face_up.rank == "Q":
        wild_ranks.add("Q")

    return wild_ranks


def card_to_dict(card: Card) -> dict:
    return {"rank": card.rank, "suit": card.suit, "code": card.code}


def card_from_dict(data: dict) -> Card:
    return Card(rank=data["rank"], suit=data["suit"], code=data["code"])
