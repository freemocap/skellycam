//! CameraGroup handle — the public interface to a synchronized group of cameras.
//!
//! A `CameraGroup` manages N cameras (N >= 1) synchronized through a shared
//! `BreakableBarrier`. From the outside, it behaves like a single camera —
//! you create it, start it, read frames, and shut it down. Internally, it
//! maintains the camera set and a gatherer thread that collects one frame
//! from each camera per cycle.
//!
//! # Example
//!
//! ```ignore
//! let identities = detect_cameras()?;
//! let configs = build_config_map(identities);
//! let mut group = CameraGroup::new(configs);
//! group.start()?;
//! while let Ok(payload) = group.try_recv_multiframe() {
//!     println!("multiframe {}", payload.frame_number);
//! }
//! group.shutdown()?;
//! ```

use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;

use crate::camera::{Camera, CameraConfig, FramePacket};
use crate::camera_group::sync_utils::BreakableBarrier;
use crate::timestamps::performance::performance_counter_nanoseconds;

use super::dispatcher::{FrontendPayload, RawFrame};
use super::types::{CameraGroupConfig, DispatcherCommand, GathererUpdate, RecordingParams};
use crate::recording::finalizer::RecordingSummary;

// ── Runtime state enum ────────────────────────────────────────────────────────

/// Lifecycle state of the camera group.
///
/// This is a runtime enum — the `CameraGroup` struct persists across all
/// states, holding the same channels, thread handles, and barrier for its
/// entire lifetime. Methods validate the current state at runtime.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CameraGroupState {
    /// Configs stored, no cameras or threads running.
    Created,
    /// All cameras streaming, gatherer running, frames flowing.
    Streaming,
    /// Shutdown initiated, threads unwinding.
    ShuttingDown,
    /// All threads joined, all resources freed. Terminal state.
    Stopped,
}

/// Snapshot of a camera's identity and current config for status reporting.
///
/// Lightweight — no channel handles, no thread handles. Just the fields
/// that downstream consumers (frontend, CLI, recording) need to display.
/// Snapshot of a camera's identity and current config for status reporting.
///
/// Holds the full `CameraConfig` (source of truth) plus identity fields.
/// The `camera_id` is the HashMap key — not duplicated here.
#[derive(Debug, Clone, serde::Serialize)]
pub struct CameraStatus {
    pub camera_name: String,
    pub camera_index: i32,
    pub device_path: String,
    pub config: CameraConfig,
}

// ── CameraGroup handle ────────────────────────────────────────────────────────

/// A synchronized group of cameras.
///
/// # State lifecycle
///
/// ```text
/// Created ── start() ──→ Streaming ── shutdown() ──→ ShuttingDown ──→ Stopped
///   │                                                       │
///   └──────────── shutdown() ────────────────────────────────┘
/// ```
///
/// Within Streaming, `pause()` / `unpause()` toggles whether frames flow
/// downstream. `apply()` can reconfigure, add, or remove cameras.
/// Handle to a CameraGroup's shared frame slots.
///
/// The dispatcher thread writes to these `Arc<Mutex<Option<T>>>` every multiframe.
/// Cloning `FrameSlots` is cheap (`Arc` ref bump) — external consumers like the
/// freemocap pipeline can poll the same slots directly without involving the
/// `CameraGroup` handle.
#[derive(Clone)]
pub struct FrameSlots {
    pub raw_frames: Arc<Mutex<Option<Vec<RawFrame>>>>,
    pub frontend_payload: Arc<Mutex<Option<FrontendPayload>>>,
}

pub struct CameraGroup {
    group_id: String,
    state: CameraGroupState,
    cameras: HashMap<String, Camera>,
    configs: HashMap<String, CameraGroupConfig>,
    barrier: Arc<BreakableBarrier>,
    paused: Arc<AtomicBool>,

    // Gatherer
    gatherer_handle: Option<JoinHandle<()>>,
    gatherer_update_sender: Option<mpsc::Sender<GathererUpdate>>,

    // Dispatcher
    dispatcher_handle: Option<JoinHandle<()>>,
    dispatcher_control_sender: Option<mpsc::Sender<DispatcherCommand>>,
    latest_frontend_payload: Arc<Mutex<Option<FrontendPayload>>>,
    latest_raw_frames: Arc<Mutex<Option<Vec<RawFrame>>>>,
    recording_active: Arc<AtomicBool>,

    // True while the gatherer is running its main loop. Set false on exit
    // (camera disconnect, barrier broken, shutdown, or camera_count==0).
    gatherer_alive: Arc<AtomicBool>,

    // Performance snapshot updated by the gatherer each cycle
    performance_snapshot: Arc<Mutex<Option<String>>>,
}

impl CameraGroup {
    // ── Creation ──────────────────────────────────────────────────────────

