"""One shared brain per process. Viewers read cached telemetry, never spawn brains."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import logging
import os
from pathlib import Path
import secrets
import time
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .brain import Brain
from .world import World

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("frankenfly")


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    action: Literal["stimulus", "pause", "resume", "clear"]
    kind: Literal["light", "shadow", "odor"] = "light"
    x: float = Field(default=480, ge=24, le=936)
    y: float = Field(default=300, ge=24, le=576)
    power: float = Field(default=1, ge=.1, le=1)


class Runtime:
    def __init__(self, data_dir, state_dir, control_token="", hz=8, steps=60):
        self.data_dir, self.state_dir = Path(data_dir), Path(state_dir)
        self.control_token = control_token
        self.hz, self.steps = hz, steps
        self.brain = None
        self.world = World()
        self.paused = False
        self.snapshot = {"status": "loading", "message": "Connecting the fly brain…"}
        self.geometry = None
        self.lock = asyncio.Lock()
        self.events = []
        self.sequence = 0
        self.last_command = 0.
        self.last_save = time.monotonic()
        self.running = True

    def event(self, text):
        self.sequence += 1
        self.events.insert(0, {"id": self.sequence, "text": text, "at": round(self.world.time, 1)})
        self.events = self.events[:12]

    def boot(self):
        self.brain = Brain(self.data_dir)
        self.geometry = self.brain.geometry()
        restored = self.brain.restore(self.state_dir / "checkpoint.npz", self.world)
        self.event("Previous session restored" if restored else "Fly connectome connected to cat body")

    async def run(self):
        try:
            await asyncio.to_thread(self.boot)
            while self.running:
                began = time.monotonic()
                async with self.lock:
                    if not self.paused:
                        telemetry = await asyncio.to_thread(self.brain.step, self.world, self.steps)
                        self.world.move(telemetry["turn"], telemetry["drive"], 1 / self.hz)
                        self.snapshot = {"status": "live", "telemetry": telemetry, "world": self.world.state(),
                                         "neurons": self.brain.n, "edges": len(self.brain.data), "events": list(self.events),
                                         "updated_at": time.time(), "paused": False}
                    else:
                        self.snapshot = {**self.snapshot, "paused": True, "events": list(self.events), "updated_at": time.time()}
                    if time.monotonic() - self.last_save >= 60:
                        await asyncio.to_thread(self.brain.save, self.state_dir / "checkpoint.npz", self.world)
                        self.last_save = time.monotonic()
                await asyncio.sleep(max(.01, 1 / self.hz - (time.monotonic() - began)))
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Simulation stopped")
            self.snapshot = {"status": "unavailable", "message": "The brain is offline. The operator needs to check the data and server logs."}
            self.running = False

    async def stop(self):
        self.running = False
        async with self.lock:
            if self.brain:
                await asyncio.to_thread(self.brain.save, self.state_dir / "checkpoint.npz", self.world)


def create_app(runtime=None):
    runtime = runtime or Runtime(os.environ.get("FRANKENFLY_DATA_DIR", str(ROOT / "data")),
                                 os.environ.get("FRANKENFLY_STATE_DIR", str(ROOT / "state")),
                                 os.environ.get("FRANKENFLY_CONTROL_TOKEN", ""),
                                 hz=max(1, min(20, float(os.environ.get("FRANKENFLY_HZ", "8")))))

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(runtime.run())
        try:
            yield
        finally:
            await runtime.stop()
            # Await an in-flight step before checkpointing/exit; do not abandon
            # a numerical worker thread while it is mutating the same state.
            await task

    app = FastAPI(title="Frankenfly", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.runtime = runtime

    @app.middleware("http")
    async def boundaries(request: Request, call_next):
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > 2048):
            return JSONResponse({"detail": "Request too large"}, status_code=413)
        if request.method == "POST":
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 2048:
                    return JSONResponse({"detail": "Request too large"}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/healthz")
    async def health():
        ready = runtime.snapshot["status"] == "live" and time.time() - runtime.snapshot.get("updated_at", 0) < 10
        return JSONResponse({"ready": ready, "status": runtime.snapshot["status"]}, status_code=200 if ready else 503)

    @app.get("/api/state")
    async def state():
        return {**runtime.snapshot, "control_enabled": bool(runtime.control_token)}

    @app.get("/api/geometry")
    async def geometry():
        if runtime.geometry is None:
            raise HTTPException(503, "Connectome is not loaded")
        return runtime.geometry

    @app.get("/api/operator")
    async def operator(request: Request):
        if not runtime.control_token or not secrets.compare_digest(request.headers.get("authorization", ""), f"Bearer {runtime.control_token}"):
            raise HTTPException(401, "Operator access required")
        return {"ok": True}

    @app.post("/api/control")
    async def control(command: Command, request: Request):
        expected = f"Bearer {runtime.control_token}"
        if not runtime.control_token or not secrets.compare_digest(request.headers.get("authorization", ""), expected):
            raise HTTPException(401, "Operator access required")
        if runtime.snapshot["status"] != "live":
            raise HTTPException(503, "The brain is offline")
        async with runtime.lock:
            now = time.monotonic()
            if now - runtime.last_command < .3:
                raise HTTPException(429, "Wait a moment before the next action")
            runtime.last_command = now
            if command.action == "stimulus":
                runtime.world.place(command.kind, command.x, command.y, command.power)
                runtime.event(f"{command.kind.capitalize()} placed in the chamber")
            elif command.action == "clear":
                runtime.world.stimuli.clear()
                runtime.event("Stimuli cleared")
            else:
                runtime.paused = command.action == "pause"
                runtime.event("Session paused" if runtime.paused else "Session resumed")
            runtime.snapshot = {**runtime.snapshot, "world": runtime.world.state(), "paused": runtime.paused, "events": list(runtime.events), "updated_at": time.time()}
        return {"ok": True}

    @app.get("/")
    async def index():
        return FileResponse(ROOT / "dist" / "index.html")

    app.mount("/assets", StaticFiles(directory=ROOT / "dist" / "assets"), name="assets")
    return app


app = create_app()
