//! CameraGroupManager: singleton registry of CameraGroups.
//! Handles CRUD lifecycle: create, update, close, recording start/stop.
//! Owned by the Axum AppState as Arc<RwLock<CameraGroupManager>>.

pub struct CameraGroupManager {}

impl CameraGroupManager {
    pub fn new() -> Self {
        Self {}
    }
}
