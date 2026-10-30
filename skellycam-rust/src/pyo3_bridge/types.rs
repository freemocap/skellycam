//! PyO3 type definitions matching the Python Pydantic models exactly.
//!
//! Every `#[pyclass]` here mirrors a Python class in:
//!   - `skellycam.core.camera.config.camera_config.CameraConfig`
//!   - `skellycam.core.recorders.videos.recording_info.RecordingInfo`
//!   - `skellycam.api.http.cameras.camera_router.StopRecordingResponse`

use std::collections::HashMap;

use pyo3::prelude::*;
use pyo3::types::PyDict;

// ── ImageResolution ────────────────────────────────────────────────────────

#[pyclass(skip_from_py_object)]
#[derive(Clone, Debug)]
pub struct ImageResolution {
    #[pyo3(get, set)]
    pub height: i32,
    #[pyo3(get, set)]
    pub width: i32,
}

#[pymethods]
impl ImageResolution {
    #[new]
    #[pyo3(signature = (height=720, width=1280))]
    fn new(height: i32, width: i32) -> Self {
        Self { height, width }
    }

    #[getter]
    fn aspect_ratio(&self) -> f64 {
        self.width as f64 / self.height as f64
    }

    fn as_tuple(&self) -> (i32, i32) {
        (self.width, self.height)
    }

    fn __repr__(&self) -> String {
        format!("ImageResolution(height={}, width={})", self.height, self.width)
    }

    fn __str__(&self) -> String {
        format!("({}x{})", self.height, self.width)
    }

    fn model_dump(&self) -> HashMap<String, i32> {
        let mut m = HashMap::new();
        m.insert("height".into(), self.height);
        m.insert("width".into(), self.width);
        m
    }
}

// ── Rotation Types ─────────────────────────────────────────────────────────

/// Python `RotationTypes` enum values.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RotationType {
    NoRotation = -1,
    Clockwise90 = 0,
    Rotate180 = 1,
    CounterClockwise90 = 2,
}

impl RotationType {
    pub fn from_i32(value: i32) -> Self {
        match value {
            -1 => Self::NoRotation,
            0 => Self::Clockwise90,
            1 => Self::Rotate180,
            2 => Self::CounterClockwise90,
            _ => Self::NoRotation,
        }
    }
}

// ── CameraConfig ───────────────────────────────────────────────────────────

#[pyclass(skip_from_py_object)]
#[derive(Debug)]
pub struct CameraConfig {
    #[pyo3(get, set)]
    pub camera_id: String,
    #[pyo3(get, set)]
    pub camera_index: i32,
    #[pyo3(get, set)]
    pub camera_name: String,
    #[pyo3(get, set)]
    pub use_this_camera: bool,
    #[pyo3(get, set)]
    pub resolution: Py<ImageResolution>,
    #[pyo3(get, set)]
    pub color_channels: i32,
    #[pyo3(get, set)]
    pub pixel_format: String,
    #[pyo3(get, set)]
    pub exposure_mode: String,
    #[pyo3(get, set)]
    pub exposure: i32,
    #[pyo3(get, set)]
    pub framerate: f64,
    #[pyo3(get, set)]
    pub rotation: i32,
    #[pyo3(get, set)]
    pub capture_fourcc: String,
    #[pyo3(get, set)]
    pub writer_fourcc: String,
}

// Manual Clone: Py<T> does not impl Clone in pyo3 0.28
impl Clone for CameraConfig {
    fn clone(&self) -> Self {
        Python::try_attach(|py| {
            Self {
                camera_id: self.camera_id.clone(),
                camera_index: self.camera_index,
                camera_name: self.camera_name.clone(),
                use_this_camera: self.use_this_camera,
                resolution: self.resolution.clone_ref(py),
                color_channels: self.color_channels,
                pixel_format: self.pixel_format.clone(),
                exposure_mode: self.exposure_mode.clone(),
                exposure: self.exposure,
                framerate: self.framerate,
                rotation: self.rotation,
                capture_fourcc: self.capture_fourcc.clone(),
                writer_fourcc: self.writer_fourcc.clone(),
            }
        }).expect("GIL must be held for CameraConfig::clone")
    }
}

