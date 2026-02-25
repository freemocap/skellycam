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

SkellyCam is the camera backend for the [FreeMoCap](https://github.com/freemocap/freemocap) markerless motion capture project.

### Key Features

- **Synchronized recording** — all cameras produce videos with precisely the same frame count, with high-resolution `perf_counter_ns` timestamps for post-hoc analysis
- **Live streaming** — WebSocket protocol delivers synchronized multi-frame payloads (one image per camera per frame event) in real time
- **Frame-locked playback** — recorded videos always display the exact same frame number across all cameras, with frame-stepping, variable-speed, and keyboard shortcuts
- **Audio capture** — optional microphone recording alongside video
- **Recording browser** — browse saved sessions with metadata (camera count, file size, duration, FPS, frame count), sorted newest-first
- **Internationalization** — UI available in 36+ languages ([help us translate!](TRANSLATING.md))

---

## Quick Start

### Prerequisites

- [Python 3.11+](https://www.python.org/downloads/) (3.12 recommended)
- [uv](https://github.com/astral-sh/uv) — fast Python package manager
- [Node.js 18+](https://nodejs.org/) — for the UI
- USB cameras or built-in webcams

### Install & Run

```bash
# Clone and install the Python server
git clone https://github.com/freemocap/skellycam
cd skellycam
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv sync

# Start the server
python -m skellycam
# or just: skellycam

# In another terminal — install and start the UI
cd skellycam-ui
npm install
npm run dev
```

Server starts on `http://localhost:53117`. Swagger docs at `http://localhost:53117/docs`.

#### Linux Only

Audio recording requires additional system packages:

```bash
sudo apt update && sudo apt install clang portaudio19-dev
```

---

## How It Works

Each camera runs in its own OS process to avoid the GIL. The `CameraOrchestrator` enforces synchronization through a two-phase capture protocol:

1. **Grab** — all cameras call `cv2.VideoCapture.grab()` simultaneously, latching sensor images in driver buffers without transferring pixel data
2. **Retrieve** — after all cameras have grabbed, each calls `cv2.VideoCapture.retrieve()` to decode the latched frame

The orchestrator assembles one frame from each camera into a single multi-frame payload — the atomic unit of data throughout the system. Consumers (WebSocket stream, video recorder, frontend) always see exactly one frame per camera per event.

For the full architecture (process model, IPC, data flow, playback sync), see the [Architecture docs](docs/architecture.md).

---

## Documentation

| Page | Description |
|------|-------------|
| [Getting Started](docs/getting-started.md) | Installation, first run, and basic workflow |
| [Architecture](docs/architecture.md) | Synchronization protocol, process model, data flow |
| [API Reference](docs/api-reference.md) | HTTP and WebSocket endpoint documentation |
| [WebSocket Protocol](docs/websocket-protocol.md) | Binary frame format, JSON messages, backpressure |
| [Configuration](docs/configuration.md) | Server settings, camera config, data directories, telemetry |
| [Development](docs/development.md) | Testing, linting, CI, and contributing |

---

## API at a Glance

| Method   | Path                                        | Description                        |
|----------|---------------------------------------------|------------------------------------|
| `GET`    | `/health`                                   | Health check                       |
| `GET`    | `/shutdown`                                 | Graceful shutdown                  |
| `POST`   | `/skellycam/camera/detect`                  | Detect available cameras           |
| `GET`    | `/skellycam/camera/microphone/detect`       | Detect available microphones       |
| `POST`   | `/skellycam/camera/group/apply`             | Create or update camera group      |
| `POST`   | `/skellycam/camera/group/all/record/start`  | Start recording                    |
| `GET`    | `/skellycam/camera/group/all/record/stop`   | Stop recording                     |
| `DELETE` | `/skellycam/camera/group/close/all`         | Close all camera groups            |
| `GET`    | `/skellycam/camera/group/all/pause_unpause` | Toggle pause                       |
| `GET`    | `/skellycam/playback/recordings`            | List recordings with stats         |
| `POST`   | `/skellycam/playback/load`                  | Load a recording for playback      |
| `GET`    | `/skellycam/playback/videos`                | List loaded videos                 |
| `GET`    | `/skellycam/playback/video/{video_id}`      | Stream a video file                |
| `GET`    | `/skellycam/playback/timestamps/{video_id}` | Get timestamp metadata             |
| `WS`     | `/skellycam/websocket/connect`              | Real-time frames and logs          |

Full details in the [API Reference](docs/api-reference.md).

---

## Development

```bash
uv sync --group dev                     # Install dev dependencies
uv run pytest skellycam/tests/ -v       # Run tests
uv run ruff check skellycam/            # Lint
uv run poe test                         # Via task runner
```

See the [Development guide](docs/development.md) for the full setup.

---

## License

**AGPL-3.0-or-later** — see [LICENSE](LICENSE). Contact the FreeMoCap team for alternative licensing.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Translations welcome — see [TRANSLATING.md](TRANSLATING.md).
