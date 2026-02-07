from fastapi.testclient import TestClient

from server.main import app


def test_smoke():
    client = TestClient(app)

    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    resp = client.get("/modules")
    assert resp.status_code == 200
    modules = resp.json()
    assert any(module["id"] == "five_card_draw" for module in modules)

    resp = client.post("/sessions", json={"module_id": "five_card_draw", "player_count": 4})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["module_id"] == "five_card_draw"
    assert payload["player_count"] == 4
    assert "payload" in payload
    assert "hands" in payload["payload"]

    session_id = payload["id"]
    resp = client.get(f"/sessions/{session_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == session_id
