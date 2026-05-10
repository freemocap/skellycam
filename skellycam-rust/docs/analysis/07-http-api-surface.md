# Component #7: HTTP API Surface

Status: **ANALYZED — stable reference artifact**

Files analyzed:
- `skellycam/api/routers.py` — router list
- `skellycam/api/http/cameras/camera_router.py` — camera endpoints + request/response models
- `skellycam/api/http/playback/playback_router.py` — playback endpoints
- `skellycam/api/http/app/health.py` — health check
- `skellycam/api/http/app/shutdown.py` — graceful shutdown
- `skellycam/api/websocket/websocket_connect.py` — WebSocket upgrade endpoint
- `skellycam/api/websocket/websocket_server.py` — WebSocket protocol (4 concurrent tasks)
- `skellycam/api/websocket/websocket_message_types.py` — WebSocket message type enum
- `skellycam/api/middleware/cors.py` — CORS middleware
- `skellycam/api/middleware/add_middleware.py` — CORS middleware registration
- `skellycam/api/server_constants.py` — host/port constants
- `skellycam/app.py` — FastAPI app factory, lifespan, route registration
- `skellycam/core/camera_group/camera_group_manager.py` — singleton manager (endpoint handler)

---

## Part 1: Server Configuration

```
Protocol:       HTTP
Host:            localhost
Port:            53117
Base URL:        http://localhost:53117
API Prefix:      /skellycam
Swagger Docs:    /docs
OpenAPI Title:   "SkellyCam API 💀📸✨"
```

All camera and playback routes are prefixed with `/skellycam`. Health and shutdown routes are at the root level (no prefix). The root `/` redirects to `/docs`.

### CORS Middleware

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # All origins allowed
    allow_methods=["*"],       # All HTTP methods
    allow_headers=["*"],       # All headers
    allow_credentials=True,
)
```

Permissive CORS — the Electron frontend loads from `file://` or `localhost:<random_port>`, so the backend must accept cross-origin requests from any origin. Rust equivalent: `tower_http::cors::CorsLayer::permissive()` in Axum.

---

## Part 2: Complete Endpoint Catalog

All endpoints return `application/json` unless noted. Errors return `500 { "detail": "<exception message>" }`.

### 2.1 Root & App

| Method | Path | Summary | Request | Response |
|--------|------|---------|---------|----------|
| `GET` | `/` | Redirect to /docs | — | 302 → `/docs` |
| `GET` | `/favicon.ico` | Serve favicon | — | `image/x-icon` file |
| `GET` | `/health` | Health check | — | `200 "Hello👋"` |
| `GET` | `/shutdown` | Graceful shutdown | — | `200 { "status": "shutdown_initiated", "message": "Server shutting down. Goodbye! 👋" }` |

**Shutdown behavior**: Sets `global_kill_flag.value = True`, waits 100ms, sends `SIGTERM` to own process. In Rust, this is `std::process::exit(0)` after a brief delay for the response to flush.

### 2.2 Camera Group Lifecycle

| Method | Path | Summary | Request Body | Response |
|--------|------|---------|-------------|----------|
| `POST` | `/skellycam/camera/group/apply` | Create or update camera group | `CameraGroupCreateRequest` | `CreateCameraGroupResponse` |
| `DELETE` | `/skellycam/camera/group/close/all` | Close all camera groups | — | `200 true` |
| `GET` | `/skellycam/camera/group/all/pause_unpause` | Toggle pause/unpause all groups | — | `200 true` |

**`POST /camera/group/apply`** — The main endpoint for creating or reconfiguring camera groups.

Request (`CameraGroupCreateRequest`):
```json
{
  "camera_configs": {
    "<camera_id>": {
      "camera_id": "camera_0",
      "camera_index": 0,
      "backend": 0,
      "resolution": { "width": 1280, "height": 720 },
      "framerate": 30.0,
      "exposure": -7,
      "brightness": 128,
      "contrast": 128,
      "saturation": 128,
      "hue": 0,
      "gamma": 100,
      "gain": 0,
      "white_balance_temperature": 4000,
      "sharpness": 128,
      "backlight_compensation": 0,
      "focus": 0,
      "zoom": 0,
      "pan": 0,
      "tilt": 0,
      "iris": 0,
      "rotation": -1,
      "video_file_extension": "mp4",
      "writer_fourcc": "XVID"
    }
  }
}
```

