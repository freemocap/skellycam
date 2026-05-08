use std::fs;
use std::path::PathBuf;
use tauri::{AppHandle, Manager};

/// Returns the logo as a base64 data URL (data:image/png;base64,...)
#[tauri::command]
pub fn get_logo_base64(app: AppHandle) -> Result<Option<String>, String> {
    let logo_path = find_logo(&app);

    let Some(path) = logo_path else {
        log::error!("Logo file not found in any expected location");
        return Ok(None);
    };

    let bytes = fs::read(&path).map_err(|e| format!("Failed to read logo: {}", e))?;
    let b64 = base64_encode(&bytes);
    Ok(Some(format!("data:image/png;base64,{}", b64)))
}

/// Returns the absolute path to the logo PNG file
#[tauri::command]
pub fn get_logo_png_path(app: AppHandle) -> Result<String, String> {
    let logo_path = find_logo(&app);
    match logo_path {
        Some(p) => Ok(p.to_string_lossy().into()),
        None => {
            // Fall back to resources path even if it doesn't exist
            let resources = app
                .path()
                .resource_dir()
                .unwrap_or_else(|_| PathBuf::from("."));
            Ok(resources
                .join("dist")
                .join("skellycam-logo.png")
                .to_string_lossy()
                .into())
        }
    }
}

fn find_logo(app: &AppHandle) -> Option<PathBuf> {
    let resources = app
        .path()
        .resource_dir()
        .unwrap_or_else(|_| PathBuf::from("."));

    // Shared path (dev mode)
    let shared_path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap_or(&resources)
        .parent()
        .unwrap_or(&resources)
        .join("shared")
        .join("skellycam-logo")
        .join("skellycam-logo.png");

    // Resources path (packaged)
    let resources_path = resources.join("skellycam-logo.png");

    // dist path within resources (packaged)
    let dist_path = resources.join("dist").join("skellycam-logo.png");

    for path in &[&shared_path, &resources_path, &dist_path] {
        if path.exists() {
            return Some(path.to_path_buf());
        }
    }

    None
}

fn base64_encode(bytes: &[u8]) -> String {
    // Simple base64 encoder — no external crate needed
    const CHARS: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

    let mut result = String::new();
    let chunks = bytes.chunks(3);

    for chunk in chunks {
        let b0 = chunk[0] as u32;
        let b1 = chunk.get(1).copied().unwrap_or(0) as u32;
        let b2 = chunk.get(2).copied().unwrap_or(0) as u32;
        let triple = (b0 << 16) | (b1 << 8) | b2;

        result.push(CHARS[((triple >> 18) & 0x3F) as usize] as char);
        result.push(CHARS[((triple >> 12) & 0x3F) as usize] as char);

        if chunk.len() > 1 {
            result.push(CHARS[((triple >> 6) & 0x3F) as usize] as char);
        } else {
            result.push('=');
        }

        if chunk.len() > 2 {
            result.push(CHARS[(triple & 0x3F) as usize] as char);
        } else {
            result.push('=');
        }
    }

    result
}
