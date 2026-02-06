from __future__ import annotations

import time
from typing import Iterable

from engine import (
    Card,
    build_wild_ranks,
    best_hand_for_player,
    compare_high,
    compare_low,
    create_deck,
    shuffle,
)


def compute_iterations(player_count: int, revealed_pairs: int) -> int:
    unknown_pairs = 5 - revealed_pairs
    base = 200
    reveal_bonus = (5 - unknown_pairs) * 20
    player_penalty = (player_count - 2) * 20
    raw = base + reveal_bonus - player_penalty
    return min(300, max(80, round(raw)))


def draw_remaining_cards(known_cards: set[str], count: int) -> list[Card]:
    deck = [card for card in create_deck() if card.code not in known_cards]
    shuffle(deck)
    return deck[:count]


def simulate_odds(
    *,
    player_count: int,
    hero_hand: list[Card],
    community_pairs: list[list[Card]],
    revealed_pairs: int,
    iterations: int,
    max_time_ms: int,
    high_low_enabled: bool,
    natural_low_enabled: bool,
    hero_index: int = 0,
) -> dict:
    known_community = [card for pair in community_pairs[:revealed_pairs] for card in pair]
    unknown_pairs = 5 - revealed_pairs
    known_cards = {card.code for card in hero_hand + known_community}

    high_wins = 0
    low_wins = 0
    scoop_wins = 0
    any_wins = 0
    iterations_run = 0
    time_capped = False
    start = time.time()

    for i in range(iterations):
        if max_time_ms and i > 0 and (time.time() - start) * 1000 >= max_time_ms:
            time_capped = True
            break

        unknown_community = draw_remaining_cards(known_cards, unknown_pairs * 2)
        full_pairs: list[list[Card]] = []
        for j in range(revealed_pairs):
            full_pairs.append(community_pairs[j])
        for j in range(unknown_pairs):
            full_pairs.append([unknown_community[j * 2], unknown_community[j * 2 + 1]])

        updated_known = set(known_cards)
        updated_known.update(card.code for card in unknown_community)

        all_hands: list[list[Card]] = [hero_hand]
        for _ in range(1, player_count):
            cards = draw_remaining_cards(updated_known, 5)
            for card in cards:
                updated_known.add(card.code)
            all_hands.append(cards)

        wild_ranks = build_wild_ranks(full_pairs, 5)
        full_community = [card for pair in full_pairs for card in pair]

        bests = [
            best_hand_for_player(hand, full_community, wild_ranks, natural_low_enabled)
            for hand in all_hands
        ]

        hero_best = bests[hero_index]

        high_winners = [hero_index]
        low_winners = [hero_index]

        for idx, opponent in enumerate(bests):
            if idx == hero_index:
                continue
            high_compare = compare_high(opponent["best_high"], hero_best["best_high"])
            if high_compare > 0:
                high_winners = [idx]
            elif high_compare == 0:
                high_winners.append(idx)

            if high_low_enabled:
                low_compare = compare_low(opponent["best_low"], hero_best["best_low"])
                if low_compare > 0:
                    low_winners = [idx]
                elif low_compare == 0:
                    low_winners.append(idx)

        hero_high = hero_index in high_winners
        hero_low = hero_index in low_winners if high_low_enabled else False

        if hero_high:
            high_wins += 1
        if hero_low:
            low_wins += 1
        if hero_high and hero_low:
            scoop_wins += 1
        if hero_high or hero_low:
            any_wins += 1
        iterations_run += 1

    denom = iterations_run or 1
    return {
        "high": high_wins / denom,
        "low": low_wins / denom if high_low_enabled else 0,
        "scoop": scoop_wins / denom if high_low_enabled else 0,
        "any": any_wins / denom if high_low_enabled else high_wins / denom,
        "iterations_run": iterations_run,
        "time_capped": time_capped,
        "elapsed_ms": int((time.time() - start) * 1000),
    }


def estimate_player_odds(
    *,
    player_count: int,
    hero_hand: list[Card],
    community_pairs: list[list[Card]],
    revealed_pairs: int,
    high_low_enabled: bool,
    natural_low_enabled: bool,
    iterations: int = 60,
) -> float:
    odds = simulate_odds(
        player_count=player_count,
        hero_hand=hero_hand,
        community_pairs=community_pairs,
        revealed_pairs=revealed_pairs,
        iterations=iterations,
        max_time_ms=3000,
        high_low_enabled=high_low_enabled,
        natural_low_enabled=natural_low_enabled,
    )
    return odds["any"] if high_low_enabled else odds["high"]
