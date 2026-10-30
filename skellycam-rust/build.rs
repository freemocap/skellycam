//! Build script: download pre-built openpnp-capture + turbojpeg static libs
//! from the latest GitHub Release on the `jonmatthis/openpnp-capture` fork.
//!
//! Every build queries the GitHub API for the latest release tag. If a newer
//! tag is found, the new artifact is downloaded. Archives already cached in
//! `target/build-artifacts/{tag}/` skip the download (same version, not stale).

use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::Command;
use tracing::{debug, error, info, info_span, warn};

const OPENPNP_REPO: &str = "jonmatthis/openpnp-capture";

fn main() {
    // ── Initialize tracing subscriber ─────────────────────────────────────
    // Defaults to INFO level; override with RUST_LOG env var.
    // e.g. RUST_LOG=debug cargo build
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .with_target(false)   // omit module path — keep output clean
        .with_writer(std::io::stderr)
        .init();

    let target = env::var("TARGET").unwrap_or_else(|_| String::from("unknown"));
    info!(
        %target,
        profile = env::var("PROFILE").as_deref().unwrap_or("unknown"),
        out_dir = %env::var("OUT_DIR").as_deref().unwrap_or("unknown"),
        "Skellycam build script starting"
    );

    // ── Resolve platform artifact ─────────────────────────────────────────
    let (archive_name, archive_ext) = match target_triple_to_artifact(&target) {
        Some(v) => {
            info!(
                %target,
                archive_name = %v.0,
                archive_ext = %v.1,
                "Target triple mapped to artifact"
            );
            v
        }
        None => {
            error!("");
            error!("╔══════════════════════════════════════════════════════════════╗");
            error!("║  openpnp-capture pre-built libraries are not yet available  ║");
            error!("║  for target: {target:<46}║", target = target);
            error!("║                                                              ║");
            error!("║  Currently supported target triples:                         ║");
            error!("║    Windows:                                                  ║");
            error!("║      x86_64-pc-windows-msvc                                  ║");
            error!("║      aarch64-pc-windows-msvc                                 ║");
            error!("║    macOS:                                                    ║");
            error!("║      x86_64-apple-darwin     (Intel)                         ║");
            error!("║      aarch64-apple-darwin    (Apple Silicon)                 ║");
            error!("║    Linux:                                                    ║");
            error!("║      x86_64-unknown-linux-gnu  (Intel/AMD 64-bit)            ║");
            error!("║      aarch64-unknown-linux-gnu (ARM64)                       ║");
            error!("║                                                              ║");
            error!(
                "║  https://github.com/{repo}/releases                  ║",
                repo = OPENPNP_REPO
            );
            error!("╚══════════════════════════════════════════════════════════════╝");
            error!("");
            std::process::exit(1);
        }
    };

    // ── Resolve latest release tag ────────────────────────────────────────

    // When SKIP_OPENPNP_DOWNLOAD is set (e.g. GitHub API is rate-limited
    // or you are offline), use the latest cached build-artifacts tag instead
    // of hitting the GitHub API. Fails if no cached artifacts exist.
    let tag = if env::var("SKIP_OPENPNP_DOWNLOAD").is_ok() {
        let build_artifacts_base = PathBuf::from(env::var("OUT_DIR").unwrap())
            .parent().and_then(|p| p.parent()).and_then(|p| p.parent())
            .unwrap_or_else(|| {
                error!("Could not resolve target directory from OUT_DIR");
                std::process::exit(1);
            })
            .join("build-artifacts");

        let sentinel = build_artifacts_base.join(".latest-resolved-tag");
        match fs::read_to_string(&sentinel) {
            Ok(tag) => {
                let tag = tag.trim().to_string();
                if tag.is_empty() {
                    error!("Sentinel file exists but is empty: {}", sentinel.display());
                    std::process::exit(1);
                }
                info!(
                    tag = %tag,
                    sentinel = %sentinel.display(),
                    "SKIP_OPENPNP_DOWNLOAD set — using cached tag from sentinel"
                );
                tag
            }
            Err(e) => {
                error!("");
                error!("╔══════════════════════════════════════════════════════════════╗");
                error!("║  SKIP_OPENPNP_DOWNLOAD is set but no cached artifacts found ║");
                error!("║                                                              ║");
                error!("║  Sentinel: {sentinel:<48}║", sentinel = sentinel.display());
                error!("║  Error: {e:<50}║", e = e);
                error!("║                                                              ║");
                error!("║  Run a full build with network access first to populate the  ║");
                error!("║  cache, or unset SKIP_OPENPNP_DOWNLOAD.                      ║");
                error!("╚══════════════════════════════════════════════════════════════╝");
                error!("");
                std::process::exit(1);
            }
        }
    } else {
        let _span = info_span!("resolve_release_tag", repo = OPENPNP_REPO).entered();
        match get_latest_tag() {
            Ok(t) => {
                info!(tag = %t, "Resolved latest openpnp-capture release tag");
                t
            }
            Err(e) => {
                error!("");
                error!("╔══════════════════════════════════════════════════════════════╗");
                error!("║  FAILED to resolve latest openpnp-capture release tag       ║");
                error!("║                                                              ║");
                error!("║  The build requires network access to determine the latest   ║");
                error!("║  release from GitHub. Ensure you have internet connectivity. ║");
                error!("║                                                              ║");
                error!("║  Tip: set SKIP_OPENPNP_DOWNLOAD=1 to use cached artifacts   ║");
                error!("║  if you have previously built with network access.           ║");
                error!("║                                                              ║");
                error!(
                    "║  Releases: https://github.com/{repo}/releases  ║",
                    repo = OPENPNP_REPO
                );
                error!("║  Error: {e:<50}║", e = e);
                error!("╚══════════════════════════════════════════════════════════════╝");
                error!("");
                std::process::exit(1);
            }
        }
    };

    // ── Set up artifact paths ─────────────────────────────────────────────
    // Paths embed the tag so you can always see which build is cached:
    //   target/release/build-artifacts/{tag}/{archive_name}
    //   target/release/build-artifacts/{tag}/{target_triple}/lib/
    let artifact_dir = PathBuf::from(env::var("OUT_DIR").unwrap());
    let target_dir = artifact_dir
        .parent()  // out/
        .and_then(|p| p.parent())  // build/
        .and_then(|p| p.parent())  // target/debug|release/
        .unwrap_or_else(|| {
            error!("Could not resolve target directory from OUT_DIR: {}", artifact_dir.display());
            std::process::exit(1);
        });
    let build_artifacts_base = target_dir.join("build-artifacts");
    let build_artifacts = build_artifacts_base.join(&tag);

    // Sentinel file: forces Cargo to re-run build.rs on every invocation
    // so get_latest_tag() always queries GitHub and catches new releases.
    let sentinel = build_artifacts_base.join(".latest-resolved-tag");
    println!("cargo:rerun-if-changed={}", sentinel.display());

    debug!(
        build_artifacts = %build_artifacts.display(),
        sentinel = %sentinel.display(),
        "Artifact cache directory"
    );

    fs::create_dir_all(&build_artifacts).unwrap_or_else(|e| {
        error!(
            "Failed to create build artifacts directory '{}': {e}",
            build_artifacts.display()
        );
        std::process::exit(1);
    });

    let archive_file = build_artifacts.join(&archive_name);

    // ── Download ──────────────────────────────────────────────────────────
    if !archive_file.exists() {
        let _span = info_span!("download_artifact", archive = %archive_name).entered();
        let url = format!(
            "https://github.com/{OPENPNP_REPO}/releases/download/{tag}/{archive_name}"
        );
        info!(%url, "Downloading openpnp-capture artifact");

        let response = ureq::get(&url)
            .call()
            .unwrap_or_else(|e| {
                error!(
                    %url,
                    "Failed to download openpnp-capture — HTTP request failed: {e}"
                );
                error!(
                    "Verify the release exists: https://github.com/{OPENPNP_REPO}/releases/tag/{tag}"
                );
                std::process::exit(1);
            });

        let status = response.status();
        debug!(%status, "HTTP response status");

        // The download URL goes through GitHub's CDN (not the API), so it
        // doesn't count against the API rate limit. But it can still 404 if
        // the asset name doesn't match what's in the release.
        if status != 200 {
            let status_code = status.as_u16();
            let body_preview = response
                .into_body()
                .read_to_string()
                .unwrap_or_default();
            error!(
                %url,
                http_status = status_code,
                response_preview = %&body_preview[..body_preview.len().min(300)],
                "Download returned HTTP {status_code} — asset may not exist in this release"
            );
            error!(
                "Verify the release and its assets: https://github.com/{OPENPNP_REPO}/releases/tag/{tag}"
            );
            std::process::exit(1);
        }

        let content_length = response
            .headers()
            .get("Content-Length")
            .and_then(|v| v.to_str().ok())
            .and_then(|v| v.parse::<u64>().ok());
        if let Some(len) = content_length {
            debug!(content_length_bytes = len, "Download size");
        }

        let bytes = response.into_body().read_to_vec().unwrap_or_else(|e| {
            error!("Failed to read response body: {e}");
            std::process::exit(1);
        });

        info!(downloaded_bytes = bytes.len(), "Download complete, writing to disk");
        fs::write(&archive_file, &bytes).unwrap_or_else(|e| {
            error!(
                "Failed to write archive to '{}': {e}",
                archive_file.display()
            );
            std::process::exit(1);
        });
    } else {
        info!(
            archive = %archive_file.display(),
            size_bytes = fs::metadata(&archive_file).map(|m| m.len()).unwrap_or(0),
            "Artifact already cached, skipping download"
        );
    }

    // ── Extract ───────────────────────────────────────────────────────────
    let extract_dir = build_artifacts.join(&target);
    if !extract_dir.exists() {
        let _span = info_span!("extract_artifact", target = %target).entered();
        info!(
            archive = %archive_file.display(),
            dest = %extract_dir.display(),
            format = archive_ext,
            "Extracting artifact"
        );

        fs::create_dir_all(&extract_dir).unwrap_or_else(|e| {
            error!(
                "Failed to create extract directory '{}': {e}",
                extract_dir.display()
            );
            std::process::exit(1);
        });

        if archive_ext == "zip" {
            debug!("Using PowerShell Expand-Archive for .zip extraction");
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
                .unwrap_or_else(|e| {
                    error!("Failed to launch PowerShell for extraction: {e}");
                    std::process::exit(1);
                });
            if !status.success() {
                error!(
                    "PowerShell Expand-Archive failed with exit code: {:?}",
                    status.code()
                );
                std::process::exit(1);
            }
        } else {
            debug!("Using tar for .tar.gz extraction");
            let status = Command::new("tar")
                .args([
                    "-xzf",
                    &archive_file.display().to_string(),
                    "-C",
                    &extract_dir.display().to_string(),
                ])
                .status()
                .unwrap_or_else(|e| {
                    error!("Failed to launch tar for extraction: {e}");
                    std::process::exit(1);
                });
            if !status.success() {
                error!(
                    "tar extraction failed with exit code: {:?}",
                    status.code()
                );
                std::process::exit(1);
            }
        }

        info!("Extraction complete");
        // Log extracted contents at debug level
        if let Ok(entries) = fs::read_dir(&extract_dir) {
            for entry in entries.flatten() {
                debug!(
                    path = %entry.path().display(),
                    is_dir = entry.file_type().map(|t| t.is_dir()).unwrap_or(false),
                    "Extracted"
                );
            }
        }
    } else {
        info!(
            extract_dir = %extract_dir.display(),
            "Artifact already extracted, skipping"
        );
    }

    // ── Link ──────────────────────────────────────────────────────────────
    {
        let _span = info_span!("link_libraries", target = %target).entered();
        let lib_dir = extract_dir.join("lib");
        info!(lib_dir = %lib_dir.display(), "Linking static libraries");

        // Verify the lib directory exists and list its contents
        if lib_dir.exists() {
            if let Ok(entries) = fs::read_dir(&lib_dir) {
                for entry in entries.flatten() {
                    debug!(
                        lib_file = %entry.path().display(),
                        "Found library"
                    );
                }
            }
        } else {
            warn!(
                "Library directory '{}' does not exist — linking may fail",
                lib_dir.display()
            );
        }

        println!("cargo:rustc-link-search=native={}", lib_dir.display());
        info!(directive = "rustc-link-search", path = %lib_dir.display());

        println!("cargo:rustc-link-lib=static=openpnp-capture");
        info!(directive = "rustc-link-lib", lib = "openpnp-capture", kind = "static");

        println!("cargo:rustc-link-lib=static=turbojpeg-static");
        info!(directive = "rustc-link-lib", lib = "turbojpeg-static", kind = "static");

        // Windows system libraries required by openpnp-capture
        if target.contains("windows") {
            for sys_lib in &["ole32", "oleaut32", "strmiids"] {
                println!("cargo:rustc-link-lib={sys_lib}");
                debug!(directive = "rustc-link-lib", lib = sys_lib, kind = "system");
            }
        }
    }

    // ── Write sentinel to force re-run on next build ─────────────────────
    fs::write(&sentinel, &tag).unwrap_or_else(|e| {
        error!(
            "Failed to write sentinel file '{}': {e}",
            sentinel.display()
        );
    });
    debug!(sentinel = %sentinel.display(), tag = %tag, "Wrote sentinel");

    info!("Skellycam build script complete");
}