#[pymethods]
impl CameraConfig {
    #[new]
    #[pyo3(signature = (
        camera_id = "000",
        camera_index = 0,
        camera_name = "Default Camera",
        use_this_camera = true,
        height = 720,
        width = 1280,
        color_channels = 3,
        pixel_format = "RGB",
        exposure_mode = "MANUAL",
        exposure = -7,
        framerate = -1.0,
        rotation = -1,
        capture_fourcc = "MJPG",
        writer_fourcc = "X264",
    ))]
    fn new(
        py: Python<'_>,
        camera_id: &str,
        camera_index: i32,
        camera_name: &str,
        use_this_camera: bool,
        height: i32,
        width: i32,
        color_channels: i32,
        pixel_format: &str,
        exposure_mode: &str,
        exposure: i32,
        framerate: f64,
        rotation: i32,
        capture_fourcc: &str,
        writer_fourcc: &str,
    ) -> PyResult<Self> {
        let resolution = Py::new(py, ImageResolution { height, width })?;
        Ok(Self {
            camera_id: camera_id.into(),
            camera_index,
            camera_name: camera_name.into(),
            use_this_camera,
            resolution,
            color_channels,
            pixel_format: pixel_format.into(),
            exposure_mode: exposure_mode.into(),
            exposure,
            framerate,
            rotation,
            capture_fourcc: capture_fourcc.into(),
            writer_fourcc: writer_fourcc.into(),
        })
    }

    /// Construct from a Python dict (the existing `CameraGroupCreateRequest` body).
    #[staticmethod]
    fn from_dict(py: Python<'_>, data: &Bound<'_, PyDict>) -> PyResult<Self> {
        let camera_id: String = get_dict_str_or(data, "camera_id", "000");
        let camera_index: i32 = get_dict_i32_or(data, "camera_index", 0);
        let camera_name: String = get_dict_str_or(data, "camera_name", "Default Camera");
        let use_this_camera: bool = get_dict_bool_or(data, "use_this_camera", true);

        let (height, width) = if let Ok(Some(res)) = data.get_item("resolution") {
            if let Ok(res_dict) = res.cast::<PyDict>() {
                let h = get_dict_i32_or(&res_dict, "height", 720);
                let w = get_dict_i32_or(&res_dict, "width", 1280);
                (h, w)
            } else {
                (720, 1280)
            }
        } else {
            (720, 1280)
        };

        let color_channels: i32 = get_dict_i32_or(data, "color_channels", 3);
        let pixel_format: String = get_dict_str_or(data, "pixel_format", "RGB");
        let exposure_mode: String = get_dict_str_or(data, "exposure_mode", "MANUAL");
        let exposure: i32 = get_dict_i32_or(data, "exposure", -7);
        let framerate: f64 = get_dict_f64_or(data, "framerate", -1.0);
        let rotation: i32 = get_dict_i32_or(data, "rotation", -1);
        let capture_fourcc: String = get_dict_str_or(data, "capture_fourcc", "MJPG");
        let writer_fourcc: String = get_dict_str_or(data, "writer_fourcc", "X264");

        let resolution = Py::new(py, ImageResolution { height, width })?;
        Ok(Self {
            camera_id, camera_index, camera_name, use_this_camera, resolution,
            color_channels, pixel_format, exposure_mode, exposure, framerate,
            rotation, capture_fourcc, writer_fourcc,
        })
    }

    // ── Computed properties (matching Python) ──────────────────────────────

    #[getter]
    fn orientation(&self, py: Python<'_>) -> String {
        let res: ImageResolution = self.resolution.borrow(py).clone();
        if res.width == res.height {
            return "SQUARE".into();
        }
        let rot = RotationType::from_i32(self.rotation);
        match rot {
            RotationType::NoRotation | RotationType::Rotate180 => "LANDSCAPE".into(),
            _ => "PORTRAIT".into(),
        }
    }

    #[getter]
    fn aspect_ratio(&self, py: Python<'_>) -> f64 {
        let res: ImageResolution = self.resolution.borrow(py).clone();
        res.aspect_ratio()
    }

    #[getter]
    fn width(&self, py: Python<'_>) -> i32 {
        let res: ImageResolution = self.resolution.borrow(py).clone();
        let rot = RotationType::from_i32(self.rotation);
        if matches!(rot, RotationType::Clockwise90 | RotationType::CounterClockwise90) {
            if res.width != res.height {
                return res.height;
            }
        }
        res.width
    }

    #[getter]
    fn height(&self, py: Python<'_>) -> i32 {
        let res: ImageResolution = self.resolution.borrow(py).clone();
        let rot = RotationType::from_i32(self.rotation);
        if matches!(rot, RotationType::Clockwise90 | RotationType::CounterClockwise90) {
            if res.width != res.height {
                return res.width;
            }
        }
        res.height
    }

    #[getter]
    fn image_shape(&self, py: Python<'_>) -> (i32, i32, i32) {
        let w = self.width(py);
        let h = self.height(py);
        let c = self.color_channels;
        (h, w, c)
    }

    #[getter]
    fn video_image_shape(&self, py: Python<'_>) -> (i32, i32) {
        let res: ImageResolution = self.resolution.borrow(py).clone();
        (res.width, res.height)
    }

    #[getter]
    fn image_size_bytes(&self, py: Python<'_>) -> i32 {
        let res: ImageResolution = self.resolution.borrow(py).clone();
        res.width * res.height * self.color_channels
    }

    /// Serialize to dict (equivalent to Pydantic `model_dump()`).
    fn model_dump(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let dict = PyDict::new(py);
        dict.set_item("camera_id", &self.camera_id)?;
        dict.set_item("camera_index", self.camera_index)?;
        dict.set_item("camera_name", &self.camera_name)?;
        dict.set_item("use_this_camera", self.use_this_camera)?;
        dict.set_item("resolution", self.resolution.bind(py).call_method0("model_dump")?)?;
        dict.set_item("color_channels", self.color_channels)?;
        dict.set_item("pixel_format", &self.pixel_format)?;
        dict.set_item("exposure_mode", &self.exposure_mode)?;
        dict.set_item("exposure", self.exposure)?;
        dict.set_item("framerate", self.framerate)?;
        dict.set_item("rotation", self.rotation)?;
        dict.set_item("capture_fourcc", &self.capture_fourcc)?;
        dict.set_item("writer_fourcc", &self.writer_fourcc)?;
        dict.set_item("orientation", self.orientation(py))?;
        dict.set_item("aspect_ratio", self.aspect_ratio(py))?;
        dict.set_item("width", self.width(py))?;
        dict.set_item("height", self.height(py))?;
        dict.set_item("image_shape", self.image_shape(py))?;
        Ok(dict.into())
    }

    fn __repr__(&self) -> String {
        format!(
            "CameraConfig(camera_id='{}', camera_index={}, camera_name='{}')",
            self.camera_id, self.camera_index, self.camera_name
        )
    }
}