    /// Create a new camera group with the given configs.
    ///
    /// The group is created in the `Created` state. No cameras or threads
    /// are started until `start()` is called.
    ///
    /// # Panics
    ///
    /// Panics if `configs` is empty — a camera group requires at least one camera.
    pub fn new(configs: HashMap<String, CameraGroupConfig>) -> Self {
        assert!(
            !configs.is_empty(),
            "CameraGroup requires at least one camera config"
        );
        let group_id = uuid::Uuid::new_v4().as_simple().to_string()[..6].to_string();
        let barrier = Arc::new(BreakableBarrier::new(1)); // placeholder, reset in start()
        Self {
            group_id,
            state: CameraGroupState::Created,
            cameras: HashMap::new(),
            configs,
            gatherer_handle: None,
            gatherer_update_sender: None,
            dispatcher_handle: None,
            dispatcher_control_sender: None,
            latest_frontend_payload: Arc::new(Mutex::new(None)),
            latest_raw_frames: Arc::new(Mutex::new(None)),
            recording_active: Arc::new(AtomicBool::new(false)),
            performance_snapshot: Arc::new(Mutex::new(None)),
            barrier,
            paused: Arc::new(AtomicBool::new(false)),
            gatherer_alive: Arc::new(AtomicBool::new(false)),
        }
    }

    // ── Lifecycle ─────────────────────────────────────────────────────────

    /// Start all camera threads and the gatherer.
    ///
    /// Creates a `BreakableBarrier` with count = camera_count + 1 (gatherer).
    /// Spawns each camera via `Camera::start()`, then spawns the gatherer thread.
    ///
    /// # Errors
    ///
    /// Returns an error if:
    /// - The group is not in the `Created` state
    /// - Any camera fails to start (hardware setup failure)
    pub fn start(&mut self) -> anyhow::Result<()> {
        if self.state != CameraGroupState::Created {
            anyhow::bail!(
                "Cannot start CameraGroup in state {:?} — must be Created",
                self.state
            );
        }

        let requested_count = self.configs.len();
        tracing::info!(
            "[CameraGroup {}] starting {} camera(s)",
            self.group_id, requested_count
        );

        // Start paused — successful cameras spin in the paused loop after
        // setup and never reach barrier.wait(), giving us time to sort out
        // which ones actually opened the hardware.
        self.paused.store(true, Ordering::SeqCst);

        // Barrier: one slot per camera + one for the gatherer
        self.barrier = Arc::new(BreakableBarrier::new(requested_count + 1));

        // Spawn all camera threads
        let mut spawn_failures: Vec<String> = Vec::new();
        for (camera_id, group_config) in &self.configs {
            match Camera::start(
                group_config.identity.clone(),
                group_config.capture_config.clone(),
                self.barrier.clone(),
                self.paused.clone(),
                0,
            ) {
                Ok(camera) => {
                    self.cameras.insert(camera_id.clone(), camera);
                }
                Err(e) => {
                    tracing::warn!(
                        "[CameraGroup {}] thread spawn failed for '{}' ({}): {}",
                        self.group_id,
                        camera_id,
                        group_config.identity.label(),
                        e
                    );
                    spawn_failures.push(camera_id.clone());
                }
            }
        }
        for id in &spawn_failures {
            self.configs.remove(id);
        }

        if self.cameras.is_empty() {
            self.paused.store(false, Ordering::SeqCst);
            anyhow::bail!(
                "All {} camera(s) failed to spawn — no cameras available",
                requested_count
            );
        }

        // Wait for each camera to finish hardware setup (stream open +
        // 30-frame stabilization). Cameras that succeed send Ready then
        // enter the paused spin; cameras that fail send Error instead.
        let stabilize_timeout = std::time::Duration::from_secs(15);
        let mut stabilization_failures: Vec<String> = Vec::new();
        for (camera_id, camera) in &self.cameras {
            match camera.wait_until_ready(stabilize_timeout) {
                Ok(()) => {}
                Err(msg) => {
                    tracing::warn!(
                        "[CameraGroup {}] camera '{}' hardware setup failed: {}",
                        self.group_id, camera_id, msg
                    );
                    stabilization_failures.push(camera_id.clone());
                }
            }
        }

        // Clean up failed cameras
        for id in &stabilization_failures {
            self.configs.remove(id);
            if let Some(camera) = self.cameras.remove(id) {
                let _ = camera.shutdown();
            }
        }

        if self.cameras.is_empty() {
            self.paused.store(false, Ordering::SeqCst);
            anyhow::bail!(
                "All {} camera(s) failed hardware setup — no cameras available",
                requested_count
            );
        }

        let total_failures = spawn_failures.len() + stabilization_failures.len();
        if total_failures > 0 {
            tracing::warn!(
                "[CameraGroup {}] {} of {} camera(s) failed, continuing with {}",
                self.group_id,
                total_failures,
                requested_count,
                self.cameras.len()
            );
        }

        // Correct the barrier count — no cameras are at barrier.wait()
        // because all successful cameras are spinning in the paused loop.
        let camera_count = self.cameras.len();
        self.barrier.set_total(camera_count + 1);

        // Release cameras into the capture loop
        self.paused.store(false, Ordering::SeqCst);

        // Collect frame receivers from each camera for the gatherer.
        // After take_frame_receiver(), the Camera handle's try_recv_frame()
        // returns Disconnected — the gatherer is now the frame consumer.
        let mut frame_receivers: Vec<(String, mpsc::Receiver<FramePacket>)> =
            Vec::with_capacity(camera_count);
        for (id, camera) in self.cameras.iter_mut() {
            frame_receivers.push((id.clone(), camera.take_frame_receiver()));
        }

        // Collect shared camera configs for the dispatcher — the dispatcher
        // reads actual negotiated framerates from these when creating recorders.
        let shared_configs: super::types::SharedConfigMap = self
            .cameras
            .iter()
            .map(|(id, camera)| (id.clone(), camera.shared_config()))
            .collect();

        // Unbounded channel — gatherer never blocks on send
        let (multi_frame_sender, multi_frame_receiver) = mpsc::channel();
        let (update_sender, update_receiver) = mpsc::channel::<GathererUpdate>();
        let (control_sender, control_receiver) = mpsc::channel::<DispatcherCommand>();

        let gatherer_handle = super::gatherer::spawn_gatherer(
            frame_receivers,
            multi_frame_sender,
            update_receiver,
            self.barrier.clone(),
            self.paused.clone(),
            self.gatherer_alive.clone(),
            self.performance_snapshot.clone(),
        );

        let dispatcher_handle = super::dispatcher::spawn_dispatcher(
            multi_frame_receiver,
            control_receiver,
            self.latest_frontend_payload.clone(),
            self.latest_raw_frames.clone(),
            self.recording_active.clone(),
            shared_configs,
        );

        self.gatherer_handle = Some(gatherer_handle);
        self.gatherer_update_sender = Some(update_sender);
        self.dispatcher_handle = Some(dispatcher_handle);
        self.dispatcher_control_sender = Some(control_sender);
        self.state = CameraGroupState::Streaming;

        tracing::info!(
            "[CameraGroup {}] started — {} cameras streaming",
            self.group_id,
            self.cameras.len()
        );
        Ok(())
    }

