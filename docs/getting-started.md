# Getting Started

## Prerequisites

- **Python 3.10+** — [python.org/downloads](https://www.python.org/downloads/)
- **uv** — Fast Python package manager: [astral.sh/uv](https://github.com/astral-sh/uv)
- **Node.js 18+** — Required for the React/Electron UI: [nodejs.org](https://nodejs.org/)
- **USB cameras or built-in webcams**

## Installing the Python Server

```bash
git clone https://github.com/freemocap/skellycam
cd skellycam
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv sync
```

To install development dependencies (pytest, ruff, etc.):

```bash
uv sync --group dev
```

### Linux-Specific Dependencies

Audio recording on Linux requires additional system packages:

```bash
sudo apt update
sudo apt install clang portaudio19-dev
```

## Installing the Frontend UI

```bash
cd skellycam-ui
npm install
```

## Running SkellyCam

### Step 1: Start the Python Server

```bash
python -m skellycam
```

The server starts on `http://localhost:53117`. You can verify it is running by visiting `http://localhost:53117/health` in your browser — you should see `"Hello👋"`.

The interactive Swagger API documentation is at `http://localhost:53117/docs`.

### Step 2: Start the UI (Development Mode)

In a separate terminal:

```bash
cd skellycam-ui
npm run dev
```

This launches the Vite dev server. If running inside Electron, it launches the Electron window; otherwise, open the URL printed in the terminal.

## First Session Workflow

1. **Detect cameras** — The UI or a `POST /skellycam/camera/detect` call scans for available USB cameras.
2. **Create camera group** — Select cameras and configure resolution/framerate/exposure via the UI or `POST /skellycam/camera/group/apply`.
3. **Live preview** — The WebSocket connection streams frames to the UI in real time.
4. **Record** — Click record or `POST /skellycam/camera/group/all/record/start` to begin recording. Stop with the stop button or `GET /skellycam/camera/group/all/record/stop`.
5. **Review** — Recordings are saved under `~/skellycam_data/recordings/` with synchronized video files and timestamp CSVs. Use the Playback page to review recordings with frame-locked multi-video playback — all videos always display the same frame number.

## Verifying the Installation

Run the test suite to confirm everything is wired up correctly:

```bash
uv run pytest skellycam/tests/ -v
```

All tests should pass without requiring physical cameras — the test suite uses mocks and a lightweight FastAPI test client.
