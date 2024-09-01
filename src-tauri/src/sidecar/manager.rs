use std::process::{Child, Command};
use crate::sidecar::path_builder::build_sidecar_path;

pub struct SidecarManager {
    pub child: Option<Child>,
}

impl SidecarManager {
    pub fn new(base_name: &str) -> Self {
        let sidecar_path = build_sidecar_path(base_name);
        println!("Spawning sidecar process for: {}", sidecar_path);
        let child = Command::new(&sidecar_path)
            .spawn()
            .expect("Failed to execute child process");
        println!("Sidecar process started successfully!");

        SidecarManager {child: Some(child)}
    }
}

impl Drop for SidecarManager {
    fn drop(&mut self) {
        if let Some(child) = self.child.as_mut() {
            println!("Killing the sidecar process...");
            let _ = child.kill();
            println!("Sidecar process killed :D")
        }
    }
}