from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from engine import (
    Card,
    build_wild_ranks,
    card_to_dict,
    create_deck,
    shuffle,
    best_hand_for_player,
    compare_high,
    compare_low,
)
from sim import compute_iterations, simulate_odds, estimate_player_odds

ALLOWED_BETS = [0.05, 0.10, 0.15, 0.20, 0.25]
ANTE = 0.05
MAX_RAISES = 3
HERO_INDEX = 0

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(ROOT, "static")
INDEX_PATH = os.path.join(ROOT, "index.html")


@dataclass
class GameState:
    player_count: int
    dealer_index: int = 0
    start_index: int = 1
    current_actor: int = 1
    hands: list[list[Card]] = field(default_factory=list)
    community_pairs: list[list[Card]] = field(default_factory=list)
    revealed_pairs: int = 0
    folded: list[bool] = field(default_factory=list)
    last_action: list[str] = field(default_factory=list)
    pot_total: float = 0.0
    contrib_this_round: list[float] = field(default_factory=list)
    current_bet: float = 0.0
    raises_this_round: int = 0
    round_number: int = 1
    high_low_enabled: bool = True
    natural_low_enabled: bool = True
    pending_players: list[int] = field(default_factory=list)
    game_over: bool = False
    message: str = ""


STATE: GameState | None = None


def _active_players(state: GameState) -> list[int]:
    return [i for i in range(state.player_count) if not state.folded[i]]


def _next_pending_player(state: GameState, start_index: int) -> int | None:
    if not state.pending_players:
        return None
    for offset in range(1, state.player_count + 1):
        idx = (start_index + offset) % state.player_count
        if idx in state.pending_players and not state.folded[idx]:
            return idx
    return None


def _reset_betting_round(state: GameState) -> None:
    state.current_bet = 0.0
    state.contrib_this_round = [0.0 for _ in range(state.player_count)]
    state.raises_this_round = 0
    state.pending_players = _active_players(state)
    state.current_actor = state.start_index


def _deal_new_hand(state: GameState) -> None:
    deck = shuffle(create_deck())
    state.hands = []
    for _ in range(state.player_count):
        hand = [deck.pop() for _ in range(5)]
        state.hands.append(hand)

    state.community_pairs = []
    for _ in range(5):
        state.community_pairs.append([deck.pop(), deck.pop()])

    state.revealed_pairs = 0
    state.folded = [False for _ in range(state.player_count)]
    state.last_action = ["" for _ in range(state.player_count)]
    state.pot_total = round(ANTE * state.player_count, 2)
    _reset_betting_round(state)


def _start_next_round(state: GameState) -> None:
    state.round_number += 1
    state.start_index = (state.start_index + 1) % state.player_count
    _deal_new_hand(state)


def _round_started_with_last_left(state: GameState) -> bool:
    last_left = (state.dealer_index - 1) % state.player_count
    return state.start_index == last_left


def _end_game(state: GameState, message: str) -> None:
    state.game_over = True
    state.message = message
    state.pending_players = []


def _showdown(state: GameState) -> tuple[list[int], list[int], bool]:
    wild_ranks = build_wild_ranks(state.community_pairs, 5)
    community = [card for pair in state.community_pairs for card in pair]
    active = _active_players(state)

    bests = {
        i: best_hand_for_player(
            state.hands[i],
            community,
            wild_ranks,
            state.natural_low_enabled,
        )
        for i in active
    }

    high_winners = []
    low_winners = []
    best_high = None
    best_low = None

    for idx in active:
        score = bests[idx]["best_high"]
        if best_high is None or compare_high(score, best_high) > 0:
            best_high = score
            high_winners = [idx]
        elif compare_high(score, best_high) == 0:
            high_winners.append(idx)

    if state.high_low_enabled:
        for idx in active:
            score = bests[idx]["best_low"]
            if best_low is None or compare_low(score, best_low) > 0:
                best_low = score
                low_winners = [idx]
            elif compare_low(score, best_low) == 0:
                low_winners.append(idx)

    if state.high_low_enabled:
        no_losers = set(high_winners) == set(active) and set(low_winners) == set(active)
    else:
        no_losers = set(high_winners) == set(active)

    return high_winners, low_winners, no_losers


