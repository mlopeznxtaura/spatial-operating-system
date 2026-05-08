"""
scene/omniverse_stream.py
NVIDIA Omniverse Kit WebRTC streaming server control layer.
Manages the Kit application process, WebRTC session lifecycle,
and bidirectional data channel messaging for the Spatial OS.

Architecture:
  RTX GPU Server runs Omniverse Kit (full USD renderer + path tracing)
  Kit captures framebuffer -> streams via WebRTC to browser
  Browser sends camera/input/selection events back via data channel
  This module is the Python control plane sitting alongside Kit.
"""

import asyncio
import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, Any
from enum import Enum

logger = logging.getLogger(__name__)


class StreamState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class StreamConfig:
    kit_app_path: str = "/opt/nvidia/omniverse/kit/kit"
    kit_app_script: str = "apps/omni.spatial_os.viewer.kit"
    webrtc_port: int = 8011
    signaling_port: int = 8012
    stream_width: int = 1920
    stream_height: int = 1080
    rtx_mode: str = "rtx"  # "rtx" | "rtx-realtime" | "iray"
    max_clients: int = 10
    usd_path: Optional[str] = None
    env: dict = field(default_factory=dict)


@dataclass
class ClientSession:
    session_id: str
    client_ip: str
    connected_at: float = field(default_factory=time.time)
    last_message_at: float = field(default_factory=time.time)
    camera_state: dict = field(default_factory=dict)
    selected_prims: list = field(default_factory=list)


