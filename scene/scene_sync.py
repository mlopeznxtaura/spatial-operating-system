"""
scene/scene_sync.py
Multi-user USD scene state synchronization.
Tracks prim selections, time code, active variants per user.
Broadcasts deltas to all connected clients via Socket.io + Supabase Realtime.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable
import socketio
from supabase import create_client, Client as SupabaseClient

logger = logging.getLogger(__name__)


@dataclass
class UserSceneState:
    user_id: str
    selected_prims: list[str] = field(default_factory=list)
    camera_position: dict = field(default_factory=lambda: {"x": 0, "y": 1.6, "z": 3})
    camera_target: dict = field(default_factory=lambda: {"x": 0, "y": 1.0, "z": 0})
    last_active: float = field(default_factory=time.time)


@dataclass
class SceneState:
    current_time_code: float = 0.0
    active_variants: dict[str, str] = field(default_factory=dict)
    loaded_usd_path: Optional[str] = None
    users: dict[str, UserSceneState] = field(default_factory=dict)
    stream_state: str = "stopped"


class SceneSyncManager:
    """
    Manages multi-user scene state synchronization.

    Uses two channels:
      - Socket.io for low-latency real-time events (camera moves, selections)
      - Supabase Realtime for durable state (scene mutations, variant changes)
    """

    def __init__(
        self,
        sio: socketio.AsyncServer,
        supabase_url: str,
        supabase_key: str,
        room_id: str = "default",
    ):
        self.sio = sio
        self.room_id = room_id
        self.state = SceneState()
        self._on_state_change: list[Callable] = []

        # Supabase for durable state
        self.supabase: SupabaseClient = create_client(supabase_url, supabase_key)
        self._realtime_channel = None

        # Register Socket.io event handlers
        self._register_sio_handlers()

    def _register_sio_handlers(self):
        @self.sio.event
        async def connect(sid, environ, auth):
            user_id = auth.get("user_id", sid) if auth else sid
            await self._handle_user_connect(sid, user_id)

        @self.sio.event
        async def disconnect(sid):
            await self._handle_user_disconnect(sid)

        @self.sio.on("camera_move")
        async def on_camera_move(sid, data):
            await self._handle_camera_move(sid, data)

        @self.sio.on("select_prim")
        async def on_select_prim(sid, data):
            await self._handle_select_prim(sid, data)

        @self.sio.on("set_time_code")
        async def on_set_time_code(sid, data):
            await self._handle_set_time_code(sid, data)

        @self.sio.on("set_variant")
        async def on_set_variant(sid, data):
            await self._handle_set_variant(sid, data)

        @self.sio.on("request_state")
        async def on_request_state(sid, data):
            await self.sio.emit("full_state", self._serialize_state(), to=sid)

    async def start_realtime_sync(self):
        """Subscribe to Supabase Realtime for durable scene state."""
        try:
            channel = self.supabase.channel(f"scene:{self.room_id}")
            channel.on_broadcast(
                event="scene_mutation",
                callback=self._on_supabase_scene_mutation,
            )
            await channel.subscribe()
            self._realtime_channel = channel
            logger.info(f"Supabase Realtime subscribed to scene:{self.room_id}")
        except Exception as e:
            logger.warning(f"Supabase Realtime unavailable: {e} — falling back to Socket.io only")

    def _on_supabase_scene_mutation(self, payload):
        """Handle durable scene mutations from Supabase."""
        mutation = payload.get("payload", {})
        mutation_type = mutation.get("type")
        if mutation_type == "usd_loaded":
            self.state.loaded_usd_path = mutation.get("path")
        elif mutation_type == "variant_set":
            prim = mutation.get("prim_path")
            variant_set = mutation.get("variant_set")
            variant = mutation.get("variant")
            if prim and variant_set:
                key = f"{prim}:{variant_set}"
                self.state.active_variants[key] = variant

    async def _handle_user_connect(self, sid: str, user_id: str):
        self.state.users[sid] = UserSceneState(user_id=user_id)
        await self.sio.enter_room(sid, self.room_id)
        # Send current state to new user
        await self.sio.emit("full_state", self._serialize_state(), to=sid)
        # Notify others
        await self.sio.emit(
            "user_joined",
            {"user_id": user_id, "sid": sid},
            room=self.room_id,
            skip_sid=sid,
        )
        logger.info(f"User {user_id} joined scene room {self.room_id}")

    async def _handle_user_disconnect(self, sid: str):
        user = self.state.users.pop(sid, None)
        if user:
            await self.sio.emit(
                "user_left",
                {"user_id": user.user_id, "sid": sid},
                room=self.room_id,
            )
            logger.info(f"User {user.user_id} left scene room {self.room_id}")

    async def _handle_camera_move(self, sid: str, data: dict):
        if sid not in self.state.users:
            return
        user = self.state.users[sid]
        user.camera_position = data.get("position", user.camera_position)
        user.camera_target = data.get("target", user.camera_target)
        user.last_active = time.time()
        # Broadcast to others (not sender) — high frequency, Socket.io only
        await self.sio.emit(
            "peer_camera_move",
            {"user_id": user.user_id, "position": user.camera_position, "target": user.camera_target},
            room=self.room_id,
            skip_sid=sid,
        )

    async def _handle_select_prim(self, sid: str, data: dict):
        if sid not in self.state.users:
            return
        user = self.state.users[sid]
        prim_path = data.get("path")
        user.selected_prims = [prim_path] if prim_path else []
        user.last_active = time.time()
        await self.sio.emit(
            "peer_selection",
            {"user_id": user.user_id, "selected_prims": user.selected_prims},
            room=self.room_id,
            skip_sid=sid,
        )

    async def _handle_set_time_code(self, sid: str, data: dict):
        time_code = data.get("time_code", 0.0)
        self.state.current_time_code = time_code
        await self.sio.emit(
            "time_code_changed",
            {"time_code": time_code, "set_by": self.state.users.get(sid, UserSceneState(user_id=sid)).user_id},
            room=self.room_id,
        )

    async def _handle_set_variant(self, sid: str, data: dict):
        prim_path = data.get("prim_path")
        variant_set = data.get("variant_set")
        variant = data.get("variant")
        if prim_path and variant_set and variant:
            key = f"{prim_path}:{variant_set}"
            self.state.active_variants[key] = variant
            await self.sio.emit("variant_changed", data, room=self.room_id)
            # Persist to Supabase
            if self._realtime_channel:
                await self._realtime_channel.send_broadcast(
                    event="scene_mutation",
                    payload={"type": "variant_set", **data},
                )

    def _serialize_state(self) -> dict:
        return {
            "current_time_code": self.state.current_time_code,
            "active_variants": self.state.active_variants,
            "loaded_usd_path": self.state.loaded_usd_path,
            "stream_state": self.state.stream_state,
            "users": {
                sid: {
                    "user_id": u.user_id,
                    "selected_prims": u.selected_prims,
                    "camera_position": u.camera_position,
                    "camera_target": u.camera_target,
                }
                for sid, u in self.state.users.items()
            },
        }

    def set_stream_state(self, state: str):
        self.state.stream_state = state

    def get_connected_user_count(self) -> int:
        return len(self.state.users)