// ── Platform mapping ──────────────────────────────────────────────────────

fn target_triple_to_artifact(target: &str) -> Option<(String, &'static str)> {
    debug!(%target, "Resolving artifact for target triple");
    match target {
        // Windows — x86_64 and ARM64
        "x86_64-pc-windows-msvc" => {
            Some(("openpnp-capture-windows-x86_64.zip".into(), "zip"))
        }
        "aarch64-pc-windows-msvc" => {
            Some(("openpnp-capture-windows-arm64.zip".into(), "zip"))
        }
        // macOS — Intel and Apple Silicon
        "x86_64-apple-darwin" => {
            Some(("openpnp-capture-macos-x86_64.tar.gz".into(), "tar.gz"))
        }
        "aarch64-apple-darwin" => {
            Some(("openpnp-capture-macos-arm64.tar.gz".into(), "tar.gz"))
        }
        // Linux — x86_64 and ARM64 (GNU)
        "x86_64-unknown-linux-gnu" => {
            Some(("openpnp-capture-linux-x86_64.tar.gz".into(), "tar.gz"))
        }
        "aarch64-unknown-linux-gnu" => {
            Some(("openpnp-capture-linux-arm64.tar.gz".into(), "tar.gz"))
        }
        _ => {
            warn!(%target, "No pre-built artifact available for this target triple");
            None
        }
    }
}

