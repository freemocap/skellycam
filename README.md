<p align="center">
    <img src="https://github.com/user-attachments/assets/55dea5bb-6823-4773-b41e-a43a4d84c2ba" height="240" alt="SkellyCam Logo">
</p>

<h3 align="center">SkellyCam</h3>
<p align="center">Frame-perfect multi-camera synchronization for USB webcams 💀📸</p>
<p align="center">
    <a href="https://github.com/freemocap/skellycam/releases/latest">
        <img src="https://img.shields.io/github/release/freemocap/skellycam.svg" alt="Latest Release">
    </a>
    <a href="https://github.com/freemocap/skellycam/blob/main/LICENSE">
        <img src="https://img.shields.io/badge/license-AGPLv3+-blue.svg" alt="AGPLv3+">
    </a>
    <a href="https://github.com/freemocap/skellycam/actions/workflows/test.yml">
        <img src="https://github.com/freemocap/skellycam/actions/workflows/test.yml/badge.svg" alt="Tests">
    </a>
</p>

---

## What SkellyCam Does

SkellyCam turns a handful of cheap USB webcams into a synchronized multi-camera system. It guarantees **frame-perfect synchronization** — every camera produces the exact same number of frames, and each "multi-frame" event delivers one image from every camera captured at the same moment. This makes it suitable for applications like markerless motion capture, 3D reconstruction, and multi-view computer vision where frame-number identity across cameras is non-negotiable.

**Recording:** All cameras in a group are guaranteed to produce videos with precisely the same frame count. Each frame has high-resolution `perf_counter_ns` timestamps for post-hoc analysis of inter-camera timing.

**Streaming:** The WebSocket protocol delivers synchronized multi-frame payloads — one image per camera per frame event, just like a single camera would deliver one image per frame, except you get multiple synchronized views.

**Playback:** Recorded videos are played back with hard frame-lock — all videos always display the same frame number, no drift, no tolerance. Frame-step, seek, and variable-speed playback all maintain frame-number identity across all cameras.

---

## Architecture

```
┌──────────────────┐         WebSocket (binary frames + JSON)         ┌──────────────────┐
│   Python Server  │ ◄──────────────────────────────────────────────► │  React/Electron  │
│  (FastAPI/Uvicorn│         HTTP REST (camera control, config)       │       UI         │
│   + OpenCV)      │ ◄──────────────────────────────────────────────► │                  │
└──────────────────┘                                                  └──────────────────┘
        │
        ├── CameraGroupManager (singleton)
        │     └── CameraGroup
        │           ├── CameraWorker (1 per camera, separate process)
        │           │     └── OpenCV capture loop
        │           ├── CameraOrchestrator (coordinated grab/retrieve)
        │           └── SharedMemory ring buffers (zero-copy IPC)
        │
        ├── WorkerRegistry (process lifecycle management)
        └── RecordingManager (video files + timestamp CSVs)
```

### How Synchronization Works

Each camera runs in its own OS process to avoid the GIL and ensure no camera blocks another. The `CameraOrchestrator` enforces synchronization through a two-phase capture protocol:

1. **Grab phase** — All camera workers call `cv2.VideoCapture.grab()` simultaneously. This latches the sensor image in the driver buffer without transferring pixel data.
2. **Retrieve phase** — After all cameras have grabbed, each worker calls `cv2.VideoCapture.retrieve()` to decode the latched frame.

Because the grab happens at nearly the same wall-clock instant across all cameras, the resulting images are temporally aligned. The orchestrator assembles one frame from each camera into a single multi-frame payload, guaranteeing every consumer (WebSocket stream, video recorder) always sees exactly one frame per camera per event.

During recording, each camera's `cv2.VideoWriter` runs in the same process as its capture loop, ensuring the write order matches the capture order. The result: all output videos have precisely the same frame count.

---

## Installation

### Prerequisites

- [Python 3.10–3.12](https://www.python.org/downloads/)
- [uv](https://github.com/astral-sh/uv) — fast Python package manager
- [Node.js 18+](https://nodejs.org/) — for the UI
- USB cameras or built-in webcams

### Python Server

```bash
git clone https://github.com/freemocap/skellycam
cd skellycam
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv sync                     # Runtime deps
uv sync --group dev         # + dev deps (pytest, ruff, etc.)
```

#### Linux only

```bash
sudo apt update && sudo apt install clang portaudio19-dev
```

### React/Electron UI

```bash
cd skellycam-ui
npm install
```

---

## Usage

### Start the Server

```bash
python -m skellycam
```

Server starts on `http://localhost:53117`. Swagger docs at `http://localhost:53117/docs`.

### Start the UI

```bash
cd skellycam-ui
npm run dev
```

---

## API Endpoints

| Method   | Path                                        | Description                    |
|----------|---------------------------------------------|--------------------------------|
| `GET`    | `/health`                                   | Server health check            |
| `GET`    | `/shutdown`                                 | Graceful server shutdown       |
| `POST`   | `/skellycam/camera/detect`                  | Detect available cameras       |
| `POST`   | `/skellycam/camera/group/apply`             | Create or update camera group  |
| `POST`   | `/skellycam/camera/group/all/record/start`  | Start recording all groups     |
| `GET`    | `/skellycam/camera/group/all/record/stop`   | Stop recording all groups      |
| `DELETE` | `/skellycam/camera/group/close/all`         | Close all camera groups        |
| `GET`    | `/skellycam/camera/group/all/pause_unpause` | Toggle pause on all groups     |
| `GET`    | `/skellycam/playback/recordings`            | List available recordings      |
| `POST`   | `/skellycam/playback/load`                  | Load a recording for playback  |
| `GET`    | `/skellycam/playback/video/{video_id}`      | Stream a video file (HTTP range) |
| `WS`     | `/skellycam/websocket/connect`              | WebSocket for frames and logs  |

---

## Development

```bash
uv run pytest skellycam/tests/ -v       # Run tests
uv run ruff check skellycam/            # Lint
uv run ruff check --fix skellycam/      # Auto-fix
uv run poe test                         # Via task runner
```

### Project Structure

```
skellycam/
├── __main__.py              # Entry point — starts uvicorn
├── app.py                   # FastAPI app factory
├── api/
│   ├── http/cameras/        # Camera control REST endpoints
│   ├── http/playback/       # Recording playback (HTTP video serving)
│   └── websocket/           # Real-time frame streaming
├── core/
│   ├── camera/              # CameraConfig, CameraWorker, OpenCV loop
│   ├── camera_group/        # CameraGroup, CameraOrchestrator, timestamps
│   ├── ipc/                 # Shared memory, pubsub, process management
│   └── recorders/           # Video recording, framerate tracking
├── system/                  # Logging, paths, diagnostics
└── tests/                   # Pytest test suite

skellycam-ui/
├── src/
│   ├── components/playback/ # Frame-locked multi-video player
│   ├── components/camera-*  # Live camera UI
│   ├── services/            # WebSocket, frame processing
│   └── store/               # Redux state
└── electron/                # Desktop app wrapper
```

---

## Building Installers

```bash
# 1. Build Python executable (Nuitka, ~1 hour)
cd skellycam-ui
..\installers\nuitka_scripts\nuitka_installer_windows.bat

# 2. Build Electron app
npm install && npm run build
```

---

## License

**AGPL-3.0-or-later** — see [LICENSE](LICENSE). Contact the FreeMoCap team for alternative licensing.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
