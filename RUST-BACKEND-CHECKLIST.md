# SkellyCam Rust integration checklist

Approved with the owner's amendments on 2026-10-30. Preserve the numbered items
below and reprint the full list after completing each step. This checklist
supersedes preliminary installer and agent-led functional testing in the earlier
plan. The owner will evaluate the launched standard UI before Rust work starts.

- [x] **1.** Launch the standard SkellyCam Python backend and Electron UI, verify their connection, and obtain the owner's functional evaluation.
- [x] **2.** Build the recovered Rust/OpenPNP PyO3 extension and verify native capture in the development application.
- [x] **3.** Update the Rust camera-group implementation to the current SkellyCam contract, implement microphone recording, and verify video, audio, timestamps, and lifecycle behavior.
- [x] **4.** Add the camera-group implementation choice to the existing API and Electron UI and verify group creation through both Python/OpenCV and Rust/PyO3.
- [x] **5.** Bundle both implementations and their runtime dependencies into the SkellyCam installer, validate the installed application, and present the focused diff and results for human commit and push.

## Constraints

- Launch the UI for the owner; provide absolute-path commands if manual launch
  is needed. The owner tests the standard workflows and reports whether they work.
- All installer/frozen-server work belongs to step 5, after functional Rust work.
- Both implementations ship in the product. Developers install required tools.
- Select the implementation when creating a group; preserve the Python path.
- Keep existing OpenPNP build machinery unless a concrete blocker requires changes.
- Exclude Tauri. Keep SkellyCam independent and integrate FreeMoCap later.
- Preserve user work and human-owned Git state; verify generated-output ignores.

## Step 1 evidence

The existing clean repos/skellycam checkout is on sfn26 at 09bfbf5a. Its application
code matches cached development-streaming at 6b9ebe17; only pyproject.toml and
uv.lock differ to use existing workspace utility sources. Use this existing
standard checkout for the UI evaluation, leaving the historical Rust worktree
intact. This does not claim validation of the newer GitHub branch tip.

The owner confirmed that standalone SkellyCam runs and works correctly. Step 1
is complete. Await the owner's requested confirmation of the remaining numbered
checklist before starting step 2.

## Launch result, 2026-10-30

Standard checkout: C:/Users/jonma/code-stuff/github/freemocap/project/repos/skellycam.
Backend: http://localhost:53117. Vite: http://127.0.0.1:5173.
Electron reported window creation and successful page load. Backend logs confirm
an active WebSocket handler and successful camera-detection requests from the UI,
with three cameras detected. The owner subsequently confirmed functional
validation, completing step 1. The owner confirmed continuation; Rust build and application capture are now verified.

Launch fixes in the standard checkout (unstaged): initialize SkellyLogs in the
standalone entry point; restore the connection-slice export module; reconcile
the frontend lockfile with declared TypeScript and Rollup dependencies. Added a
narrow source-ignore exception and /.test-artifacts/ for launch logs.

Backend is launched with PYTHONIOENCODING=utf-8 to support redirected Unicode
logs. Electron/esbuild package installers were run to install their binaries.
Diagnostic logs: repos/skellycam/.test-artifacts/ui-launch/.

To relaunch manually, run these in separate PowerShell terminals:

    Set-Location 'C:/Users/jonma/code-stuff/github/freemocap/project/repos/skellycam'
    $env:PYTHONIOENCODING = 'utf-8'
    .\.venv\Scripts\python.exe -m skellycam

    Set-Location 'C:/Users/jonma/code-stuff/github/freemocap/project/repos/skellycam/skellycam-ui'
    npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort

Do not run duplicate servers while the existing launch is active. The backend
was started separately from Electron and may remain running when the UI closes.

## Step 2 evidence

- Rust 1.98.1; Python 3.12; locked Cargo dependencies; OpenPNP native artifact build.23.
- cargo build --release --locked succeeded, with MSVC LNK4098 runtime-library warning.
- maturin develop --release --locked installed the PyO3 extension into the worktree .venv.
- Import and native enumeration succeeded, finding three USB cameras.
- Single-camera bridge smoke test delivered 89 frames in 3 seconds (29.6 fps), then closed normally.
- Real application detection/group-creation routes created RustCameraGroupManager
  with three cameras; the three-second frame-polling check delivered 87 multiframe
  payloads, closed all camera groups, and exited 0. Logs are under .test-artifacts/.
- The diagnostic has no WebSocket log consumer, so it cancels the unused log
  queue's exit join after capture; normal group shutdown completed before that.
- Found for step 3: startup's stabilization loop has a placeholder shutdown check
  that always returns false, allowing a no-frame camera to hang timeout cleanup.
- Standard Python UI camera groups were closed through its API (not recording)
  to release devices for the native checks; UI/server were left running.

All five steps are complete. Commit, push, and downstream integration remain human-owned.

## Step 3 evidence

- Overlaid the validated local development-streaming application source from
  the sfn26 checkout (09bfbf5a plus the approved launcher logging fix) into this
  recovery worktree as ordinary unstaged source edits. The original checkout
  and Git history remain unchanged. Overlay manifest: .test-artifacts/python-baseline-overlay.json.
- Implemented native PortAudio microphone capture, bounded callback handoff,
  Rust WAV writing, error reporting, and timestamp sidecars using the existing
  microphone device-index contract. Python supplies the PortAudio library path;
  no Python audio callback runs for the Rust backend.
