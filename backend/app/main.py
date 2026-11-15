"""VITALIS backend: simulation loop, REST routes and the /ws frame stream."""
import asyncio
import contextlib
import logging
import sqlite3

import numpy as np
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import analysis, llm
from .alerts import AlertTracker
from .db import Database, now_iso
from .pipeline import Pipeline
from .simulator import CHUNK, FS, SCENARIOS, Simulator
from .spaceweather import get_spaceweather
from .stats import ALPHA, VitalStats, global_status, radiation_status

FRAME_SECONDS = CHUNK / FS
TICKS_PER_VITALS_UPDATE = 5  # vitals are recomputed once per second
WARMUP_TICKS = 125  # 25 s of data so the first frame already has trustworthy vitals
log = logging.getLogger("vitalis.db")


class Engine:
    """Runs simulator -> pipeline -> stats -> alerts and builds one frame per tick."""

    def __init__(self, seed=None, db=None):
        self.db = None  # attached after the warm-up so those first seconds are not stored
        self.logged_alerts = set()
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
        self.db = db

    def _record(self, chunk):
        """Store this second; an alert is stored once, when it first appears."""
        try:
            self.db.record_sample(now_iso(), chunk.t, self.sim.scenario.id, self.vitals,
                                  round(chunk.dose_rate, 1), round(chunk.dose_total_msv, 3), self.radiation,
                                  self.global_block["status"])
            for alert in self.alert_list:
                if alert["id"] not in self.logged_alerts:
                    self.logged_alerts.add(alert["id"])
                    self.db.log_alert(alert)
        except sqlite3.Error as e:  # a storage problem must not stop the live stream
            log.warning("Could not store samples: %s", e)

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
            if self.db:
                self._record(chunk)
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


class AnalysisIn(BaseModel):
    minutes: int = Field(60, ge=1, le=1440)


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
    app.state.db = Database()
    app.state.engine = Engine(db=app.state.db)
    app.state.clients = set()
    task = asyncio.create_task(run_simulation(app))
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    app.state.db.close()


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
    app.state.db.log_scenario(body.id)
    return {"ok": True, "scenario": body.id}


@app.get("/api/checkins")
def list_checkins():
    return app.state.db.checkins()


@app.post("/api/checkin")
def add_checkin(body: CheckInIn):
    return app.state.db.add_checkin(**body.model_dump())


@app.get("/api/history")
def history(metric: str, minutes: int = Query(60, ge=1, le=1440)):
    try:
        return {"metric": metric, "points": app.state.db.history(metric, minutes)}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown metric '{metric}'")


@app.get("/api/alerts/log")
def alerts_log(limit: int = Query(50, ge=1, le=500)):
    return app.state.db.alert_log(limit)


@app.get("/api/stats")
def database_stats():
    return app.state.db.stats()


# A plain `def` route runs in a worker thread, so the analysis never blocks the event loop
@app.post("/api/analysis")
def run_analysis(body: AnalysisIn | None = None):
    stats = analysis.window_stats(app.state.db, (body or AnalysisIn()).minutes)
    return app.state.db.save_report(llm.refine(stats, analysis.local_report(stats)))


@app.get("/api/analysis/latest")
def latest_analysis():
    report = app.state.db.latest_report()
    if report is None:
        raise HTTPException(status_code=404, detail="No analysis has been run yet")
    return report


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