    /// Apply a new set of camera configs.
    ///
    /// Pauses the group, diffs the new configs against the current set, applies
    /// changes (reconfigure / add camera / remove camera), then unpauses. This
    /// ensures that the gatherer is idle and no cameras are blocked at the
    /// barrier while `set_total()` or shutdown operations happen.
    ///
    /// - **Changed configs** (same camera ID, different settings): sends
    ///   `Configure` command to the camera thread, which applies settings
    ///   on its existing COM context.
    /// - **New cameras**: spawns the camera thread and notifies the gatherer.
    /// - **Removed cameras**: shuts down the camera thread and notifies the gatherer.
    ///
    /// Calling with the same configs repeatedly is a no-op.
    ///
    /// Only valid in the `Streaming` state.
    pub fn apply(&mut self, new_configs: HashMap<String, CameraGroupConfig>) -> anyhow::Result<()> {
        if self.state != CameraGroupState::Streaming {
            anyhow::bail!(
                "Cannot apply configs to CameraGroup in state {:?} — must be Streaming",
                self.state
            );
        }

        // Pause the gatherer before making any changes — cameras are not at
        // the barrier while paused, so set_total() and shutdown() are safe.
        self.pause();
        std::thread::sleep(std::time::Duration::from_millis(100));

        // Compute the diff
        let mut changed = Vec::new();
        let mut added = Vec::new();
        let mut removed = Vec::new();

        for (id, new_cfg) in &new_configs {
            match self.configs.get(id) {
                Some(existing_cfg) => {
                    if !camera_config_eq(&existing_cfg.capture_config, &new_cfg.capture_config) {
                        changed.push((id.clone(), new_cfg.clone()));
                    }
                }
                None => {
                    added.push((id.clone(), new_cfg.clone()));
                }
            }
        }

        for id in self.configs.keys() {
            if !new_configs.contains_key(id) {
                removed.push(id.clone());
            }
        }

        // Reconfigure changed cameras
        for (id, new_cfg) in &changed {
            self.reconfigure_camera(id, &new_cfg.capture_config)?;
        }

        // Add new cameras
        for (id, new_cfg) in &added {
            self.add_camera(id.clone(), new_cfg.clone())?;
        }

        // Remove cameras no longer in the config set
        for id in &removed {
            self.remove_camera(id)?;
        }

        // Store new configs
        self.configs = new_configs;

        // Push updated shared config refs to the dispatcher so it sees
        // actual framerates for any newly added or reconfigured cameras.
        if !added.is_empty() || !changed.is_empty() {
            let updated_configs: super::types::SharedConfigMap = self
                .cameras
                .iter()
                .map(|(id, camera)| (id.clone(), camera.shared_config()))
                .collect();
            if let Some(ref sender) = self.dispatcher_control_sender {
                let _ = sender.send(super::types::DispatcherCommand::UpdateConfigs {
                    configs: updated_configs,
                });
            }
        }

        let total = changed.len() + added.len() + removed.len();
        if total > 0 {
            tracing::info!(
                "[CameraGroup {}] applied configs: {} reconfigured, {} added, {} removed",
                self.group_id,
                changed.len(),
                added.len(),
                removed.len()
            );
        }

        // Resume frame flow now that all changes are applied
        self.unpause();
        std::thread::sleep(std::time::Duration::from_millis(100));

        Ok(())
    }