- Aligned Rust audio/video clocks to Python perf_counter_ns at module import.
- Separated the Rust adapter from the standard Python manager; implemented
  group-scoped close/record/pause, current polling/state/frame contracts, and
  current recording finalization. Native CSV evidence is retained separately.
- Fixed cancellable bounded startup/exposure calibration and rotated output
  dimensions; incomplete native recordings now raise errors through PyO3.
- Final hardware diagnostic: 3 cameras, one rotated 90 degrees, live frame and
  state checks, an exposure update, 120 frames per video, 179200 audio samples,
  current recording metadata/timing readers, clean close, exit 0.
  Log: .test-artifacts/native-rotation-recording.log.
- Python contract/reference tests: 4 passed. Rust unit suite: 21 passed;
  5 hardware tests excluded from the ordinary parallel run, then explicitly
  run serially: all 5 passed. Corrected pre-existing tests that ignored their
  startup timeout or assumed distinct ticks for immediate clock reads.
- MSVC LNK4098 warning remains for installer-stage dependency review.

## Step 4 evidence

- Added a stable application manager that selects Python/OpenCV (default) or
  Rust/OpenPNP when creating a camera group. Active groups must be closed before
  choosing another engine; the WebSocket retains the stable manager reference.
- Added the API request backend field and Electron camera-backend dropdown.
  Selection is disabled while connecting, streaming, or recording. Server state
  carries the active backend so a reconnected UI reports it accurately.
- Overlaid the validated current Electron UI into this recovery worktree.
  Manifest: .test-artifacts/ui-baseline-overlay.json. Source checkout unchanged.
- TypeScript check passed. Actual Electron UI launched from this worktree at
  http://127.0.0.1:5174, with backend on localhost:53117. Screenshots and evidence
  under .test-artifacts/python-ui-capture.png and rust-ui-capture.png.
- Used the UI to create one Python group and one Rust group, each with three
  visible live 1280x720 camera streams. Rust displayed approximately 30 fps;
  JavaScript error collector reported no errors.
- Rust HTTP recording endpoints returned the current response schema after a
  3-camera/microphone recording: 92 frames, mean 30.28 fps, complete output under
  .test-artifacts/http-rust-1793359075696.
- Seven Python backend-selection, adapter-contract and reference tests passed.

## Step 5 evidence

- Built and installed the unsigned Windows x64 NSIS installer. Installed app:
  `.test-artifacts/installed-app/skellycam.exe`. Installer:
  `skellycam-ui/release/2.0.0-alpha.6/skellycam_2.0.0-alpha.6_x64_installer.exe`.
- Launched with PATH limited to Windows system directories. Electron started
  the server from its own `resources/app.asar.unpacked/skellycam_server/` folder;
  no developer Python, Rust toolchain, or system FFmpeg was available on PATH.
- Through the installed Electron UI, created a Python group and a Rust group,
  each displaying three real 1280x720 streams. No renderer exceptions occurred.
- Installed Rust recording: three videos, 90 frames each, approximately 30.3 fps;
  stereo microphone WAV at 44100 Hz with 146432 samples, zero dropped chunks,
  and no stream error. Current timestamp CSVs, metadata, and statistics finalized.
  Evidence: `.test-artifacts/installed-validation.json` and screenshots named
  `installed-python-capture.png` and `installed-rust-capture.png`.
- A separate frozen-server test shut down during native recording and produced
  finalized videos, microphone audio, and timing statistics (91 video frames).
- Fixed Windows server-directory resolution, camera-enumeration DLL collection,
  frozen UTF-8 log output, native shutdown finalization, and stale native wheel
  caching. Locked offline sync now rebuilds changed Rust sources. Utility Git
  revisions are pinned to the installed, tested commits; no Git fetch was used.
- Final Python contract/citation suite: 9 passed. TypeScript and Vite production
  builds passed. Earlier Rust checks: 21 unit tests and 5 serial hardware tests.
- Local electron-builder's legacy tool archive contains unused macOS symlinks.
  For this Windows build, extracted its Windows tools into the ignored task-local
  cache while excluding the Darwin directory; no Windows security setting changed.
- Validation is Windows x64 only. Signing and macOS/Linux runs remain release/CI
  checks. Existing OpenPNP MSVC LNK4098 remains visible. The unpublished local
  build's update check reports a handled HTTP error; camera operation is unaffected.
- Cameras were released after validation; the installed UI remains open.

## Human review handoff

The focused patch `.test-artifacts/skellycam-rust-integration.patch` compares
the result with `09bfbf5a958dd152b1c991ea3c5c7e802cc32497` on `sfn26`, rather than
the recovery checkout's historical Rust commit. It includes the recovered native
crate and the integration changes, excludes Tauri and the obsolete Rust copy,
and omits unchanged baseline files. The current standard checkout already has
some step-1 launch fixes, so review overlapping changes before applying the patch.

The recovery checkout remains detached. No staging, commits, branch changes,
or pushes were performed during this implementation. The owner should integrate
the reviewed changes into SkellyCam's `sfn26` branch, then commit and push before
any FreeMoCap consumer update. A later main-branch PR is a separate Git handoff.

## Integration follow-up

The owner approved committing and integrating this work on 2026-10-30. The
reviewed changes are now in the main sfn26 checkout. Validation evidence and
the installer are being preserved under the containing workspace path
`.test-artifacts/skellycam-rust-validation-2026-10-30/` before removal of the
recovery worktree. Earlier recovery paths above are historical evidence paths.
