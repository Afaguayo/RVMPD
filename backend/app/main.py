"""VITALIS backend: simulation loop, REST routes and the /ws frame stream."""
import asyncio
import contextlib
from datetime import datetime, timezone

import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .alerts import AlertTracker
from .pipeline import Pipeline
from .simulator import CHUNK, FS, SCENARIOS, Simulator
from .spaceweather import get_spaceweather
from .stats import ALPHA, VitalStats, global_status, radiation_status

FRAME_SECONDS = CHUNK / FS
TICKS_PER_VITALS_UPDATE = 5  # vitals are recomputed once per second
WARMUP_TICKS = 125  # 25 s of data so the first frame already has trustworthy vitals


class Engine:
    """Runs simulator -> pipeline -> stats -> alerts and builds one frame per tick."""

    def __init__(self, seed=None):
        self.sim = Simulator(seed)
        self.pipeline = Pipeline(self.sim.rng)
        self.stats = VitalStats()
        self.alerts = AlertTracker()
        self.ticks = 0
        self.vitals = {}
        self.radiation = "green"
        self.global_block = {}
        self.alert_list = []
        for _ in range(WARMUP_TICKS):
            self._advance()

    def _advance(self):
        chunk = self.sim.step()
        self.pipeline.push(chunk)
        self.ticks += 1
        if self.pipeline.ready and self.ticks % TICKS_PER_VITALS_UPDATE == 0:
            values, sqi = self.pipeline.measure(chunk.truth)
            results = self.stats.update(values, sqi)
            self.radiation = radiation_status(chunk.truth["dose_rate"])
            self.vitals = {name: r.as_dict() for name, r in results.items()}
            self.alert_list = self.alerts.update(chunk.t, results, self.radiation)
            scores = [r.sqi for r in results.values()]
            mean = float(np.mean(scores))
            self.global_block = {
                "status": global_status(results, self.radiation),
                # The family-wise guarantee of the Holm correction, not a sensor score
                "confidence": 1 - ALPHA,
                "sqi": round(mean, 2),
                "link": "ok",
            }
        return chunk

    def next_frame(self):
        chunk = self._advance()
        return {
            "type": "frame",
            "t": round(chunk.t, 1),
            "scenario": self.sim.scenario.id,
            "wave": {"fs": FS, "ecg": chunk.ecg.round(4).tolist(), "ppg": chunk.ppg.round(3).tolist(),
                     "resp": chunk.resp.round(3).tolist()},
            "vitals": self.vitals,
            "radiation": {"dose_rate_usv_h": round(chunk.dose_rate, 1),
                          "dose_total_msv": round(chunk.dose_total_msv, 3), "status": self.radiation},
            "global": self.global_block,
            "alerts": self.alert_list,
        }


class ScenarioChange(BaseModel):
    id: str


class CheckInIn(BaseModel):
    mood: int = Field(ge=1, le=5)
    sleep_hours: float = Field(ge=0, le=24)
    note: str = ""


async def run_simulation(app):
    """Advance the simulation in real time and broadcast each frame to every client."""
    next_tick = asyncio.get_running_loop().time()
    while True:
        frame = app.state.engine.next_frame()
        for ws in list(app.state.clients):
            try:
                await ws.send_json(frame)
            except Exception:
                app.state.clients.discard(ws)
        next_tick += FRAME_SECONDS
        await asyncio.sleep(max(0.0, next_tick - asyncio.get_running_loop().time()))


@contextlib.asynccontextmanager
async def lifespan(app):
    app.state.engine = Engine()
    app.state.clients = set()
    app.state.checkins = []
    task = asyncio.create_task(run_simulation(app))
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(title="VITALIS", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "*"],
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/scenarios")
def scenarios():
    return [{"id": s.id, "name": s.name, "description": s.description} for s in SCENARIOS.values()]


@app.post("/api/scenario")
def set_scenario(body: ScenarioChange):
    if body.id not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Unknown scenario '{body.id}'")
    app.state.engine.sim.set_scenario(body.id)
    return {"ok": True, "scenario": body.id}


@app.get("/api/checkins")
def list_checkins():
    return list(reversed(app.state.checkins))


@app.post("/api/checkin")
def add_checkin(body: CheckInIn):
    checkin = {"id": len(app.state.checkins) + 1, **body.model_dump(),
               "t": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    app.state.checkins.append(checkin)
    return checkin


@app.get("/api/spaceweather")
async def spaceweather():
    return await get_spaceweather()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    app.state.clients.add(ws)
    try:
        while True:
            await ws.receive_text()  # the client never sends; this just detects the disconnect
    except WebSocketDisconnect:
        app.state.clients.discard(ws)
