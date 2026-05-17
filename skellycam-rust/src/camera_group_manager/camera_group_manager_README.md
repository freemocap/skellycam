# Camera Group Manager Module

Manages the lifecycle of multiple `CameraGroup` instances. Pure Rust — no Python,
no PyO3. Holds a `HashMap<String, CameraGroup>` registry keyed by short UUID.

## Quick Start

```rust
use skellycam::camera::{detect_cameras, CameraConfig};
use skellycam::camera_group::CameraGroupConfig;
use skellycam::camera_group_manager::CameraGroupManager;

fn main() -> anyhow::Result<()> {
    let identities = detect_cameras()?;

    // Build configs
    let configs: Vec<CameraGroupConfig> = identities.iter()
        .map(|id| CameraGroupConfig {
            identity: id.clone(),
            capture_config: CameraConfig {
                camera_id: id.camera_id.clone(),
                camera_index: id.camera_index as u32,
                width: 1280, height: 720, exposure: -7,
                exposure_mode: "MANUAL".into(), framerate: 30.0, rotation: -1,
            },
        })
        .collect();

    // Create manager and start a group
    let mut manager = CameraGroupManager::new();
    let group_id = manager.create_or_update_group(configs, None)?;
    println!("Created group: {group_id}");

    // Inspect state
    println!("Active groups: {:?}", manager.list_groups());
    let state = manager.to_state_dict();
    println!("{}", serde_json::to_string_pretty(&state)?);

    // Shut down
    manager.close_group(&group_id)?;
    Ok(())
}
```

## Architecture

```
┌─────────────────────────────────────────┐
│  CameraGroupManager (pure Rust)         │
│                                         │
│  groups: HashMap<String, CameraGroup>   │
│                                         │
│  create_or_update(configs, id?) → id    │
│  remove_group(id) → Option<CameraGroup> │
│  close_group(id) → Result              │
│  close_all_groups()                     │
│  list_groups() → Vec<String>           │
│  group_count() → usize                 │
│  to_state_dict() → ManagerState         │
└─────────────────────────────────────────┘
         │
         │ delegates lifecycle to
         ▼
┌─────────────────────────────────────────┐
│  CameraGroup (from camera_group/)       │
│  - start(), apply(), shutdown()         │
│  - try_recv_multiframe()                │
│  - camera_statuses()                    │
│  - pause/unpause/toggle_pause           │
└─────────────────────────────────────────┘
```

## Public API

```rust
impl CameraGroupManager {
    pub fn new() -> Self
    pub fn create_or_update_group(&mut self, configs: Vec<CameraGroupConfig>, group_id: Option<String>) -> anyhow::Result<String>
    pub fn remove_group(&mut self, group_id: &str) -> Option<CameraGroup>
    pub fn close_group(&mut self, group_id: &str) -> anyhow::Result<()>
    pub fn close_all_groups(&mut self)
    pub fn list_groups(&self) -> Vec<String>
    pub fn group_count(&self) -> usize
    pub fn to_state_dict(&self) -> ManagerState
}
```

## Design Decisions

**Pure Rust, no Python.** This module knows nothing about PyO3 or Python dicts.
It is the authoritative Rust-side manager. The PyO3 bridge (`PyO3CameraGroupManager`)
wraps this type for Python consumers.

**Idempotent create_or_update.** Re-creating a group with an existing ID shuts down
the old group first. Safe to call repeatedly — the result is always one group with
the given ID and the latest configs.

**CameraGroup handles lifecycle.** The manager does not directly manage cameras or
threads. It delegates all lifecycle operations to `CameraGroup` (start, apply configs,
shutdown). The manager is a registry, not a controller.

**Serializable state.** `to_state_dict()` returns a `ManagerState` that serializes
to JSON via serde. Used by the CLI test harness for debugging and by the PyO3 bridge
for Python-facing status reporting.

**Drop-safe.** The `Drop` implementation shuts down all remaining groups if the
manager is dropped without explicit `close_all_groups()`. Prevents orphaned camera
threads.

## Files

| File | Purpose |
|---|---|
| `mod.rs` | `CameraGroupManager` struct and all logic |

## Build

```bash
cargo build --release
```
