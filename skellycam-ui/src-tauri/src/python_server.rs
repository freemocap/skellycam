use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::{AppHandle, Manager, State};

const SERVER_EXE_NAME: &str = if cfg!(windows) {
    "skellycam_server.exe"
} else {
    "skellycam_server"
};

pub struct PythonServerState {
    child: Mutex<Option<Child>>,
    current_exe_path: Mutex<Option<String>>,
}

impl PythonServerState {
    pub fn new() -> Self {
        Self {
            child: Mutex::new(None),
            current_exe_path: Mutex::new(None),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExecutableCandidate {
    pub name: String,
    pub path: String,
    pub description: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_valid: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub resolved_path: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProcessInfo {
    pub pid: Option<u32>,
    pub killed: bool,
}

// ── Path helpers ──────────────────────────────────────────────

fn resources_path(app: &AppHandle) -> PathBuf {
    app.path()
        .resource_dir()
        .unwrap_or_else(|_| PathBuf::from("."))
}

fn default_install_unpacked_path() -> PathBuf {
    let home = dirs_fallback();
    match std::env::consts::OS {
        "windows" => home.join("AppData").join("Local").join("Programs").join("skellycam").join("resources"),
        "macos" => PathBuf::from("/Applications/skellycam.app/Contents/Resources"),
        "linux" => PathBuf::from("/opt/skellycam/resources"),
        _ => home.join("skellycam").join("resources"),
    }
}

fn dirs_fallback() -> PathBuf {
    std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("."))
}

// ── Candidate resolution (matches app-paths.ts + python-server.ts) ──

fn build_candidates(app: &AppHandle) -> Vec<ExecutableCandidate> {
    let resources = resources_path(app);
    let default_install = default_install_unpacked_path();
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));

    vec![
        ExecutableCandidate {
            name: "bundled".into(),
            path: resources.join(SERVER_EXE_NAME).to_string_lossy().into(),
            description: "Executable bundled with the running app (resources)".into(),
            is_valid: None,
            error: None,
            resolved_path: None,
        },
        ExecutableCandidate {
            name: "default-install".into(),
            path: default_install.join(SERVER_EXE_NAME).to_string_lossy().into(),
            description: "Executable in the platform default install location".into(),
            is_valid: None,
            error: None,
            resolved_path: None,
        },
        ExecutableCandidate {
            name: "development".into(),
            path: resources
                .parent()
                .unwrap_or(&resources)
                .join("dist")
                .join(SERVER_EXE_NAME)
                .to_string_lossy()
                .into(),
            description: "Development build executable (../dist/)".into(),
            is_valid: None,
            error: None,
            resolved_path: None,
        },
        ExecutableCandidate {
            name: "portable".into(),
            path: cwd.join(SERVER_EXE_NAME).to_string_lossy().into(),
            description: "Portable executable in the current working directory".into(),
            is_valid: None,
            error: None,
            resolved_path: None,
        },
        ExecutableCandidate {
            name: "system-path".into(),
            path: SERVER_EXE_NAME.into(),
            description: "Executable available in system PATH".into(),
            is_valid: None,
            error: None,
            resolved_path: None,
        },
    ]
}

fn validate_executable(path: &str) -> Result<(), String> {
    let p = PathBuf::from(path);

    if !p.exists() {
        return Err(format!("Executable not found at: {}", path));
    }

    let meta = p
        .metadata()
        .map_err(|e| format!("Cannot stat: {}: {}", path, e))?;

    if !meta.is_file() {
        return Err(format!("Path is not a file: {}", path));
    }

    // On Unix, also check execute permission
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let perms = meta.permissions();
        if perms.mode() & 0o111 == 0 {
            return Err(format!("File is not executable: {}", path));
        }
    }

    // On Windows, warn if no .exe extension
    #[cfg(windows)]
    {
        if !path.to_lowercase().ends_with(".exe") {
            log::warn!("Executable doesn't have .exe extension: {}", path);
        }
    }

    Ok(())
}

