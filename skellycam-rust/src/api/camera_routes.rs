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

/// Health check — returns "skellycam ok"
#[utoipa::path(
    get,
    path = "/health",
    responses(
        (status = 200, description = "Server is alive", body = str)
    )
)]
async fn health_check() -> &'static str {
    "skellycam ok"
}

/// Initiate graceful server shutdown
#[utoipa::path(
    get,
    path = "/shutdown",
    responses(
        (status = 200, description = "Shutdown initiated")
    )
)]
async fn shutdown(State(state): State<Arc<AppState>>) -> Result<Json<serde_json::Value>, AppError> {
    state.shutdown_flag.store(true, Ordering::SeqCst);
    Ok(Json(serde_json::json!({"message": "shutting down"})))
}

// ── Detection ──────────────────────────────────────────────────────────────

/// Detect connected cameras
#[utoipa::path(
    post,
    path = "/skellycam/camera/detect",
    responses(
        (status = 200, description = "Cameras detected", body = DetectedCamerasResponse),
        (status = 500, description = "Detection failed")
    )
)]
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

/// Create or update a camera group
#[utoipa::path(
    post,
    path = "/skellycam/camera/group/apply",
    request_body = CameraGroupApplyRequest,
    responses(
        (status = 200, description = "Group created", body = CreateCameraGroupResponse),
        (status = 400, description = "Bad request"),
        (status = 500, description = "Creation failed")
    )
)]
async fn create_or_update_group(
    State(state): State<Arc<AppState>>,
    Json(request): Json<CameraGroupApplyRequest>,
) -> Result<Json<CreateCameraGroupResponse>, AppError> {
    if request.camera_configs.is_empty() {
        return Err(AppError::BadRequest(
            "camera_configs must not be empty".into(),
        ));
    }

    // Build a HashMap<String, CameraGroupConfig> keyed by camera_id.
    // For an existing group, reuse stored identities. For new cameras
    // (either first create or adding to an existing group), detect.
    //
    // IMPORTANT: both locks are always dropped before detection and always
    // re-acquired after. tokio Mutex is NOT reentrant — holding the lock
    // across a second lock().await on the same Mutex deadlocks the task.
    let existing_identities: HashMap<String, CameraIdentity> = {
        let manager = state.camera_manager.lock().await;
        let active_id = state.active_group_id.lock().await;

        if let Some(ref gid) = *active_id {
            tracing::info!("[apply] active group exists: {gid} — will update via apply()");
        } else {
            tracing::info!("[apply] no active group — will create new");
        }

        let identities = active_id
            .as_ref()
            .and_then(|id| manager.get_group(id))
            .map(|g| {
                let statuses = g.camera_statuses();
                tracing::debug!(
                    "[apply] loaded {} existing camera identities from group",
                    statuses.len()
                );
                statuses
                    .into_iter()
                    .map(|s| {
                        let cid = s.config.camera_id.clone();
                        let identity = CameraIdentity {
                            camera_name: s.camera_name,
                            camera_index: s.camera_index,
                            camera_id: cid.clone(),
                            device_path: s.device_path,
                            formats: vec![],
                        };
                        (cid, identity)
                    })
                    .collect()
            })
            .unwrap_or_default();

        // Both locks dropped here when they go out of scope
        identities
    };

    // Only re-detect for camera IDs not already in the existing group
    let need_detection: Vec<String> = request
        .camera_configs
        .keys()
        .filter(|id| !existing_identities.contains_key(*id))
        .cloned()
        .collect();

    if !need_detection.is_empty() {
        tracing::info!(
            "[apply] {} new camera(s) need detection: {:?}",
            need_detection.len(),
            need_detection
        );
    } else {
        tracing::debug!("[apply] all {} camera(s) already known — skipping detection", request.camera_configs.len());
    }

    let detected: Option<Vec<crate::camera::CameraDetection>> = if !need_detection.is_empty() {
        let result: Result<Vec<crate::camera::CameraDetection>, AppError> = tokio::task::spawn_blocking(|| detect_cameras())
            .await
            .map_err(|e| AppError::Internal(format!("Camera detection panicked: {e}")))?
            .map_err(|e| AppError::Internal(format!("Camera detection failed: {e}")));
        let cams = result?;
        tracing::debug!("[apply] detection complete — {} cameras found", cams.len());
        Some(cams)
    } else {
        None
    };

    // Re-acquire locks now that detection is done
    let mut manager = state.camera_manager.lock().await;
    let active_id = state.active_group_id.lock().await.clone();

    tracing::debug!(
        "[apply] building config map for {} cameras",
        request.camera_configs.len()
    );

    let mut new_configs: HashMap<String, CameraGroupConfig> = HashMap::new();
    let mut response_configs: HashMap<String, CameraConfigOutput> = HashMap::new();

    for (cam_id, input) in &request.camera_configs {
        // Prefer existing identity, fall back to detected, error if neither
        let identity: CameraIdentity = if let Some(existing) = existing_identities.get(cam_id) {
            existing.clone()
        } else if let Some(ref detected_list) = detected {
            detected_list
                .iter()
                .find(|d| d.identity.camera_id == *cam_id || d.identity.camera_index == input.camera_index)
                .map(|d| d.identity.clone())
                .ok_or_else(|| {
                    AppError::BadRequest(format!(
                        "Camera '{}' (index {}) not found in detected devices",
                        cam_id, input.camera_index
                    ))
                })?
        } else {
            return Err(AppError::BadRequest(format!(
                "Camera '{}' not found in existing group and no detection run",
                cam_id
            )));
        };

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
        response_configs.insert(cam_id.clone(), output);

        new_configs.insert(
            cam_id.clone(),
            CameraGroupConfig {
                identity,
                capture_config,
            },
        );
    }

    let group_id = if let Some(ref existing_id) = active_id {
        tracing::info!(
            "[apply] updating existing group {existing_id} with {} cameras",
            new_configs.len()
        );
        tracing::debug!(
            "[apply] config diff — cameras: {:?}",
            new_configs.keys().collect::<Vec<_>>()
        );
        let group = manager
            .get_group_mut(existing_id)
            .ok_or_else(|| AppError::Internal("Active group not found in manager".into()))?;
        group
            .apply(new_configs)
            .map_err(|e| AppError::Internal(format!("Failed to apply config update: {e}")))?;
        tracing::info!("[apply] group {existing_id} updated successfully");
        existing_id.clone()
    } else {
        let cam_count = new_configs.len();
        tracing::info!("[apply] creating new group with {cam_count} camera(s)");
        let configs: Vec<CameraGroupConfig> = new_configs.into_values().collect();
        let gid = manager
            .create_or_update_group(configs, None)
            .map_err(|e| AppError::Internal(format!("Failed to create camera group: {e}")))?;
        tracing::info!("[apply] group {gid} created — {cam_count} cameras streaming");
        gid
    };

    *state.active_group_id.lock().await = Some(group_id.clone());

    Ok(Json(CreateCameraGroupResponse {
        group_id,
        camera_configs: response_configs,
    }))
}

