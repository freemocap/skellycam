//! Build script: download pre-built openpnp-capture + turbojpeg static libs
//! from the latest GitHub Release on the `jonmatthis/openpnp-capture` fork.
//!
//! Archives are cached in `target/build-artifacts/` — incremental builds
//! skip the download entirely.

use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::Command;

const OPENPNP_REPO: &str = "jonmatthis/openpnp-capture";

fn main() {
    let target = env::var("TARGET").unwrap_or_else(|_| String::from("unknown"));

    let (archive_name, archive_ext) = match target_triple_to_artifact(&target) {
        Some(v) => v,
        None => {
            eprintln!();
            eprintln!("╔══════════════════════════════════════════════════════════════╗");
            eprintln!("║  openpnp-capture pre-built libraries are not yet available  ║");
            eprintln!("║  for target: {target:<46}║");
            eprintln!("║                                                              ║");
            eprintln!("║  Currently supported:                                        ║");
            eprintln!("║    x86_64-pc-windows-msvc                                    ║");
            eprintln!("║    aarch64-pc-windows-msvc                                   ║");
            eprintln!("║                                                              ║");
            eprintln!("║  macOS and Linux support is in progress.                     ║");
            eprintln!("║  https://github.com/{OPENPNP_REPO}/releases                  ║");
            eprintln!("╚══════════════════════════════════════════════════════════════╝");
            eprintln!();
            std::process::exit(1);
        }
    };

    // ── Resolve latest release tag ──────────────────────────────────────
    let tag = get_latest_tag().unwrap_or_else(|_| {
        // Fallback if no network or API issue — the highest known tag
        // should be updated when a new build is published.
        eprintln!("  [build.rs] WARNING: could not reach GitHub API, using fallback tag");
        "build.2".to_string()
    });
    eprintln!("  [build.rs] openpnp-capture release: {tag}");

    // ── Download ────────────────────────────────────────────────────────
    let artifact_dir = PathBuf::from(env::var("OUT_DIR").unwrap());
    let build_artifacts = artifact_dir
        .parent().unwrap()  // out/
        .parent().unwrap()  // build/
        .parent().unwrap()  // target/debug|release/
        .join("build-artifacts");

    let download_dir = build_artifacts.join("downloads");
    fs::create_dir_all(&download_dir).unwrap();

    let archive_file = download_dir.join(&archive_name);

    if !archive_file.exists() {
        let url = format!(
            "https://github.com/{OPENPNP_REPO}/releases/download/{tag}/{archive_name}"
        );
        eprintln!("  [build.rs] downloading: {url}");

        let response = ureq::get(&url)
            .call()
            .unwrap_or_else(|e| {
                panic!(
                    "Failed to download openpnp-capture from:\n  {url}\n  Error: {e}\n\n\
                     Make sure the release exists at:\n  \
                     https://github.com/{OPENPNP_REPO}/releases/tag/{tag}"
                )
            });

        let bytes = response.into_body().read_to_vec().unwrap();
        fs::write(&archive_file, &bytes).unwrap();
    }

    // ── Extract ─────────────────────────────────────────────────────────
    let extract_dir = build_artifacts.join(&target);
    if !extract_dir.exists() {
        fs::create_dir_all(&extract_dir).unwrap();

        if archive_ext == "zip" {
            let status = Command::new("powershell")
                .args([
                    "-NoProfile",
                    "-Command",
                    &format!(
                        "Expand-Archive -Path '{}' -DestinationPath '{}' -Force",
                        archive_file.display(),
                        extract_dir.display(),
                    ),
                ])
                .status()
                .unwrap();
            if !status.success() {
                panic!("Failed to extract: {}", archive_file.display());
            }
        } else {
            // tar.gz — Linux/macOS (when we add support)
            let status = Command::new("tar")
                .args([
                    "-xzf",
                    &archive_file.display().to_string(),
                    "-C",
                    &extract_dir.display().to_string(),
                ])
                .status()
                .unwrap();
            if !status.success() {
                panic!("Failed to extract: {}", archive_file.display());
            }
        }
    }

    // ── Link ────────────────────────────────────────────────────────────
    let lib_dir = extract_dir.join("lib");
    println!("cargo:rustc-link-search=native={}", lib_dir.display());
    println!("cargo:rustc-link-lib=static=openpnp-capture");
    println!("cargo:rustc-link-lib=static=turbojpeg-static");

    // Windows system libraries required by openpnp-capture
    if target.contains("windows") {
        println!("cargo:rustc-link-lib=ole32");
        println!("cargo:rustc-link-lib=oleaut32");
        println!("cargo:rustc-link-lib=strmiids");
    }
}

// ── Platform mapping ──────────────────────────────────────────────────────

fn target_triple_to_artifact(target: &str) -> Option<(String, &'static str)> {
    match target {
        "x86_64-pc-windows-msvc" => {
            Some(("openpnp-capture-windows-x86_64.zip".into(), "zip"))
        }
        "aarch64-pc-windows-msvc" => {
            Some(("openpnp-capture-windows-arm64.zip".into(), "zip"))
        }
        _ => None,
    }
}

// ── GitHub API: resolve latest release tag ────────────────────────────────

fn get_latest_tag() -> Result<String, String> {
    let url = format!(
        "https://api.github.com/repos/{OPENPNP_REPO}/releases/latest"
    );
    let response = ureq::get(&url)
        .header("Accept", "application/vnd.github+json")
        .header("User-Agent", "skellycam-build-rs")
        .header("X-GitHub-Api-Version", "2022-11-28")
        .call()
        .map_err(|e| format!("HTTP request failed: {e}"))?;

    let body = response
        .into_body()
        .read_to_string()
        .map_err(|e| format!("Failed to read response: {e}"))?;

    // Extract "tag_name":"build.N" from the JSON response.
    // The JSON looks like: {...,"tag_name":"build.2","name":...}
    // Split on the key, take the second piece (everything after the key),
    // then extract the value before the closing quote.
    for part in body.split("\"tag_name\":\"") {
        if let Some(tag) = part.split('"').next() {
            if tag.starts_with("build.") {
                return Ok(tag.to_string());
            }
        }
    }

    Err("Could not find tag_name in release JSON".into())
}
