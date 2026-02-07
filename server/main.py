from __future__ import annotations

import os
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from server.core.module_loader import build_registry
from server.core.session_store import Session, SessionStore
from server.core.types import ActionRequest, SessionCreateRequest, SessionState


app = FastAPI(title="Trainer Backend")

MODULES_ROOT = os.path.join(os.path.dirname(__file__), "modules")
MODULE_REGISTRY = build_registry(MODULES_ROOT)
SESSIONS = SessionStore()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/modules")
def list_modules() -> list[dict]:
    return [module.config.model_dump() for module in MODULE_REGISTRY.values()]


@app.post("/sessions", response_model=SessionState)
def create_session(request: SessionCreateRequest) -> SessionState:
    module = MODULE_REGISTRY.get(request.module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found.")

    limits = module.config.player_limits
    if request.player_count < limits.min or request.player_count > limits.max:
        raise HTTPException(status_code=400, detail="Invalid player count.")

    state = module.module.init_state(request.player_count)
    session_id = str(uuid.uuid4())
    session = Session(
        id=session_id,
        module_id=request.module_id,
        player_count=request.player_count,
        state=state,
    )
    SESSIONS.add(session)

    payload = module.module.render_payload(state, request.player_count)
    return SessionState(
        id=session_id,
        module_id=request.module_id,
        player_count=request.player_count,
        payload=payload,
    )


@app.get("/sessions/{session_id}", response_model=SessionState)
def get_session(session_id: str) -> SessionState:
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    module = MODULE_REGISTRY.get(session.module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found.")

    payload = module.module.render_payload(session.state, session.player_count)
    return SessionState(
        id=session.id,
        module_id=session.module_id,
        player_count=session.player_count,
        payload=payload,
    )


@app.post("/sessions/{session_id}/action", response_model=SessionState)
def apply_action(session_id: str, request: ActionRequest) -> SessionState:
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    module = MODULE_REGISTRY.get(session.module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found.")

    session.state = module.module.apply_action(
        session.state, request.model_dump(), session.player_count
    )
    payload = module.module.render_payload(session.state, session.player_count)
    return SessionState(
        id=session.id,
        module_id=session.module_id,
        player_count=session.player_count,
        payload=payload,
    )