// ── Recording ──────────────────────────────────────────────────────────────

/// Start recording on the active camera group
#[utoipa::path(
    post,
    path = "/skellycam/camera/group/all/record/start",
    request_body = StartRecordingRequest,
    responses(
        (status = 200, description = "Recording started", body = bool),
        (status = 400, description = "No active group"),
        (status = 500, description = "Recording start failed")
    )
)]
async fn start_recording(
    State(state): State<Arc<AppState>>,
    Json(request): Json<StartRecordingRequest>,
) -> Result<Json<bool>, AppError> {
    tracing::debug!(
        "[recording] request — dir: '{}'  name: '{}'  mic: {}",
        request.recording_directory,
        request.recording_name,
        request.mic_device_index
    );

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

    let output_dir = if request.recording_directory.is_empty() {
        let default = default_recording_dir()?;
        tracing::info!("[recording] using default dir: {default}");
        default
    } else {
        let expanded = if request.recording_directory.starts_with('~') {
            request
                .recording_directory
                .replace('~', &dirs::home_dir().unwrap_or_default().display().to_string())
        } else {
            request.recording_directory.clone()
        };
        tracing::info!("[recording] using provided dir: {expanded}");
        expanded
    };

    let label = if request.recording_name.is_empty() {
        let ts = recording_timestamp_name();
        tracing::debug!("[recording] auto-generated label: {ts}");
        Some(ts)
    } else {
        Some(request.recording_name.clone())
    };

    tracing::info!(
        "[recording] starting — dir: {output_dir}   label: {}",
        label.as_deref().unwrap_or("—")
    );

    std::fs::create_dir_all(&output_dir)
        .map_err(|e| AppError::Internal(format!("Failed to create recording dir '{output_dir}': {e}")))?;

    eprintln!("[recording] dir created: {output_dir}");

    group
        .start_recording(RecordingParams {
            output_dir,
            label,
        })
        .map_err(|e| AppError::Internal(format!("Failed to start recording: {e}")))?;

    Ok(Json(true))
}

