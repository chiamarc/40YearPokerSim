from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Session:
    id: str
    module_id: str
    player_count: int
    state: Any


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def add(self, session: Session) -> None:
        self._sessions[session.id] = session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)
