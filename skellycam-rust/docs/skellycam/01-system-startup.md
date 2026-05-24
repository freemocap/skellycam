# Component #1: System Startup & Process Model

Status: **AUDITED — updated for actual Rust implementation (2026-05-23)**

Files analyzed:
- `skellycam/__init__.py` — package init, beartype, freeze_support, logging
- `skellycam/__main__.py` — entry_point(), main(), uvicorn server lifecycle
- `skellycam/app.py` — create_fastapi_app(), lifespan, route registration
- `skellycam/core/ipc/process_management/worker_registry.py` — WorkerRegistry
- `skellycam/core/ipc/process_management/managed_worker.py` — ManagedWorker ABC, ManagedProcess, ManagedThread

---

## What It Does

Boots the SkellyCam server, manages the lifecycle of worker processes/threads, and ensures clean shutdown.

### Startup Sequence (exact order)

1. `entry_point()` → `multiprocessing.freeze_support()` (Windows) → `asyncio.run(main())`
2. `main()`:
   - Suppress benign `ConnectionResetError` on Windows ProactorEventLoop
   - Create `global_kill_flag = multiprocessing.Value("b", False)` — shared c_bool
   - Create `WorkerRegistry(global_kill_flag, WorkerMode.PROCESS)`
   - Start heartbeat thread (writes `time.perf_counter()` to shared `Value("d")` every 1s)
   - Start child monitor thread (polls workers, triggers parent shutdown if any die unexpectedly)
   - Install SIGTERM/SIGINT handlers on parent process → set `global_kill_flag`
   - Kill any existing process on the server port
   - Build FastAPI app via `create_fastapi_app(global_kill_flag, worker_registry)`
   - Start uvicorn server
   - On shutdown (finally): set kill flag, stop server, call `worker_registry.shutdown_all()`

### FastAPI App Factory (`create_fastapi_app`)

- Receives `global_kill_flag` and `worker_registry` as constructor args (not globals — explicit dependency injection)
- Attaches them to `app.state` for access from route handlers
- Registers routes: health, shutdown, camera routers (prefixed with `/skellycam`)
- Registers CORS middleware
- Customizes OpenAPI schema
- Lifespan: pre-compiles bytecode (Windows `spawn` workaround), creates base folder, initializes telemetry

### WorkerRegistry

Single responsibility: track all spawned workers and provide escalating shutdown.

- Maintains `_workers: list[ManagedWorker]`
- `create_worker(target, name, log_queue, kwargs)` → creates `ManagedProcess` (or `ManagedThread` if `WorkerMode.THREAD`), registers it, returns it
- `start_heartbeat()` → spawns two daemon threads:
  - **Heartbeat thread**: writes `time.perf_counter()` to shared `Value("d")` every second with lock
  - **Child monitor thread**: polls all workers every second; if any died with non-zero exit code without being intentionally terminated → sets global kill flag + sends SIGTERM to parent
- `shutdown_all()` — 3-phase escalating shutdown:
  1. Set kill flag, wait up to `kill_flag_timeout` (3s)
  2. `terminate()` (SIGTERM) stragglers, wait 3s
  3. `kill()` (SIGKILL) remaining, wait 2s
  4. Raise if zombies remain
- Also has `atexit` safety net if shutdown wasn't called

### ManagedWorker / ManagedProcess / ManagedThread

Abstract base class with concrete process and thread implementations.

**ManagedProcess** wraps `multiprocessing.Process`:
- Entry point wrapper installs SIGTERM/SIGINT handlers in child
- Configures logging in child (if `log_queue` provided)
- `atexit` safety net: if child exits uncleanly without kill flag → sets kill flag
- On exception: logs, sets kill flag, re-raises
- `finally`: cancels log queue join thread (prevents child hanging on pipe buffer flush)

**ManagedThread** wraps `threading.Thread`:
- Shares parent's address space and logging config
- Cannot be force-killed — `terminate()` and `kill()` just set the global kill flag
- Worker function must cooperatively check `ipc.should_continue`

### Shutdown Flow

```
HTTP POST /shutdown → set app.state.global_kill_flag = True
                      ↓
SIGTERM/SIGINT handler → global_kill_flag = True
                      ↓
main() finally block → worker_registry.shutdown_all()
                      ↓
              1. kill_flag → wait 3s
              2. terminate() → wait 3s
              3. kill() → wait 2s
              4. raise if zombies
```

---

## Python-Specific Problems This Architecture Solves

