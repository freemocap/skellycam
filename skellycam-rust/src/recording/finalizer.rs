//! Recording finalizer: validates frame counts across cameras, generates
//! RecordingInfo JSON, and produces a human-readable summary.
//!
//! Fed by the VideoRecorder (video files) and CsvWriter (timestamp CSVs).
//! Reads the CSV files to count frames and validate consistency.

use std::fs;
use std::path::{Path, PathBuf};

use anyhow::Context;

use crate::camera::CameraIdentity;

/// Metadata about a single camera in the recording.
#[derive(serde::Serialize)]
struct CameraRecordingInfo {
    camera_index: i32,
    display_name: String,
    unique_identifier: String,
    width: u32,
    height: u32,
    frame_count: u64,
    video_path: String,
    timestamp_csv_path: String,
}

/// The RecordingInfo JSON written alongside the video and CSV files.
#[derive(serde::Serialize)]
struct RecordingInfo {
    recording_directory: String,
    camera_count: usize,
    total_frames_per_camera: u64,
    cameras: Vec<CameraRecordingInfo>,
}

pub struct RecordingSummary {
    pub total_frames_per_camera: u64,
    pub video_paths: Vec<PathBuf>,
    pub csv_paths: Vec<PathBuf>,
    pub info_json_path: PathBuf,
}

/// Validate recording output and generate RecordingInfo JSON.
///
/// Reads each camera's timestamp CSV to count frames, validates that all
/// cameras recorded the same number of frames, then writes a RecordingInfo
/// JSON file to the recording directory.
pub fn finalize_recording(
    recording_dir: &Path,
    camera_infos: &[(CameraIdentity, u32, u32)],  // (identity, width, height)
    video_paths: &[PathBuf],
    csv_paths: &[PathBuf],
) -> anyhow::Result<RecordingSummary> {
    if camera_infos.len() != video_paths.len() || camera_infos.len() != csv_paths.len() {
        anyhow::bail!(
            "Mismatch: {} cameras, {} videos, {} CSVs",
            camera_infos.len(),
            video_paths.len(),
            csv_paths.len(),
        );
    }

    let mut cameras: Vec<CameraRecordingInfo> = Vec::new();
    let mut frame_counts: Vec<u64> = Vec::new();

    for idx in 0..camera_infos.len() {
        let (identity, width, height) = &camera_infos[idx];
        let video_path = &video_paths[idx];
        let csv_path = &csv_paths[idx];

        let frame_count = count_csv_rows(csv_path)
            .with_context(|| format!("Failed to read timestamp CSV for camera {idx}"))?;

        cameras.push(CameraRecordingInfo {
            camera_index: identity.camera_index,
            display_name: identity.camera_name.clone(),
            unique_identifier: identity.camera_id.clone(),
            width: *width,
            height: *height,
            frame_count,
            video_path: video_path
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string(),
            timestamp_csv_path: csv_path
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string(),
        });

        frame_counts.push(frame_count);
    }

    // Validate: all cameras must have the same frame count
    let first_count = frame_counts[0];
    for (idx, &count) in frame_counts.iter().enumerate().skip(1) {
        if count != first_count {
            anyhow::bail!(
                "Frame count mismatch: camera 0 has {first_count} frames, camera {idx} has {count} frames"
            );
        }
    }

    let info = RecordingInfo {
        recording_directory: recording_dir
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string(),
        camera_count: cameras.len(),
        total_frames_per_camera: first_count,
        cameras,
    };

    let json_path = recording_dir.join("recording_info.json");
    let json_string = serde_json::to_string_pretty(&info)
        .context("Failed to serialize RecordingInfo")?;
    fs::write(&json_path, json_string)
        .context("Failed to write recording_info.json")?;

    Ok(RecordingSummary {
        total_frames_per_camera: first_count,
        video_paths: video_paths.to_vec(),
        csv_paths: csv_paths.to_vec(),
        info_json_path: json_path,
    })
}

/// Count the number of data rows in a CSV file (excluding header).
fn count_csv_rows(path: &Path) -> anyhow::Result<u64> {
    let mut reader = csv::Reader::from_path(path)
        .with_context(|| format!("Failed to open CSV: {}", path.display()))?;
    let count = reader.records().count() as u64;
    Ok(count)
}
