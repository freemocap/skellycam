use std::collections::HashMap;
use std::sync::atomic::Ordering;
use std::sync::Arc;

use axum::extract::State;
use axum::routing::{delete, get, post};
use axum::{Json, Router};

use crate::camera::detect_cameras;
use crate::camera::{CameraConfig, CameraIdentity};
use crate::camera_group::{CameraGroupConfig, RecordingParams};

use super::application_state::AppState;
use super::error::AppError;
use super::models::*;

pub fn camera_routes() -> Router<Arc<AppState>> {
    Router::new()
        .route("/health", get(health_check))
        .route("/shutdown", get(shutdown))
        .route("/skellycam/camera/detect", post(detect_cameras_handler))
        .route(
            "/skellycam/camera/group/apply",
            post(create_or_update_group),
        )
        .route(
            "/skellycam/camera/group/all/record/start",
            post(start_recording),
        )
        .route(
            "/skellycam/camera/group/all/record/stop",
            get(stop_recording),
        )
        .route(
            "/skellycam/camera/group/all/pause_unpause",
            get(toggle_pause_unpause),
        )
        .route(
            "/skellycam/camera/group/close/all",
            delete(close_all_groups),
        )
}

// ── Health ─────────────────────────────────────────────────────────────────

async fn health_check() -> &'static str {
    "skellycam ok"
}

async fn shutdown(State(state): State<Arc<AppState>>) -> Result<Json<serde_json::Value>, AppError> {
    state.shutdown_flag.store(true, Ordering::SeqCst);
    Ok(Json(serde_json::json!({"message": "shutting down"})))
}

// ── Detection ──────────────────────────────────────────────────────────────

async fn detect_cameras_handler(
    State(_state): State<Arc<AppState>>,
) -> Result<Json<DetectedCamerasResponse>, AppError> {
    let cameras = tokio::task::spawn_blocking(|| detect_cameras())
        .await
        .map_err(|e| AppError::Internal(format!("Camera detection task panicked: {e}")))?
        .map_err(|e| AppError::Internal(format!("Camera detection failed: {e}")))?;

    let detected: Vec<DetectedCamera> = cameras.into_iter().map(DetectedCamera::from).collect();

    Ok(Json(DetectedCamerasResponse { cameras: detected }))
}

// ── Group create/apply ─────────────────────────────────────────────────────

async fn create_or_update_group(
    State(state): State<Arc<AppState>>,
    Json(request): Json<CameraGroupApplyRequest>,
) -> Result<Json<CreateCameraGroupResponse>, AppError> {
    if request.camera_configs.is_empty() {
        return Err(AppError::BadRequest(
            "camera_configs must not be empty".into(),
        ));
    }

    // Re-detect to get full CameraIdentity for each requested camera
    let all_cameras = tokio::task::spawn_blocking(|| detect_cameras())
        .await
        .map_err(|e| AppError::Internal(format!("Camera detection panicked: {e}")))?
        .map_err(|e| AppError::Internal(format!("Camera detection failed: {e}")))?;

    let mut configs: Vec<CameraGroupConfig> = Vec::new();
    let mut response_configs: HashMap<String, CameraConfigOutput> = HashMap::new();

    for (cam_id, input) in &request.camera_configs {
        // Find the detected camera identity
        let identity: CameraIdentity = all_cameras
            .iter()
            .find(|c| c.camera_id == *cam_id || c.camera_index == input.camera_index)
            .cloned()
            .ok_or_else(|| {
                AppError::BadRequest(format!(
                    "Camera '{}' (index {}) not found in detected devices",
                    cam_id, input.camera_index
                ))
            })?;

        let capture_config = CameraConfig {
            camera_id: identity.camera_id.clone(),
            camera_index: identity.camera_index as u32,
            width: input.resolution.width.max(1) as u32,
            height: input.resolution.height.max(1) as u32,
            exposure: input.exposure,
            exposure_mode: if input.exposure_mode.is_empty() {
                "MANUAL".into()
            } else {
                input.exposure_mode.clone()
            },
            framerate: input.framerate,
            rotation: input.rotation,
        };

        let output = CameraConfigOutput::from(&capture_config);

        configs.push(CameraGroupConfig {
            identity,
            capture_config,
        });
        response_configs.insert(cam_id.clone(), output);
    }

    // Use CameraGroupManager to create or replace the active group
    let mut manager = state.camera_manager.lock().await;

    // Close existing active group if any
    if let Some(old_id) = state.active_group_id.lock().await.take() {
        let _ = manager.close_group(&old_id);
    }

    let group_id = manager
        .create_or_update_group(configs, None)
        .map_err(|e| AppError::Internal(format!("Failed to create camera group: {e}")))?;

    *state.active_group_id.lock().await = Some(group_id.clone());

    Ok(Json(CreateCameraGroupResponse {
        group_id,
        camera_configs: response_configs,
    }))
}