/// Stop recording and return summary
#[utoipa::path(
    get,
    path = "/skellycam/camera/group/all/record/stop",
    responses(
        (status = 200, description = "Recording stopped", body = StopRecordingResponse),
        (status = 400, description = "No active group"),
        (status = 500, description = "Recording stop failed")
    )
)]
async fn stop_recording(
    State(state): State<Arc<AppState>>,
) -> Result<Json<Vec<StopRecordingResponse>>, AppError> {
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

    tracing::info!("[recording] stopping — group: {active_id}");
    let summary = group
        .stop_recording()
        .map_err(|e| AppError::Internal(format!("Failed to stop recording: {e}")))?;

    let mut lines: Vec<String> = Vec::new();
    lines.push(format!(
        "[recording] stopped — {} frames/camera, {} videos, {} CSVs",
        summary.total_frames_per_camera,
        summary.video_paths.len(),
        summary.csv_paths.len()
    ));
    for video_path in &summary.video_paths {
        lines.push(format!("[recording]   video: {}", video_path.display()));
    }
    for csv_path in &summary.csv_paths {
        lines.push(format!("[recording]   timestamps: {}", csv_path.display()));
    }
    lines.push(format!(
        "[recording]   info JSON: {}",
        summary.info_json_path.display()
    ));
    tracing::info!("\n{}", lines.join("\n"));

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

    Ok(Json(vec![StopRecordingResponse {
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
    }]))
}

// ── Pause / unpause ────────────────────────────────────────────────────────

/// Toggle pause on the active camera group
#[utoipa::path(
    get,
    path = "/skellycam/camera/group/all/pause_unpause",
    responses(
        (status = 200, description = "Pause toggled", body = bool),
        (status = 400, description = "No active group")
    )
)]
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

    let was_paused = group.is_paused();
    group.toggle_pause();
    let now_paused = group.is_paused();
    tracing::info!("[pause] group {active_id}: {was_paused} → {now_paused}");
    Ok(Json(now_paused))
}

// ── Close all ──────────────────────────────────────────────────────────────

/// Close all camera groups
#[utoipa::path(
    delete,
    path = "/skellycam/camera/group/close/all",
    responses(
        (status = 200, description = "All groups closed", body = bool)
    )
)]
async fn close_all_groups(
    State(state): State<Arc<AppState>>,
) -> Result<Json<bool>, AppError> {
    tracing::info!("[close] shutting down all camera groups");
    let mut manager = state.camera_manager.lock().await;
    let count = manager.group_count();
    manager.close_all_groups();
    *state.active_group_id.lock().await = None;
    tracing::info!("[close] all {count} group(s) closed");
    Ok(Json(true))
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/// Build the default recording directory: `~/skellycam_data/recordings/<timestamp>/`.
fn default_recording_dir() -> Result<String, AppError> {
    let home = dirs::home_dir()
        .ok_or_else(|| AppError::Internal("Cannot determine home directory".into()))?;
    let base = home.join("skellycam_data").join("recordings");
    let dir = base.join(recording_timestamp_name());
    Ok(dir.display().to_string())
}

/// Generate a filename-safe timestamp like `2026-05-19T12_34_56_gmt-4`.
fn recording_timestamp_name() -> String {
    let now: chrono::DateTime<chrono::Local> = chrono::Local::now();
    let offset_secs = now.offset().local_minus_utc();
    let offset_hours = offset_secs / 3600;
    let sign = if offset_hours >= 0 { "" } else { "-" };
    let abs_hours = offset_hours.abs();
    format!(
        "{}_gmt{}{}",
        now.format("%Y-%m-%dT%H_%M_%S"),
        sign,
        abs_hours
    )
}
