//! Build script: detect OpenCV installation and set up linking.

fn main() {
    // The opencv crate handles detection via env vars, vcpkg, pkg-config, and brew.
    // We just check that one of the detection paths will find OpenCV.
    let link_libs = std::env::var("OPENCV_LINK_LIBS").ok();
    let link_paths = std::env::var("OPENCV_LINK_PATHS").ok();
    let include_paths = std::env::var("OPENCV_INCLUDE_PATHS").ok();

    if link_libs.is_some() && link_paths.is_some() && include_paths.is_some() {
        println!("cargo:warning=Using OpenCV from environment variables");
        return;
    }

    // Check common install locations
    #[cfg(target_os = "windows")]
    {
        let chocolatey = std::path::Path::new("C:\\tools\\opencv\\build\\x64\\vc16\\lib");
        let manual = std::path::Path::new("C:\\opencv\\build\\x64\\vc16\\lib");
        if chocolatey.exists() {
            println!("cargo:warning=Found OpenCV at C:\\tools\\opencv (chocolatey)");
            println!("cargo:rustc-link-search=native=C:\\tools\\opencv\\build\\x64\\vc16\\lib");
            println!("cargo:rustc-link-lib=opencv_world4130");
        } else if manual.exists() {
            println!("cargo:warning=Found OpenCV at C:\\opencv");
            println!("cargo:rustc-link-search=native=C:\\opencv\\build\\x64\\vc16\\lib");
            println!("cargo:rustc-link-lib=opencv_world4100");
        }
    }

    #[cfg(target_os = "macos")]
    {
        println!("cargo:warning=On macOS, install OpenCV via: brew install opencv");
    }

    #[cfg(target_os = "linux")]
    {
        println!("cargo:warning=On Linux, install OpenCV via: sudo apt install libopencv-dev");
    }
}
