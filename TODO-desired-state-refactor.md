# TODO: Desired-state (PUT) endpoint refactor — skellycam write-side

## Status
The **read-side** state projection is DONE (committed): `CameraGroupState` carries
`recording_in_progress` / `paused`, `/health` returns `{alive, pid}`, and the `APP_STATE`
websocket message carries `server_pid`. skellycam-ui consumes it (a `connection` Redux slice,
websocket-only connectedness, PID display, self-heal on disconnect, Launch/Stop split from the
connection status).

This document tracks the **deferred write-side**: replacing the imperative camera / recording /
streaming endpoints with idempotent desired-state PUTs. Rationale: HTTP PUT = desired-state write
plane; the websocket `APP_STATE` snapshot = observed-state read plane (CQRS / level-triggered).
Expressing a desired state is always valid and idempotent, so the UI's controls become
"declare what you want" rather than commands gated on a mirrored state machine.

## Backend (skellycam)

### `api/http/cameras/camera_router.py` — replace imperative endpoints
- `PUT /camera/group` — body = desired `{camera_configs}`; **empty dict = close all groups**.
  Replaces `POST /group/apply` + `DELETE /group/close/all`.
- `PUT /camera/group/recording` —
  `{desired: "recording" | "idle", recording_name?, recording_directory?, mic_device_index?}`.
  Replaces `POST /group/all/record/start` + `GET /group/all/record/stop`.
- `PUT /camera/group/streaming` — `{desired: "streaming" | "paused"}`.
  Replaces `GET /group/all/pause_unpause` (a toggle — the worst idempotency offender).
- Keep `POST /camera/detect` and `GET /camera/microphone/detect` (not stateful singletons).

### `core/camera_group/camera_group.py`
- Add `async def pause(self, await_paused=True)` and `async def unpause(self, await_unpaused=True)`,
  delegating to `self.cameras.pause` / `self.cameras.unpause` (parallel to existing `pause_unpause`).

### `core/camera_group/camera_group_manager.py`
- Add `is_recording` property:
  `any(cg.cameras.orchestrator.all_cameras_recording for cg in self.camera_groups.values())`
  — used to gate recording start/stop idempotently.
- Add `async def set_all_groups_streaming(self, *, paused: bool, await_state_change=True)`.
- **Remove the dead/broken `pause_all_groups` / `unpause_all_groups`** (they call a nonexistent
  `CameraGroup.pause` / `unpause` — never worked) and the now-unused `pause_unpause_all_groups`.

### Endpoint → manager wiring (idempotent reconcilers)
- `PUT /camera/group`: empty → `close_all_camera_groups()`; else `create_or_update_camera_group(configs)`.
- `PUT .../recording`: `recording` → if not `is_recording`: `start_recording_all_groups(...)`;
  `idle` → if `is_recording`: `stop_recording_all_groups()`.
- `PUT .../streaming`: `set_all_groups_streaming(paused = desired == "paused")`
  (orchestrator pause/unpause are already idempotent).

### Tests
- `tests/test_camera_router.py` — update to the new routes / verbs / payloads.
- `tests/conftest.py` — replace the mocked `pause_all_groups` / `unpause_all_groups` /
  `pause_unpause_all_groups` with `set_all_groups_streaming` / `is_recording`.

## Frontend (skellycam-ui)
- `services/server/server-helpers/server-urls.ts` — repoint camera / recording / pause endpoints
  to the new PUT routes.
- `store/slices/cameras/cameras-thunks.ts` — `camerasConnectOrUpdate` + `closeCameras` → one
  `PUT /camera/group` (empty body closes); `pauseUnpauseCameras` → `PUT /camera/group/streaming`.
- `store/slices/recording/recording-thunks.ts` — start/stop → `PUT /camera/group/recording`.
- Delete the optimistic `.fulfilled` reducers in `cameras-slice.ts` / `recording-slice.ts`
  (`connectionStatus='connected'`, `isRecording=true`) — observed state now comes ONLY from the
  `APP_STATE` snapshot (single source of truth; the read-side reconcilers are already wired).
- Optional: a `desired` / `observed` split for snappy buttons (else rely on the ~1s snapshot cadence).

## Why this was deferred
The read-side already fixed the daily pains (connectedness contradiction, stale-state-after-restart,
PID display). This write-side adds robustness — idempotent retries / double-clicks, kills the
pause-toggle ambiguity, removes optimistic writes, and fixes the dead pause methods. It is a
breaking HTTP API change landed atomically across backend + UI + tests, so it deserves its own pass.
