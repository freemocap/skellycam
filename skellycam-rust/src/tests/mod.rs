pub mod all_tests;
pub mod api_server_tests;
pub mod detection_tests;
pub mod lifecycle_tests;
pub mod manager_tests;
pub mod multi_camera_tests;
pub mod pause_tests;
pub mod recording_tests;
pub mod rotation_tests;
pub mod update_config_tests;

/// Emit multiple lines as a single `tracing::info!` event.
///
/// Each element is one line. Empty strings produce blank lines.
/// The block is prefixed with `\n` so it is visually separated
/// from the preceding log line.
pub(crate) fn info_block(lines: &[&str]) {
    tracing::info!("\n{}", lines.join("\n"));
}
