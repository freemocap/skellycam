//! PyO3CameraGroupManager — Python-facing wrapper for the Rust camera group.
//! Handles PyDict → CameraGroupConfig conversion and provides frame polling
//! via `latest_frontend_payload()`.
//!
//! All lifecycle logic is delegated to `CameraGroup`. This module is a
//! thin adapter — Python type conversion only.

use std::sync::Mutex;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};

use crate::camera::{detect_cameras, CameraConfig};
use crate::camera_group::{CameraGroup, CameraGroupConfig, CameraStatus};

// ── PyO3 class ─────────────────────────────────────────────────────────────

#[pyclass]
pub struct PyO3CameraGroupManager {
    group: Option<Mutex<CameraGroup>>,
    camera_statuses: Vec<CameraStatus>,
}

#[pymethods]
impl PyO3CameraGroupManager {
    #[new]
    fn new() -> Self {
        Self {
            group: None,
            camera_statuses: Vec::new(),
        }
    }

    /// Create a camera group from a Python dict mapping camera_id → config_dict.
    fn create_or_update_group(
        &mut self,
        configs: &Bound<'_, PyDict>,
    ) -> PyResult<String> {
        // Close existing group first
        self.close_all_groups_inner();

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
                .or_else(|_| value.get_item("camera_index")?.extract())?;

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
            return Err(PyValueError::new_err("No valid camera configs provided"));
        }

        let mut group = CameraGroup::new(rust_configs);
        group.start()
            .map_err(|e| {
                PyRuntimeError::new_err(format!("Failed to start camera group: {e}"))
            })?;

        let camera_statuses = group.camera_statuses();
        self.camera_statuses = camera_statuses;

        let group_id = uuid::Uuid::new_v4()
            .as_simple()
            .to_string()[..6]
            .to_string();

        self.group = Some(Mutex::new(group));

        Ok(group_id)
    }

    /// Poll for latest JPEG frame payloads.
    ///
    /// Returns a dict mapping group_id → (frame_number, timestamp_ns, jpeg_bytes).
    /// `if_newer_than` filters to frames with frame_number > threshold.
    #[pyo3(signature = (if_newer_than = None))]
    fn get_latest_frame_payloads(
        &self,
        py: Python<'_>,
        if_newer_than: Option<i64>,
    ) -> Py<PyDict> {
        let threshold = if_newer_than.unwrap_or(-1);
        let result = PyDict::new(py);

        if let Some(ref group_mutex) = self.group {
            let group = group_mutex.lock().unwrap();
            if let Some(payload) = group.latest_frontend_payload() {
                if payload.frame_number > threshold {
                    let py_bytes = PyBytes::new(py, &payload.jpeg_bytes);
                    let _ = result.set_item(
                        group.group_id(),
                        (payload.frame_number, payload.timestamp_ns, py_bytes),
                    );
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
        self.group.as_ref()
            .map(|g| vec![g.lock().unwrap().group_id().to_string()])
            .unwrap_or_default()
    }

    /// Return the number of active groups.
    fn group_count(&self) -> usize {
        if self.group.is_some() { 1 } else { 0 }
    }

    /// Serialize the manager's state to a Python dict.
    fn to_state_dict(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let result = PyDict::new(py);
        let groups_dict = PyDict::new(py);

        if let Some(ref group_mutex) = self.group {
            let group = group_mutex.lock().unwrap();
            let group_state = PyDict::new(py);
            group_state.set_item("group_id", group.group_id())?;
            group_state.set_item("camera_count", self.camera_statuses.len())?;

            let cameras_list: Vec<Py<PyDict>> = self
                .camera_statuses
                .iter()
                .map(|cam| {
                    let d = PyDict::new(py);
                    d.set_item("camera_index", cam.camera_index)?;
                    d.set_item("display_name", &cam.camera_name)?;
                    d.set_item("unique_identifier", &cam.config.camera_id)?;
                    d.set_item("width", cam.config.width as i32)?;
                    d.set_item("height", cam.config.height as i32)?;
                    Ok(d.into())
                })
                .collect::<PyResult<Vec<_>>>()?;

            group_state.set_item("cameras", cameras_list)?;
            let gid = group.group_id().to_string();
            drop(group);
            groups_dict.set_item(&gid, group_state)?;
        }

        result.set_item("camera_groups", groups_dict)?;
        Ok(result.into())
    }

    fn __repr__(&self) -> String {
        format!(
            "PyO3CameraGroupManager(groups={})",
            if self.group.is_some() { 1 } else { 0 }
        )
    }
}

impl PyO3CameraGroupManager {
    fn close_all_groups_inner(&mut self) {
        if let Some(mutex) = self.group.take() {
            let mut group = mutex.into_inner().unwrap();
            let _ = group.shutdown();
        }
        self.camera_statuses.clear();
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
