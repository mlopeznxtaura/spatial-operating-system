"""
telemetry/metrics.py
Prometheus metrics for the Spatial Operating System.
"""

from prometheus_client import Counter, Gauge, Histogram, Summary, REGISTRY, make_asgi_app
import logging

logger = logging.getLogger(__name__)

# Active WebSocket/streaming sessions
ACTIVE_SESSIONS = Gauge(
    "spatial_os_active_sessions",
    "Number of currently active client sessions",
)

# Scene load events
SCENE_LOAD_TOTAL = Counter(
    "spatial_os_scene_load_total",
    "Total number of USD scenes loaded",
    labelnames=["usd_path"],
)

# WebRTC/WS message volume
WEBRTC_MESSAGES_TOTAL = Counter(
    "spatial_os_webrtc_messages_total",
    "Total WebRTC/WebSocket messages processed",
    labelnames=["message_type"],
)

# Scene load latency
SCENE_LOAD_DURATION = Histogram(
    "spatial_os_scene_load_duration_seconds",
    "Time taken to load a USD scene",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

# Omniverse Kit process restarts
KIT_RESTARTS_TOTAL = Counter(
    "spatial_os_kit_process_restarts_total",
    "Number of times the Omniverse Kit process was restarted",
)

# Stream uptime tracking
STREAM_UPTIME = Gauge(
    "spatial_os_stream_uptime_seconds",
    "Seconds since the Omniverse stream was started",
)

# Camera update rate (messages per second per session)
CAMERA_UPDATES_TOTAL = Counter(
    "spatial_os_camera_updates_total",
    "Total camera move events received from clients",
)

# Prim selection events
PRIM_SELECTIONS_TOTAL = Counter(
    "spatial_os_prim_selections_total",
    "Total prim selection events",
)

# USD variant switch events
VARIANT_SWITCHES_TOTAL = Counter(
    "spatial_os_variant_switches_total",
    "Total USD variant switch events",
    labelnames=["prim_path"],
)

# WebSocket connection errors
WS_ERRORS_TOTAL = Counter(
    "spatial_os_ws_errors_total",
    "Total WebSocket errors",
    labelnames=["error_type"],
)


def make_metrics_app():
    """Return a Prometheus ASGI app to mount at /metrics."""
    return make_asgi_app()


def record_message(message_type: str):
    """Helper to increment the correct counter for a message type."""
    WEBRTC_MESSAGES_TOTAL.labels(message_type=message_type).inc()

    if message_type == "camera_move":
        CAMERA_UPDATES_TOTAL.inc()
    elif message_type == "select_prim":
        PRIM_SELECTIONS_TOTAL.inc()
    elif message_type == "set_variant":
        VARIANT_SWITCHES_TOTAL.labels(prim_path="unknown").inc()


def get_metrics_summary() -> dict:
    """Return a quick Python-side summary of current metric values."""
    return {
        "active_sessions": ACTIVE_SESSIONS._value.get(),
        "total_messages": sum(
            sample.value
            for metric in REGISTRY.collect()
            if metric.name == "spatial_os_webrtc_messages_total"
            for sample in metric.samples
        ),
    }

