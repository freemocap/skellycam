//! PyO3CameraGroupManager — Python-facing wrapper for the Rust camera group.
//! Handles PyDict → CameraGroupConfig conversion and provides frame polling
//! via `latest_frontend_payload()`.
//!
//! All lifecycle logic is delegated to `CameraGroup`. This module is a
//! thin adapter — Python type conversion only.

use std::sync::Mutex;
use std::collections::HashMap;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};

use crate::camera::{detect_cameras, CameraConfig, CameraIdentity};
use crate::camera_group::{CameraGroup, CameraGroupConfig, CameraStatus};

// ── PyO3 class ─────────────────────────────────────────────────────────────

#[pyclass(name = "CameraGroupManager")]
pub struct PyO3CameraGroupManager {
    groups: HashMap<String, Mutex<CameraGroup>>,
    camera_statuses: Vec<CameraStatus>,
}

#[pymethods]
impl PyO3CameraGroupManager {
    #[new]
    fn new() -> Self {
        Self {
            groups: HashMap::new(),
            camera_statuses: Vec::new(),
        }
    }

    /// Create a camera group from a Python dict mapping camera_id → config_dict.
    ///
    /// Detects all cameras, matches each config entry to a physical device by
    /// `camera_index`, and starts a new `CameraGroup`. The group runs until
    /// `close_all_groups()` is called or the manager is dropped.
    fn create_or_update_group(
        &mut self,
        configs: &Bound<'_, PyDict>,
    ) -> PyResult<String> {
        let all_cameras = detect_cameras()
            .map_err(|e| {
                PyRuntimeError::new_err(format!("Camera detection failed: {e}"))
            })?;

        if all_cameras.is_empty() {
            return Err(PyRuntimeError::new_err("No cameras detected"));
        }

        let mut rust_configs: HashMap<String, CameraGroupConfig> = HashMap::new();

        for (key, value) in configs.iter() {
            let python_camera_id: String = key.extract()?;
            let parsed = parse_config_entry(&value, &python_camera_id)?;

            let mut identity = all_cameras
                .iter()
                .find(|c| c.camera_index == parsed.camera_index as i32)
                .cloned()
                .ok_or_else(|| {
                    PyValueError::new_err(format!(
                        "Camera index {} not found (available: {})",
                        parsed.camera_index,
                        all_cameras
                            .iter()
                            .map(|c| c.camera_index.to_string())
                            .collect::<Vec<_>>()
                            .join(", ")
                    ))
                })?;

            identity.camera_id = python_camera_id;
            rust_configs.insert(parsed.camera_id.clone(), parsed.into_group_config(identity));
        }

        if rust_configs.is_empty() {
            return Err(PyValueError::new_err("No valid camera configs provided"));
        }

        let mut group = CameraGroup::new(rust_configs);
        group.start()
            .map_err(|e| {
                PyRuntimeError::new_err(format!("Failed to start camera group: {e}"))
            })?;

        self.camera_statuses = group.camera_statuses();

        let group_id = uuid::Uuid::new_v4()
            .as_simple()
            .to_string()[..6]
            .to_string();

        self.groups.insert(group_id.clone(), Mutex::new(group));
        Ok(group_id)
    }

    /// Poll for latest JPEG frame payloads across all groups.
    ///
    /// Returns a dict mapping group_id → (frame_number, timestamp_ns, jpeg_bytes).
    #[pyo3(signature = (if_newer_than = None))]
    fn get_latest_frame_payloads(
        &self,
        py: Python<'_>,
        if_newer_than: Option<i64>,
    ) -> Py<PyDict> {
        let threshold = if_newer_than.unwrap_or(-1);
        let result = PyDict::new(py);

        for (group_id, group_mutex) in &self.groups {
            let group = group_mutex.lock().unwrap();
            if let Some(payload) = group.latest_frontend_payload() {
                if payload.frame_number > threshold {
                    let py_bytes = PyBytes::new(py, &payload.jpeg_bytes);
                    let _ = result.set_item(
                        group_id.as_str(),
                        (payload.frame_number, payload.timestamp_ns, py_bytes),
                    );
                }
            }
        }

        result.into()
    }

