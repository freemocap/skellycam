---
sidebar_position: 3
---
# Architecture

## System Overview

SkellyCam is a client-server application with two main components:

1. **Python Server** (`skellycam/`) — A FastAPI/Uvicorn server that manages cameras, captures frames, records video, and streams data over WebSocket.
2. **React/Electron UI** (`skellycam-ui/`) — A frontend that displays live camera feeds, provides configuration controls, and manages recordings.

```
┌──────────────────────────────────────────────────────────────┐
│                     React/Electron UI                        │
│  ┌─────────┐  ┌──────────────┐  ┌─────────────────────────┐ │
│  │  Redux   │  │  WebSocket   │  │   OffscreenCanvas       │ │
│  │  Store   │  │  Connection  │  │   Workers (per camera)  │ │
│  └─────────┘  └──────────────┘  └─────────────────────────┘ │
└──────────────────────────┬───────────────────────────────────┘
                           │ WebSocket (binary frames + JSON)
                           │ HTTP REST (camera control)
┌──────────────────────────▼───────────────────────────────────┐
│                     FastAPI Server                            │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  HTTP Router │  │  WebSocket   │  │  CameraGroup       │  │
│  │  (cameras,   │  │  Server      │  │  Manager           │  │
│  │   health,    │  │  (frames,    │  │  (singleton)       │  │
│  │   shutdown)  │  │   logs,      │  │                    │  │
│  │             │  │   state)     │  │                    │  │
│  └─────────────┘  └──────────────┘  └────────┬───────────┘  │
│                                               │              │
│  ┌────────────────────────────────────────────▼───────────┐  │
│  │                    CameraGroup                         │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │  │
│  │  │ CameraWorker │  │ CameraWorker │  │ Orchestrator │  │  │
│  │  │ (Process 1)  │  │ (Process 2)  │  │ (sync logic) │  │  │
│  │  └──────┬───────┘  └──────┬───────┘  └─────────────┘  │  │
│  │         │                 │                            │  │
│  │  ┌──────▼─────────────────▼───────────────────────┐    │  │
│  │  │        SharedMemory Ring Buffers               │    │  │
│  │  │   (zero-copy frame transfer between procs)     │    │  │
│  │  └────────────────────────────────────────────────┘    │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## Process Model

SkellyCam uses Python's `multiprocessing` module to run each camera in its own process. This avoids the GIL and ensures that slow cameras do not block fast ones. Frame-perfect synchronization is the system's primary design goal — every architectural decision serves it.

### Main Process

The main process runs the FastAPI/Uvicorn server and manages:

- **WorkerRegistry** — Tracks all spawned worker processes and provides a heartbeat mechanism for health monitoring.
- **CameraGroupManager** — Singleton that creates/destroys camera groups and routes API calls to the correct group.
- **WebSocket Server** — Sends synchronized multi-frame binary payloads (one image per camera per frame event) and JSON messages (logs, state, framerate updates) to connected clients.

### Camera Worker Processes

Each camera gets its own `CameraWorker` running in a separate `multiprocessing.Process`:

1. **OpenCV Capture Loop** — Calls `cv2.VideoCapture.grab()` and `.retrieve()` in a coordinated two-phase protocol, grabbing frames as fast as the camera allows.
2. **Frame Metadata** — Each frame is annotated with high-resolution `perf_counter_ns` timestamps at multiple lifecycle stages (pre-grab, post-grab, pre-retrieve, post-retrieve, etc.).
3. **Shared Memory Write** — The raw frame data is written to a shared memory ring buffer, making it available to the main process without copying.

### Frame Synchronization — The Core Protocol

The `CameraOrchestrator` enforces frame-perfect synchronization through a two-phase coordinated capture:

1. **Grab phase** — All camera workers call `cv2.VideoCapture.grab()` at the same moment. This latches the sensor image in the driver's buffer without transferring pixel data. Because `grab()` is fast (microseconds), the temporal spread across cameras is minimal.
2. **Barrier** — The orchestrator waits until every camera in the group has completed its grab.
3. **Retrieve phase** — Each worker calls `cv2.VideoCapture.retrieve()` to decode the latched frame into a numpy array.
4. **Assembly** — The orchestrator combines one frame from each camera into a single multi-frame payload. This payload is the atomic unit of data throughout the system — it is never split apart.

The result: consumers (WebSocket stream, video recorder, frontend) always see exactly one frame per camera per event, and all frames within an event share the same frame number. Recorded videos are guaranteed to have the same frame count.

**During recording**, each camera's `cv2.VideoWriter` runs in the camera's own process, writing frames in the order they are captured. Because the orchestrator ensures every camera produces exactly one frame per event, and recording starts and stops for all cameras at the same event boundary, the output videos are guaranteed to have identical frame counts.

**During playback**, the frontend uses a hybrid native-decode + authoritative-counter strategy. All `<video>` elements play via the browser's native `.play()` for smooth hardware-decoded rendering. A `requestAnimationFrame` loop maintains a single authoritative frame counter computed from wall-clock elapsed time × fps × playbackRate. Every few ticks, each video's `currentTime` is compared against the target — any camera drifting beyond ±0.5 frames is force-seeked back into alignment. When paused or frame-stepping, the system sets `video.currentTime` directly on all elements simultaneously. The frame number shown on every camera overlay comes from the authoritative counter, never from any individual video element, guaranteeing all cameras display the same frame at all times.

## Data Flow: Capture to Display

1. **Camera → SharedMemory** — Each camera worker writes its frame into a per-camera shared memory ring buffer.
2. **SharedMemory → MultiFrame buffer** — The orchestrator reads frames from all cameras and writes a synchronized multi-frame to a second shared memory buffer.
3. **MultiFrame → WebSocket** — The WebSocket server reads the latest multi-frame, JPEG-compresses each camera's image, and packs them into a binary payload.
4. **WebSocket → Frontend** — The binary payload is sent over WebSocket. The frontend parses the binary protocol, creates `ImageBitmap` objects, and renders to `OffscreenCanvas` via Web Workers.

## Data Flow: Recording

When recording is active:

1. Each camera worker writes frames directly to a `cv2.VideoWriter` in its own process.
2. Per-frame timestamps are accumulated in memory and flushed to CSV when recording stops.
3. After recording completes, the `RecordingFinalizer` processes the timestamp data, computes inter-camera synchronization statistics, and saves summary reports.

## IPC Mechanisms

### Shared Memory Ring Buffers

Frame data is transferred between processes using `multiprocessing.shared_memory.SharedMemory`. Ring buffers allow the producer (camera worker) and consumer (main process) to operate independently without blocking.

### PubSub

A lightweight publish/subscribe system built on `multiprocessing.Queue` is used for non-frame data like framerate updates and recording status changes.

### Global Kill Flag

A `multiprocessing.Value("b", False)` shared across all processes. When set to `True`, all camera workers and the server begin graceful shutdown.

## Frontend Architecture

The React UI uses:

- **Redux Toolkit** — Global state management for cameras, recording, framerate data, logs, and theme.
- **WebSocket Connection** — Persistent connection to the server with automatic reconnection and heartbeat.
- **FrameProcessor** — Parses the binary multi-frame protocol and creates `ImageBitmap` objects.
- **CanvasManager** — Manages `OffscreenCanvas` + `Worker` pairs for each camera, enabling GPU-accelerated rendering without blocking the main thread.
- **Frame-locked Playback** — The playback page uses native `.play()` for smooth hardware-decoded rendering. A `requestAnimationFrame` loop drives an authoritative frame counter (wall-clock × fps × rate) and periodically drift-corrects each `<video>` element back into alignment. When paused or frame-stepping, `video.currentTime` is set directly on all elements simultaneously. Frame overlays are updated via direct DOM manipulation to avoid React re-renders during playback.
- **Material UI** — Component library for the control panels, tree views, and layout.
