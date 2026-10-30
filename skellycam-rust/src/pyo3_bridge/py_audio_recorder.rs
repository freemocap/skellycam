use pyo3::prelude::*;
use pyo3::exceptions::PyRuntimeError;
use crate::recording::audio::AudioRecorder;

#[pyclass(name = "AudioRecorder")]
pub struct PyAudioRecorder { recorder: AudioRecorder }

#[pymethods]
impl PyAudioRecorder {
    #[new]
    fn new(py: Python<'_>, library_path: String, output_path: String,
        device_index: i32, timebase_mapping: String,
    ) -> PyResult<Self> {
        let mapping = serde_json::from_str(&timebase_mapping)
            .map_err(|error| PyRuntimeError::new_err(format!("Invalid audio timebase: {error}")))?;
        let recorder = py.detach(move || AudioRecorder::start(
            library_path, output_path.into(), device_index, mapping,
        )).map_err(|error| PyRuntimeError::new_err(format!("Microphone startup: {error:#}")))?;
        Ok(Self { recorder })
    }

    fn stop(&mut self, py: Python<'_>) -> PyResult<String> {
        py.detach(|| self.recorder.stop())
            .map(|metadata| metadata.to_string())
            .map_err(|error| PyRuntimeError::new_err(format!("Microphone finalization: {error:#}")))
    }
}