// ── RecordingInfo ──────────────────────────────────────────────────────────

#[pyclass(skip_from_py_object)]
#[derive(Clone, Debug)]
pub struct RecordingInfo {
    #[pyo3(get, set)]
    pub recording_name: String,
    #[pyo3(get, set)]
    pub recording_directory: String,
    #[pyo3(get, set)]
    pub recording_uuid: String,
    #[pyo3(get, set)]
    pub mic_device_index: i32,
}

#[pymethods]
impl RecordingInfo {
    #[new]
    #[pyo3(signature = (recording_name, recording_directory, recording_uuid = None, mic_device_index = -1))]
    fn new(
        recording_name: &str,
        recording_directory: &str,
        recording_uuid: Option<&str>,
        mic_device_index: i32,
    ) -> Self {
        let uuid = match recording_uuid {
            Some(s) if !s.is_empty() => s.into(),
            _ => uuid::Uuid::new_v4().to_string(),
        };
        Self {
            recording_name: recording_name.into(),
            recording_directory: recording_directory.into(),
            recording_uuid: uuid,
            mic_device_index,
        }
    }

    /// Construct from a Python dict (the `StartRecordingRequest` body).
    #[staticmethod]
    fn from_dict(_py: Python<'_>, data: &Bound<'_, PyDict>) -> PyResult<Self> {
        let recording_name: String = data
            .get_item("recording_name")?
            .map(|v| v.extract())
            .unwrap_or(Err(pyo3::exceptions::PyKeyError::new_err("recording_name")))?;
        let recording_directory: String = data
            .get_item("recording_directory")?
            .map(|v| v.extract())
            .unwrap_or(Err(pyo3::exceptions::PyKeyError::new_err("recording_directory")))?;
        let recording_uuid: String = data
            .get_item("recording_uuid")?
            .map(|v| v.extract())
            .unwrap_or(Ok(String::new()))?;
        let mic_device_index: i32 = get_dict_i32_or(data, "mic_device_index", -1);
        Ok(Self::new(
            &recording_name,
            &recording_directory,
            Some(recording_uuid.as_str()),
            mic_device_index,
        ))
    }

