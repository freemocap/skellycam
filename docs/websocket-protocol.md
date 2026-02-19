# WebSocket Protocol

The WebSocket endpoint at `/skellycam/websocket/connect` carries three types of traffic:

1. **Binary frame payloads** (server → client) — Multi-camera JPEG frames
2. **JSON messages** (server → client) — Log records, framerate updates, application state
3. **Text messages** (client → server) — Frame acknowledgments and ping/pong

## Connection Lifecycle

1. Client opens a WebSocket connection to `/skellycam/websocket/connect`.
2. Server accepts the connection and starts four concurrent tasks: image relay, log relay, state sender, and client message handler.
3. Client begins receiving messages immediately.
4. When the client disconnects (or the server shuts down), all tasks are cancelled and the connection is closed.

## Binary Frame Payload

When cameras are active, the server sends binary (bytes) messages containing JPEG-compressed frames from all cameras in the active group. The binary format is defined by the frontend's `binary-protocol.ts` and the backend's `create_frontend_payload_bytearray.py`.

The payload structure packs multiple camera frames into a single binary message, allowing the frontend to parse and render all cameras from one WebSocket message.

## JSON Messages (Server → Client)

### Log Records

```json
{
  "message_type": "log_record",
  "levelname": "INFO",
  "levelno": 20,
  "message": "Camera group started",
  "name": "skellycam.core.camera_group",
  "filename": "camera_group.py",
  "lineno": 42,
  "funcName": "start",
  "created": 1700000000.123,
  "formatted_message": "2024-01-01 12:00:00 [INFO] Camera group started",
  "delta_t": "0.123ms"
}
```

Log records with a level at or above `TRACE` (level 5) are forwarded to the WebSocket. The frontend displays these in the log terminal panel.

### Framerate Updates

```json
{
  "message_type": "framerate_update",
  "camera_group_id": "group-0",
  "backend_framerate": {
    "mean_frame_duration_ms": 33.3,
    "mean_frames_per_second": 30.0,
    "frame_duration_max": 40.1,
    "frame_duration_min": 28.5,
    "frame_duration_mean": 33.3,
    "frame_duration_stddev": 2.1,
    "frame_duration_median": 33.2,
    "frame_duration_coefficient_of_variation": 0.063,
    "calculation_window_size": 100,
    "framerate_source": "Server"
  },
  "frontend_framerate": {
    "mean_frame_duration_ms": 34.1,
    "mean_frames_per_second": 29.3,
    "framerate_source": "Display",
    ...
  }
}
```

Sent approximately once per second when cameras are active. The `backend_framerate` represents the true camera capture rate (computed from frame numbers and capture timestamps, accurate even when the WebSocket skips frames due to backpressure). The `frontend_framerate` represents the WebSocket delivery rate (what the UI actually receives).

### Application State

```json
{
  "message_type": "app_state",
  "state": {
    "camera_groups": {
      "group-0": {
        "id": "group-0",
        "camera_ids": ["0", "1"],
        "is_recording": false,
        "is_paused": false
      }
    }
  }
}
```

Sent periodically (every ~1 second) and whenever the application state changes.

## Client → Server Messages

### Frame Acknowledgment

After processing a binary frame payload, the client sends an acknowledgment:

```json
{
  "frameNumber": 42,
  "displayImageSizes": {
    "group-0": {
      "0": { "width": 640, "height": 480 },
      "1": { "width": 640, "height": 480 }
    }
  }
}
```

The `frameNumber` field tells the server which frame has been rendered. The server uses this for backpressure management — it will not send new frames until the previous frame is acknowledged. If the frontend falls behind, the server skips frames to prevent buffer bloat.

The `displayImageSizes` field (optional) tells the server the current display dimensions, allowing it to resize JPEG frames to match, reducing bandwidth.

### Ping/Pong

Sending the text `"ping"` will receive `"pong"` in response. This can be used for connection health checks.

## Backpressure Management

The server tracks the last sent frame number and the last acknowledged frame number. If the frontend has not acknowledged the most recent frame:

1. The server skips sending new frames.
2. After acknowledgment arrives, the server skips one additional frame to let the frontend catch up.
3. If the gap exceeds 1000 frames, a trace-level warning is logged.

This ensures the WebSocket buffer does not grow unbounded even when the frontend rendering is slower than the camera capture rate.
