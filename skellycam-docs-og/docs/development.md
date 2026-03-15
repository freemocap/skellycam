---
sidebar_position: 7
---
# Development

## Setting Up the Development Environment

```bash
git clone https://github.com/freemocap/skellycam
cd skellycam
uv venv
source .venv/bin/activate
uv sync --group dev
```

This installs runtime dependencies plus development tools: pytest, pytest-asyncio, ruff, poethepoet, and build tools.

## Running Tests

### Backend (Python)

```bash
# Run all tests
uv run pytest skellycam/tests/ -v

# Run a specific test file
uv run pytest skellycam/tests/test_health.py -v

# Run with short tracebacks
uv run pytest skellycam/tests/ -v --tb=short
```

The test suite uses a lightweight FastAPI `TestClient` with mocked camera dependencies. No physical cameras are required.

:::note
`asyncio_mode = "auto"` is set in `pyproject.toml`, so async test functions do not need the `@pytest.mark.asyncio` decorator.
:::

### Test Structure

```
skellycam/tests/
├── conftest.py                            # Shared fixtures (mock app, client, mock managers)
├── mocks/
│   ├── camera_mock.py                     # MockVideoCapture (simulates cv2.VideoCapture)
│   └── test_camera_mock.py                # Tests for the mock itself
├── test_camera_config.py                  # CameraConfig model logic
├── test_camera_config_extended.py         # Extended config tests
├── test_camera_group_manager.py           # CameraGroupManager creation and singleton
├── test_camera_orchestrator.py            # Orchestrator synchronization tests
├── test_camera_router.py                  # Camera REST endpoint tests
├── test_frontend_payload_and_recording.py # Binary payload creation and recording tests
├── test_health.py                         # Health and root endpoint tests
├── test_playback.py                       # Playback endpoint tests
├── test_pubsub.py                         # IPC publish/subscribe tests
├── test_shared_memory.py                  # Shared memory ring buffer tests
├── test_shutdown.py                       # Shutdown endpoint tests
├── test_timestamps_and_framerate.py       # Timestamp and framerate tracking tests
├── test_websocket.py                      # WebSocket connection and protocol tests
├── test_websocket_internals.py            # WebSocket server internal logic tests
└── test_worker_lifecycle.py               # Worker process lifecycle tests
```

### Key Test Fixtures (conftest.py)

- `mock_camera_group_manager` — A MagicMock standing in for CameraGroupManager with AsyncMock async methods. Patches `get_or_create_camera_group_manager` at all import sites.
- `app` — A lightweight FastAPI app with the same routes but no heavy lifespan (no bytecode compilation, no logging setup).
- `client` — A synchronous `TestClient` wrapping the test app, suitable for both HTTP and WebSocket tests.

### Frontend (TypeScript)

```bash
cd skellycam-ui

# Type checking
npx tsc --noEmit

# End-to-end tests (requires Electron)
npm run e2e
```

## Linting

SkellyCam uses [Ruff](https://docs.astral.sh/ruff/) for linting, configured in `pyproject.toml`.

```bash
# Check for lint issues
uv run ruff check skellycam/

# Auto-fix lint issues
uv run ruff check --fix skellycam/
```

The primary lint rule enabled is `TC` (flake8-type-checking), which moves type-only imports behind `if TYPE_CHECKING:` blocks. This reduces import time for spawned child processes.

### Suppressing False Positives

If Ruff tries to move an import that is needed at runtime (e.g., used in `isinstance()`, `TypeAdapter`, or Pydantic field types), add a `# noqa: TC001/TC002/TC003` comment:

```python
from skellycam.core.camera.config.camera_config import CameraConfig  # noqa: TC003
```

## Task Runner

[poethepoet](https://github.com/nat-n/poethepoet) provides shorthand task commands:

```bash
uv run poe test        # Run pytest
uv run poe lint        # Run ruff check
uv run poe lint-fix    # Auto-fix ruff violations
uv run poe tc-check    # Preview TYPE_CHECKING import moves
uv run poe tc-fix      # Apply TYPE_CHECKING import moves
uv run poe tc          # Apply imports + run tests to verify
```

## Continuous Integration

GitHub Actions runs on every push and pull request (`.github/workflows/test.yml`):

- **Backend tests** — Python 3.11 and 3.12 on Ubuntu, Windows, and macOS
- **Linting** — Ruff check on all platforms
- **Frontend typecheck** — TypeScript `tsc --noEmit` on Ubuntu

## Code Organization Conventions

### Python

- **Type hints everywhere** — All function signatures, return types, and variables should have type annotations.
- **New-style type hints** — Use `str | None` instead of `Optional[str]`, `dict[str, int]` instead of `Dict[str, int]`.
- **Global imports only** — No local imports inside functions or methods.
- **Fail loudly** — Raise exceptions on errors instead of printing warnings or returning defaults.
- **Pydantic models** — Used for all API request/response schemas and configuration objects.
- **Logging** — Uses [skellylogs](https://github.com/freemocap/skellylogs) with custom levels like `logger.trace()`, `logger.success()`, and `logger.api()`.

### TypeScript (Frontend)

- **React 19** functional components with hooks
- **Redux Toolkit** for state management with typed hooks
- **Material UI** for component styling
- **OffscreenCanvas workers** for live camera frame rendering
- **Frame-locked playback** — recorded videos use a leader-based synchronization strategy: the first video drives canonical time via its native `.play()`, a `requestAnimationFrame` loop reads `leader.currentTime` to derive the frame number, and follower videos are drift-corrected when they diverge beyond 2 frames. Overlays are updated via direct DOM refs to avoid React re-renders during playback.

## Adding a New API Endpoint

1. Create a new router file in the appropriate `skellycam/api/http/` subdirectory.
2. Define your Pydantic request/response models.
3. Add the router to `skellycam/api/routers.py`:
   ```python
   from skellycam.api.http.your_module.your_router import your_router
   SKELLYCAM_ROUTERS = [..., your_router]
   ```
4. Write tests in `skellycam/tests/test_your_router.py` using the `client` fixture from `conftest.py`.

## Adding a New Test

1. Create a test file in `skellycam/tests/test_*.py`.
2. Use the `client` fixture for HTTP/WebSocket endpoint tests.
3. Use `mock_camera_group_manager` for tests that need to interact with camera management.
4. Async test functions work automatically — no decorator needed (`asyncio_mode = "auto"`).

## Building Installers

### Python Executable (Nuitka)

```bash
cd skellycam-ui
..\installers\nuitka_scripts\nuitka_installer_windows.bat
```

This produces a standalone executable (build takes ~1 hour).

### Electron App

```bash
cd skellycam-ui
npm install && npm run build
```

See `electron-builder.json` for packaging configuration.
