use tauri::AppHandle;

/// Returns the app version from tauri.conf.json
#[tauri::command]
pub fn get_app_version(app: AppHandle) -> Result<String, String> {
    Ok(app.package_info().version.to_string())
}
