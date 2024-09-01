
pub fn build_sidecar_path(base_sidecar_name:&str) -> String {
    println!("Building os-specific path for sidecar: {}", base_sidecar_name);

    let arch = if cfg!(target_arch = "x86") {
        "i686"
    } else if cfg!(target_arch = "x86_64") {
        "x86_64"
    } else if cfg!(target_arch = "arm") {
        "arm"
    } else if cfg!(target_arch = "aarch64") {
        "aarch64"
    } else {
        panic!("Unsupported architecture");
    };
    println!("Architecture: {}", arch);

    let os = if cfg!(target_os = "windows") {
        "pc-windows"
    } else if cfg!(target_os = "macos") {
        "apple-darwin"
    } else if cfg!(target_os = "linux") {
        "unknown-linux"
    } else if cfg!(target_os = "android") {
        "linux-android"
    } else {
        panic!("Unsupported OS");
    };
    println!("Operating System: {}", os);

    let env = if cfg!(target_env = "gnu") {
        "-gnu"
    } else if cfg!(target_env = "msvc") {
        "-msvc"
    } else {
        ""
    };
    println!("Environment: {}", env);

    let ext = if cfg!(target_os = "windows") {
        ".exe"
    } else {
        ""
    };
    println!("Extension: {}", ext);

    let sidecar_path = format!("{}-{}-{}{}{}", base_sidecar_name,  arch, os, env, ext);
    println!("Sidecar path: {}", sidecar_path);
    return sidecar_path
}
