//! PyO3 bridge module — exposes the Rust camera engine to Python.
//!
//! This module wraps the Rust `CameraGroupManager`, `CameraGroup`, and related
//! types as `#[pyclass]` objects with Python-native method signatures.
//! The Python module name is `_skellycam_rust` (underscore prefix = private
//! implementation detail consumed by `skellycam.core.camera_group.camera_group_manager`).

mod camera_group_manager;
mod types;

use pyo3::prelude::*;
use pyo3::Py;
use pyo3::types::{PyDict, PyList};

use types::{
    CameraConfig, CameraStatusDict, FramerateData, ImageResolution, RecordingInfo,
    StatsSummary, StopRecordingResponse,
};

/// The Python module initialization function.
///
/// Called when Python executes `import _skellycam_rust`.
/// Registers all PyO3 classes so they are available as
/// `_skellycam_rust.CameraGroupManager`, etc.
#[pymodule]
fn _skellycam_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Initialize tracing subscriber for Rust log output.
    // try_init() is a no-op if a subscriber already exists (e.g. in tests).
    // We use the fmt subscriber (stderr) instead of pyo3_log because
    // pyo3_log requires the Python interpreter in every thread that logs,
    // and our camera/pipeline threads are pure OS threads without the GIL.
    let _ = tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("skellycam=info")),
        )
        .try_init();

    // ── Data types ──
    m.add_class::<ImageResolution>()?;
    m.add_class::<CameraConfig>()?;
    m.add_class::<RecordingInfo>()?;
    m.add_class::<StatsSummary>()?;
    m.add_class::<StopRecordingResponse>()?;
    m.add_class::<CameraStatusDict>()?;
    m.add_class::<FramerateData>()?;

    // ── Engine ──
    m.add_class::<camera_group_manager::CameraGroupManager>()?;

    // ── Functions ──
    m.add_function(wrap_pyfunction!(detect_cameras, m)?)?;

    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("__doc__", "SkellyCam Rust camera engine (Rust + openpnp-capture)")?;

    Ok(())
}

/// Detect all available cameras and return a list of dicts with
/// `camera_index`, `display_name`, `unique_identifier`, and `device_path`.
#[pyfunction]
fn detect_cameras(py: Python<'_>) -> pyo3::PyResult<Vec<Py<PyDict>>> {
    let cameras = crate::camera::enumerate_directshow_cameras()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("Camera detection failed: {e}")))?;

    let mut result = Vec::with_capacity(cameras.len());
    for cam in cameras {
        let d = PyDict::new(py);

        let format_dicts: Vec<Py<PyDict>> = cam.formats.iter().map(|f| {
            let fd = PyDict::new(py);
            fd.set_item("width", f.width).unwrap();
            fd.set_item("height", f.height).unwrap();
            fd.set_item("fps", f.fps).unwrap();
            fd.set_item("fourcc", f.fourcc).unwrap();
            fd.set_item("fourcc_str", &f.fourcc_str).unwrap();
            fd.into()
        }).collect();
        let formats_list = PyList::new(py, format_dicts)?;

        d.set_item("camera_index", cam.camera_index)?;
        d.set_item("display_name", cam.display_name)?;
        d.set_item("unique_identifier", cam.unique_identifier)?;
        d.set_item("device_path", cam.device_path)?;
        d.set_item("formats", formats_list)?;
        result.push(d.into());
    }

    Ok(result)
}