// ── GitHub API: resolve latest release tag ────────────────────────────────

fn get_latest_tag() -> Result<String, String> {
    let url = format!(
        "https://api.github.com/repos/{OPENPNP_REPO}/releases/latest"
    );
    debug!(%url, "Querying GitHub API for latest release");

    let response = ureq::get(&url)
        .header("Accept", "application/vnd.github+json")
        .header("User-Agent", "skellycam-build-rs")
        .header("X-GitHub-Api-Version", "2022-11-28")
        .call()
        .map_err(|e| format!("HTTP request failed: {e}"))?;

    let status = response.status();

    // Extract all headers as owned values BEFORE consuming the body
    // (header get() returns a borrow into response, so we clone into String)
    let rate_limit_remaining = response
        .headers()
        .get("X-RateLimit-Remaining")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("?")
        .to_string();
    let rate_limit_limit = response
        .headers()
        .get("X-RateLimit-Limit")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("?")
        .to_string();
    let rate_limit_reset = response
        .headers()
        .get("X-RateLimit-Reset")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.parse::<i64>().ok());

    let rate_pct = rate_limit_limit
        .parse::<u32>()
        .ok()
        .zip(rate_limit_remaining.parse::<u32>().ok())
        .map(|(limit, remaining)| {
            let used = limit.saturating_sub(remaining);
            (used * 100) / limit.max(1)
        })
        .unwrap_or(0);

    // Prominent rate limit banner — always visible at INFO level
    info!("");
    info!("┌──────────────────────────────────────────────────────────────────┐");
    info!(
        "│  GitHub API rate limit                                         │"
    );
    info!(
        "│    {used} requests used, {remaining} remaining of {limit} ({pct}%)                   │",
        used = rate_limit_limit.parse::<u32>().unwrap_or(0)
            .saturating_sub(rate_limit_remaining.parse::<u32>().unwrap_or(0)),
        remaining = rate_limit_remaining,
        limit = rate_limit_limit,
        pct = rate_pct,
    );
    info!("│  Unauthenticated: 60 req/hour per IP. Authenticated: 5,000.     │");
    info!("│  Set SKIP_OPENPNP_DOWNLOAD=1 to build without hitting the API.   │");
    info!("└──────────────────────────────────────────────────────────────────┘");
    info!("");

    let body = response
        .into_body()
        .read_to_string()
        .map_err(|e| format!("Failed to read response: {e}"))?;

    debug!(response_len = body.len(), "GitHub API response body received");

    // ── Check for rate limiting (HTTP 403 or 429) ──────────────────────
    if status == 403 || status == 429 {
        let github_message = extract_json_string(&body, "message");
        let is_rate_limit = github_message
            .as_deref()
            .map(|m| m.contains("rate limit"))
            .unwrap_or(false);

        if is_rate_limit {
            let reset_info = match rate_limit_reset {
                Some(epoch) => {
                    let now = std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .map(|d| d.as_secs() as i64)
                        .unwrap_or(0);
                    let secs = (epoch - now).max(0);
                    format!(
                        "Resets in {} min {} sec (Unix epoch {}).",
                        secs / 60,
                        secs % 60,
                        epoch
                    )
                }
                None => "Check X-RateLimit-Reset header for reset time.".to_string(),
            };

            return Err(format!(
                "GitHub API rate limit exceeded (unauthenticated requests are limited to \
                 {rate_limit_limit}/hour per IP address). {reset_info} \
                 GitHub says: \"{msg}\". \
                 To build now without hitting the API, set SKIP_OPENPNP_DOWNLOAD=1 \
                 to use cached artifacts from the last successful download.",
                rate_limit_limit = rate_limit_limit,
                reset_info = reset_info,
                msg = github_message.unwrap_or_default(),
            ));
        }

        // Some other 403/429 (e.g. secondary rate limit, abuse detection)
        return Err(format!(
            "GitHub API returned HTTP {status}. Response: {}",
            &body[..body.len().min(500)]
        ));
    }

    // ── Check for other unexpected status codes ────────────────────────
    if status != 200 {
        return Err(format!(
            "GitHub API returned unexpected HTTP status {status}. Response: {}",
            &body[..body.len().min(500)]
        ));
    }

    // Extract "tag_name":"build.N" from the JSON response.
    // The JSON looks like: {...,"tag_name":"build.7","name":...}
    for part in body.split("\"tag_name\":\"") {
        if let Some(tag) = part.split('"').next() {
            if tag.starts_with("build.") {
                debug!(%tag, "Parsed tag_name from GitHub release JSON");
                return Ok(tag.to_string());
            }
        }
    }

    error!(
        response_preview = %&body[..body.len().min(500)],
        "Could not find tag_name in GitHub release JSON response"
    );
    Err("Could not find tag_name in release JSON".into())
}

/// Extract a string value for a JSON key — minimal parser so we can read
/// GitHub error messages without pulling in serde.
fn extract_json_string(json: &str, key: &str) -> Option<String> {
    let search = format!("\"{}\":\"", key);
    for part in json.split(&search).skip(1) {
        if let Some(value) = part.split('"').next() {
            return Some(value.to_string());
        }
    }
    None
}
