use std::sync::atomic::AtomicBool;
use std::sync::Arc;

use tokio::sync::broadcast;
use tokio::sync::Mutex;

use crate::camera_group_manager::CameraGroupManager;

/// Shared application state accessible from all Axum routes.
///
/// `frame_broadcast` carries JPEG-encoded frontend payload bytes from
/// the camera relay thread to WebSocket clients. `None` when no camera
/// group is actively streaming.
///
/// `relay_thread` holds the join handle for the blocking OS thread that
/// reads frames from the camera group, encodes them, and pushes to the
/// broadcast channel. On close, we set `running = false` and join this
/// thread, which drops the CameraGroup (triggering clean shutdown).
pub struct AppState {
    pub camera_manager: Arc<Mutex<CameraGroupManager>>,
    pub frame_broadcast: Arc<Mutex<Option<broadcast::Sender<Vec<u8>>>>>,
    pub running: Arc<AtomicBool>,
    pub relay_thread: Arc<Mutex<Option<std::thread::JoinHandle<()>>>>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            camera_manager: Arc::new(Mutex::new(CameraGroupManager::new())),
            frame_broadcast: Arc::new(Mutex::new(None)),
            running: Arc::new(AtomicBool::new(true)),
            relay_thread: Arc::new(Mutex::new(None)),
        }
    }
}
