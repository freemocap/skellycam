//! PyO3CameraGroupManager — Python-facing wrapper for the Rust camera group
//! manager. Handles PyDict → CameraGroupConfig conversion and runs a JPEG
//! pipeline thread for Python frame polling.
//!
//! Delegates all lifecycle logic to the pure Rust `CameraGroupManager`.
//!
//! Thread model:
//!   Camera threads (N) — openpnp-capture, blocked at barrier each cycle
//!   Gatherer thread (1) — releases barrier, collects frames → sync_channel
//!   Pipeline thread (1) — reads sync_channel, JPEG encodes, stores result
//!   Python asyncio — polls get_latest_frame_payloads() every ~10ms

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};

use crate::camera::{detect_cameras, CameraConfig};
use crate::camera_group::{consume_multiframe_loop, CameraGroup, CameraGroupConfig, CameraStatus};

// ── Internal state per camera group ────────────────────────────────────────

struct GroupState {
    camera_statuses: Vec<CameraStatus>,
    pipeline_handle: Option<JoinHandle<()>>,
    latest_payload: Arc<Mutex<Option<(i64, f64, Vec<u8>)>>>,
    running: Arc<AtomicBool>,
}

// ── PyO3 class ─────────────────────────────────────────────────────────────

#[pyclass]
pub struct PyO3CameraGroupManager {
    groups: std::collections::HashMap<String, GroupState>,
}

#[pymethods]
impl PyO3CameraGroupManager {
    #[new]
    fn new() -> Self {
        Self {
            groups: std::collections::HashMap::new(),
        }
    }

    /// Create a camera group from a Python dict mapping camera_id → config_dict.
    ///
    /// Each config dict must have `camera_index` (int).
    /// Optional: `width` (int, default 1280), `height` (int, default 720).
    ///
    /// Returns the group_id string (6 hex chars).
    fn create_or_update_group(
        &mut self,
        configs: &Bound<'_, PyDict>,
    ) -> PyResult<String> {
        // Close any existing groups first
        self.close_all_groups_inner();

        // Enumerate cameras once
        let all_cameras = detect_cameras()
            .map_err(|e| {
                PyRuntimeError::new_err(format!("Camera detection failed: {e}"))
            })?;

        if all_cameras.is_empty() {
            return Err(PyRuntimeError::new_err("No cameras detected"));
        }

        let mut rust_configs: std::collections::HashMap<String, CameraGroupConfig> =
            std::collections::HashMap::new();

        for (key, value) in configs.iter() {
            let python_camera_id: String = key.extract()?;

            let camera_index: i32 = value
                .getattr("get")
                .and_then(|get| get.call1(("camera_index",)))
                .or_else(|_| value.getattr("camera_index"))
                .and_then(|v| v.extract())
                .or_else(|_| {
                    value.get_item("camera_index")?.extract()
                })?;

            let camera_id: String =
                get_field_string(&value, "camera_id", &python_camera_id);
            let width: u32 = get_field_i32(&value, "width", 1280) as u32;
            let height: u32 = get_field_i32(&value, "height", 720) as u32;
            let exposure: i32 = get_field_i32(&value, "exposure", -7);
            let exposure_mode: String =
                get_field_string(&value, "exposure_mode", "MANUAL");
            let framerate: f64 = get_field_f64(&value, "framerate", -1.0);
            let rotation: i32 = get_field_i32(&value, "rotation", -1);

            let mut identity = all_cameras
                .iter()
                .find(|c| c.camera_index == camera_index)
                .cloned()
                .ok_or_else(|| {
                    PyValueError::new_err(format!(
                        "Camera index {camera_index} not found (available: {})",
                        all_cameras
                            .iter()
                            .map(|c| c.camera_index.to_string())
                            .collect::<Vec<_>>()
                            .join(", ")
                    ))
                })?;

            // Override the openpnp-generated unique_identifier with the
            // Python-provided camera_id.
            identity.camera_id = python_camera_id;

            rust_configs.insert(
                camera_id.clone(),
                CameraGroupConfig {
                    capture_config: CameraConfig {
                        camera_id,
                        camera_index: camera_index as u32,
                        width,
                        height,
                        exposure,
                        exposure_mode,
                        framerate,
                        rotation,
                    },
                    identity,
                },
            );
        }

        if rust_configs.is_empty() {
            return Err(PyValueError::new_err(
                "No valid camera configs provided",
            ));
        }

        // Create and start the CameraGroup
        let mut group = CameraGroup::new(rust_configs);
        group
            .start()
            .map_err(|e| {
                PyRuntimeError::new_err(format!(
                    "Failed to start camera group: {e}"
                ))
            })?;

        let camera_statuses = group.camera_statuses();

        let latest_payload =
            Arc::new(Mutex::new(None::<(i64, f64, Vec<u8>)>));
        let running = Arc::new(AtomicBool::new(true));

        let latest_payload_clone = latest_payload.clone();
        let running_clone = running.clone();

        let group_id = uuid::Uuid::new_v4()
            .as_simple()
            .to_string()[..6]
            .to_string();

        let thread_name = format!("pipeline-{group_id}");

        let pipeline_handle = thread::Builder::new()
            .name(thread_name)
            .spawn(move || {
                pipeline_loop(
                    group,
                    latest_payload_clone,
                    running_clone,
                );
            })
            .map_err(|e| {
                PyRuntimeError::new_err(format!(
                    "Failed to spawn pipeline thread: {e}"
                ))
            })?;

        self.groups.insert(
            group_id.clone(),
            GroupState {
                camera_statuses,
                pipeline_handle: Some(pipeline_handle),
                latest_payload,
                running,
            },
        );

        Ok(group_id)
    }

