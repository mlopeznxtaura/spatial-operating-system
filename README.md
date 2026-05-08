# Spatial Operating System

**Cluster 04 — NextAura, Inc.**

> An OpenUSD-native app platform where the UI is a room, not a window.

## Overview

A spatial computing platform where the user's physical space replaces the desktop. Panels, documents, and tools exist as 3D objects anchored in a room. Multiple users share the same scene in real-time. OpenUSD is the scene graph and document format. NVIDIA Omniverse streams RTX-rendered USD scenes via WebRTC. ARKit + visionOS bring it to Apple hardware. MediaPipe + ONNX handle hand and gaze tracking. LiveKit manages real-time voice. PhysX + Warp add physics to UI elements.

## SDKs in This Cluster (20)

- OpenUSD
- NVIDIA Omniverse SDK
- Apple visionOS SDK
- ARKit SDK
- OpenXR SDK
- WebXR API
- React Three Fiber
- Three.js
- NVIDIA Warp
- NVIDIA PhysX SDK
- Babylon.js XR
- LiveKit SDK
- ONNX Runtime
- MediaPipe Tasks
- Framer Motion
- Zustand
- FastAPI
- Supabase SDK
- Socket.io SDK
- A-Frame

## Architecture

```
[USD Scene Graph] <-> [Omniverse Kit Server (RTX)]
        |                        |
   [OpenUSD]              [WebRTC Stream]
        |                        |
[React Three Fiber]      [Browser Client]
        |
[WebXR / ARKit / visionOS]
        |
[MediaPipe Hand/Gaze Tracking]
        |
[LiveKit Voice] + [Supabase Realtime State] + [Socket.io Events]
```

## File Structure

```
spatial-os/
  scene/
    usd_loader.py          # Load + compose .usda scenes via OpenUSD
    omniverse_stream.py    # Omniverse Kit WebRTC streaming server
    scene_sync.py          # Multi-user scene state sync
  client/
    src/
      App.jsx              # React Three Fiber spatial shell
      xr/
        XRSession.jsx      # WebXR session manager
        HandTracking.jsx   # MediaPipe hand + gaze input
      panels/
        SpatialPanel.jsx   # 3D UI panel component
        PanelManager.jsx   # Panel layout in 3D space
      physics/
        PhysicsWorld.jsx   # PhysX + Warp physics layer
      voice/
        VoiceRoom.jsx      # LiveKit spatial voice
      store/
        sceneStore.js      # Zustand scene state
  api/
    server.py              # FastAPI backend
    routes.py              # Scene, session, sync routes
  telemetry/
    metrics.py             # Prometheus metrics
  main.py                  # Entry point
```

## Start Here

Research what it takes to load a `.usda` file in Three.js. Understand the USD subset safe for web rendering before writing any code.

**Recommended path:** `@needle-tools/usd` (WASM-backed Three.js Hydra delegate) for USD loading. React Three Fiber + `@react-three/xr` for the spatial UI layer. Zustand for scene state.

## Part of the 500 SDKs / 25 Clusters Series

NextAura, Inc. — Marco Lopez — github.com/mlopeznxtaura
