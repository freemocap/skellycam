# Configuration

## Server Settings

Server network configuration is defined in `skellycam/api/server_constants.py`:

```python
PROTOCOL = "http"
HOSTNAME = "localhost"
PORT = 53117
APP_URL = f"{PROTOCOL}://{HOSTNAME}:{PORT}"
```

To change the server port, edit `PORT` before starting the server. The frontend UI must be configured to connect to the same host and port.

## Camera Configuration

Each camera in a group has its own `CameraConfig` with the following settings:

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `camera_id` | `str` | `"0"` | Unique identifier for the camera |
| `resolution_width` | `int` | `1280` | Capture width in pixels |
| `resolution_height` | `int` | `720` | Capture height in pixels |
| `framerate` | `int` | `30` | Target capture framerate |
| `exposure` | `int` | `-5` | Camera exposure value (hardware-dependent) |
| `rotation` | `int` | `0` | Image rotation: 0, 90, 180, or 270 degrees |

Camera configuration is applied via the `POST /skellycam/camera/group/apply` endpoint or through the UI's camera configuration panel.

### Resolution

The requested resolution may not match the actual resolution if the camera does not support it. OpenCV will silently fall back to the nearest supported resolution. The actual resolution is reported back in the response.

### Exposure

Exposure values are hardware-dependent. Common USB webcams use negative integer values (e.g., -5, -7, -10) where more negative means shorter exposure time. The valid range depends on the camera model.

### Rotation

Rotation is applied in software after frame capture. The options are:

| Value | Rotation |
|-------|----------|
| `0` | No rotation |
| `1` | 90° clockwise |
| `2` | 180° |
| `3` | 90° counter-clockwise |

## Data Directories

All SkellyCam data is stored under `~/skellycam_data/` by default. This base directory is defined in `skellycam/system/default_paths.py`.

### Directory Structure

```
~/skellycam_data/
├── recordings/
│   └── 2024-09-15T14_30_00/          # One folder per recording session
│       ├── 2024-09-15T14_30_00_info.json   # Recording metadata
│       └── synchronized_videos/
│           ├── *.camera0.mp4               # Video file per camera
│           ├── *.camera1.mp4
│           └── timestamps/
│               ├── *_timestamps.csv        # Multi-frame timestamps
│               ├── *_stats.txt             # Human-readable statistics
│               ├── *_stats.json            # Machine-readable statistics
│               └── camera_timestamps/
│                   ├── *.camera0.timestamps.csv
│                   └── *.camera1.timestamps.csv
└── logs_info_and_settings/
    └── logs/
        └── log_*.log                       # Timestamped log files
```

### Recording Metadata

The `_info.json` file contains the recording configuration including camera settings, recording name, UUID, and start timestamp.

### Timestamp CSVs

Per-camera timestamp files contain one row per frame with high-resolution `perf_counter_ns` timestamps at each lifecycle stage. The multi-frame timestamp file contains inter-camera synchronization data.

## Logging Configuration

SkellyCam uses custom log levels defined in `skellycam/system/logging_configuration/log_levels.py`:

| Level | Value | Description |
|-------|-------|-------------|
| `LOOP` | 3 | Logs inside tight loops (debug only) |
| `TRACE` | 5 | Low-level debug information |
| `DEBUG` | 10 | Standard debug output |
| `INFO` | 20 | General information |
| `SUCCESS` | 22 | Operation completed successfully |
| `API` | 25 | API request/response logging |
| `WARNING` | 30 | Unexpected but non-fatal conditions |
| `ERROR` | 40 | Errors |

The default log level is `TRACE`. Logs at `TRACE` level and above are forwarded to connected WebSocket clients for display in the UI's log terminal.

To change the log level, edit `LOG_LEVEL` in `skellycam/__init__.py`:

```python
LOG_LEVEL = LogLevels.TRACE  # Change to LogLevels.INFO for less verbose output
```