| Problem | Python Solution | Why It Exists |
|---------|----------------|---------------|
| GIL prevents true parallelism | `multiprocessing.Process` — each camera gets its own Python interpreter | CPython threads serialize on the GIL for CPU-bound work |
| Processes have separate address spaces | `multiprocessing.Value("b")` for kill flag, `SharedMemory` for frames, `multiprocessing.Queue` for messages | Processes can't share heap objects — everything crossing the boundary must be serialized or in shared memory |
| Windows `spawn` re-imports everything | `freeze_support()` + `if __name__ == "__main__"` guard + staggered spawn (250ms) | Windows has no `fork()`, so each child re-imports the entire module tree, causing file-locking races |
| Parent crash leaves orphaned children | Heartbeat timestamp in shared memory, children poll `check_main_process_heartbeat()` | OS processes are independent — parent death doesn't automatically kill children |
| Child crash must not go unnoticed | Child monitor thread polls all workers, triggers parent shutdown on unexpected death | Processes die silently — the parent must explicitly poll |
| Processes can hang on exit | 3-phase escalating shutdown (kill flag → SIGTERM → SIGKILL) + `atexit` safety net | Python process exit is cooperative; blocking I/O or deadlocks can prevent clean exit |
| Log queue blocks child exit | `log_queue.cancel_join_thread()` in child's `finally` block | `multiprocessing.Queue` uses a feeder thread that blocks on pipe buffer flush |
| Graceful shutdown requires coordination | `global_kill_flag` shared across all processes, polled in every loop iteration | No built-in mechanism to broadcast "shut down" across independent processes |
| Bytecode compilation races on Windows spawn | `ensure_bytecode_compiled()` in app lifespan | Multiple processes importing the same .py files simultaneously cause PermissionError |
| Type safety across process boundaries | `beartype` decorates every function at import time | Python type hints are not enforced at runtime by default |

---

## What Was Actually Built

| Python Concept | Rust Implementation | Notes |
|---------------|-------------------|-------|
| `multiprocessing.Process` | `std::thread::spawn` for camera/gatherer/dispatcher threads; `tokio` runtime for HTTP/WebSocket | Two concurrency models coexist: OS threads for the camera pipeline, async for the server |
| `multiprocessing.Value("b")` | `Arc<AtomicBool>` for `paused`, `recording_active`, `gatherer_alive`, `shutdown_flag` | Same pattern — atomic flags shared across threads |
| Heartbeat thread | Not implemented | Threads share the process address space — no orphan detection needed |
| Child monitor thread | Not implemented | `JoinHandle` collected in `CameraGroup` and `CameraGroupManager`; thread panics are caught at `join()` time |
| `WorkerRegistry` with escalating shutdown | `CameraGroupManager::close_all_groups()` — iterates groups, calls `shutdown()` on each | No 3-phase escalation; `Camera::shutdown()` sends command + joins thread |
| `freeze_support()` + staggered spawn | Not needed | Rust threads don't re-import modules |
| `atexit` safety net | `Drop` impl on `CameraGroupManager` — calls `close_all_groups()` if any groups remain | Compiler-guaranteed cleanup |
| SIGTERM/SIGINT handlers | `tokio::signal::ctrl_c()` + `shutdown_flag` in `with_graceful_shutdown()` | Axum-native graceful shutdown; the `shutdown_flag` is also checked by `GET /shutdown` |
| FastAPI app lifespan | Axum `Router` with `with_state()`, startup code in `main()` before `axum::serve`, shutdown in `Drop` + `close_all_groups()` | No lifespan context manager; init is explicit in `run_server()` |
| `multiprocessing.Queue` for logs | `tracing` with two layers: `SkellyFormat` (stderr) + `LogRelayLayer` (broadcast to WebSocket) | Log relay bridges `tokio::sync::broadcast` → `tokio::sync::mpsc` in the WebSocket handler |

### Startup Sequence (actual Rust implementation)

```
run_server() in main.rs:
  1. Create Arc<AppState> with:
     - camera_manager: Mutex<CameraGroupManager>
     - shutdown_flag: Arc<AtomicBool>
     - active_group_id: Mutex<Option<String>>
  2. Build Axum Router via build_router(state)
  3. Bind TCP listener on 0.0.0.0:53117
  4. axum::serve with graceful_shutdown:
     - Waits for either Ctrl+C OR shutdown_flag == true
  5. On exit: camera_manager.blocking_lock().close_all_groups()
```

No heartbeat thread, no child monitor, no worker registry. The process model is dramatically simpler because threads share the process fate.

---

## Functionality Preserved

1. **Single global kill switch** — `shutdown_flag: Arc<AtomicBool>` in `AppState`, checked by WebSocket loop and exposed via `GET /shutdown`
2. **Clean exit** — All camera handles, ffmpeg subprocesses, and threads released via `Drop` impls and explicit `shutdown()` calls
3. **Windows compatibility** — Works on Windows; no `fork()`, no Unix signals for threads
4. **Graceful Ctrl+C handling** — `tokio::signal::ctrl_c()` triggers clean shutdown
5. **Camera group cleanup on server exit** — `CameraGroupManager::close_all_groups()` called in `run_server()` after server stops

## Functionality Not Preserved (by design)

- **Escalating shutdown** — Not needed; thread `JoinHandle` + channel drop is sufficient. A panicked thread is caught at `join()` and the process can abort.
- **Child crash → parent aware** — Thread panics propagate via `JoinHandle::join()`. Camera errors are communicated via `CameraEvent::Error` channel.
- **Idempotent shutdown** — `CameraGroup::shutdown()` checks state and returns error if already `Stopped`.
- **Startup port check** — Not implemented; `TcpListener::bind` will error if port is in use, and the caller can retry.
