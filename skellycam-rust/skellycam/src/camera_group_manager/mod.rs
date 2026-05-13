//! CameraGroupManager: lifecycle management for multiple camera groups.
//!
//! Wraps a `HashMap<String, CameraGroup>` registry keyed by short UUID (first 6
//! hex characters of a UUIDv4). Provides create/close/list/state operations.
//!
//! This is a Rust API — the HTTP layer (Phase 6) will wrap these methods
//! behind Axum route handlers.

use std::collections::HashMap;

use crate::camera_group::{CameraGroup, CameraGroupConfig};

/// Serializable snapshot of the manager's current state.
/// Mirrors the Python `state_dict` format for frontend compatibility.
#[derive(Debug, Clone, serde::Serialize)]
pub struct ManagerState {
    pub groups: Vec<GroupState>,
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct GroupState {
    pub group_id: String,
    pub camera_count: usize,
    pub cameras: Vec<CameraState>,
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct CameraState {
    pub camera_index: i32,
    pub display_name: String,
    pub unique_identifier: String,
    pub width: u32,
    pub height: u32,
}

pub struct CameraGroupManager {
    groups: HashMap<String, CameraGroup>,
}

impl CameraGroupManager {
    pub fn new() -> Self {
        Self {
            groups: HashMap::new(),
        }
    }

    /// Create a new camera group or replace an existing one with the same ID.
    ///
    /// Returns the group UUID (6-char hex string). If `group_id` is provided,
    /// that identifier is used; otherwise a new UUID is generated.
    pub fn create_or_update_group(
        &mut self,
        configs: Vec<CameraGroupConfig>,
        group_id: Option<String>,
    ) -> anyhow::Result<String> {
        let group_id = group_id.unwrap_or_else(|| {
            let uuid = uuid::Uuid::new_v4();
            uuid.as_simple().to_string()[..6].to_string()
        });

        // If a group with this ID already exists, shut it down first
        if let Some(existing) = self.groups.remove(&group_id) {
            tracing::info!("CameraGroupManager: replacing existing group {group_id}");
            existing.shutdown();
            existing.wait_for_shutdown();
        }

        let group = CameraGroup::create(configs)?;
        self.groups.insert(group_id.clone(), group);

        tracing::info!("CameraGroupManager: created group {group_id}");
        Ok(group_id)
    }

    /// Remove a camera group from the registry without shutting it down.
    /// Returns `Some(CameraGroup)` if the group existed, `None` otherwise.
    /// The caller is responsible for shutting down the returned group.
    pub fn remove_group(&mut self, group_id: &str) -> Option<CameraGroup> {
        self.groups.remove(group_id)
    }

    /// Shut down and remove a single camera group by its identifier.
    pub fn close_group(&mut self, group_id: &str) -> anyhow::Result<()> {
        if let Some(group) = self.groups.remove(group_id) {
            tracing::info!("CameraGroupManager: closing group {group_id}");
            group.shutdown();
            group.wait_for_shutdown();
            Ok(())
        } else {
            anyhow::bail!("Group '{group_id}' not found");
        }
    }

    /// Shut down and remove all camera groups.
    pub fn close_all_groups(&mut self) {
        tracing::info!(
            "CameraGroupManager: closing all {} group(s)",
            self.groups.len()
        );
        for (id, group) in self.groups.drain() {
            tracing::info!("CameraGroupManager: closing group {id}");
            group.shutdown();
            group.wait_for_shutdown();
        }
    }

    /// Return the identifiers of all active groups.
    pub fn list_groups(&self) -> Vec<String> {
        self.groups.keys().cloned().collect()
    }

    /// Return the number of active groups.
    pub fn group_count(&self) -> usize {
        self.groups.len()
    }

    /// Produce a serializable snapshot of the manager's state.
    /// Used by the frontend (via WebSocket relay) to display camera status.
    pub fn to_state_dict(&self) -> ManagerState {
        let groups: Vec<GroupState> = self
            .groups
            .iter()
            .map(|(id, group)| GroupState {
                group_id: id.clone(),
                camera_count: group.camera_handles.len(),
                cameras: group
                    .camera_handles
                    .iter()
                    .map(|handle| CameraState {
                        camera_index: handle.identity.camera_index,
                        display_name: handle.identity.display_name.clone(),
                        unique_identifier: handle.identity.unique_identifier.clone(),
                        width: handle.width,
                        height: handle.height,
                    })
                    .collect(),
            })
            .collect();

        ManagerState { groups }
    }
}

impl Default for CameraGroupManager {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for CameraGroupManager {
    fn drop(&mut self) {
        if !self.groups.is_empty() {
            tracing::warn!(
                "CameraGroupManager dropped with {} active group(s) — shutting down",
                self.groups.len()
            );
            self.close_all_groups();
        }
    }
}