Response (`CreateCameraGroupResponse`):
```json
{
  "group_id": "<uuid>",
  "camera_configs": {
    "<camera_id>": { ... }   // Extracted configs (actual camera capabilities, not requested)
  }
}
```

Logic: If no camera group exists with these camera IDs, creates and starts a new one. If a group already exists with these camera IDs, calls `update_camera_settings()` on that group (reconfigure cameras). The response contains the *extracted* configs — what the cameras actually support, returned after the two-phase startup (open cameras → discover capabilities → return actual config).

### 2.3 Device Detection

| Method | Path | Summary | Query Params | Response |
|--------|------|---------|-------------|----------|
| `POST` | `/skellycam/camera/detect` | Detect available cameras | `filter_virtual: bool` (default true), `backend_id: int` (optional) | `DetectedCamerasResponse` |
| `GET` | `/skellycam/camera/microphone/detect` | Detect microphones | — | `DetectedMicrophonesResponse` |

**`POST /camera/detect`** — Uses `nokhwa` (or platform-specific API) to enumerate connected cameras.

Response (`DetectedCamerasResponse`):
```json
{
  "cameras": [
    {
      "camera_id": "Integrated Camera",
      "camera_index": 0,
      "backend": 0,
      "backend_name": "Auto",
      "resolution": { "width": 1920, "height": 1080 },
      "framerate": 30.0,
      "supported_resolutions": [ ... ]
    }
  ]
}
```

**`GET /camera/microphone/detect`** — Returns available audio input devices.

Response (`DetectedMicrophonesResponse`):
```json
{
  "microphones": {
    "0": "Microphone (Realtek Audio)",
    "1": "USB Microphone"
  }
}
```

### 2.4 Recording Control

| Method | Path | Summary | Request Body | Response |
|--------|------|---------|-------------|----------|
| `POST` | `/skellycam/camera/group/all/record/start` | Start recording all groups | `StartRecordingRequest` | `200 true` |
| `GET` | `/skellycam/camera/group/all/record/stop` | Stop recording all groups | — | `list[StopRecordingResponse]` |

**`POST /camera/group/all/record/start`**

Request (`StartRecordingRequest`):
```json
{
  "recording_name": "recording_2026-05-10_14-30-00",
  "recording_directory": "~/skellycam_data/recordings",
  "mic_device_index": -1
}
```