    /// Poll for latest raw per-camera JPEG bytes across all groups.
    ///
    /// Returns a dict mapping group_id → dict of camera_id → frame metadata.
    /// Each camera dict contains: camera_index, width, height, jpeg_bytes.
    /// These are the raw MJPEG bytes from the camera, before any frontend
    /// encoding or wire-format packing — suitable for direct image validation.
    fn get_latest_raw_frames(
        &self,
        py: Python<'_>,
    ) -> Py<PyDict> {
        let result = PyDict::new(py);

        for (group_id, group_mutex) in &self.groups {
            let group = group_mutex.lock().unwrap();
            if let Some(raw_frames) = group.latest_raw_frames() {
                let group_dict = PyDict::new(py);
                for frame in &raw_frames {
                    let frame_dict = PyDict::new(py);
                    let _ = frame_dict.set_item("camera_index", frame.camera_index);
                    let _ = frame_dict.set_item("width", frame.width);
                    let _ = frame_dict.set_item("height", frame.height);
                    let _ = frame_dict.set_item("jpeg_bytes", PyBytes::new(py, &frame.jpeg_bytes));
                    let _ = group_dict.set_item(frame.camera_id.as_str(), frame_dict);
                }
                let _ = result.set_item(group_id.as_str(), group_dict);
            }
        }

        result.into()
    }

    /// Pause all camera groups (suppress downstream frame sends).
    fn pause(&self) {
        for group_mutex in self.groups.values() {
            if let Ok(mut group) = group_mutex.lock() {
                group.pause();
            }
        }
    }

    /// Unpause all camera groups (resume downstream frame sends).
    fn unpause(&self) {
        for group_mutex in self.groups.values() {
            if let Ok(mut group) = group_mutex.lock() {
                group.unpause();
            }
        }
    }

    /// Apply updated camera configs to an existing group.
    ///
    /// Takes a Python dict mapping camera_id → config_dict (same format as
    /// `create_or_update_group`). Calls `CameraGroup::apply()` which diffs
    /// the configs and applies changes (reconfigure, add, or remove cameras).
    fn apply_configs(
        &mut self,
        _py: Python<'_>,
        group_id: &str,
        configs: &Bound<'_, PyDict>,
    ) -> PyResult<()> {
        let group_mutex = self.groups.get(group_id)
            .ok_or_else(|| PyValueError::new_err(format!("Group '{group_id}' not found")))?;
        let mut group = group_mutex.lock().unwrap();

        let all_cameras = detect_cameras()
            .map_err(|e| PyRuntimeError::new_err(format!("Camera detection failed: {e}")))?;

        let mut rust_configs: HashMap<String, CameraGroupConfig> = HashMap::new();

        for (key, value) in configs.iter() {
            let python_camera_id: String = key.extract()?;
            let parsed = parse_config_entry(&value, &python_camera_id)?;

            let identity = all_cameras
                .iter()
                .find(|c| c.camera_index == parsed.camera_index as i32)
                .cloned()
                .unwrap_or_else(|| {
                    CameraIdentity {
                        camera_name: format!("Camera {}", parsed.camera_index),
                        camera_index: parsed.camera_index as i32,
                        camera_id: parsed.camera_id.clone(),
                        device_path: String::new(),
                        formats: vec![],
                    }
                });

            rust_configs.insert(parsed.camera_id.clone(), parsed.into_group_config(identity));
        }

        group.apply(rust_configs)
            .map_err(|e| PyRuntimeError::new_err(format!("Config apply failed: {e}")))?;

        self.camera_statuses = group.camera_statuses();
        Ok(())
    }

    /// Return a JSON string of the latest performance snapshot from the gatherer.
    fn get_performance_snapshot(&self) -> Option<String> {
        for group_mutex in self.groups.values() {
            if let Ok(group) = group_mutex.lock() {
                if let Some(snapshot) = group.latest_performance_snapshot() {
                    return Some(snapshot);
                }
            }
        }
        None
    }

    /// Start recording across all camera groups.
    #[pyo3(signature = (output_dir, label = None))]
    fn start_recording(&self, output_dir: &str, label: Option<&str>) -> PyResult<()> {
        use crate::camera_group::RecordingParams;
        let params = RecordingParams {
            output_dir: output_dir.to_string(),
            label: label.map(|s| s.to_string()),
        };
        for group_mutex in self.groups.values() {
            let mut group = group_mutex.lock().unwrap();
            group.start_recording(params.clone())
                .map_err(|e| {
                    PyRuntimeError::new_err(format!("Failed to start recording: {e}"))
                })?;
        }
        Ok(())
    }