    /// Shut down all cameras and the gatherer.
    ///
    /// Sends shutdown commands to all cameras, breaks the barrier, and joins
    /// all threads. Consumes the group (transitions to `Stopped`).
    pub fn shutdown(&mut self) -> anyhow::Result<()> {
        if self.state == CameraGroupState::Stopped {
            anyhow::bail!("CameraGroup is already Stopped");
        }

        tracing::info!("[CameraGroup {}] shutting down", self.group_id);
        self.state = CameraGroupState::ShuttingDown;

        // Shut down each camera
        let camera_ids: Vec<String> = self.cameras.keys().cloned().collect();
        for id in camera_ids {
            if let Some(camera) = self.cameras.remove(&id) {
                if let Err(e) = camera.shutdown() {
                    tracing::error!(
                        "[CameraGroup {}] camera '{}' shutdown error: {}",
                        self.group_id, id, e
                    );
                }
            }
        }

        // Send shutdown to dispatcher
        if let Some(sender) = &self.dispatcher_control_sender {
            let _ = sender.send(DispatcherCommand::Shutdown);
        }

        // Break the barrier to release the gatherer
        self.barrier.break_barrier();

        // Join the gatherer thread
        if let Some(handle) = self.gatherer_handle.take() {
            if let Err(e) = handle.join() {
                tracing::error!(
                    "[CameraGroup {}] gatherer thread panicked: {:?}",
                    self.group_id,
                    e.downcast_ref::<&str>().unwrap_or(&"unknown panic message")
                );
            }
        }

        // Join the dispatcher thread
        if let Some(handle) = self.dispatcher_handle.take() {
            if let Err(e) = handle.join() {
                tracing::error!(
                    "[CameraGroup {}] dispatcher thread panicked: {:?}",
                    self.group_id,
                    e.downcast_ref::<&str>().unwrap_or(&"unknown panic message")
                );
            }
        }

        self.state = CameraGroupState::Stopped;
        tracing::info!("[CameraGroup {}] shutdown complete", self.group_id);
        Ok(())
    }

    // ── Frontend polling ──────────────────────────────────────────────────

    /// Return the latest encoded frontend payload, if any.
    ///
    /// The dispatcher thread encodes every multiframe and stores the result
    /// in a shared slot. This method returns a clone of the latest one.
    /// Returns `None` if no payload has been produced yet.
    pub fn latest_frontend_payload(&self) -> Option<FrontendPayload> {
        self.latest_frontend_payload
            .lock()
            .ok()
            .and_then(|guard| guard.clone())
    }

    /// Return the latest per-camera raw JPEG frames, if any.
    ///
    /// The dispatcher stores individual camera JPEGs in a shared slot each
    /// multiframe. Decode them on demand via `skellycam::decode::mjpeg_to_rgb()`.
    /// Returns `None` if no multiframe has been processed yet.
    pub fn latest_raw_frames(&self) -> Option<Vec<RawFrame>> {
        self.latest_raw_frames
            .lock()
            .ok()
            .and_then(|guard| guard.clone())
    }

    /// Return clones of the shared frame slots for external consumers.
    ///
    /// The dispatcher thread writes into these slots every multiframe. External
    /// consumers (like the freemocap pipeline) can poll the same `Arc` slots
    /// directly without going through the `CameraGroup` handle or copying data
    /// across process boundaries. Each clone is a cheap `Arc` ref bump.
    pub fn frame_slots(&self) -> FrameSlots {
        FrameSlots {
            raw_frames: self.latest_raw_frames.clone(),
            frontend_payload: self.latest_frontend_payload.clone(),
        }
    }

    // ── Capture control ───────────────────────────────────────────────────

    /// Pause frame capture and output.
    ///
    /// Sets a shared atomic flag checked by every camera thread and the gatherer
    /// at the end of each cycle. Cameras and the gatherer complete their current
    /// cycle (so no partial frames exist) then spin in place checking for commands
    /// and updates respectively. No frames are captured, no frame numbers advance,
    /// and no thread is blocked at the barrier — safe to call `barrier.set_total()`
    /// during subsequent `apply()` operations.
    pub fn pause(&mut self) {
        self.paused.store(true, Ordering::SeqCst);
    }

    /// Resume frame output.
    pub fn unpause(&mut self) {
        self.paused.store(false, Ordering::SeqCst);
    }

    /// Toggle between paused and unpaused.
    pub fn toggle_pause(&mut self) {
        let was_paused = self.paused.load(Ordering::SeqCst);
        self.paused.store(!was_paused, Ordering::SeqCst);
    }

    /// Whether the gatherer is still running.
    ///
    /// Returns `false` if the gatherer has exited for any reason (camera
    /// disconnect, barrier broken, shutdown, or zero cameras remaining).
    /// Returns `true` during normal streaming operation.
    pub fn is_alive(&self) -> bool {
        self.gatherer_alive.load(Ordering::SeqCst)
    }

    /// Whether the group is currently paused.
    pub fn is_paused(&self) -> bool {
        self.paused.load(Ordering::SeqCst)
    }

    // ── Recording ────────────────────────────────────────────────────────

