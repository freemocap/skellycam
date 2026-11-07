# Developing the two camera backends

The Electron application and Python API remain the application shell. Camera
groups use Python/OpenCV by default; choose Rust/OpenPNP in the Camera backend
control before connecting cameras. Close an existing group before changing its
implementation. Both implementations are installed together.

## Native build prerequisites

SkellyCam and FreeMoCap Core environments build `skellycam-rust` from source
during `uv sync`, even when the Python/OpenCV backend is selected.

- Rust 1.88 or newer. The crate uses the 2024 edition, released in Rust 1.85
  [@rustEdition2024], and the locked `image` 0.25.10 dependency declares
  `rust-version = "1.88.0"` [@image02510RustVersion]. rustup does not refresh an
  installed `stable` toolchain; run `rustup update stable`. Cargo older than 1.85
  stops with "feature `edition2024` is required".
- Windows: Visual Studio 2022 Build Tools 17.14 with the "Desktop development
  with C++" workload. The OpenPNP build.23 Windows objects were compiled by MSVC
  build 35226 (Visual Studio 2022 17.14), and the final link must use build tools
  at least as recent as those that built any input. [@msvcBinaryCompatibility]
  Visual Studio 2019 (MSVC 14.29) lacks the `_Thrd_sleep_for` STL symbol that the
  library references, so its link fails with LNK2019 and LNK1120. Visual Studio
  2019 may remain installed; rustc selected the newer Build Tools.

On 2026-11-07, Windows x64 with Rust 1.99.1 and Visual Studio 2022 Build Tools
17.14 (linker 14.44.35229) completed Core's `uv sync` and imported
`_skellycam_rust`. No physical cameras were attached, so this validates
installation and native module loading, not capture or recording.

## Run this SkellyCam checkout

Validated development tools: Python 3.12, Rust 1.98.1, MSVC, Node, and npm.
The existing OpenPNP build script remains in use; this machine used its cached
build.23 artifact. Tauri is outside this integration.

1. Synchronize from the repository root:

   ```powershell
   uv sync --locked
   ```

   The native package tracks Rust source changes in its uv cache keys, so this
   command also rebuilds changed native code. [@uvCacheKeys]

2. Run the backend in that terminal:

   ```powershell
   $env:PYTHONIOENCODING = 'utf-8'
   ./.venv/Scripts/python.exe -m skellycam
   ```

3. Run Electron in a second terminal, starting from the repository root:

   ```powershell
   Set-Location skellycam-ui
   npm.cmd ci
   npm.cmd run dev -- --host 127.0.0.1 --port 5174 --strictPort
   ```

The backend serves localhost:53117. Avoid launching a second backend while an
installed application owns that port.

## Installer contents

PyInstaller collects the PyO3 extension, camera-discovery DLLs, PortAudio, and
the imageio-ffmpeg executable. The native recorder receives the explicit bundled
encoder path. [@imageioFfmpegExecutable] [@ffmpegSidecarCommand]
Electron packages that complete server directory outside ASAR. Users need no
Python, Rust toolchain, or separate FFmpeg installation.

The installer workflow builds Rust before freezing Python. On Windows, the
server path is `skellycam_server/skellycam_server.exe`. Native recording is
finalized before normal application shutdown signals process termination.

## Review and integration

The validated native implementation was integrated into the sfn26 checkout
without merging unrelated history from the historical Rust branch.

Review the focused integration patch under
the workspace `.test-artifacts/skellycam-rust-validation-2026-10-30/skellycam-rust-integration.patch`, compared with validated
SkellyCam revision `09bfbf5a958dd152b1c991ea3c5c7e802cc32497` (`sfn26`). It excludes
Tauri and the obsolete Rust copy. The owner owns branch changes, commits, and
pushes. FreeMoCap dependency changes are a separate integration stage.

Local validation covers Windows x64. Other operating systems and release
signing remain CI/release validation. The existing OpenPNP static library emits
MSVC LNK4098; capture and recording pass, but the warning is not suppressed.

## macOS ARM64 build validation

On 2026-11-02, the build.23 macOS ARM64 artifact contained `libturbojpeg.a`.
The build script now links `turbojpeg` on macOS, retaining `turbojpeg-static`
on other targets. Core integration validation with Python 3.12.14 completed
`uv sync --frozen --group dev` and imported `_skellycam_rust` successfully.
No physical cameras were attached, so this validates installation and native
module loading, not capture or recording.