    /// Stop recording across all camera groups and return summaries.
    fn stop_recording(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let result = PyDict::new(py);
        for (group_id, group_mutex) in &self.groups {
            let mut group = group_mutex.lock().unwrap();
            match group.stop_recording() {
                Ok(summary) => {
                    let summary_dict = recording_summary_to_pydict(py, &summary)?;
                    result.set_item(group_id.as_str(), summary_dict)?;
                }
                Err(e) => {
                    return Err(PyRuntimeError::new_err(format!(
                        "Failed to stop recording for group {group_id}: {e}"
                    )));
                }
            }
        }
        Ok(result.into())
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

        for (group_id, group_mutex) in &self.groups {
            let group = group_mutex.lock().unwrap();
            let group_state = PyDict::new(py);
            group_state.set_item("group_id", group.group_id())?;
            let statuses = group.camera_statuses();
            group_state.set_item("camera_count", statuses.len())?;

            let cameras_list: Vec<Py<PyDict>> = statuses
                .iter()
                .map(|cam| {
                    let d = PyDict::new(py);
                    d.set_item("camera_index", cam.camera_index)?;
                    d.set_item("display_name", &cam.camera_name)?;
                    d.set_item("unique_identifier", &cam.config.camera_id)?;
                    d.set_item("width", cam.config.width as i32)?;
                    d.set_item("height", cam.config.height as i32)?;
                    d.set_item("is_paused", group.is_paused())?;
                    d.set_item("is_recording", group.is_recording())?;
                    Ok(d.into())
                })
                .collect::<PyResult<Vec<_>>>()?;

            group_state.set_item("cameras", cameras_list)?;
            drop(group);
            groups_dict.set_item(group_id.as_str(), group_state)?;
        }

        result.set_item("camera_groups", groups_dict)?;
        Ok(result.into())
    }

    fn __repr__(&self) -> String {
        format!(
            "CameraGroupManager(groups={})",
            self.groups.len()
        )
    }
}

