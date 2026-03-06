---
sidebar_position: 4
---
# API Reference

The SkellyCam server exposes a REST API for camera management and a WebSocket endpoint for real-time streaming. Interactive Swagger documentation is available at `http://localhost:53117/docs` when the server is running.

## Base URL

All endpoints are served from `http://localhost:53117`. Camera-specific endpoints are prefixed with `/skellycam`.

## App Endpoints

### `GET /health`

Health check endpoint.

**Response:** `"Hello👋"` (200 OK)

### `GET /shutdown`

Initiates graceful server shutdown. Sets the global kill flag, sends `SIGTERM` to the server process, and returns immediately.

**Response:**
```json
{
  "status": "shutdown_initiated",
  "message": "Server shutting down. Goodbye! 👋"
}
```

## Camera Endpoints

All camera endpoints are prefixed with `/skellycam/camera`.

### `POST /skellycam/camera/detect`

Detects available camera devices on the system.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `filter_virtual` | `bool` | `true` | Exclude virtual cameras from results |
| `backend_id` | `int \| null` | `null` | OpenCV backend ID to use for detection |

**Response:**
```json
{
  "cameras": [
    {
      "index": 0,
      "name": "HD Webcam",
      "vendor_id": 1234,
      "product_id": 5678,
      "path": "/dev/video0",
      "backend_id": 200,
      "backend_name": "V4L2"
    }
  ]
}
```

### `GET /skellycam/camera/microphone/detect`

Detects available microphone devices on the system. Returns a mapping of device index to device name.

**Response:**
```json
{
  "microphones": {
    "0": "Built-in Microphone",
    "1": "USB Audio Device"
  }
}
```

### `POST /skellycam/camera/group/apply`

Creates a new camera group or updates an existing one. If the provided camera IDs match an existing group, the group's settings are updated; otherwise, a new group is created and started.

**Request Body:**
```json
{
  "camera_configs": {
    "000": {
      "camera_id": "000",
      "camera_index": 0,
      "camera_name": "Camera-000",
      "use_this_camera": true,
      "resolution": { "width": 1280, "height": 720 },
      "framerate": -1,
      "color_channels": 3,
      "pixel_format": "RGB",
      "exposure_mode": "MANUAL",
      "exposure": -7,
      "rotation": -1,
      "capture_fourcc": "MJPG",
      "writer_fourcc": "X264"
    }
  }
}
```

**Response:**
```json
{
  "group_id": "group-0",
  "camera_configs": {
    "0": { ... }
  }
}
```

### `POST /skellycam/camera/group/all/record/start`

Starts recording for all active camera groups.

**Request Body:**
```json
{
  "recording_name": "2024-09-15T14_30_00",
  "recording_directory": "~/skellycam_data/recordings",
  "mic_device_index": -1
}
```

All fields have defaults. `mic_device_index: -1` disables audio recording.

**Response:** `true` (200 OK)

### `GET /skellycam/camera/group/all/record/stop`

Stops recording for all active camera groups. Triggers timestamp processing and statistics generation.

**Response:** `true` (200 OK)

### `DELETE /skellycam/camera/group/close/all`

Closes all camera groups, releasing all camera resources and stopping all worker processes.

**Response:** `true` (200 OK)

### `GET /skellycam/camera/group/all/pause_unpause`

Toggles pause/unpause on all camera groups. When paused, cameras stop capturing frames but remain open.

**Response:** `true` (200 OK)

## WebSocket Endpoint

### `WS /skellycam/websocket/connect`

Persistent WebSocket connection for real-time frame streaming, log forwarding, and application state updates. See [WebSocket Protocol](websocket-protocol.md) for the full protocol specification.

## Playback Endpoints

All playback endpoints are prefixed with `/skellycam/playback`. They serve pre-recorded video files over HTTP for browser-native `<video>` playback with full seeking support via HTTP range requests.

### `GET /skellycam/playback/recordings`

Lists available recording directories in the default recordings folder (`~/skellycam_data/recordings/`).

**Response:**
```json
[
  {
    "name": "2024-09-15T14_30_00",
    "path": "/home/user/skellycam_data/recordings/2024-09-15T14_30_00",
    "video_count": 3,
    "total_size_bytes": 157286400,
    "created_timestamp": "2024-09-15T14:30:00",
    "total_frames": 9000,
    "duration_seconds": 300.0,
    "fps": 30.0
  }
]
```

### `POST /skellycam/playback/load`

Loads a recording folder for playback. The server validates the path, discovers video files (checking both the folder directly and a `synchronized_videos/` subfolder), and makes them available for streaming.

**Request Body:**
```json
{
  "recording_path": "~/skellycam_data/recordings/2024-09-15T14_30_00"
}
```

**Response:**
```json
{
  "recording_path": "/home/user/skellycam_data/recordings/2024-09-15T14_30_00",
  "videos": [
    {
      "video_id": "recording.camera0",
      "filename": "recording.camera0.mp4",
      "size_bytes": 52428800,
      "stream_url": "/skellycam/playback/video/recording.camera0"
    }
  ]
}
```

### `GET /skellycam/playback/video/{video_id}`

Streams a loaded video file. The response is a standard `FileResponse` with the correct `Content-Type` header, and Starlette handles HTTP range requests automatically — this enables browser-native seeking, buffering, and hardware-accelerated decoding via `<video>` elements.

### `GET /skellycam/playback/timestamps/{video_id}`

Returns metadata about the timestamp CSV for a given video, if available. Searches the recording's `timestamps/camera_timestamps/` folder.

## Error Handling

All endpoints return standard HTTP error codes:

- **200** — Success
- **400** — Bad request (invalid parameters)
- **500** — Internal server error (with error detail in response body)

Errors are returned as:
```json
{
  "detail": "Error description string"
}
```