Logic: Resolves `~` to home directory, creates recording directory, calls `start_recording_all_groups()` which iterates all camera groups and calls `camera_group.start_recording()`. The pause-before-record protocol runs (see Component #5). If `mic_device_index >= 0`, starts audio recording.

**`GET /camera/group/all/record/stop`**

Response (`StopRecordingResponse` per camera group):
```json
[{
  "recording_name": "recording_2026-05-10_14-30-00",
  "recording_path": "/home/user/skellycam_data/recordings/recording_2026-05-10_14-30-00",
  "number_of_cameras": 2,
  "number_of_frames": 1500,
  "total_duration_sec": 50.123,
  "mean_framerate": 29.97,
  "mean_inter_camera_sync_ms": 0.45,
  "framerate_stats": {
    "median": 29.97, "mean": 29.95, "std": 0.5, "min": 27.0, "max": 32.0
  },
  "frame_duration_stats": {
    "median": 33.3, "mean": 33.4, "std": 0.8, "min": 31.0, "max": 37.0
  },
  "inter_camera_grab_range_ms_stats": {
    "median": 0.45, "mean": 0.47, "std": 0.12, "min": 0.1, "max": 1.2
  }
}]
```

Logic: Calls `stop_recording_all_groups()` which iterates all camera groups and calls `camera_group.stop_recording()` (pause → set last_recording_frame_number → unpause → wait for RecordingFinishedMessages → RecordingFinalizer.finalize_recording()). Returns recording name, path, and timestamp statistics for each group.

### 2.5 Playback

| Method | Path | Summary | Query Params | Response |
|--------|------|---------|-------------|----------|
| `GET` | `/skellycam/playback/recordings` | List available recordings | `recording_parent_directory` (optional) | `list[RecordingListEntry]` |
| `GET` | `/skellycam/playback/{recording_id}/videos` | List videos in a recording | `recording_parent_directory` (optional) | `list[VideoInfo]` |
| `GET` | `/skellycam/playback/{recording_id}/videos/{video_id}` | Stream a video file | `recording_parent_directory` (optional) | `video/*` binary stream |
| `GET` | `/skellycam/playback/{recording_id}/timestamps` | Get timestamps for all videos | `recording_parent_directory` (optional) | `{ "timestamps": {...}, "warnings": [...] }` |
| `GET` | `/skellycam/playback/{recording_id}/videos/{video_id}/timestamps` | Get timestamps for one video | `recording_parent_directory` (optional) | `{ "video_id": ..., "headers": [...], "row_count": N }` |

These are read-only endpoints for the frontend to browse and play back previously recorded sessions. They serve static files from disk — no camera interaction.

**`GET /playback/recordings`** — Lists recording directories, sorted newest first. Each entry includes video count, total size, creation timestamp, and optionally frame count/duration/FPS if timestamp CSVs are found.

**`GET /playback/{recording_id}/videos/{video_id}`** — Streams a video file with proper Content-Type header. Uses FastAPI's `FileResponse` which supports HTTP range requests for seeking. Axum equivalent: `axum::body::Body::from` with a `tokio::fs::File` and `.header("Content-Type", ...)`.

**Path traversal protection**: Resolves the requested path and verifies it starts with the parent directory. Returns 400 for traversal attempts.

---

## Part 3: WebSocket Protocol

### Upgrade Endpoint

| Method | Path | Summary |
|--------|------|---------|
| `WS` | `/skellycam/websocket/connect` | WebSocket upgrade |

The upgrade handler accepts the connection, creates a `WebsocketServer`, and runs 4 concurrent async tasks:

### Server → Client Messages

| Type | Wire Format | Content | Rate |
|------|-----------|---------|------|
| Frontend image payload | Binary | Multi-camera binary protocol (see Component #4) | Every 10ms, throttled by backpressure |
| Framerate update | JSON text | `{ "message_type": "framerate_update", "camera_group_id": "...", "backend_framerate": {...}, "frontend_framerate": {...} }` | ~4 Hz |
| App state | JSON text | `{ "message_type": "app_state", "state": { "camera_groups": {...} } }` | Every 1s (only when changed) |
| Log record | JSON text | `{ "message_type": "log_record", ...skellylogs fields... }` | On each log message |
| Performance data | JSON text | Per-camera frame lifecycle timing data | On demand |
| Ping response | Text | `"pong"` | In response to "ping" |

### Client → Server Messages

| Wire Format | Content | Effect |
|-----------|---------|--------|
| JSON text | `{ "frameNumber": N, "displayImageSizes": {...} }` | Backpressure acknowledgment: frontend has displayed frame N. Server skips sending if unacknowledged. Also sets per-camera display sizes for image scaling. |
| Text | `"ping"` | Server responds `"pong"` |
| Text | `"pong"` | No action |

### WebSocket Message Type Enum

```python
class WebsocketMessageType(str, enum.Enum):
    FRAMERATE_UPDATE = "framerate_update"
    APP_STATE = "app_state"
    PERFORMANCE_DATA = "performance_data"
    LOG_RECORD = "log_record"
```

Rust equivalent: an enum with `#[serde(rename_all = "snake_case")]` serialization.

### Backpressure Protocol

The frontend sends `{"frameNumber": N}` to acknowledge it has rendered frame N. The server tracks `last_sent_frame_number` and `last_received_frontend_confirmation`. If the frontend hasn't acknowledged the last sent frame:

1. Server skips sending the next payload (waits for frontend to catch up)
2. If the gap exceeds 1000 frames, logs a trace warning

This is cooperative backpressure over WebSocket — the frontend controls its own ingestion rate.

### Framerate Tracking

Two independent calculations per camera group:

- **Server (backend) framerate**: Computed from `(frame_number, capture_timestamp_ns)` pairs — true camera capture rate, accurate even when frames are skipped in the WebSocket relay
- **Display (frontend) framerate**: Computed from WebSocket send times — what the UI actually receives

Both are sent together in `FramerateUpdateMessage` at ~4 Hz. After each send, both trackers are cleared so the next report reflects only the recent interval.

### Concurrency Safety

Python uses `asyncio.Lock` (`self._send_lock`) because the `websockets` library doesn't support concurrent writes. In Rust with Axum, `WebSocket::split()` gives separate `SplitSink` and `SplitStream` halves — the sink can be wrapped in an `Arc<Mutex<>>` if multiple tasks send, or channel-based fan-in can serialize writes.

---

## Part 4: Error Handling Pattern

Every endpoint follows the same pattern:

```python
@router.method("/path")
async def endpoint(request: Request, ...) -> ResponseType:
    try:
        # ... endpoint logic ...
        return result
    except Exception as e:
        logger.error(f"Error in {request.url}: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

In Rust/Axum, this becomes a centralized error type:

```rust
enum AppError {
    Internal(anyhow::Error),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({"detail": self.0.to_string()}))
        ).into_response()
    }
}

