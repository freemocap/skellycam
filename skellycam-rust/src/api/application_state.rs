use std::sync::atomic::AtomicBool;
use std::sync::Arc;

use tokio::sync::Mutex;

use crate::camera_group_manager::CameraGroupManager;

/// Shared application state accessible from all Axum routes.
///
/// `camera_manager` wraps the `CameraGroupManager` registry. Routes acquire
/// the lock briefly to create, query, or close groups — the lock is never
/// held across camera I/O or frame encoding.
///
/// `active_group_id` tracks the single "active" group so routes like
/// `/record/start` and `/pause_unpause` can find it without the caller
/// passing a group ID each time (matches the Python API convention of
/// operating on "all" groups at once).
///
/// `shutdown_flag` is set by the `/shutdown` endpoint and checked by the
/// Axum graceful-shutdown future.
pub struct AppState {
    pub camera_manager: Arc<Mutex<CameraGroupManager>>,
    pub active_group_id: Arc<Mutex<Option<String>>>,
    pub shutdown_flag: Arc<AtomicBool>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            camera_manager: Arc::new(Mutex::new(CameraGroupManager::new())),
            active_group_id: Arc::new(Mutex::new(None)),
            shutdown_flag: Arc::new(AtomicBool::new(false)),
        }
    }
}