    /// Begin recording frames to disk.
    ///
    /// Sends a `StartRecording` command to the dispatcher thread. The dispatcher
    /// will create per-camera VideoRecorders and CsvWriters.
    pub fn start_recording(&mut self, params: RecordingParams) -> anyhow::Result<()> {
        let sender = self
            .dispatcher_control_sender
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("Dispatcher not running"))?;
        sender
            .send(DispatcherCommand::StartRecording { params })
            .map_err(|_| anyhow::anyhow!("Dispatcher disconnected"))?;
        Ok(())
    }

    /// Stop recording and return a summary of the recording session.
    pub fn stop_recording(&mut self) -> anyhow::Result<RecordingSummary> {
        let (tx, rx) = mpsc::channel();
        let sender = self
            .dispatcher_control_sender
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("Dispatcher not running"))?;
        sender
            .send(DispatcherCommand::StopRecording { response_tx: tx })
            .map_err(|_| anyhow::anyhow!("Dispatcher disconnected"))?;
        rx.recv()
            .map_err(|_| anyhow::anyhow!("Dispatcher did not respond"))
    }

    /// Whether the group is currently recording.
    pub fn is_recording(&self) -> bool {
        self.recording_active.load(Ordering::SeqCst)
    }

    // ── Accessors ─────────────────────────────────────────────────────────

    /// Return the latest performance snapshot JSON from the gatherer, if any.
    pub fn latest_performance_snapshot(&self) -> Option<String> {
        self.performance_snapshot.lock().ok().and_then(|g| g.clone())
    }

    /// Number of cameras currently in the group.
    pub fn camera_count(&self) -> usize {
        self.cameras.len()
    }

    /// The group's current lifecycle state.
    pub fn state(&self) -> CameraGroupState {
        self.state
    }

    /// The group's unique identifier (first 6 chars of a UUID v4).
    pub fn group_id(&self) -> &str {
        &self.group_id
    }

    /// References to all camera identities.
    pub fn camera_identities(&self) -> Vec<&crate::camera::CameraIdentity> {
        self.cameras.values().map(|c| c.identity()).collect()
    }

    /// Snapshots of all cameras' identity and current config.
    ///
    /// Used for status reporting — no channel or thread handles.
    pub fn camera_statuses(&self) -> Vec<CameraStatus> {
        self.cameras
            .iter()
            .map(|(_id, camera)| {
                let identity = camera.identity();
                CameraStatus {
                    camera_name: identity.camera_name.clone(),
                    camera_index: identity.camera_index,
                    device_path: identity.device_path.clone(),
                    config: camera.config().clone(),
                }
            })
            .collect()
    }

    // ── Private helpers ───────────────────────────────────────────────────

    /// Send a `Configure` command to a running camera.
    ///
    /// The camera thread applies the new settings on its existing COM context.
    /// Settings that can be changed on-the-fly (exposure) take effect
    /// immediately. Settings that require a stream restart (resolution,
    /// framerate) may not take full effect until the camera is restarted.
    fn reconfigure_camera(&self, camera_id: &str, config: &CameraConfig) -> anyhow::Result<()> {
        let camera = self
            .cameras
            .get(camera_id)
            .ok_or_else(|| anyhow::anyhow!("Camera '{}' not found in group", camera_id))?;
        camera.configure(config.clone());
        Ok(())
    }

    /// Start a new camera, extract its frame receiver, and notify the
    /// gatherer via the update channel. Updates the barrier count to
    /// include the new participant.
    fn add_camera(
        &mut self,
        camera_id: String,
        group_config: CameraGroupConfig,
    ) -> anyhow::Result<()> {
        // Update barrier count BEFORE starting the camera so the
        // new camera joins with the correct barrier total.
        let new_total = self.cameras.len() + 1 + 1; // existing + new + gatherer
        self.barrier.set_total(new_total);

        // The payload's frame_number is the gatherer's step at assembly
        // time. After the barrier releases, every camera increments
        // frame_number past that value. Adding 1 matches what the
        // existing cameras will send next — without this, the new
        // camera is permanently one frame behind.
        let current_frame = self
            .latest_frontend_payload
            .lock()
            .ok()
            .and_then(|g| g.as_ref().map(|p| p.frame_number))
            .unwrap_or(0)
            + 1;

        let mut camera = Camera::start(
            group_config.identity.clone(),
            group_config.capture_config.clone(),
            self.barrier.clone(),
            self.paused.clone(),
            current_frame,
        )
        .map_err(|e| {
            // Revert barrier count on failure
            let old_total = self.cameras.len() + 1;
            self.barrier.set_total(old_total);
            anyhow::anyhow!(
                "Failed to add camera '{}' ({}): {}",
                camera_id,
                group_config.identity.label(),
                e
            )
        })?;

        let frame_receiver = camera.take_frame_receiver();

        let stabilize_start = std::time::Instant::now();
        tracing::debug!(
            "[CameraGroup {}] waiting for camera '{}' to stabilize...",
            self.group_id, camera_id,
        );
        camera
            .wait_until_ready(std::time::Duration::from_secs(15))
            .map_err(|msg| {
                anyhow::anyhow!("Camera '{}' stabilization failed: {msg}", camera_id)
            })?;
        tracing::info!(
            "[CameraGroup {}] camera '{}' stabilized in {:.1}s",
            self.group_id, camera_id,
            stabilize_start.elapsed().as_secs_f64()
        );

        self.cameras.insert(camera_id.clone(), camera);

        // Now notify the gatherer — the camera is ready and streaming
        let update_sender = self
            .gatherer_update_sender
            .as_ref()
            .expect("gatherer update channel not initialized");
        update_sender
            .send(GathererUpdate::AddCamera {
                camera_id: camera_id.clone(),
                frame_receiver,
            })
            .map_err(|_| anyhow::anyhow!("Gatherer disconnected — cannot add camera"))?;

        tracing::info!(
            "[CameraGroup {}] added camera '{}' — {} total",
            self.group_id,
            camera_id,
            self.cameras.len()
        );
        Ok(())
    }

    /// Shut down a running camera and notify the gatherer to stop
    /// collecting from it. Updates the barrier count.
    fn remove_camera(&mut self, camera_id: &str) -> anyhow::Result<()> {
        let camera = self
            .cameras
            .remove(camera_id)
            .ok_or_else(|| anyhow::anyhow!("Camera '{}' not found in group", camera_id))?;

        camera.shutdown().map_err(|e| {
            anyhow::anyhow!("Failed to shut down camera '{}': {}", camera_id, e)
        })?;

        // Notify the gatherer to stop expecting frames from this camera
        let update_sender = self
            .gatherer_update_sender
            .as_ref()
            .expect("gatherer update channel not initialized");
        let _ = update_sender.send(GathererUpdate::RemoveCamera {
            camera_id: camera_id.to_string(),
        });

        // Update barrier for the reduced camera count
        let new_count = if self.cameras.is_empty() {
            1 // placeholder — group will likely shut down
        } else {
            self.cameras.len() + 1 // remaining cameras + gatherer
        };
        self.barrier.set_total(new_count);

        tracing::info!(
            "[CameraGroup {}] removed camera '{}' — {} remaining",
            self.group_id,
            camera_id,
            self.cameras.len()
        );
        Ok(())
    }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/// Compare two `CameraConfig` values for equality.
