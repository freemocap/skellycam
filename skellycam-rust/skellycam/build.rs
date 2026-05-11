//! Build script: detect OpenCV, set up linking, and copy runtime DLLs.

use std::path::Path;

fn main() {
    let link_libs = std::env::var("OPENCV_LINK_LIBS").ok();
    let link_paths = std::env::var("OPENCV_LINK_PATHS").ok();
    let include_paths = std::env::var("OPENCV_INCLUDE_PATHS").ok();

    if link_libs.is_none() || link_paths.is_none() || include_paths.is_none() {
        // Fallback: detect from common locations
        #[cfg(target_os = "windows")]
        {
            let chocolatey = Path::new("C:\\tools\\opencv\\build\\x64\\vc16\\lib");
            let manual = Path::new("C:\\opencv\\build\\x64\\vc16\\lib");
            if chocolatey.exists() {
                println!("cargo:warning=Found OpenCV at C:\\tools\\opencv (chocolatey)");
                println!("cargo:rustc-link-search=native=C:\\tools\\opencv\\build\\x64\\vc16\\lib");
                println!("cargo:rustc-link-lib=opencv_world4130");
                copy_opencv_dlls("C:\\tools\\opencv\\build\\x64\\vc16\\bin");
            } else if manual.exists() {
                println!("cargo:warning=Found OpenCV at C:\\opencv");
                println!("cargo:rustc-link-search=native=C:\\opencv\\build\\x64\\vc16\\lib");
                println!("cargo:rustc-link-lib=opencv_world4100");
                copy_opencv_dlls("C:\\opencv\\build\\x64\\vc16\\bin");
            }
        }
        return;
    }

    println!("cargo:warning=Using OpenCV from environment variables");

    // Copy runtime DLLs next to the binary so `cargo run` works
    let lib_dir = link_paths.as_ref().unwrap();
    let bin_dir = lib_dir.replace("\\lib", "\\bin").replace("/lib", "/bin");
    let bin_path = Path::new(&bin_dir);
    if bin_path.exists() {
        copy_opencv_dlls(&bin_dir);
    }
}

fn copy_dll(bin_dir: &str, target_dir: &Path, name: &str) {
    let src = Path::new(bin_dir).join(name);
    if src.exists() {
        let dest = target_dir.join(name);
        let _ = std::fs::copy(&src, &dest);
    }
}

fn copy_opencv_dlls(bin_dir: &str) {
    // OUT_DIR = target/release/build/skellycam-HASH/out
    // We want: target/release  (or target/debug)
    let out_dir = std::env::var("OUT_DIR").unwrap();
    let target_dir = Path::new(&out_dir)
        .parent()  // skellycam-HASH
        .and_then(|p| p.parent())  // build
        .and_then(|p| p.parent())  // release or debug
        .expect("Failed to determine target directory");

    // Determine DLL suffix from the lib name
    let (world_dll, ffmpeg_dll, msmf_dll) = if bin_dir.contains("tools") {
        ("opencv_world4130.dll", "opencv_videoio_ffmpeg4130_64.dll", "opencv_videoio_msmf4130_64.dll")
    } else {
        ("opencv_world4100.dll", "opencv_videoio_ffmpeg4100_64.dll", "opencv_videoio_msmf4100_64.dll")
    };

    copy_dll(bin_dir, target_dir, world_dll);
    copy_dll(bin_dir, target_dir, ffmpeg_dll);
    copy_dll(bin_dir, target_dir, msmf_dll);
}
