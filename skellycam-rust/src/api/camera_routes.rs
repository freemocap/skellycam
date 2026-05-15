use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use axum::extract::State;
use axum::routing::post;
use axum::{Json, Router};
use tokio::sync::broadcast;

use crate::camera::{enumerate_directshow_cameras, CameraCaptureConfig};
use crate::camera_group::{CameraGroup, CameraGroupConfig};
use crate::frontend_payload::encode_multiframe;

use super::application_state::AppState;
use super::error::AppError;
use super::models::*;

pub fn camera_routes() -> Router<Arc<AppState>> {
    Router::new()
        .route("/skellycam/camera/detect", post(detect_cameras))
        .route("/skellycam/camera/group/apply", post(create_or_update_group))
        .route("/skellycam/camera/group/close/all", axum::routing::delete(close_all_groups))
}

async fn detect_cameras(
    State(_state): State<Arc<AppState>>,
) -> Result<Json<DetectedCamerasResponse>, AppError> {
    // enumerate_directshow_cameras uses COM (via openpnp-capture) which must run
    // on a dedicated thread, not a tokio worker. spawn_blocking ensures that.
    let cameras = tokio::task::spawn_blocking(|| enumerate_directshow_cameras())
        .await
        .map_err(|e| AppError::Internal(format!("Camera enumeration task panicked: {e}")))?
        .map_err(|e| AppError::Internal(format!("Camera enumeration failed: {e}")))?;

    let count = cameras.len();
    let detected: Vec<DetectedCamera> = cameras
        .into_iter()
        .map(|c| DetectedCamera {
            camera_index: c.camera_index,
            display_name: c.display_name,
            unique_identifier: c.unique_identifier,
            device_path: c.device_path,
            formats: c
                .formats
                .iter()
                .map(|f| DetectedFormat {
                    width: f.width,
                    height: f.height,
                    fps: f.fps,
                    fourcc: f.fourcc,
                    fourcc_str: f.fourcc_str.clone(),
                })
                .collect(),
        })
        .collect();

    Ok(Json(DetectedCamerasResponse {
        cameras: detected,
        camera_count: count,
    }))
}

async fn create_or_update_group(
    State(state): State<Arc<AppState>>,
    Json(request): Json<CameraGroupApplyRequest>,
) -> Result<Json<CreateCameraGroupResponse>, AppError> {
    if request.camera_indices.is_empty() {
        return Err(AppError::BadRequest("camera_indices must not be empty".into()));
    }

    // Close any existing active group first
    close_active_group(&state).await;

    // Enumerate to get camera identities (must run on blocking thread for COM)
    let all_cameras = tokio::task::spawn_blocking(|| enumerate_directshow_cameras())
        .await
        .map_err(|e| AppError::Internal(format!("Camera enumeration panicked: {e}")))?
        .map_err(|e| AppError::Internal(format!("Camera enumeration failed: {e}")))?;

    let mut configs = Vec::new();
    for &index in &request.camera_indices {
        let identity = all_cameras
            .iter()
            .find(|c| c.camera_index == index as i32)
            .cloned()
            .ok_or_else(|| AppError::BadRequest(format!("Camera index {index} not found")))?;

        configs.push(CameraGroupConfig {
            capture_config: CameraCaptureConfig {
                camera_id: identity.unique_identifier.clone(),
                camera_index: index,
                width: 1280,
                height: 720,
                exposure: -7,
                exposure_mode: "MANUAL".to_string(),
                framerate: -1.0,
                rotation: -1,
            },
            identity,
        });
    }

    let camera_count = configs.len();

    // Create the camera group
    let group = CameraGroup::create(configs)
        .map_err(|e| AppError::Internal(format!("Failed to create camera group: {e}")))?;

    // Create broadcast channel for encoded frames
    let (broadcast_tx, _) = broadcast::channel::<Vec<u8>>(4);
    {
        let mut guard = state.frame_broadcast.lock().await;
        *guard = Some(broadcast_tx.clone());
    }

    // Spawn relay thread: owns the entire CameraGroup → receives frames → encodes → broadcasts
    let shutdown_flag = state.running.clone();
    let handle = thread::Builder::new()
        .name("frame-relay".into())
        .spawn(move || {
            relay_loop(group, broadcast_tx, shutdown_flag);
        })
        .map_err(|e| AppError::Internal(format!("Failed to spawn relay thread: {e}")))?;

    {
        let mut guard = state.relay_thread.lock().await;
        *guard = Some(handle);
    }

    Ok(Json(CreateCameraGroupResponse {
        group_id: "active".into(),
        camera_count,
    }))
}

async fn close_all_groups(
    State(state): State<Arc<AppState>>,
) -> Result<Json<CloseAllResponse>, AppError> {
    close_active_group(&state).await;
    Ok(Json(CloseAllResponse { success: true }))
}

async fn close_active_group(state: &Arc<AppState>) {
    state.running.store(false, Ordering::SeqCst);

    let mut guard = state.relay_thread.lock().await;
    if let Some(handle) = guard.take() {
        let _ = handle.join();
    }
    drop(guard);

    // Reset running flag for next group
    state.running.store(true, Ordering::SeqCst);

    let mut guard = state.frame_broadcast.lock().await;
    *guard = None;
}

/// Blocking loop: receive multiframes, encode to JPEG, broadcast to WebSocket clients.
fn relay_loop(
    group: CameraGroup,
    tx: broadcast::Sender<Vec<u8>>,
    shutdown: Arc<std::sync::atomic::AtomicBool>,
) {
    while shutdown.load(Ordering::SeqCst) {
        match group.multi_frame_receiver.recv_timeout(Duration::from_millis(100)) {
            Ok(payload) => {
                match encode_multiframe(&payload) {
                    Ok(binary) => {
                        let _ = tx.send(binary);
                    }
                    Err(e) => {
                        eprintln!("[frame-relay] encode error: {e}");
                    }
                }
            }
            Err(std::sync::mpsc::RecvTimeoutError::Timeout) => continue,
            Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => break,
        }
    }
    // CameraGroup is dropped here → shutdown sent to all cameras
    group.shutdown();
    group.wait_for_shutdown();
    eprintln!("[frame-relay] exited");
}
