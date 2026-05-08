"""
main.py
Entry point for the Spatial Operating System backend.
Wires together FastAPI, Omniverse stream, Socket.io, and Prometheus.

Environment variables:
  STREAM_USD_PATH     Path to the default .usda scene to load on startup
  KIT_APP_PATH        Path to the Omniverse Kit executable
  WEBRTC_PORT         WebRTC streaming port (default: 8011)
  LIVEKIT_URL         LiveKit server URL
  LIVEKIT_API_KEY     LiveKit API key
  LIVEKIT_API_SECRET  LiveKit API secret
  SUPABASE_URL        Supabase project URL
  SUPABASE_KEY        Supabase service role key
  PORT                uvicorn port (default: 8000)
  HOST                uvicorn host (default: 0.0.0.0)
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from scene.omniverse_stream import StreamConfig, init_stream_server
from scene.scene_sync import SceneSyncManager
from telemetry.metrics import make_metrics_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("spatial-os")

# --- Config from environment ---
KIT_APP_PATH = os.getenv("KIT_APP_PATH", "/opt/nvidia/omniverse/kit/kit")
WEBRTC_PORT = int(os.getenv("WEBRTC_PORT", "8011"))
STREAM_USD_PATH = os.getenv("STREAM_USD_PATH")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
AUTO_START_STREAM = os.getenv("AUTO_START_STREAM", "false").lower() == "true"

# --- Socket.io server ---
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)

# --- Scene sync manager ---
scene_sync: SceneSyncManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global scene_sync

    logger.info("Spatial OS backend starting...")

    # Initialize stream server config
    stream_config = StreamConfig(
        kit_app_path=KIT_APP_PATH,
        webrtc_port=WEBRTC_PORT,
        usd_path=STREAM_USD_PATH,
    )
    stream_server = init_stream_server(stream_config)
    logger.info(f"Stream server initialized (Kit: {KIT_APP_PATH})")

    # Auto-start stream if configured
    if AUTO_START_STREAM:
        logger.info("AUTO_START_STREAM=true — starting Omniverse Kit stream...")
        success = await stream_server.start()
        if success:
            logger.info("Omniverse Kit stream started")
        else:
            logger.warning("Omniverse Kit stream failed to start — continuing without stream")

    # Initialize scene sync (Supabase optional)
    if SUPABASE_URL and SUPABASE_KEY:
        scene_sync = SceneSyncManager(
            sio=sio,
            supabase_url=SUPABASE_URL,
            supabase_key=SUPABASE_KEY,
        )
        await scene_sync.start_realtime_sync()
        logger.info("Scene sync initialized with Supabase Realtime")
    else:
        logger.warning("SUPABASE_URL/KEY not set — scene sync will use Socket.io only")
        scene_sync = SceneSyncManager(
            sio=sio,
            supabase_url="",
            supabase_key="",
        )

    logger.info(f"Spatial OS backend ready on {HOST}:{PORT}")
    yield

    # Shutdown
    logger.info("Spatial OS backend shutting down...")
    if AUTO_START_STREAM:
        await stream_server.stop()
    logger.info("Shutdown complete")


# --- FastAPI app ---
app = FastAPI(
    title="Spatial Operating System API",
    description="Backend for the OpenUSD-native Spatial OS. Cluster 04 — NextAura.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow local dev and any deployed frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(router)

# Mount Prometheus metrics
metrics_app = make_metrics_app()
app.mount("/metrics", metrics_app)

# Mount Socket.io at /socket.io
sio_app = socketio.ASGIApp(sio, other_asgi_app=app)

# The actual ASGI app to serve (Socket.io wraps FastAPI)
asgi_app = sio_app


if __name__ == "__main__":
    uvicorn.run(
        "main:asgi_app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
        ws="websockets",
    )

