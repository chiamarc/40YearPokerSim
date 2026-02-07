from __future__ import annotations

import math
import time

from engine import (
    Card,
    build_wild_ranks,
    evaluate_high_five,
)

LOW_RANK_VALUES = {
    "A": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
}


def compute_iterations(player_count: int, revealed_pairs: int) -> int:
    unknown_pairs = 5 - revealed_pairs
    base = 200
    reveal_bonus = (5 - unknown_pairs) * 20
    player_penalty = (player_count - 2) * 20
    raw = base + reveal_bonus - player_penalty
    return min(300, max(80, round(raw)))


def _comb(n: int, k: int) -> int:
    if k < 0 or k > n:
        return 0
    return math.comb(n, k)


def _low_pair_distribution(counts: list[int], draw_count: int) -> dict[tuple[int, int], float]:
    total = sum(counts)
    if draw_count <= 0 or total <= 0 or draw_count > total:
        return {}

    denom = _comb(total, draw_count)
    if denom == 0:
        return {}

    distribution: dict[tuple[int, int], float] = {}

    for r1 in range(1, 14):
        c1 = counts[r1]
        if c1 == 0:
            continue
        lower = sum(counts[1:r1])

        # r1 == r2 (need at least two of r1, and no lower ranks drawn)
        ways_same = 0
        rest_same = total - lower - c1
        for k1 in range(2, min(c1, draw_count) + 1):
            ways_same += _comb(c1, k1) * _comb(rest_same, draw_count - k1)
        if ways_same:
            distribution[(r1, r1)] = distribution.get((r1, r1), 0) + ways_same / denom

        # r1 < r2
        for r2 in range(r1 + 1, 14):
            c2 = counts[r2]
            if c2 == 0:
                continue
            mid = sum(counts[r1 + 1 : r2])
            rest = total - lower - mid - c1 - c2
            if rest < 0:
                continue
            ways = 0
            max_k1 = min(c1, draw_count - 1)
            for k1 in range(1, max_k1 + 1):
                max_k2 = min(c2, draw_count - k1)
                for k2 in range(1, max_k2 + 1):
                    ways += _comb(c1, k1) * _comb(c2, k2) * _comb(rest, draw_count - k1 - k2)
            if ways:
                distribution[(r1, r2)] = distribution.get((r1, r2), 0) + ways / denom

    return distribution


def _low_strength_to_prob(values: list[int]) -> float:
    high = values[-1]
    total = sum(values)
    if high <= 6:
        base = 0.65
    elif high <= 7:
        base = 0.55
    elif high <= 8:
        base = 0.45
    elif high <= 9:
        base = 0.33
    elif high <= 10:
        base = 0.22
    else:
        base = 0.12

    base += max(0.0, min(0.18, (25 - total) / 100))

    distinct = len(set(values))
    if distinct == 4:
        base *= 0.6
    elif distinct == 3:
        base *= 0.3
    elif distinct == 2:
        base *= 0.15
    elif distinct <= 1:
        base *= 0.05

    return max(0.02, min(0.85, base))


def _estimate_low_odds(
    *,
    player_count: int,
    hero_hand: list[Card],
    community_pairs: list[list[Card]],
    revealed_pairs: int,
    natural_low_enabled: bool,
) -> float:
    hand_low_vals = sorted(LOW_RANK_VALUES[card.rank] for card in hero_hand)[:3]
    if len(set(hand_low_vals)) < 3:
        # Duplicate low ranks in hand reduce low potential.
        dup_factor = 0.35 if len(set(hand_low_vals)) == 2 else 0.15
    else:
        dup_factor = 1.0

    revealed_cards = [card for pair in community_pairs[:revealed_pairs] for card in pair]
    revealed_vals = sorted(LOW_RANK_VALUES[card.rank] for card in revealed_cards)

    counts = [0] * 14
    for i in range(1, 14):
        counts[i] = 4

    for card in hero_hand + revealed_cards:
        counts[LOW_RANK_VALUES[card.rank]] -= 1

    unknown_count = (5 - revealed_pairs) * 2
    if unknown_count <= 0:
        community_vals = (revealed_vals + [13, 13])[:2]
        low_values = sorted(hand_low_vals + community_vals)
        return _low_strength_to_prob(low_values) * dup_factor

    distribution = _low_pair_distribution(counts, unknown_count)
    if not distribution:
        return 0.0

    odds = 0.0
    for (r1, r2), prob in distribution.items():
        community_vals = sorted(revealed_vals + [r1, r2])[:2]
        low_values = sorted(hand_low_vals + community_vals)
        odds += prob * _low_strength_to_prob(low_values) * dup_factor

    if not natural_low_enabled:
        odds = min(0.9, odds * 1.15)

    player_penalty = 1.0 - ((player_count - 2) * 0.06)
    odds *= max(0.55, player_penalty)
    return max(0.02, min(0.85, odds))

def _heuristic_odds(
    *,
    player_count: int,
    hero_hand: list[Card],
    community_pairs: list[list[Card]],
    revealed_pairs: int,
    high_low_enabled: bool,
    natural_low_enabled: bool,
) -> dict:
    wild_ranks = build_wild_ranks(community_pairs, revealed_pairs)
    high_score = evaluate_high_five(hero_hand, wild_ranks)
    high_rank = max(0, min(9, high_score[0]))

    base_high = [0.10, 0.14, 0.18, 0.22, 0.27, 0.33, 0.40, 0.48, 0.58, 0.70][
        high_rank
    ]
    reveal_boost = 1.0 + (revealed_pairs * 0.03)
    player_penalty = 1.0 - ((player_count - 2) * 0.06)
    high = max(0.02, min(0.95, base_high * reveal_boost * player_penalty))

    low = 0.0
    if high_low_enabled:
        low = _estimate_low_odds(
            player_count=player_count,
            hero_hand=hero_hand,
            community_pairs=community_pairs,
            revealed_pairs=revealed_pairs,
            natural_low_enabled=natural_low_enabled,
        )
        low = max(0.02, min(0.85, low * reveal_boost))

    scoop = 0.0
    if high_low_enabled:
        scoop = max(0.0, min(0.5, high * low * 0.8))
        any_win = max(high, low)
    else:
        any_win = high

    return {
        "high": high,
        "low": low,
        "scoop": scoop,
        "any": any_win,
        "iterations_run": 0,
        "time_capped": False,
    }


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
    min_iterations: int | None = None,
    max_iterations: int | None = None,
) -> dict:
    start = time.time()
    odds = _heuristic_odds(
        player_count=player_count,
        hero_hand=hero_hand,
        community_pairs=community_pairs,
        revealed_pairs=revealed_pairs,
        high_low_enabled=high_low_enabled,
        natural_low_enabled=natural_low_enabled,
    )
    return {
        **odds,
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
        min_iterations=iterations,
        max_iterations=iterations,
    )
    return odds["any"] if high_low_enabled else odds["high"]
