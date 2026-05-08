use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Serialize, Deserialize)]
struct TelemetryConfig {
    telemetry_enabled: bool,
}

impl Default for TelemetryConfig {
    fn default() -> Self {
        Self {
            telemetry_enabled: true,
        }
    }
}

fn config_path() -> PathBuf {
    let home = std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("."));

    home.join("skellycam_data")
        .join("telemetry_config.json")
}

fn read_config() -> TelemetryConfig {
    let path = config_path();
    match fs::read_to_string(&path) {
        Ok(raw) => match serde_json::from_str::<TelemetryConfig>(&raw) {
            Ok(config) => config,
            Err(e) => {
                log::error!("Failed to parse telemetry config: {}", e);
                TelemetryConfig::default()
            }
        },
        Err(_) => TelemetryConfig::default(),
    }
}

fn write_config(config: &TelemetryConfig) -> Result<(), String> {
    let path = config_path();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("Failed to create config dir: {}", e))?;
    }
    let json = serde_json::to_string_pretty(config)
        .map_err(|e| format!("Failed to serialize config: {}", e))?;
    fs::write(&path, json + "\n").map_err(|e| format!("Failed to write config: {}", e))
}

#[tauri::command]
pub fn get_telemetry_enabled() -> Result<bool, String> {
    Ok(read_config().telemetry_enabled)
}

#[tauri::command]
pub fn set_telemetry_enabled(enabled: bool) -> Result<bool, String> {
    write_config(&TelemetryConfig {
        telemetry_enabled: enabled,
    })?;
    Ok(enabled)
}
