mod app_info;
mod assets;
mod file_system;
mod http_proxy;
mod python_server;
mod telemetry;

use python_server::PythonServerState;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_fs::init())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .manage(PythonServerState::new())
        .invoke_handler(tauri::generate_handler![
            // Python server
            python_server::start_python_server,
            python_server::stop_python_server,
            python_server::get_executable_path,
            python_server::get_executable_candidates,
            python_server::refresh_candidates,
            python_server::is_python_server_running,
            python_server::get_process_info,
            // File system
            file_system::open_folder,
            file_system::get_home_directory,
            file_system::get_folder_contents,
            // HTTP proxy
            http_proxy::proxy_fetch,
            // Assets
            assets::get_logo_base64,
            assets::get_logo_png_path,
            // Telemetry
            telemetry::get_telemetry_enabled,
            telemetry::set_telemetry_enabled,
            // App info
            app_info::get_app_version,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