impl PyO3CameraGroupManager {
    fn close_all_groups_inner(&mut self) {
        for (id, mutex) in self.groups.drain() {
            let mut group = mutex.into_inner().unwrap();
            let _ = group.shutdown();
            tracing::info!("Closed camera group {id}");
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

/// Parsed fields from one Python config dict entry (before identity resolution).
struct ParsedConfigEntry {
    camera_id: String,
    camera_index: u32,
    width: u32,
    height: u32,
    exposure: i32,
    exposure_mode: String,
    framerate: f64,
    rotation: i32,
}

/// Extract config fields from a single Python dict value.
///
/// Handles both object-attribute access (`obj.camera_index`) and dict-key
/// access (`obj["camera_index"]`), matching the dual getattr/get_item pattern
/// Python developers expect from a Rust-backed API.
fn parse_config_entry(
    value: &Bound<'_, PyAny>,
    python_camera_id: &str,
) -> PyResult<ParsedConfigEntry> {
    let camera_index: i32 = value
        .getattr("get")
        .and_then(|get| get.call1(("camera_index",)))
        .or_else(|_| value.getattr("camera_index"))
        .and_then(|v| v.extract())
        .or_else(|_| value.get_item("camera_index")?.extract())?;

    let camera_id = get_field_string(value, "camera_id", python_camera_id);
    let width = get_field_i32(value, "width", 1280) as u32;
    let height = get_field_i32(value, "height", 720) as u32;
    let exposure = get_field_i32(value, "exposure", -7);
    let exposure_mode = get_field_string(value, "exposure_mode", "MANUAL");
    let framerate = get_field_f64(value, "framerate", -1.0);
    let rotation = get_field_i32(value, "rotation", -1);

    Ok(ParsedConfigEntry {
        camera_id,
        camera_index: camera_index as u32,
        width,
        height,
        exposure,
        exposure_mode,
        framerate,
        rotation,
    })
}

impl ParsedConfigEntry {
    fn into_group_config(self, identity: CameraIdentity) -> CameraGroupConfig {
        CameraGroupConfig {
            capture_config: CameraConfig {
                camera_id: self.camera_id.clone(),
                camera_index: self.camera_index,
                width: self.width,
                height: self.height,
                exposure: self.exposure,
                exposure_mode: self.exposure_mode,
                framerate: self.framerate,
                rotation: self.rotation,
            },
            identity,
        }
    }
}

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

fn recording_summary_to_pydict(
    py: Python<'_>,
    summary: &crate::recording::finalizer::RecordingSummary,
) -> PyResult<Py<PyDict>> {
    let d = PyDict::new(py);
    d.set_item("total_frames_per_camera", summary.total_frames_per_camera)?;
    d.set_item(
        "video_paths",
        summary
            .video_paths
            .iter()
            .map(|p| p.to_string_lossy().to_string())
            .collect::<Vec<_>>(),
    )?;
    d.set_item(
        "csv_paths",
        summary
            .csv_paths
            .iter()
            .map(|p| p.to_string_lossy().to_string())
            .collect::<Vec<_>>(),
    )?;
    d.set_item(
        "info_json_path",
        summary.info_json_path.to_string_lossy().to_string(),
    )?;
    if let Some(ref stats) = summary.stats {
        let stats_json = serde_json::to_string(stats)
            .map_err(|e| PyRuntimeError::new_err(format!("stats serialization: {e}")))?;
        d.set_item("stats_json", stats_json)?;
    }
    Ok(d.into())
}

use pyo3::exceptions::{PyRuntimeError, PyValueError};

// ── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Verify that `parse_config_entry` correctly extracts all fields from a
    /// Python dict using the dual getattr/get_item access pattern.
    #[test]
    fn parse_config_entry_extracts_all_fields() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let dict = PyDict::new(py);
            dict.set_item("camera_index", 2_i32).unwrap();
            dict.set_item("camera_id", "test_cam_01").unwrap();
            dict.set_item("width", 640_i32).unwrap();
            dict.set_item("height", 480_i32).unwrap();
            dict.set_item("exposure", -5_i32).unwrap();
            dict.set_item("exposure_mode", "AUTO").unwrap();
            dict.set_item("framerate", 60.0_f64).unwrap();
            dict.set_item("rotation", 1_i32).unwrap();

            let parsed = parse_config_entry(&dict.as_borrowed(), "fallback_id")
                .expect("parse_config_entry should succeed");

            assert_eq!(parsed.camera_id, "test_cam_01");
            assert_eq!(parsed.camera_index, 2);
            assert_eq!(parsed.width, 640);
            assert_eq!(parsed.height, 480);
            assert_eq!(parsed.exposure, -5);
            assert_eq!(parsed.exposure_mode, "AUTO");
            assert_eq!(parsed.framerate, 60.0);
            assert_eq!(parsed.rotation, 1);
        });
    }

    /// Fields not present in the dict should get sensible defaults.
    #[test]
    fn parse_config_entry_missing_fields_use_defaults() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let dict = PyDict::new(py);
            dict.set_item("camera_index", 0_i32).unwrap();

            let parsed = parse_config_entry(&dict.as_borrowed(), "fallback")
                .expect("parse_config_entry should succeed");

            assert_eq!(parsed.width, 1280);
            assert_eq!(parsed.height, 720);
            assert_eq!(parsed.exposure, -7);
            assert_eq!(parsed.exposure_mode, "MANUAL");
            assert_eq!(parsed.framerate, -1.0);
            assert_eq!(parsed.rotation, -1);
        });
    }

    /// When `camera_id` is absent, fall back to the Python dict key.
    #[test]
    fn parse_config_entry_falls_back_camera_id() {
        pyo3::Python::initialize();
        Python::attach(|py| {
            let dict = PyDict::new(py);
            dict.set_item("camera_index", 0_i32).unwrap();
            // camera_id absent — should use the fallback

            let parsed = parse_config_entry(&dict.as_borrowed(), "fallback_key")
                .expect("parse_config_entry should succeed");

            assert_eq!(parsed.camera_id, "fallback_key");
        });
    }

    /// `ParsedConfigEntry::into_group_config` produces a valid CameraGroupConfig.
    #[test]
    fn into_group_config_builds_valid_config() {
        let entry = ParsedConfigEntry {
            camera_id: "cam_1".into(),
            camera_index: 0,
            width: 640,
            height: 480,
            exposure: -7,
            exposure_mode: "MANUAL".into(),
            framerate: 30.0,
            rotation: -1,
        };

        let identity = CameraIdentity {
            camera_name: "Test Cam".into(),
            camera_index: 0,
            camera_id: "cam_1".into(),
            device_path: String::new(),
            formats: vec![],
        };

        let cfg = entry.into_group_config(identity);
        assert_eq!(cfg.capture_config.camera_id, "cam_1");
        assert_eq!(cfg.capture_config.width, 640);
        assert_eq!(cfg.capture_config.height, 480);
        assert_eq!(cfg.capture_config.exposure, -7);
    }
}
