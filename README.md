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

### Recording

All cameras in a group are guaranteed to produce videos with precisely the same frame count. Each frame has high-resolution `perf_counter_ns` timestamps for post-hoc analysis of inter-camera timing.

### Streaming

The WebSocket protocol delivers synchronized multi-frame payloads — one image per camera per frame event, just like a single camera would deliver one image per frame, except you get multiple synchronized views.

### Playback

Recorded videos are played back with hard frame-lock — all videos always display the **exact same frame number**, no drift, no tolerance. The playback system provides:

- **Frame-perfect sync across all cameras** — a single authoritative frame counter drives all video elements; every camera view displays the identical frame number at all times
- **Per-camera frame overlay** — each camera view shows the current frame number (top-right), camera ID (bottom-left), and SMPTE-style timecode (bottom-right) burned into the viewport
- **Smooth native playback** — videos play using the browser's native hardware decoder (via `HTMLVideoElement.play()`) rather than per-frame seeking, eliminating choppiness
- **Drift correction** — a `requestAnimationFrame` monitoring loop periodically checks each video's `currentTime` against the authoritative wall-clock counter and force-resyncs any camera that drifts beyond ±0.5 frames
- **Frame-stepping** — arrow keys step forward/back by 1 frame (or 10 with Shift), with all cameras snapping to the target simultaneously
- **Variable-speed playback** — 0.1× to 8× speed with all cameras staying frame-locked at every rate
- **Keyboard shortcuts** — Space (play/pause), ←/→ (frame step), Shift+←/→ (10-frame step), Home/End (jump to start/end)

### Recording Browser

The recording browser lists all saved recording sessions with rich metadata:

- **Newest-first sorting** — recordings are ordered by timestamp (parsed from folder names), most recent on top
- **Per-recording stats** — camera count, total file size, duration, frame count, recording FPS, and relative time ("2h ago", "3d ago")
- **Manual path entry** — load any recording folder by typing or pasting its path
- **One-click load** — click a recording to immediately open it in the synced video player

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

### How Playback Synchronization Works

The playback system uses a hybrid native-decode + authoritative-counter strategy:

```
                    ┌─────────────────────────────┐
                    │   Authoritative Frame Counter │
                    │   (wall-clock × fps × rate)   │
                    └──────────┬──────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
        ┌──────────┐    ┌──────────┐     ┌──────────┐
        │ Camera 0 │    │ Camera 1 │     │ Camera N │
        │ <video>  │    │ <video>  │     │ <video>  │
        │ .play()  │    │ .play()  │     │ .play()  │
        └────┬─────┘    └────┬─────┘     └────┬─────┘
             │               │                 │
             ▼               ▼                 ▼
        drift check     drift check       drift check
        (±0.5 frames)   (±0.5 frames)    (±0.5 frames)
             │               │                 │
             └───── resync if needed ──────────┘
```

During playback, all `<video>` elements run via native `.play()` for smooth hardware-decoded rendering. A `requestAnimationFrame` loop maintains a single authoritative frame counter computed from `wall-clock elapsed time × fps × playbackRate`. Every few ticks, each video's `currentTime` is compared against the target — any camera drifting beyond ±0.5 frames is force-seeked back into alignment.

The frame number shown on every camera overlay comes from this authoritative counter, **never** from any individual video element, guaranteeing all cameras display the same frame at all times.

When paused or frame-stepping, the system sets `video.currentTime` directly on all elements simultaneously (no native `.play()` involved), which is perfectly fine for single-frame operations.

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

### Playing Back Recordings

1. Navigate to the **Playback** page (slideshow icon in the sidebar)
2. The recording browser lists all sessions from `~/skellycam_data/recordings/`, newest first
3. Click a recording to load it — or type a custom folder path
4. All camera streams open in a synchronized grid with frame overlays
5. Use transport controls or keyboard shortcuts to play, pause, seek, and step through frames

---

## API Endpoints

| Method   | Path                                        | Description                                          |
|----------|---------------------------------------------|------------------------------------------------------|
| `GET`    | `/health`                                   | Server health check                                  |
| `GET`    | `/shutdown`                                 | Graceful server shutdown                             |
| `POST`   | `/skellycam/camera/detect`                  | Detect available cameras                             |
| `POST`   | `/skellycam/camera/group/apply`             | Create or update camera group                        |
| `POST`   | `/skellycam/camera/group/all/record/start`  | Start recording all groups                           |
| `GET`    | `/skellycam/camera/group/all/record/stop`   | Stop recording all groups                            |
| `DELETE` | `/skellycam/camera/group/close/all`         | Close all camera groups                              |
| `GET`    | `/skellycam/camera/group/all/pause_unpause` | Toggle pause on all groups                           |
| `GET`    | `/skellycam/playback/recordings`            | List recordings (with stats: size, frames, fps, etc.)|
| `POST`   | `/skellycam/playback/load`                  | Load a recording for playback                        |
| `GET`    | `/skellycam/playback/videos`                | List currently loaded videos                         |
| `GET`    | `/skellycam/playback/video/{video_id}`      | Stream a video file (HTTP range requests)            |
| `GET`    | `/skellycam/playback/timestamps/{video_id}` | Get timestamp CSV metadata for a video               |
| `WS`     | `/skellycam/websocket/connect`              | WebSocket for live frames and logs                   |

### Playback API Details

**`GET /skellycam/playback/recordings`** returns an array of recording entries, each containing:

| Field              | Type            | Description                                     |
|--------------------|-----------------|-------------------------------------------------|
| `name`             | `string`        | Folder name (typically an ISO timestamp)         |
| `path`             | `string`        | Absolute path to the recording folder            |
| `video_count`      | `int`           | Number of camera video files                     |
| `total_size_bytes` | `int`           | Combined size of all video files                 |
| `created_timestamp`| `string | null` | ISO 8601 timestamp of folder creation            |
| `total_frames`     | `int | null`    | Frame count (from timestamp CSVs if available)   |
| `duration_seconds` | `float | null`  | Recording duration in seconds                    |
| `fps`              | `float | null`  | Effective framerate                              |

Recordings are returned sorted newest-first by folder name.

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
│   ├── http/playback/       # Recording playback (HTTP video serving + metadata)
│   │   └── playback_router.py  # /recordings, /load, /video/{id}, /timestamps/{id}
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
│   ├── pages/
│   │   ├── CamerasPage.tsx     # Live camera view
│   │   ├── PlaybackPage.tsx    # Recording browser → synced video player
│   │   └── WelcomePage.tsx     # Landing page
│   ├── components/
│   │   ├── playback/
│   │   │   ├── SyncedVideoPlayer.tsx  # Frame-locked multi-video player
│   │   │   ├── PlaybackControls.tsx   # Transport bar (play, seek, step, speed)
│   │   │   └── RecordingBrowser.tsx   # Recording list with stats + manual path
│   │   ├── camera-views/       # Live camera grid
│   │   ├── camera-config-*/    # Camera configuration panels
│   │   └── framerate-viewer/   # Real-time FPS charts
│   ├── services/               # WebSocket, frame processing, server URLs
│   ├── store/                  # Redux state (cameras, recording, videos, etc.)
│   └── layout/                 # App shell, routing, panel layout
└── electron/                   # Desktop app wrapper (main + preload)
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
