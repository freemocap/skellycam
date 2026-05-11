//! Shared application state injected into Axum handlers via State extractor.
//! The CameraGroupManager is the singleton that owns all camera groups.

use std::sync::Arc;
use std::sync::atomic::AtomicBool;
use tokio::sync::RwLock;
use crate::camera_group_manager::CameraGroupManager;

/// Shared state accessible by all HTTP and WebSocket handlers.
pub struct ApplicationState {
    /// Global kill flag — when set to true, all components begin shutdown.
    pub global_kill_flag: Arc<AtomicBool>,
    /// Registry of all active camera groups.
    pub camera_group_manager: Arc<RwLock<CameraGroupManager>>,
}