def _finish_hand(state: GameState, reason: str) -> None:
    if reason == "folded":
        winners = _active_players(state)
        state.message = f"Hand ended: player {winners[0] + 1} wins by folds."
    else:
        high_winners, low_winners, no_losers = _showdown(state)
        if state.high_low_enabled:
            state.message = (
                f"Showdown: high winners {', '.join(str(i + 1) for i in high_winners)}; "
                f"low winners {', '.join(str(i + 1) for i in low_winners)}."
            )
        else:
            state.message = f"Showdown: high winners {', '.join(str(i + 1) for i in high_winners)}."
        if no_losers:
            _end_game(state, "Game over: no losers this round.")
            return

    if _round_started_with_last_left(state):
        _end_game(state, "Game over: final starting position completed.")
        return

    if not state.game_over:
        _start_next_round(state)


def _ai_action_for_player(state: GameState, player_index: int) -> tuple[str, float]:
    player_hand = state.hands[player_index]
    odds = estimate_player_odds(
        player_count=state.player_count,
        hero_hand=player_hand,
        community_pairs=state.community_pairs,
        revealed_pairs=state.revealed_pairs,
        high_low_enabled=state.high_low_enabled,
        natural_low_enabled=state.natural_low_enabled,
    )
    roll = random.random()

    if state.current_bet == 0:
        if state.raises_this_round < MAX_RAISES:
            raise_chance = min(0.6, max(0.08, odds * 1.4))
            if roll < raise_chance:
                return "raise", 0.05
        if odds >= 0.05:
            return "call", 0.0
        return "fold", 0.0

    if state.raises_this_round < MAX_RAISES:
        raise_chance = min(0.45, max(0.05, odds * 0.9))
        if roll < raise_chance and odds >= 0.12:
            return "raise", 0.10
    if odds >= 0.08:
        return "call", 0.0
    return "fold", 0.0


def _serialize_state(state: GameState) -> dict[str, Any]:
    wild_ranks = build_wild_ranks(state.community_pairs, state.revealed_pairs)
    return {
        "player_count": state.player_count,
        "dealer_index": state.dealer_index,
        "start_index": state.start_index,
        "current_actor": state.current_actor,
        "hands": [[card_to_dict(card) for card in hand] for hand in state.hands],
        "community_pairs": [
            [card_to_dict(card) for card in pair] for pair in state.community_pairs
        ],
        "revealed_pairs": state.revealed_pairs,
        "wild_ranks": sorted(wild_ranks),
        "folded": state.folded,
        "last_action": state.last_action,
        "pot_total": state.pot_total,
        "contrib_this_round": state.contrib_this_round,
        "current_bet": state.current_bet,
        "raises_this_round": state.raises_this_round,
        "round_number": state.round_number,
        "high_low_enabled": state.high_low_enabled,
        "natural_low_enabled": state.natural_low_enabled,
        "pending_players": state.pending_players,
        "game_over": state.game_over,
        "message": state.message,
        "hero_index": HERO_INDEX,
        "allowed_bets": ALLOWED_BETS,
    }


def _ensure_state() -> GameState:
    global STATE
    if STATE is None:
        STATE = GameState(player_count=4)
        _deal_new_hand(STATE)
    return STATE


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b"{}"
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


