import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .actions import Actions
from .config import ACTIONS_PATH, Settings
from .engine import Engine

WEB = Path(__file__).parent / "web"
PUSH_INTERVAL = 1 / 15
NO_CACHE = {"Cache-Control": "no-cache"}


class Overlay(BaseModel):
    landmarks: bool | None = None
    trails: bool | None = None
    boxes: bool | None = None


def create_app(settings: Settings) -> FastAPI:
    engine = Engine(settings, Actions(ACTIONS_PATH))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine.start()
        yield
        engine.stop()

    app = FastAPI(title="gestura", lifespan=lifespan)

    @app.get("/")
    def index():
        return FileResponse(WEB / "index.html", headers=NO_CACHE)

    @app.get("/static/{name}")
    def static(name: str):
        path = WEB / name
        if not path.exists() or path.parent != WEB:
            raise HTTPException(404)
        return FileResponse(path, headers=NO_CACHE)

    @app.get("/stream.mjpg")
    def stream():
        return StreamingResponse(engine.mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.get("/api/state")
    def state():
        return engine.snapshot()

    @app.get("/api/events")
    def events(after: int = 0):
        return engine.events_after(after)

    @app.post("/api/overlay")
    def overlay(body: Overlay):
        for key, value in body.model_dump(exclude_none=True).items():
            engine.overlay[key] = value
        return engine.overlay

    @app.websocket("/ws")
    async def ws(socket: WebSocket):
        await socket.accept()
        last = 0
        try:
            while engine.running:
                events = engine.events_after(last)
                if events:
                    last = events[-1]["id"]
                await socket.send_json({"state": engine.snapshot(), "events": events})
                await asyncio.sleep(PUSH_INTERVAL)
        except (WebSocketDisconnect, RuntimeError):
            pass

    return app
