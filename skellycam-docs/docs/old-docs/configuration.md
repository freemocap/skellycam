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
| `camera_id` | `str` | `"000"` | Unique identifier for the camera |
| `resolution` | `object` | `{"width": 1280, "height": 720}` | Capture resolution in pixels |
| `framerate` | `float` | `-1` | Target capture framerate (`-1` uses camera default) |
| `exposure` | `int` | `-7` | Camera exposure value (hardware-dependent) |
| `exposure_mode` | `str` | `"MANUAL"` | Exposure mode: `MANUAL`, `AUTO`, or `RECOMMENDED` |
| `rotation` | `int` | `-1` | Image rotation (see table below) |
| `capture_fourcc` | `str` | `"MJPG"` | FOURCC code for capture codec |
| `writer_fourcc` | `str` | `"X264"` | FOURCC code for recording codec |

Camera configuration is applied via the `POST /skellycam/camera/group/apply` endpoint or through the UI's camera configuration panel.

### Resolution

Resolution is specified as a nested object with `width` and `height` fields:

```json
{
  "resolution": { "width": 1280, "height": 720 }
}
```

The requested resolution may not match the actual resolution if the camera does not support it. OpenCV will silently fall back to the nearest supported resolution. The actual resolution is reported back in the response.

### Framerate

Set `framerate` to `-1` (the default) to use the camera's native framerate and run the frame loop as fast as the hardware allows. Set a positive value (e.g., `30`) to target a specific capture rate.

### Exposure

Exposure values are hardware-dependent. Common USB webcams use negative integer values (e.g., -5, -7, -10) where more negative means shorter exposure time. The valid range depends on the camera model.

### Rotation

Rotation is applied in software after frame capture. The values correspond to OpenCV's `cv2.rotate()` codes:

| Value | Rotation |
|-------|----------|
| `-1` | No rotation (default) |
| `0` | 90° clockwise |
| `1` | 180° |
| `2` | 90° counter-clockwise |

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
├── logs_info_and_settings/
│   └── logs/
│       └── log_*.log                       # Timestamped log files
├── telemetry_config.json                   # Telemetry opt-in/opt-out
└── telemetry_uid                           # Anonymous user ID for telemetry
```

### Recording Metadata

The `_info.json` file contains the recording configuration including camera settings, recording name, UUID, and start timestamp.

### Timestamp CSVs

Per-camera timestamp files contain one row per frame with high-resolution `perf_counter_ns` timestamps at each lifecycle stage. The multi-frame timestamp file contains inter-camera synchronization data.

## Logging

SkellyCam uses [skellylogs](https://github.com/freemocap/skellylogs) for logging, which provides custom log levels and WebSocket log forwarding. The log level is set in `skellycam/__init__.py`:

```python
LOG_LEVEL = LogLevels.TRACE  # Change to LogLevels.INFO for less verbose output
```

Logs at `TRACE` level and above are forwarded to connected WebSocket clients for display in the UI's log terminal.

For details on log levels, handlers, and configuration options, see the [skellylogs repository](https://github.com/freemocap/skellylogs).

## Telemetry

SkellyCam collects anonymous usage telemetry to help the development team understand how the software is used. Telemetry is managed by the [skellypings](https://github.com/freemocap/skellypings) package.

### What Is Collected

An `app_opened` event is sent at startup containing anonymous system specifications: OS name and version, CPU architecture, CPU count (physical and logical), total RAM, and Python version. No camera data, recordings, or personally identifiable information is collected.

### Opting Out

Telemetry is enabled by default. To disable it, edit `~/skellycam_data/telemetry_config.json`:

```json
{
  "telemetry_enabled": false
}
```

You can also toggle telemetry from the Settings page in the UI. The setting takes effect on the next server start.
