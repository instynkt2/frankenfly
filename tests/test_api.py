import asyncio
import time
from fastapi.testclient import TestClient
from frankenfly.server import Runtime, create_app


class OfflineRuntime(Runtime):
    async def run(self):
        self.snapshot = {"status": "unavailable", "message": "No data"}


class FixtureRuntime(Runtime):
    """API fixture only. Never reachable from the production application."""
    async def run(self):
        self.snapshot = {"status": "live", "world": self.world.state(), "paused": False, "updated_at": time.time()}


def test_missing_data_does_not_turn_into_a_fake_brain(tmp_path):
    runtime = OfflineRuntime(tmp_path, tmp_path, "test-key")
    with TestClient(create_app(runtime)) as client:
        assert client.get("/healthz").status_code == 503
        assert client.get("/api/geometry").status_code == 503
        assert client.get("/api/state").json()["status"] == "unavailable"
        assert client.get("/").status_code == 200


def test_operator_access_validation_limits_and_real_world_update(tmp_path):
    runtime = FixtureRuntime(tmp_path, tmp_path, "test-key")
    headers = {"Authorization": "Bearer test-key"}
    with TestClient(create_app(runtime)) as client:
        assert client.get("/api/operator").status_code == 401
        assert client.get("/api/operator", headers=headers).status_code == 200
        assert client.post("/api/control", json={"action": "clear"}).status_code == 401
        assert client.post("/api/control", headers=headers, json={"action":"stimulus","x":2000}).status_code == 422
        response=client.post("/api/control", headers=headers, json={"action":"stimulus","kind":"odor","x":100,"y":200})
        assert response.status_code == 200
        state = client.get("/api/state").json()
        assert any(s["kind"] == "odor" and s["x"] == 100 for s in state["world"]["stimuli"])
        assert client.post("/api/control", headers=headers, json={"action":"clear"}).status_code == 429
        assert client.post("/api/control", headers=headers, content=b"x"*3000).status_code == 413
        assert client.get("/assets/../../.env").status_code != 200
