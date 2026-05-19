use std::sync::Arc;

use axum::response::Html;
use axum::Router;
use tower_http::cors::{Any, CorsLayer};
use utoipa::OpenApi;

use crate::websocket;

use super::application_state::AppState;
use super::camera_routes::camera_routes;
use super::camera_routes::{
    __path_close_all_groups, __path_create_or_update_group,
    __path_detect_cameras_handler, __path_health_check, __path_shutdown,
    __path_start_recording, __path_stop_recording,
    __path_toggle_pause_unpause,
};
use super::models::*;

#[derive(OpenApi)]
#[openapi(
    paths(
        health_check,
        shutdown,
        detect_cameras_handler,
        create_or_update_group,
        start_recording,
        stop_recording,
        toggle_pause_unpause,
        close_all_groups,
    ),
    components(schemas(
        DetectedCamera,
        DetectedCamerasResponse,
        CameraConfigInput,
        CameraConfigOutput,
        CameraGroupApplyRequest,
        CreateCameraGroupResponse,
        StartRecordingRequest,
        StopRecordingResponse,
        CloseAllResponse,
    )),
    info(
        title = "Skellycam API",
        version = "0.1.0",
        description = "Multi-camera capture and recording system"
    )
)]
struct ApiDoc;

pub fn build_router(state: Arc<AppState>) -> Router {
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    Router::new()
        .merge(camera_routes())
        .merge(websocket::server::websocket_route())
        .route("/api-docs/openapi.json", axum::routing::get(openapi_json))
        .route("/docs", axum::routing::get(swagger_ui))
        .route("/test", axum::routing::get(serve_test_page))
        .layer(axum::middleware::from_fn(super::middleware::log_requests))
        .layer(cors)
        .with_state(state)
}

async fn openapi_json() -> axum::Json<utoipa::openapi::OpenApi> {
    axum::Json(ApiDoc::openapi())
}

async fn swagger_ui() -> Html<&'static str> {
    Html(SWAGGER_HTML)
}

async fn serve_test_page() -> Html<&'static str> {
    Html(include_str!("test_page.html"))
}

const SWAGGER_HTML: &str = r##"<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Skellycam API Docs</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"/>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js" crossorigin></script>
  <script>
    SwaggerUIBundle({
      url: "/api-docs/openapi.json",
      dom_id: "#swagger-ui",
      deepLinking: true,
    });
  </script>
</body>
</html>"##;
