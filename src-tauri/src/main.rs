// Prevents additional console window on Windows in release, DO NOT REMOVE!!
// #![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{Manager};
// use tauri::WindowEvent;
// use std::process::Child;
use std::sync::{Arc, Mutex};

mod sidecar;
use sidecar::manager::SidecarManager;

fn main() {
    println!("Running `main.rs`...");
    let sidecar_base_name: &str = "../dist/skellycam";

    println!("Setting up Tauri application...");
    tauri::Builder::default()
        .setup(|app| {
            let sidecar_manager = SidecarManager::new(sidecar_base_name);
            app.manage(Arc::new(Mutex::new(sidecar_manager)));
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
    println!("Tauri application is running...");
}