    #[getter]
    fn full_recording_path(&self) -> String {
        format!("{}/{}", self.recording_directory, self.recording_name)
    }

    #[getter]
    fn videos_folder(&self) -> String {
        format!("{}/synchronized_videos", self.full_recording_path())
    }

    #[getter]
    fn timestamps_folder(&self) -> String {
        format!("{}/synchronized_videos/timestamps", self.full_recording_path())
    }

    #[getter]
    fn camera_timestamps_folder(&self) -> String {
        format!("{}/synchronized_videos/timestamps/camera_timestamps", self.full_recording_path())
    }

    #[getter]
    fn recording_info_path(&self) -> String {
        format!("{}/{}_info.json", self.full_recording_path(), self.recording_name)
    }

    #[getter]
    fn audio_file_path(&self) -> String {
        format!("{}/{}.audio.wav", self.videos_folder(), self.recording_name)
    }

    fn model_dump(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let dict = PyDict::new(py);
        dict.set_item("recording_name", &self.recording_name)?;
        dict.set_item("recording_directory", &self.recording_directory)?;
        dict.set_item("recording_uuid", &self.recording_uuid)?;
        dict.set_item("mic_device_index", self.mic_device_index)?;
        Ok(dict.into())
    }

    fn __repr__(&self) -> String {
        format!(
            "RecordingInfo(name='{}', dir='{}')",
            self.recording_name, self.recording_directory
        )
    }
}

// ── StatsSummary ───────────────────────────────────────────────────────────

#[pyclass(skip_from_py_object)]
#[derive(Clone, Debug)]
pub struct StatsSummary {
    #[pyo3(get, set)]
    pub median: f64,
    #[pyo3(get, set)]
    pub mean: f64,
    #[pyo3(get, set)]
    pub std: f64,
    #[pyo3(get, set)]
    pub min: f64,
    #[pyo3(get, set)]
    pub max: f64,
}

#[pymethods]
impl StatsSummary {
    #[new]
    fn new(median: f64, mean: f64, std: f64, min: f64, max: f64) -> Self {
        Self { median, mean, std, min, max }
    }

    fn model_dump(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let dict = PyDict::new(py);
        dict.set_item("median", self.median)?;
        dict.set_item("mean", self.mean)?;
        dict.set_item("std", self.std)?;
        dict.set_item("min", self.min)?;
        dict.set_item("max", self.max)?;
        Ok(dict.into())
    }
}

