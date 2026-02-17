# SkellyCam Documentation 💀📸

SkellyCam turns cheap USB webcams into a frame-perfect synchronized multi-camera system. It is the camera backend for the [FreeMoCap](https://github.com/freemocap/freemocap) motion capture project.

## What Makes SkellyCam Different

Most multi-camera setups suffer from inter-camera drift — cameras run on independent clocks, so frame N from camera A does not correspond to frame N from camera B. SkellyCam solves this with a two-phase coordinated capture protocol (grab, then retrieve) that ensures every "multi-frame" event contains one image from every camera captured at the same wall-clock instant.

**The guarantees:**

- All recorded videos have **precisely the same frame count**
- Each multi-frame payload delivered over WebSocket contains **exactly one image per camera** for that frame event
- Playback of recorded videos is **hard frame-locked** — all videos always display the same frame number, no drift, no tolerance

## Documentation

| Page | Description |
|------|-------------|
| [Getting Started](getting-started.md) | Installation, first run, and basic usage |
| [Architecture](architecture.md) | Synchronization protocol, process model, data flow |
| [API Reference](api-reference.md) | HTTP and WebSocket endpoint documentation |
| [WebSocket Protocol](websocket-protocol.md) | Binary frame format, JSON messages, backpressure |
| [Configuration](configuration.md) | Server settings, camera config, data directories |
| [Development](development.md) | Testing, linting, CI, and contributing guidelines |

## Quick Start

```bash
git clone https://github.com/freemocap/skellycam
cd skellycam
uv venv && source .venv/bin/activate
uv sync

python -m skellycam          # Start server on localhost:53117

# In another terminal:
cd skellycam-ui
npm install && npm run dev   # Start UI
```