class OmniverseStreamServer:
    """
    Controls an NVIDIA Omniverse Kit streaming instance.

    The Kit process runs separately (heavy NVIDIA runtime).
    This class:
      - Launches/terminates the Kit process
      - Manages WebRTC signaling via the Kit HTTP API
      - Routes client messages (camera moves, selections, USD commands)
      - Broadcasts scene state changes to all connected clients
    """

    def __init__(self, config: StreamConfig):
        self.config = config
        self.state = StreamState.STOPPED
        self._kit_process: Optional[subprocess.Popen] = None
        self._sessions: dict[str, ClientSession] = {}
        self._message_handlers: dict[str, Callable] = {}
        self._on_state_change: Optional[Callable] = None

        # Register built-in message handlers
        self._register_default_handlers()

    def _register_default_handlers(self):
        self._message_handlers["camera_move"] = self._handle_camera_move
        self._message_handlers["select_prim"] = self._handle_select_prim
        self._message_handlers["load_usd"] = self._handle_load_usd
        self._message_handlers["set_variant"] = self._handle_set_variant
        self._message_handlers["set_time"] = self._handle_set_time

    async def start(self) -> bool:
        """Launch the Omniverse Kit streaming process."""
        if self.state == StreamState.RUNNING:
            logger.warning("Stream already running")
            return True

        self.state = StreamState.STARTING
        logger.info("Starting Omniverse Kit streaming server...")

        cmd = [
            self.config.kit_app_path,
            self.config.kit_app_script,
            "--/app/livestream/enabled=true",
            f"--/app/livestream/port={self.config.webrtc_port}",
            f"--/renderer/resolution/width={self.config.stream_width}",
            f"--/renderer/resolution/height={self.config.stream_height}",
            f"--/rtx/rendermode={self.config.rtx_mode}",
        ]

        if self.config.usd_path:
            cmd.append(f"--/app/startup/file={self.config.usd_path}")

        env = {**self.config.env}

        try:
            self._kit_process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            # Wait for Kit to become ready (polls signaling endpoint)
            ready = await self._wait_for_ready(timeout=60)
            if ready:
                self.state = StreamState.RUNNING
                logger.info(f"Omniverse Kit ready on port {self.config.webrtc_port}")
                return True
            else:
                self.state = StreamState.ERROR
                logger.error("Kit failed to become ready within timeout")
                return False
        except FileNotFoundError:
            logger.error(f"Kit executable not found: {self.config.kit_app_path}")
            self.state = StreamState.ERROR
            return False

    async def _wait_for_ready(self, timeout: int = 60) -> bool:
        """Poll Kit's health endpoint until ready."""
        import aiohttp
        health_url = f"http://localhost:{self.config.webrtc_port}/health"
        start = time.time()

        async with aiohttp.ClientSession() as session:
            while time.time() - start < timeout:
                try:
                    async with session.get(health_url, timeout=aiohttp.ClientTimeout(total=2)) as resp:
                        if resp.status == 200:
                            return True
                except Exception:
                    pass
                await asyncio.sleep(2)
        return False

    async def stop(self):
        """Gracefully stop the Kit process."""
        if self._kit_process:
            self._kit_process.terminate()
            try:
                self._kit_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._kit_process.kill()
            self._kit_process = None
        self.state = StreamState.STOPPED
        self._sessions.clear()
        logger.info("Omniverse stream stopped")

    def register_session(self, session_id: str, client_ip: str) -> ClientSession:
        session = ClientSession(session_id=session_id, client_ip=client_ip)
        self._sessions[session_id] = session
        logger.info(f"Client connected: {session_id} from {client_ip}")
        return session

    def unregister_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Client disconnected: {session_id}")

    async def handle_client_message(self, session_id: str, message: dict) -> dict:
        """Route an incoming WebRTC data channel message to the right handler."""
        msg_type = message.get("type")
        if not msg_type:
            return {"error": "message missing 'type' field"}

        handler = self._message_handlers.get(msg_type)
        if not handler:
            return {"error": f"unknown message type: {msg_type}"}

        session = self._sessions.get(session_id)
        if not session:
            return {"error": f"unknown session: {session_id}"}

        session.last_message_at = time.time()
        return await handler(session, message)

    async def _handle_camera_move(self, session: ClientSession, msg: dict) -> dict:
        """Forward camera transform to Kit via its HTTP API."""
        camera_data = msg.get("camera", {})
        session.camera_state = camera_data

        # Send to Kit's camera control endpoint
        await self._send_to_kit("POST", "/camera/set", camera_data)
        return {"status": "ok"}

    async def _handle_select_prim(self, session: ClientSession, msg: dict) -> dict:
        prim_path = msg.get("path")
        session.selected_prims = [prim_path] if prim_path else []
        await self._send_to_kit("POST", "/selection/set", {"paths": session.selected_prims})
        return {"status": "ok", "selected": session.selected_prims}

    async def _handle_load_usd(self, session: ClientSession, msg: dict) -> dict:
        usd_path = msg.get("path")
        if not usd_path:
            return {"error": "missing 'path'"}
        await self._send_to_kit("POST", "/scene/load", {"path": usd_path})
        return {"status": "ok", "loaded": usd_path}

    async def _handle_set_variant(self, session: ClientSession, msg: dict) -> dict:
        await self._send_to_kit("POST", "/scene/variant", msg)
        return {"status": "ok"}

    async def _handle_set_time(self, session: ClientSession, msg: dict) -> dict:
        time_code = msg.get("time_code", 0)
        await self._send_to_kit("POST", "/timeline/set", {"time_code": time_code})
        return {"status": "ok", "time_code": time_code}

    async def _send_to_kit(self, method: str, endpoint: str, data: dict) -> dict:
        """Send a command to the Kit HTTP control API."""
        import aiohttp
        url = f"http://localhost:{self.config.webrtc_port}{endpoint}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method, url, json=data, timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    return await resp.json()
        except Exception as e:
            logger.error(f"Kit API call failed {method} {endpoint}: {e}")
            return {"error": str(e)}

    def get_status(self) -> dict:
        return {
            "state": self.state.value,
            "active_sessions": len(self._sessions),
            "webrtc_port": self.config.webrtc_port,
            "usd_path": self.config.usd_path,
            "kit_pid": self._kit_process.pid if self._kit_process else None,
        }


# Global singleton for FastAPI to reference
_stream_server: Optional[OmniverseStreamServer] = None


def get_stream_server() -> Optional[OmniverseStreamServer]:
    return _stream_server


def init_stream_server(config: StreamConfig) -> OmniverseStreamServer:
    global _stream_server
    _stream_server = OmniverseStreamServer(config)
    return _stream_server