// ── StopRecordingResponse ──────────────────────────────────────────────────

#[pyclass(skip_from_py_object)]
#[derive(Debug)]
pub struct StopRecordingResponse {
    #[pyo3(get, set)]
    pub recording_name: String,
    #[pyo3(get, set)]
    pub recording_path: String,
    #[pyo3(get, set)]
    pub number_of_cameras: i32,
    #[pyo3(get, set)]
    pub number_of_frames: i32,
    #[pyo3(get, set)]
    pub total_duration_sec: f64,
    #[pyo3(get, set)]
    pub mean_framerate: f64,
    #[pyo3(get, set)]
    pub mean_inter_camera_sync_ms: f64,
    #[pyo3(get, set)]
    pub framerate_stats: Py<StatsSummary>,
    #[pyo3(get, set)]
    pub frame_duration_stats: Py<StatsSummary>,
    #[pyo3(get, set)]
    pub inter_camera_grab_range_ms_stats: Py<StatsSummary>,
}

impl Clone for StopRecordingResponse {
    fn clone(&self) -> Self {
        Python::try_attach(|py| {
            Self {
                recording_name: self.recording_name.clone(),
                recording_path: self.recording_path.clone(),
                number_of_cameras: self.number_of_cameras,
                number_of_frames: self.number_of_frames,
                total_duration_sec: self.total_duration_sec,
                mean_framerate: self.mean_framerate,
                mean_inter_camera_sync_ms: self.mean_inter_camera_sync_ms,
                framerate_stats: self.framerate_stats.clone_ref(py),
                frame_duration_stats: self.frame_duration_stats.clone_ref(py),
                inter_camera_grab_range_ms_stats: self.inter_camera_grab_range_ms_stats.clone_ref(py),
            }
        }).expect("GIL must be held for StopRecordingResponse::clone")
    }
}

#[pymethods]
impl StopRecordingResponse {
    #[new]
    fn new(
        recording_name: &str,
        recording_path: &str,
        number_of_cameras: i32,
        number_of_frames: i32,
        total_duration_sec: f64,
        mean_framerate: f64,
        mean_inter_camera_sync_ms: f64,
        framerate_stats: Py<StatsSummary>,
        frame_duration_stats: Py<StatsSummary>,
        inter_camera_grab_range_ms_stats: Py<StatsSummary>,
    ) -> Self {
        Self {
            recording_name: recording_name.into(),
            recording_path: recording_path.into(),
            number_of_cameras,
            number_of_frames,
            total_duration_sec,
            mean_framerate,
            mean_inter_camera_sync_ms,
            framerate_stats,
            frame_duration_stats,
            inter_camera_grab_range_ms_stats,
        }
    }

    fn model_dump(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let dict = PyDict::new(py);
        dict.set_item("recording_name", &self.recording_name)?;
        dict.set_item("recording_path", &self.recording_path)?;
        dict.set_item("number_of_cameras", self.number_of_cameras)?;
        dict.set_item("number_of_frames", self.number_of_frames)?;
        dict.set_item("total_duration_sec", self.total_duration_sec)?;
        dict.set_item("mean_framerate", self.mean_framerate)?;
        dict.set_item("mean_inter_camera_sync_ms", self.mean_inter_camera_sync_ms)?;
        dict.set_item("framerate_stats", self.framerate_stats.bind(py).call_method0("model_dump")?)?;
        dict.set_item("frame_duration_stats", self.frame_duration_stats.bind(py).call_method0("model_dump")?)?;
        dict.set_item("inter_camera_grab_range_ms_stats", self.inter_camera_grab_range_ms_stats.bind(py).call_method0("model_dump")?)?;
        Ok(dict.into())
    }
}

// ── CameraStatusDict (for to_state_dict()) ─────────────────────────────────

