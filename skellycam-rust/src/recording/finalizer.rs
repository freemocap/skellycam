//! Recording finalizer: validates that every camera recorded the same number of
//! frames and reports where the recording's files are.
//!
//! Fed by the VideoRecorder (video files) and CsvWriter (per-camera timestamp CSVs).
//! Reads the CSV files to count frames and validate consistency. SkellyCam's Python
//! recording finalizer then writes the recording's info and timestamp files.

use std::path::{Path, PathBuf};

use anyhow::Context;

use crate::camera::CameraIdentity;

pub struct RecordingSummary {
    pub total_frames_per_camera: u64,
    pub video_paths: Vec<PathBuf>,
    pub csv_paths: Vec<PathBuf>,
    /// Folder holding this recording; empty when the recording failed to finalize.
    pub recording_dir: PathBuf,
    pub stats: Option<crate::camera_group::recording_stats::RecordingStatsSummary>,
}

/// Validate recording output.
///
/// Reads each camera's timestamp CSV to count frames and validates that all
/// cameras recorded the same number of frames.
pub fn finalize_recording(
    recording_dir: &Path,
    camera_infos: &[(CameraIdentity, u32, u32)],  // (identity, width, height)
    video_paths: &[PathBuf],
    csv_paths: &[PathBuf],
    stats: Option<crate::camera_group::recording_stats::RecordingStatsSummary>,
) -> anyhow::Result<RecordingSummary> {
    if camera_infos.len() != video_paths.len() || camera_infos.len() != csv_paths.len() {
        anyhow::bail!(
            "Mismatch: {} cameras, {} videos, {} CSVs",
            camera_infos.len(),
            video_paths.len(),
            csv_paths.len(),
        );
    }

    let mut frame_counts: Vec<u64> = Vec::with_capacity(csv_paths.len());
    for (idx, csv_path) in csv_paths.iter().enumerate() {
        let frame_count = count_csv_rows(csv_path)
            .with_context(|| format!("Failed to read timestamp CSV for camera {idx}"))?;
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

    Ok(RecordingSummary {
        total_frames_per_camera: first_count,
        video_paths: video_paths.to_vec(),
        csv_paths: csv_paths.to_vec(),
        recording_dir: recording_dir.to_path_buf(),
        stats,
    })
}

/// Count the number of data rows in a CSV file (excluding header).
fn count_csv_rows(path: &Path) -> anyhow::Result<u64> {
    let mut reader = csv::Reader::from_path(path)
        .with_context(|| format!("Failed to open CSV: {}", path.display()))?;
    let count = reader.records().count() as u64;
    Ok(count)
}