def _send_json(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _send_file(handler: BaseHTTPRequestHandler, path: str, content_type: str) -> None:
    if not os.path.exists(path):
        handler.send_error(HTTPStatus.NOT_FOUND)
        return
    with open(path, "rb") as f:
        data = f.read()
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _handle_action(state: GameState, player_index: int, action_type: str, amount: float) -> dict:
    if state.game_over:
        return {"error": "Game is over.", **_serialize_state(state)}
    if player_index != state.current_actor:
        return {"error": "Not this player's turn.", **_serialize_state(state)}
    if state.folded[player_index]:
        return {"error": "Player already folded.", **_serialize_state(state)}

    if action_type == "fold":
        state.folded[player_index] = True
        state.last_action[player_index] = "Fold"
        if player_index in state.pending_players:
            state.pending_players.remove(player_index)
    elif action_type == "call":
        call_amount = max(state.current_bet - state.contrib_this_round[player_index], 0.0)
        state.pot_total = round(state.pot_total + call_amount, 2)
        state.contrib_this_round[player_index] += call_amount
        state.last_action[player_index] = f"Call {call_amount:.2f}" if call_amount > 0 else "Check"
        if player_index in state.pending_players:
            state.pending_players.remove(player_index)
    elif action_type == "raise":
        if amount not in ALLOWED_BETS:
            return {"error": "Invalid raise amount.", **_serialize_state(state)}
        if state.raises_this_round >= MAX_RAISES:
            return {"error": "Max raises reached.", **_serialize_state(state)}
        new_bet = state.current_bet + amount
        raise_amount = max(new_bet - state.contrib_this_round[player_index], 0.0)
        state.pot_total = round(state.pot_total + raise_amount, 2)
        state.contrib_this_round[player_index] = new_bet
        state.current_bet = new_bet
        state.raises_this_round += 1
        state.last_action[player_index] = f"Raise {amount:.2f}"
        state.pending_players = [i for i in _active_players(state) if i != player_index]
    else:
        return {"error": "Invalid action.", **_serialize_state(state)}

    active_players = _active_players(state)
    if len(active_players) == 1:
        _finish_hand(state, "folded")
        return _serialize_state(state)

    if not state.pending_players:
        if state.revealed_pairs < 5:
            state.revealed_pairs += 1
            _reset_betting_round(state)
            state.message = f"Reveal pair {state.revealed_pairs}."
        else:
            _finish_hand(state, "showdown")
        return _serialize_state(state)

    next_actor = _next_pending_player(state, player_index)
    state.current_actor = next_actor if next_actor is not None else state.start_index
    return _serialize_state(state)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            _send_file(self, INDEX_PATH, "text/html; charset=utf-8")
            return
        if self.path.startswith("/static/"):
            rel = self.path.replace("/static/", "", 1)
            file_path = os.path.join(STATIC_DIR, rel)
            if file_path.endswith(".css"):
                content_type = "text/css; charset=utf-8"
            elif file_path.endswith(".js"):
                content_type = "text/javascript; charset=utf-8"
            else:
                content_type = "application/octet-stream"
            _send_file(self, file_path, content_type)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path == "/new_game":
            data = _read_json(self)
            player_count = int(data.get("player_count", 4))
            player_count = max(2, min(8, player_count))
            high_low = bool(data.get("high_low", True))
            natural_low = bool(data.get("natural_low", True))

            global STATE
            start_index = 1 % player_count
            STATE = GameState(
                player_count=player_count,
                dealer_index=0,
                start_index=start_index,
                current_actor=start_index,
                high_low_enabled=high_low,
                natural_low_enabled=natural_low,
            )
            _deal_new_hand(STATE)
            STATE.message = "New game started."
            _send_json(self, _serialize_state(STATE))
            return

        if self.path == "/reveal_next":
            state = _ensure_state()
            if state.game_over:
                _send_json(self, {"error": "Game is over.", **_serialize_state(state)}, 400)
                return
            if state.revealed_pairs >= 5:
                _send_json(self, _serialize_state(state))
                return
            state.revealed_pairs += 1
            _reset_betting_round(state)
            state.message = f"Reveal pair {state.revealed_pairs}."
            _send_json(self, _serialize_state(state))
            return

        if self.path == "/action":
            state = _ensure_state()
            data = _read_json(self)
            player_index = int(data.get("player_index", -1))
            action_type = data.get("action", "")
            amount = float(data.get("amount", 0)) if data.get("amount") is not None else 0.0
            payload = _handle_action(state, player_index, action_type, amount)
            status = 400 if "error" in payload else 200
            _send_json(self, payload, status)
            return

        if self.path == "/opponent_action":
            state = _ensure_state()
            if state.game_over:
                _send_json(self, {"error": "Game is over.", **_serialize_state(state)}, 400)
                return
            data = _read_json(self)
            player_index = int(data.get("player_index", -1))
            if player_index == HERO_INDEX:
                _send_json(self, {"error": "Hero cannot use opponent action.", **_serialize_state(state)}, 400)
                return
            if player_index != state.current_actor:
                _send_json(self, {"error": "Not this player's turn.", **_serialize_state(state)}, 400)
                return
            if state.folded[player_index]:
                _send_json(self, {"error": "Player already folded.", **_serialize_state(state)}, 400)
                return
            action_type, amount = _ai_action_for_player(state, player_index)
            payload = _handle_action(state, player_index, action_type, amount)
            status = 400 if "error" in payload else 200
            _send_json(self, payload, status)
            return

        if self.path == "/all_action":
            state = _ensure_state()
            if state.game_over:
                _send_json(self, {"error": "Game is over.", **_serialize_state(state)}, 400)
                return

            loop_guard = 0
            while not state.game_over:
                loop_guard += 1
                if loop_guard > 50:
                    break
                if state.current_actor == HERO_INDEX and not state.folded[HERO_INDEX]:
                    break
                if state.folded[state.current_actor]:
                    if state.current_actor in state.pending_players:
                        state.pending_players.remove(state.current_actor)
                    state.current_actor = _next_pending_player(state, state.current_actor) or state.start_index
                    continue
                action_type, amount = _ai_action_for_player(state, state.current_actor)
                _handle_action(state, state.current_actor, action_type, amount)
            _send_json(self, _serialize_state(state))
            return

        if self.path == "/simulate":
            state = _ensure_state()
            if state.game_over:
                _send_json(self, {"error": "Game is over.", **_serialize_state(state)}, 400)
                return

            hero_hand = state.hands[HERO_INDEX]
            iterations = compute_iterations(state.player_count, state.revealed_pairs)
            odds = simulate_odds(
                player_count=state.player_count,
                hero_hand=hero_hand,
                community_pairs=state.community_pairs,
                revealed_pairs=state.revealed_pairs,
                iterations=iterations,
                max_time_ms=int(os.getenv("SIM_MAX_TIME_MS", "8000")),
                high_low_enabled=state.high_low_enabled,
                natural_low_enabled=state.natural_low_enabled,
            )

            call_cost = max(state.current_bet - state.contrib_this_round[HERO_INDEX], 0.0)
            pot = state.pot_total
            split_win = (odds["high"] + odds["low"]) / 2 if state.high_low_enabled else odds["high"]
            expected = pot * split_win - call_cost

            decision = "Bet/Call" if expected >= 0 else "Check/Fold"
            if odds["iterations_run"] == 0:
                sim_note = " Heuristic estimate (no Monte Carlo iterations)."
            else:
                sim_note = (
                    f" Simulation ran {odds['iterations_run']} iterations in {odds['elapsed_ms'] / 1000:.1f}s"
                    f"{' (time cap reached).' if odds['time_capped'] else '.'}"
                )

            payload = {
                "odds": odds,
                "recommendation": {
                    "decision": decision,
                    "ev": round(expected, 2),
                    "detail": f"EV uses split-pot odds and your call cost.{sim_note}",
                    "betting_constraints": (
                        f"Betting caps: max bet/raise $0.25, up to {MAX_RAISES} raises per round."
                    ),
                },
                **_serialize_state(state),
            }
            _send_json(self, payload)
            return

        self.send_error(HTTPStatus.NOT_FOUND)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 3000), Handler)
    print("Tyler trainer running at http://localhost:3000")
    server.serve_forever()