// ── Recording ──────────────────────────────────────────────────────────────

async fn start_recording(
    State(state): State<Arc<AppState>>,
    Json(request): Json<StartRecordingRequest>,
) -> Result<Json<bool>, AppError> {
    let active_id = state
        .active_group_id
        .lock()
        .await
        .clone()
        .ok_or_else(|| AppError::BadRequest("No active camera group".into()))?;

    let mut manager = state.camera_manager.lock().await;
    let group = manager
        .get_group_mut(&active_id)
        .ok_or_else(|| AppError::Internal("Active group not found in manager".into()))?;

    let dir = if request.recording_directory.is_empty() {
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        format!("recordings_{timestamp}")
    } else {
        request.recording_directory
    };

    std::fs::create_dir_all(&dir)
        .map_err(|e| AppError::Internal(format!("Failed to create recording dir: {e}")))?;

    let label = if request.recording_name.is_empty() {
        None
    } else {
        Some(request.recording_name)
    };

    group
        .start_recording(RecordingParams {
            output_dir: dir,
            label,
        })
        .map_err(|e| AppError::Internal(format!("Failed to start recording: {e}")))?;

    Ok(Json(true))
}

async fn stop_recording(
    State(state): State<Arc<AppState>>,
) -> Result<Json<StopRecordingResponse>, AppError> {
    let active_id = state
        .active_group_id
        .lock()
        .await
        .clone()
        .ok_or_else(|| AppError::BadRequest("No active camera group".into()))?;

    let mut manager = state.camera_manager.lock().await;
    let group = manager
        .get_group_mut(&active_id)
        .ok_or_else(|| AppError::Internal("Active group not found in manager".into()))?;

    let summary = group
        .stop_recording()
        .map_err(|e| AppError::Internal(format!("Failed to stop recording: {e}")))?;

    let total_frames = summary.total_frames_per_camera as i32;
    let recording_path = summary
        .info_json_path
        .parent()
        .map(|p| p.display().to_string())
        .unwrap_or_default();
    let recording_name = summary
        .info_json_path
        .parent()
        .and_then(|p| p.file_name())
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_default();

    // Derive duration and FPS from stats when available
    let (duration, framerate) = if let Some(ref stats) = summary.stats {
        let total_multiframes = stats.total_multiframes as f64;
        // multiframe_fps is the gatherer's output rate
        let fps = stats
            .multiframe_fps
            .as_ref()
            .map(|s| s.mean)
            .unwrap_or(0.0);
        let dur = if fps > 0.0 {
            total_multiframes / fps
        } else {
            0.0
        };
        (dur, fps)
    } else {
        (0.0, 0.0)
    };

    Ok(Json(StopRecordingResponse {
        recording_name,
        recording_path,
        number_of_cameras: summary.video_paths.len() as i32,
        number_of_frames: total_frames,
        total_duration_sec: duration,
        mean_framerate: framerate,
        mean_inter_camera_sync_ms: 0.0,
        framerate_stats: StatsSummary {
            median: 0.0,
            mean: 0.0,
            std: 0.0,
            min: 0.0,
            max: 0.0,
        },
        frame_duration_stats: StatsSummary {
            median: 0.0,
            mean: 0.0,
            std: 0.0,
            min: 0.0,
            max: 0.0,
        },
        inter_camera_grab_range_ms_stats: StatsSummary {
            median: 0.0,
            mean: 0.0,
            std: 0.0,
            min: 0.0,
            max: 0.0,
        },
    }))
}

// ── Pause / unpause ────────────────────────────────────────────────────────

async fn toggle_pause_unpause(
    State(state): State<Arc<AppState>>,
) -> Result<Json<bool>, AppError> {
    let active_id = state
        .active_group_id
        .lock()
        .await
        .clone()
        .ok_or_else(|| AppError::BadRequest("No active camera group".into()))?;

    let mut manager = state.camera_manager.lock().await;
    let group = manager
        .get_group_mut(&active_id)
        .ok_or_else(|| AppError::Internal("Active group not found in manager".into()))?;

    group.toggle_pause();
    Ok(Json(group.is_paused()))
}

// ── Close all ──────────────────────────────────────────────────────────────

async fn close_all_groups(
    State(state): State<Arc<AppState>>,
) -> Result<Json<CloseAllResponse>, AppError> {
    let mut manager = state.camera_manager.lock().await;
    manager.close_all_groups();
    *state.active_group_id.lock().await = None;
    Ok(Json(CloseAllResponse { success: true }))
}