#[pyclass(skip_from_py_object)]
#[derive(Clone, Debug)]
pub struct CameraStatusDict {
    #[pyo3(get, set)]
    pub connected: bool,
    #[pyo3(get, set)]
    pub closed: bool,
    #[pyo3(get, set)]
    pub recording_in_progress: bool,
    #[pyo3(get, set)]
    pub is_paused: bool,
    #[pyo3(get, set)]
    pub error: bool,
}

#[pymethods]
impl CameraStatusDict {
    #[new]
    #[pyo3(signature = (connected=true, closed=false, recording_in_progress=false, is_paused=false, error=false))]
    fn new(
        connected: bool,
        closed: bool,
        recording_in_progress: bool,
        is_paused: bool,
        error: bool,
    ) -> Self {
        Self { connected, closed, recording_in_progress, is_paused, error }
    }

    fn model_dump(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let dict = PyDict::new(py);
        dict.set_item("connected", self.connected)?;
        dict.set_item("closed", self.closed)?;
        dict.set_item("recording_in_progress", self.recording_in_progress)?;
        dict.set_item("is_paused", self.is_paused)?;
        dict.set_item("error", self.error)?;
        Ok(dict.into())
    }
}

// ── FramerateData ──────────────────────────────────────────────────────────

#[pyclass(skip_from_py_object)]
#[derive(Clone, Debug)]
pub struct FramerateData {
    #[pyo3(get, set)]
    pub mean_frame_duration_ms: f64,
    #[pyo3(get, set)]
    pub mean_frames_per_second: f64,
    #[pyo3(get, set)]
    pub frame_duration_stddev: f64,
    #[pyo3(get, set)]
    pub frame_duration_median: f64,
    #[pyo3(get, set)]
    pub calculation_window_size: i32,
    #[pyo3(get, set)]
    pub framerate_source: String,
}

#[pymethods]
impl FramerateData {
    #[new]
    fn new(
        mean_frame_duration_ms: f64,
        mean_frames_per_second: f64,
        frame_duration_stddev: f64,
        frame_duration_median: f64,
        calculation_window_size: i32,
        framerate_source: &str,
    ) -> Self {
        Self {
            mean_frame_duration_ms,
            mean_frames_per_second,
            frame_duration_stddev,
            frame_duration_median,
            calculation_window_size,
            framerate_source: framerate_source.into(),
        }
    }

    fn model_dump(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let dict = PyDict::new(py);
        dict.set_item("mean_frame_duration_ms", self.mean_frame_duration_ms)?;
        dict.set_item("mean_frames_per_second", self.mean_frames_per_second)?;
        dict.set_item("frame_duration_stddev", self.frame_duration_stddev)?;
        dict.set_item("frame_duration_median", self.frame_duration_median)?;
        dict.set_item("calculation_window_size", self.calculation_window_size)?;
        dict.set_item("framerate_source", &self.framerate_source)?;
        Ok(dict.into())
    }
}

// ── Dict helpers ───────────────────────────────────────────────────────────

fn get_dict_str_or(data: &Bound<'_, PyDict>, key: &str, default: &str) -> String {
    data.get_item(key)
        .ok()
        .flatten()
        .and_then(|v| v.extract().ok())
        .unwrap_or_else(|| default.into())
}

fn get_dict_i32_or(data: &Bound<'_, PyDict>, key: &str, default: i32) -> i32 {
    data.get_item(key)
        .ok()
        .flatten()
        .and_then(|v| v.extract().ok())
        .unwrap_or(default)
}

fn get_dict_f64_or(data: &Bound<'_, PyDict>, key: &str, default: f64) -> f64 {
    data.get_item(key)
        .ok()
        .flatten()
        .and_then(|v| v.extract().ok())
        .unwrap_or(default)
}

fn get_dict_bool_or(data: &Bound<'_, PyDict>, key: &str, default: bool) -> bool {
    data.get_item(key)
        .ok()
        .flatten()
        .and_then(|v| v.extract().ok())
        .unwrap_or(default)
}
