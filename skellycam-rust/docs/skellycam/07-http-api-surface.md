# Component #7: HTTP API Surface

Status: **AUDITED — updated for actual Rust implementation (2026-05-23)**

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

## Part 1: Implementation Reality — Server Configuration

```
Protocol:       HTTP
Host:            0.0.0.0
Port:            53117
Base URL:        http://localhost:53117
API Prefix:      /skellycam
Swagger Docs:    /docs (custom Swagger UI via utoipa)
Test Page:       /test (built-in HTML test harness)
OpenAPI Title:   "Skellycam API"
```

### CORS Middleware (Rust)

```rust
let cors = CorsLayer::new()
    .allow_origin(Any)
    .allow_methods(Any)
    .allow_headers(Any);
```

### Route Registration (Actual)

```rust
Router::new()
    .merge(camera_routes())      // /skellycam/camera/...
    .merge(websocket_route())    // /skellycam/websocket/connect
    .route("/api-docs/openapi.json", get(openapi_json))
    .route("/docs", get(swagger_ui))
    .route("/test", get(serve_test_page))
    .layer(log_request_middleware)
    .layer(cors)
    .with_state(state)
```

### Endpoints Implemented

| Method | Path | Status |
|--------|------|--------|
| `GET` | `/health` | **Implemented** — returns `"OK"` |
| `GET` | `/shutdown` | **Implemented** — sets `shutdown_flag`, triggers graceful shutdown |
| `POST` | `/skellycam/camera/detect` | **Implemented** — enumerates via `openpnp-capture` |
| `POST` | `/skellycam/camera/group/apply` | **Implemented** — `create_or_update_group()` |
| `DELETE` | `/skellycam/camera/group/close/all` | **Implemented** — `close_all_groups()` |
| `GET` | `/skellycam/camera/group/all/pause_unpause` | **Implemented** — `toggle_pause()` on all groups |
| `POST` | `/skellycam/camera/group/all/record/start` | **Implemented** — `start_recording()` |
| `GET` | `/skellycam/camera/group/all/record/stop` | **Implemented** — `stop_recording()` |
| `WS` | `/skellycam/websocket/connect` | **Implemented** — binary frames + framerate JSON + log relay |
| `GET` | `/docs` | **Implemented** — static Swagger UI |
| `GET` | `/api-docs/openapi.json` | **Implemented** — `utoipa`-generated schema |
| `GET` | `/test` | **Implemented** — built-in HTML test page |

### Endpoints NOT Implemented

| Method | Path | Reason |
|--------|------|--------|
| `GET` | `/` | Not redirected to /docs (uses /test instead) |
| `GET` | `/favicon.ico` | Not needed |
| `GET` | `/skellycam/camera/microphone/detect` | Audio recording deferred |
| `GET` | `/skellycam/playback/*` | Playback endpoints deferred |
| `GET` | `/skellycam/playback/{id}/videos/{vid}` | Video streaming deferred |

### Camera Config (Reduced from Python's 20+ fields)

```rust
pub struct CameraConfig {
    pub camera_id: String,
    pub camera_index: u32,
    pub width: u32,
    pub height: u32,
    pub exposure: i32,
    pub exposure_mode: String,  // "MANUAL", "AUTO", "RECOMMEND"
    pub framerate: f64,
    pub rotation: i32,
}
```

8 fields vs Python's 20+. The Rust impl uses `openpnp-capture` which exposes DirectShow properties generically rather than through named UVC controls. Only exposure is directly managed; all other UVC properties (brightness, contrast, etc.) would need custom property ID mapping.

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