    /// Poll for latest JPEG frame payloads.
    ///
    /// Returns a dict mapping group_id → (frame_number, timestamp_ns, jpeg_bytes).
    /// `if_newer_than` filters to frames with frame_number > threshold.
    /// Returns an empty dict if no new frames are available.
    #[pyo3(signature = (if_newer_than = None))]
    fn get_latest_frame_payloads(
        &self,
        py: Python<'_>,
        if_newer_than: Option<i64>,
    ) -> Py<PyDict> {
        let threshold = if_newer_than.unwrap_or(-1);
        let result = PyDict::new(py);

        for (_group_id, state) in &self.groups {
            if let Ok(guard) = state.latest_payload.lock() {
                if let Some((frame_number, timestamp, bytes)) =
                    guard.as_ref()
                {
                    if *frame_number > threshold {
                        let py_bytes = PyBytes::new(py, bytes);
                        let _ = result.set_item(
                            _group_id,
                            (*frame_number, *timestamp, py_bytes),
                        );
                    }
                }
            }
        }

        result.into()
    }

    /// Shut down and remove all camera groups.
    fn close_all_groups(&mut self) {
        self.close_all_groups_inner();
    }

    /// Return the group IDs of all active groups.
    fn list_groups(&self) -> Vec<String> {
        self.groups.keys().cloned().collect()
    }

    /// Return the number of active groups.
    fn group_count(&self) -> usize {
        self.groups.len()
    }

    /// Serialize the manager's state to a Python dict.
    fn to_state_dict(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let result = PyDict::new(py);
        let groups_dict = PyDict::new(py);

        for (group_id, state) in &self.groups {
            let group_state = PyDict::new(py);
            group_state.set_item("group_id", group_id)?;
            group_state.set_item(
                "camera_count",
                state.camera_statuses.len(),
            )?;

            let cameras_list: Vec<Py<PyDict>> = state
                .camera_statuses
                .iter()
                .map(|cam| {
                    let d = PyDict::new(py);
                    d.set_item("camera_index", cam.camera_index)?;
                    d.set_item("display_name", &cam.camera_name)?;
                    d.set_item(
                        "unique_identifier",
                        &cam.camera_id,
                    )?;
                    d.set_item("width", cam.width as i32)?;
                    d.set_item("height", cam.height as i32)?;
                    Ok(d.into())
                })
                .collect::<PyResult<Vec<_>>>()?;

            group_state.set_item("cameras", cameras_list)?;
            groups_dict.set_item(group_id, group_state)?;
        }

        result.set_item("camera_groups", groups_dict)?;
        Ok(result.into())
    }

    fn __repr__(&self) -> String {
        format!(
            "PyO3CameraGroupManager(groups={})",
            self.groups.len()
        )
    }
}

impl PyO3CameraGroupManager {
    fn close_all_groups_inner(&mut self) {
        for (group_id, mut state) in self.groups.drain() {
            state.running.store(false, Ordering::SeqCst);
            if let Some(handle) = state.pipeline_handle.take() {
                let _ = handle.join();
            }
            tracing::info!(
                "PyO3CameraGroupManager: closed group {group_id}"
            );
        }
    }
}

impl Default for PyO3CameraGroupManager {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for PyO3CameraGroupManager {
    fn drop(&mut self) {
        self.close_all_groups_inner();
    }
}

// ── Pipeline thread ────────────────────────────────────────────────────────

fn pipeline_loop(
    mut group: CameraGroup,
    latest_payload: Arc<Mutex<Option<(i64, f64, Vec<u8>)>>>,
    running: Arc<AtomicBool>,
) {
    let receiver = group.take_multiframe_receiver();

    consume_multiframe_loop(&receiver, &running, 100, |payload| {
        match crate::frontend_payload::encode_multiframe(&payload) {
            Ok(binary) => {
                let timestamp_ns = if payload.frames.is_empty() {
                    0.0
                } else {
                    let sum: i64 = payload
                        .frames
                        .iter()
                        .map(|f| f.timestamps.frame_available_ns)
                        .sum();
                    (sum as f64) / (payload.frames.len() as f64)
                };
                let frame_number = payload
                    .frames
                    .first()
                    .map(|f| f.frame_number)
                    .unwrap_or(0);

                if let Ok(mut guard) = latest_payload.lock() {
                    *guard = Some((frame_number, timestamp_ns, binary));
                }
            }
            Err(e) => {
                tracing::error!("Pipeline encode error: {e}");
            }
        }
        true
    });

    let _ = group.shutdown();
    tracing::info!("Pipeline thread exited");
}

// ── Helpers ─────────────────────────────────────────────────────────────────

fn get_field_i32(value: &Bound<'_, PyAny>, name: &str, default: i32) -> i32 {
    value
        .getattr(name)
        .and_then(|v| v.extract())
        .or_else(|_| value.get_item(name)?.extract())
        .unwrap_or(default)
}

fn get_field_f64(value: &Bound<'_, PyAny>, name: &str, default: f64) -> f64 {
    value
        .getattr(name)
        .and_then(|v| v.extract())
        .or_else(|_| value.get_item(name)?.extract())
        .unwrap_or(default)
}

fn get_field_string(
    value: &Bound<'_, PyAny>,
    name: &str,
    default: &str,
) -> String {
    value
        .getattr(name)
        .and_then(|v| v.extract::<String>())
        .or_else(|_| value.get_item(name)?.extract::<String>())
        .unwrap_or_else(|_| default.to_string())
}

use pyo3::exceptions::{PyRuntimeError, PyValueError};