impl From<anyhow::Error> for AppError {
    fn from(error: anyhow::Error) -> Self {
        tracing::error!("{:#}", error);
        Self::Internal(error)
    }
}
```

And endpoint handlers return `Result<impl IntoResponse, AppError>`. Axum automatically converts `AppError` to an HTTP 500 JSON response.

---

## Part 5: What Changes in Rust

### Route Registration (Axum)

```rust
pub fn create_router(state: Arc<AppState>) -> Router {
    let skellycam_routes = Router::new()
        // WebSocket
        .route("/websocket/connect", get(websocket_handler))
        // Camera
        .route("/camera/detect", post(camera_detect))
        .route("/camera/microphone/detect", get(microphone_detect))
        .route("/camera/group/apply", post(camera_group_apply))
        .route("/camera/group/all/record/start", post(record_start))
        .route("/camera/group/all/record/stop", get(record_stop))
        .route("/camera/group/close/all", delete(close_all_groups))
        .route("/camera/group/all/pause_unpause", get(pause_unpause))
        // Playback
        .route("/playback/recordings", get(playback_list_recordings))
        .route("/playback/:recording_id/videos", get(playback_list_videos))
        .route("/playback/:recording_id/videos/:video_id", get(playback_stream_video))
        .route("/playback/:recording_id/timestamps", get(playback_all_timestamps))
        .route("/playback/:recording_id/videos/:video_id/timestamps", get(playback_video_timestamps));

    let app_routes = Router::new()
        .route("/health", get(health_check))
        .route("/shutdown", get(shutdown));

    Router::new()
        .route("/", get(|| async { Redirect::to("/docs") }))
        .route("/favicon.ico", get(serve_favicon))
        .merge(app_routes)
        .nest("/skellycam", skellycam_routes)
        .layer(CorsLayer::permissive())
        .with_state(state)
}
```

Note: The Python code uses `POST` for `/camera/detect`. This is unusual (detection is read-only). Keep it as `POST` for compatibility.

### Request/Response Models → Rust Structs

All Pydantic `BaseModel` classes become Rust structs with `serde`:

```rust
#[derive(Debug, Serialize, Deserialize)]
pub struct CameraGroupCreateRequest {
    pub camera_configs: HashMap<String, CameraConfig>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CreateCameraGroupResponse {
    pub group_id: String,
    pub camera_configs: HashMap<String, CameraConfig>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct StartRecordingRequest {
    #[serde(default = "default_recording_name")]
    pub recording_name: String,
    #[serde(default = "default_recording_directory")]
    pub recording_directory: String,
    #[serde(default = "default_microphone_device_index")]
    pub micro_device_index: i32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct StopRecordingResponse {
    pub recording_name: String,
    pub recording_path: String,
    pub number_of_cameras: usize,
    pub number_of_frames: usize,
    pub total_duration_seconds: f64,
    pub mean_framerate: f64,
    pub mean_inter_camera_sync_milliseconds: f64,
    pub framerate_statistics: StatisticsSummary,
    pub frame_duration_statistics: StatisticsSummary,
    pub inter_camera_grab_range_milliseconds_statistics: StatisticsSummary,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct StatisticsSummary {
    pub median: f64,
    pub mean: f64,
    pub standard_deviation: f64,
    pub minimum: f64,
    pub maximum: f64,
}
```

**Naming convention**: Rust struct fields use `snake_case`. Serde's default behavior is to serialize as snake_case. The Python API uses camelCase for the WebSocket JSON messages (`frameNumber`, `displayImageSizes`) but snake_case for HTTP response models (Pydantic dumps by field name, which are snake_case in Python). We need to verify the exact wire format — but since the frontend currently works, we match whatever the Python code produces. Pydantic `BaseModel.model_dump()` defaults to field names (snake_case in the Python code). So we use `#[serde(rename_all = "snake_case")]` or just let serde default.

### App State (Axum)

```rust
pub struct AppState {
    pub global_kill_flag: Arc<AtomicBool>,
    pub camera_group_manager: Arc<RwLock<CameraGroupManager>>,
}

// Extracted via Axum State extractor:
async fn record_start(
    State(state): State<Arc<AppState>>,
    Json(request): Json<StartRecordingRequest>,
) -> Result<Json<bool>, AppError> {
    let manager = state.camera_group_manager.read().await;
    // ...
}
```

### Static File Serving (Playback)

Python's `FileResponse` with range request support → Axum's `ServeFile` or `tower_http::services::ServeDir`. For range requests (video seeking), use `axum_range` crate or manual `Range` header handling.

---

## Functionality That Must Be Preserved

1. **All endpoint paths identical** — frontend hardcodes these URLs
2. **Request/response JSON shapes identical** — frontend parses specific field names
3. **POST /camera/detect** — keep as POST even though it's logically a read operation
4. **`~` expansion in recording_directory** — resolve tilde to home directory
5. **CORS permissive** — allow all origins, methods, headers
6. **500 error format** — `{ "detail": "<message>" }`
7. **Swagger/OpenAPI docs at /docs** — Axum doesn't have built-in Swagger; use `utoipa` or `aide` crate, or serve a static Swagger UI page
8. **Root redirect to /docs**
9. **WebSocket at /skellycam/websocket/connect** — exact path
10. **WebSocket binary protocol unchanged** — frontend image payload format (see Component #4)
11. **WebSocket backpressure protocol** — frameNumber acknowledgments from frontend
12. **Serialized state every 1s** — app_state messages only when state changed
13. **Framerate updates at ~4 Hz** — server and display framerate trackers
14. **Ping/pong** — keep-alive mechanism
15. **Shutdown endpoint** — triggers clean server shutdown
16. **Health endpoint at /health** — simple liveness check

---

## Confirmed Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **utoipa for OpenAPI/Swagger** | Standard crate for Axum OpenAPI generation. Derive macros on request/response structs produce the schema. Serve Swagger UI via `utoipa-swagger-ui`. |
| 2 | **Range requests: use `tower_http::services::ServeDir`** | It supports `Accept-Ranges` and `Range` headers natively. Video seeking just works. If it doesn't integrate cleanly with axum's dynamic path resolution, fall back to manual `FileResponse` without range support (the playback feature is secondary). |
| 3 | **`Arc<RwLock<CameraGroupManager>>` in Axum State** | No module-level global. Rust best practice: shared state goes in the router's `State` extractor. The "singleton" property emerges from having one router with one `AppState`. Thread-safe, testable, no static mutable state. |