///
/// `CameraConfig` does not derive `PartialEq`, so we compare the fields
/// that affect capture behavior. `camera_id` and `camera_index` are
/// identity fields that do not change for a given physical device.
fn camera_config_eq(a: &CameraConfig, b: &CameraConfig) -> bool {
    a.width == b.width
        && a.height == b.height
        && a.exposure == b.exposure
        && a.exposure_mode == b.exposure_mode
        && (a.framerate - b.framerate).abs() < 0.1
        && a.rotation == b.rotation
}

// ── Gatherer cycle states ────────────────────────────────────────────────────

/// High-frequency states of the gatherer's internal frame cycle.
///
/// Every transition automatically records a nanosecond-precision monotonic
/// timestamp. These timestamps populate the `MultiFramePayload`'s gatherer-level
/// fields.
///
/// Cycle order: `CollectingFrames → AllFramesReceived → WaitingAtBarrier
/// → AssemblingPayload → SendingDownstream → CollectingFrames`. The barrier
/// fires the moment the last frame arrives, releasing all cameras to begin
/// their next capture spin in parallel with the gatherer's payload work.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GathererState {
    /// Receiving one `FramePacket` from each camera.
    CollectingFrames,
    /// All frames received. Marker state immediately before entering the
    /// barrier — no per-cycle work happens here.
    AllFramesReceived,
    /// Blocked at `BreakableBarrier::wait()`, synchronized with all cameras.
    WaitingAtBarrier,
    /// Barrier released; building the `MultiFramePayload` struct.
    AssemblingPayload,
    /// Sending `MultiFramePayload` through channel to downstream consumer.
    SendingDownstream,
}

/// Gatherer-level timestamps populated by state transitions.
///
/// These represent the gatherer's own loop lifecycle (one set per multiframe
/// cycle, distinct from the per-camera per-frame timestamps in
/// `FrameLifecycleTimestamps`).
#[derive(Debug, Clone, Copy)]
pub struct GathererTimestamps {
    /// Stamped at the start of each gatherer iteration (top of the
    /// CollectingFrames state). For iteration 0 this is when the gatherer
    /// thread began; for every subsequent iteration it equals the previous
    /// iteration's `post_send_downstream_ns`. The interval
    /// `all_frames_received_ns - collecting_start_ns` is the time the
    /// gatherer spent blocked waiting on `receiver.recv()` for every camera.
    pub collecting_start_ns: i64,
    /// Stamped when the last camera's `FramePacket` is received in this cycle.
    pub all_frames_received_ns: i64,
    /// Stamped when the gatherer itself exits `barrier.wait()`.
    pub post_barrier_ns: i64,
    /// Stamped after the `MultiFramePayload` struct is assembled.
    pub payload_assembled_ns: i64,
    /// Stamped just before `multi_frame_sender.send(payload)` is called.
    pub pre_send_downstream_ns: i64,
}