fn validate_all_candidates(app: &AppHandle) -> Vec<ExecutableCandidate> {
    let candidates = build_candidates(app);

    let mut validated: Vec<ExecutableCandidate> = candidates
        .into_iter()
        .map(|mut c| {
            match validate_executable(&c.path) {
                Ok(()) => {
                    c.is_valid = Some(true);
                    // Resolve the real path for dedup
                    let resolved = std::fs::canonicalize(&c.path)
                        .unwrap_or_else(|_| PathBuf::from(&c.path));
                    c.resolved_path = Some(resolved.to_string_lossy().into());
                    log::info!("  ✓ {}: Valid", c.name);
                }
                Err(e) => {
                    c.is_valid = Some(false);
                    c.error = Some(e.clone());
                    log::info!("  ✗ {}: {}", c.name, e);
                }
            }
            c
        })
        .collect();

    // Deduplicate by resolved path
    let mut seen = std::collections::HashSet::new();
    validated.retain(|c| {
        let key = c.resolved_path.clone().unwrap_or_else(|| c.path.clone());
        if seen.contains(&key) {
            log::info!("  ⚠ Skipping duplicate: {} (same as another candidate)", c.name);
            false
        } else {
            seen.insert(key);
            true
        }
    });

    let valid_count = validated.iter().filter(|c| c.is_valid == Some(true)).count();
    log::info!(
        "Validation complete: {}/{} unique candidates are valid",
        valid_count,
        validated.len()
    );

    validated
}

// ── Tauri commands ────────────────────────────────────────────

#[tauri::command]
pub async fn start_python_server(
    exe_path: Option<String>,
    app: AppHandle,
    state: State<'_, PythonServerState>,
) -> Result<(), String> {
    log::info!("Starting python server subprocess...");

    // Shut down any existing process first
    stop_python_server(state.clone()).await?;

    let executable_path = if let Some(ref path) = exe_path {
        validate_executable(path)?;
        log::info!("Using provided executable path: {}", path);
        path.clone()
    } else {
        let candidates = validate_all_candidates(&app);
        let valid = candidates
            .iter()
            .find(|c| c.is_valid == Some(true))
            .ok_or_else(|| {
                let errors: Vec<String> = candidates
                    .iter()
                    .map(|c| format!("  - {}: {}", c.name, c.error.as_deref().unwrap_or("Unknown error")))
                    .collect();
                format!(
                    "No valid Python server executable found:\n{}",
                    errors.join("\n")
                )
            })?;
        log::info!(
            "Using auto-detected executable path: {}",
            valid.path
        );
        valid.path.clone()
    };

    // Spawn the child process
    let child = Command::new(&executable_path)
        .spawn()
        .map_err(|e| format!("Failed to spawn Python server: {}", e))?;

    let pid = child.id();
    log::info!("Python server started successfully (PID: {})", pid);

    // Store state
    *state.current_exe_path.lock().unwrap() = Some(executable_path);
    *state.child.lock().unwrap() = Some(child);

    Ok(())
}

#[tauri::command]
pub async fn stop_python_server(
    state: State<'_, PythonServerState>,
) -> Result<(), String> {
    let mut child_opt = state.child.lock().unwrap();

    let Some(mut child) = child_opt.take() else {
        log::info!("No Python server process to shutdown");
        return Ok(());
    };

    let pid = child.id();
    log::info!("Shutting down Python server (PID: {})", pid);

    // Try graceful kill first, then force kill
    if let Err(e) = child.kill() {
        log::error!("Error killing process tree: {}", e);
    }

    // Wait for cleanup
    std::thread::sleep(std::time::Duration::from_secs(1));

    match child.try_wait() {
        Ok(Some(status)) => log::info!("Python server exited with: {:?}", status),
        Ok(None) => {
            log::warn!("Python server may not have exited cleanly, force killing");
            let _ = child.kill();
        }
        Err(e) => {
            log::error!("Error waiting for process: {}", e);
            let _ = child.kill();
        }
    }

    *state.current_exe_path.lock().unwrap() = None;
    log::info!("Python server shutdown complete");

    Ok(())
}

#[tauri::command]
pub async fn get_executable_path(
    state: State<'_, PythonServerState>,
) -> Result<Option<String>, String> {
    Ok(state.current_exe_path.lock().unwrap().clone())
}

#[tauri::command]
pub async fn get_executable_candidates(
    app: AppHandle,
) -> Result<Vec<ExecutableCandidate>, String> {
    Ok(validate_all_candidates(&app))
}

#[tauri::command]
pub async fn refresh_candidates(
    app: AppHandle,
) -> Result<Vec<ExecutableCandidate>, String> {
    log::info!("Refreshing executable candidates validation...");
    Ok(validate_all_candidates(&app))
}

#[tauri::command]
pub async fn is_python_server_running(
    state: State<'_, PythonServerState>,
) -> Result<bool, String> {
    let child_opt = state.child.lock().unwrap();
    Ok(child_opt.is_some())
}

#[tauri::command]
pub async fn get_process_info(
    state: State<'_, PythonServerState>,
) -> Result<Option<ProcessInfo>, String> {
    let child_opt = state.child.lock().unwrap();
    match &*child_opt {
        Some(child) => Ok(Some(ProcessInfo {
            pid: Some(child.id()),
            killed: false,
        })),
        None => Ok(None),
    }
}
