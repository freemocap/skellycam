//! CameraGroupManager: lifecycle management for multiple camera groups.
//!
//! Wraps a `HashMap<String, CameraGroup>` registry keyed by short UUID
//! (first 6 hex characters of a UUIDv4). Provides create/close/list/state
//! operations. Pure Rust — no Python, no PyO3.

use std::collections::HashMap;

use crate::camera_group::{CameraGroup, CameraGroupConfig, CameraStatus};

/// Serializable snapshot of the manager's current state.
#[derive(Debug, Clone, serde::Serialize)]
pub struct ManagerState {
    pub groups: Vec<GroupState>,
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct GroupState {
    pub group_id: String,
    pub camera_count: usize,
    pub cameras: Vec<CameraStatus>,
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
            tracing::info!(
                "CameraGroupManager: replacing existing group {group_id}"
            );
            // Call shutdown on the old group — consumes it
            let mut old_group = existing;
            let _ = old_group.shutdown();
        }

        let mut group = CameraGroup::new(
            configs
                .into_iter()
                .map(|cfg| (cfg.identity.camera_id.clone(), cfg))
                .collect(),
        );
        group.start()?;
        self.groups.insert(group_id.clone(), group);

        tracing::info!("CameraGroupManager: created group {group_id}");
        Ok(group_id)
    }

    /// Remove a camera group from the registry without shutting it down.
    /// Returns `Some(CameraGroup)` if the group existed.
    /// The caller is responsible for shutting down the returned group.
    pub fn remove_group(&mut self, group_id: &str) -> Option<CameraGroup> {
        self.groups.remove(group_id)
    }

    /// Shut down and remove a single camera group by its identifier.
    pub fn close_group(&mut self, group_id: &str) -> anyhow::Result<()> {
        if let Some(mut group) = self.groups.remove(group_id) {
            tracing::info!("CameraGroupManager: closing group {group_id}");
            let _ = group.shutdown();
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
        for (id, mut group) in self.groups.drain() {
            tracing::info!("CameraGroupManager: closing group {id}");
            let _ = group.shutdown();
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
    pub fn to_state_dict(&self) -> ManagerState {
        let groups: Vec<GroupState> = self
            .groups
            .iter()
            .map(|(id, group)| {
                let cameras = group.camera_statuses();
                GroupState {
                    group_id: id.clone(),
                    camera_count: cameras.len(),
                    cameras,
                }
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