impl GathererTimestamps {
    pub fn new() -> Self {
        Self {
            collecting_start_ns: 0,
            all_frames_received_ns: 0,
            post_barrier_ns: 0,
            payload_assembled_ns: 0,
            pre_send_downstream_ns: 0,
        }
    }
}

impl Default for GathererTimestamps {
    fn default() -> Self {
        Self::new()
    }
}

/// Manages the gatherer's runtime state cycle with automatic timestamp recording.
///
/// Every call to `transition_to()`:
/// 1. Validates that the transition is legal.
/// 2. Records a nanosecond timestamp in `timestamps`.
/// 3. Updates the current state.
pub struct GathererStateMachine {
    state: GathererState,
    pub timestamps: GathererTimestamps,
}

impl GathererStateMachine {
    pub fn new() -> Self {
        let now = performance_counter_nanoseconds();
        let mut timestamps = GathererTimestamps::new();
        timestamps.collecting_start_ns = now;
        Self {
            state: GathererState::CollectingFrames,
            timestamps,
        }
    }

    /// Transition to `next` state.
    ///
    /// Returns `Err(GathererInvalidTransition)` if the transition is not legal.
    /// On success, the corresponding timestamp field(s) are populated
    /// automatically.
    pub fn transition_to(
        &mut self,
        next: GathererState,
    ) -> Result<(), GathererInvalidTransition> {
        let now = performance_counter_nanoseconds();
        self.validate(next)?;
        self.record_timestamp(next, now);
        self.state = next;
        Ok(())
    }

    pub fn current_state(&self) -> GathererState {
        self.state
    }

    fn validate(&self, next: GathererState) -> Result<(), GathererInvalidTransition> {
        let valid = matches!(
            (self.state, next),
            (GathererState::CollectingFrames, GathererState::AllFramesReceived)
                | (GathererState::AllFramesReceived, GathererState::WaitingAtBarrier)
                | (GathererState::WaitingAtBarrier, GathererState::AssemblingPayload)
                | (GathererState::AssemblingPayload, GathererState::SendingDownstream)
                | (GathererState::SendingDownstream, GathererState::CollectingFrames)
        );
        if valid {
            Ok(())
        } else {
            Err(GathererInvalidTransition {
                from: self.state,
                to: next,
            })
        }
    }

    fn record_timestamp(&mut self, next: GathererState, now: i64) {
        match next {
            GathererState::AllFramesReceived => {
                self.timestamps.all_frames_received_ns = now;
            }
            GathererState::WaitingAtBarrier => {
                // About to call barrier.wait().
            }
            GathererState::AssemblingPayload => {
                self.timestamps.post_barrier_ns = now;
            }
            GathererState::SendingDownstream => {
                self.timestamps.payload_assembled_ns = now;
                self.timestamps.pre_send_downstream_ns = now;
            }
            GathererState::CollectingFrames => {
                // Stamp the start of the next iteration's collection phase.
                self.timestamps.collecting_start_ns = now;
            }
        }
    }
}

impl Default for GathererStateMachine {
    fn default() -> Self {
        Self::new()
    }
}

impl std::fmt::Debug for GathererStateMachine {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("GathererStateMachine")
            .field("state", &self.state)
            .field("timestamps", &self.timestamps)
            .finish()
    }
}

/// Error returned when an invalid gatherer state transition is attempted.
#[derive(Debug, Clone, Copy)]
pub struct GathererInvalidTransition {
    pub from: GathererState,
    pub to: GathererState,
}

impl std::fmt::Display for GathererInvalidTransition {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "Invalid gatherer state transition: {:?} → {:?}",
            self.from, self.to
        )
    }
}

impl std::error::Error for GathererInvalidTransition {}

// ── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gatherer_state_machine_full_cycle() {
        let mut gsm = GathererStateMachine::new();
        assert_eq!(gsm.current_state(), GathererState::CollectingFrames);

        gsm.transition_to(GathererState::AllFramesReceived).unwrap();
        assert_eq!(gsm.current_state(), GathererState::AllFramesReceived);
        assert!(gsm.timestamps.all_frames_received_ns > 0);

        gsm.transition_to(GathererState::WaitingAtBarrier).unwrap();
        assert_eq!(gsm.current_state(), GathererState::WaitingAtBarrier);

        gsm.transition_to(GathererState::AssemblingPayload).unwrap();
        assert_eq!(gsm.current_state(), GathererState::AssemblingPayload);
        assert!(gsm.timestamps.post_barrier_ns > 0);

        gsm.transition_to(GathererState::SendingDownstream).unwrap();
        assert_eq!(gsm.current_state(), GathererState::SendingDownstream);
        assert!(gsm.timestamps.payload_assembled_ns > 0);
        assert!(gsm.timestamps.pre_send_downstream_ns > 0);

        gsm.transition_to(GathererState::CollectingFrames).unwrap();
        assert_eq!(gsm.current_state(), GathererState::CollectingFrames);
    }

    #[test]
    fn gatherer_state_machine_rejects_invalid_transitions() {
        let mut gsm = GathererStateMachine::new();

        // Cannot skip from CollectingFrames to WaitingAtBarrier
        assert!(gsm
            .transition_to(GathererState::WaitingAtBarrier)
            .is_err());

        // Advance one step, cannot go backwards
        gsm.transition_to(GathererState::AllFramesReceived).unwrap();
        assert!(gsm
            .transition_to(GathererState::CollectingFrames)
            .is_err());
    }

    #[test]
    fn gatherer_state_machine_timestamps_are_monotonic() {
        let mut gsm = GathererStateMachine::new();

        gsm.transition_to(GathererState::AllFramesReceived).unwrap();
        let all_recv = gsm.timestamps.all_frames_received_ns;

        gsm.transition_to(GathererState::WaitingAtBarrier).unwrap();

        gsm.transition_to(GathererState::AssemblingPayload).unwrap();
        let post_barrier = gsm.timestamps.post_barrier_ns;
        assert!(
            post_barrier >= all_recv,
            "post_barrier_ns must be >= all_frames_received_ns"
        );

        gsm.transition_to(GathererState::SendingDownstream).unwrap();
        let assembled = gsm.timestamps.payload_assembled_ns;
        assert!(
            assembled >= post_barrier,
            "payload_assembled_ns must be >= post_barrier_ns"
        );
    }

    #[test]
    fn camera_group_new_requires_configs() {
        let mut configs = HashMap::new();
        configs.insert(
            "cam_1".to_string(),
            CameraGroupConfig {
                identity: crate::camera::CameraIdentity {
                    camera_name: "Test Cam".into(),
                    camera_index: 0,
                    camera_id: "cam_1".into(),
                    device_path: String::new(),
                    formats: Vec::new(),
                },
                capture_config: CameraConfig {
                    camera_id: "cam_1".into(),
                    camera_index: 0,
                    width: 640,
                    height: 480,
                    exposure: -7,
                    exposure_mode: "MANUAL".into(),
                    framerate: -1.0,
                    rotation: -1,
                },
            },
        );

        let group = CameraGroup::new(configs);
        assert_eq!(group.state(), CameraGroupState::Created);
        assert_eq!(group.camera_count(), 0); // No cameras until start()
        assert!(!group.is_paused());
        assert!(!group.is_recording());
        assert!(!group.group_id().is_empty());
    }

    #[test]
    #[should_panic(expected = "CameraGroup requires at least one camera config")]
    fn camera_group_new_panics_on_empty_configs() {
        CameraGroup::new(HashMap::new());
    }

    #[test]
    fn camera_group_pause_unpause_toggle() {
        let mut configs = HashMap::new();
        configs.insert(
            "cam_1".to_string(),
            CameraGroupConfig {
                identity: crate::camera::CameraIdentity {
                    camera_name: "Test Cam".into(),
                    camera_index: 0,
                    camera_id: "cam_1".into(),
                    device_path: String::new(),
                    formats: Vec::new(),
                },
                capture_config: CameraConfig {
                    camera_id: "cam_1".into(),
                    camera_index: 0,
                    width: 640,
                    height: 480,
                    exposure: -7,
                    exposure_mode: "MANUAL".into(),
                    framerate: -1.0,
                    rotation: -1,
                },
            },
        );

        let mut group = CameraGroup::new(configs);
        assert!(!group.is_paused());

        group.pause();
        assert!(group.is_paused());

        group.unpause();
        assert!(!group.is_paused());

        group.toggle_pause();
        assert!(group.is_paused());

        group.toggle_pause();
        assert!(!group.is_paused());
    }

    #[test]
    fn camera_group_start_fails_when_not_created() {
        let mut configs = HashMap::new();
        configs.insert(
            "cam_1".to_string(),
            CameraGroupConfig {
                identity: crate::camera::CameraIdentity {
                    camera_name: "Test Cam".into(),
                    camera_index: 0,
                    camera_id: "cam_1".into(),
                    device_path: String::new(),
                    formats: Vec::new(),
                },
                capture_config: CameraConfig {
                    camera_id: "cam_1".into(),
                    camera_index: 0,
                    width: 640,
                    height: 480,
                    exposure: -7,
                    exposure_mode: "MANUAL".into(),
                    framerate: -1.0,
                    rotation: -1,
                },
            },
        );

        let mut group = CameraGroup::new(configs);
        // Manually set state to Streaming to test the guard
        group.state = CameraGroupState::Streaming;
        let result = group.start();
        assert!(result.is_err());
    }

    #[test]
    fn camera_config_eq_detects_changes() {
        let a = CameraConfig {
            camera_id: "cam_1".into(),
            camera_index: 0,
            width: 640,
            height: 480,
            exposure: -7,
            exposure_mode: "MANUAL".into(),
            framerate: -1.0,
            rotation: -1,
        };

        let b = CameraConfig {
            exposure: -5, // changed
            ..a.clone()
        };

        assert!(camera_config_eq(&a, &a)); // reflexive
        assert!(!camera_config_eq(&a, &b)); // exposure changed

        let c = CameraConfig {
            framerate: 60.0,
            ..a.clone()
        };
        assert!(!camera_config_eq(&a, &c)); // framerate changed
    }
}
