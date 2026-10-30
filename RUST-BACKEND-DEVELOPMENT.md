# Developing the two camera backends

The Electron application and Python API remain the application shell. Camera
groups use Python/OpenCV by default; choose Rust/OpenPNP in the Camera backend
control before connecting cameras. Close an existing group before changing its
implementation. Both implementations are installed together.

## Run this SkellyCam checkout

Validated development tools: Python 3.12, Rust 1.98.1, MSVC, Node, and npm.
The existing OpenPNP build script remains in use; this machine used its cached
build.23 artifact. Tauri is outside this integration.

1. Synchronize from the repository root:

   ```powershell
   Set-Location 'C:/Users/jonma/code-stuff/github/freemocap/project/repos/skellycam'
   uv sync --locked
   ```

   The native package tracks Rust source changes in its uv cache keys, so this
   command also rebuilds changed native code. [@uvCacheKeys]

2. Run the backend in that terminal:

   ```powershell
   $env:PYTHONIOENCODING = 'utf-8'
   ./.venv/Scripts/python.exe -m skellycam
   ```

3. Run Electron in a second terminal:

   ```powershell
   Set-Location 'C:/Users/jonma/code-stuff/github/freemocap/project/repos/skellycam/skellycam-ui'
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
