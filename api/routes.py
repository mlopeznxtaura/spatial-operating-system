"""
api/routes.py
FastAPI routes for the Spatial Operating System backend.
"""

import asyncio
import json
import logging
import os
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from scene.omniverse_stream import get_stream_server, StreamConfig, init_stream_server
from scene.usd_loader import load_scene
from telemetry.metrics import (
    ACTIVE_SESSIONS, SCENE_LOAD_TOTAL, WEBRTC_MESSAGES_TOTAL,
    SCENE_LOAD_DURATION, KIT_RESTARTS_TOTAL
)

logger = logging.getLogger(__name__)
router = APIRouter()

LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "devsecret")
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "wss://localhost:7880")


# --- Request/Response Models ---

class LoadSceneRequest(BaseModel):
    usd_path: str

class StartStreamRequest(BaseModel):
    usd_path: Optional[str] = None
    rtx_mode: str = "rtx-realtime"
    width: int = 1920
    height: int = 1080

class JoinSessionRequest(BaseModel):
    user_id: str
    room_name: str = "spatial-os"

class ClientMessage(BaseModel):
    type: str
    data: dict = {}


# --- Health ---

@router.get("/health")
async def health():
    server = get_stream_server()
    return {
        "status": "ok",
        "stream": server.get_status() if server else {"state": "not_initialized"},
    }


# --- Scene ---

@router.post("/scene/load")
async def scene_load(req: LoadSceneRequest):
    with SCENE_LOAD_DURATION.time():
        try:
            loader = load_scene(req.usd_path)
            scene_data = loader.get_scene_data()
            SCENE_LOAD_TOTAL.labels(usd_path=req.usd_path[:64]).inc()

            # Also tell the stream server to load it
            server = get_stream_server()
            if server and server.state.value == "running":
                await server._send_to_kit("POST", "/scene/load", {"path": req.usd_path})

            return {"status": "ok", "scene": scene_data}
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Scene load error: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/scene/data")
async def scene_data(usd_path: str):
    try:
        loader = load_scene(usd_path)
        return loader.get_scene_data()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="USD file not found")


# --- Stream ---

@router.post("/stream/start")
async def stream_start(req: StartStreamRequest):
    server = get_stream_server()
    if not server:
        config = StreamConfig(
            usd_path=req.usd_path,
            rtx_mode=req.rtx_mode,
            stream_width=req.width,
            stream_height=req.height,
        )
        server = init_stream_server(config)

    success = await server.start()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start Omniverse Kit stream")
    return {"status": "ok", "stream": server.get_status()}


@router.post("/stream/stop")
async def stream_stop():
    server = get_stream_server()
    if not server:
        return {"status": "not_running"}
    await server.stop()
    return {"status": "stopped"}


@router.get("/stream/status")
async def stream_status():
    server = get_stream_server()
    if not server:
        return {"state": "not_initialized"}
    return server.get_status()


# --- Sessions ---

@router.post("/session/join")
async def session_join(req: JoinSessionRequest):
    """Register a client and return a LiveKit token."""
    try:
        from livekit import api as lk_api
        token = lk_api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        token.with_identity(req.user_id)
        token.with_name(req.user_id)
        token.with_grants(lk_api.VideoGrants(room_join=True, room=req.room_name))
        jwt = token.to_jwt()
    except ImportError:
        # livekit-api not installed — return a dev placeholder
        jwt = f"dev-token-{req.user_id}-{req.room_name}"
        logger.warning("livekit package not installed — returning placeholder token")

    ACTIVE_SESSIONS.inc()
    server = get_stream_server()
    if server:
        server.register_session(req.user_id, "unknown")

    return {"livekit_token": jwt, "livekit_url": LIVEKIT_URL, "user_id": req.user_id}


@router.delete("/session/{session_id}")
async def session_leave(session_id: str):
    ACTIVE_SESSIONS.dec()
    server = get_stream_server()
    if server:
        server.unregister_session(session_id)
    return {"status": "ok"}


# --- WebSocket ---

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    server = get_stream_server()
    logger.info(f"WS client connected: {session_id}")

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
                WEBRTC_MESSAGES_TOTAL.labels(message_type=message.get("type", "unknown")).inc()

                if server:
                    result = await server.handle_client_message(session_id, message)
                    await websocket.send_text(json.dumps(result))
                else:
                    await websocket.send_text(json.dumps({"error": "stream server not running"}))
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "invalid JSON"}))
    except WebSocketDisconnect:
        logger.info(f"WS client disconnected: {session_id}")
        ACTIVE_SESSIONS.dec()
        if server:
            server.unregister_session(session_id)

