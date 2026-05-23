# Component #1: System Startup & Process Model

Status: **ANALYZED — stable reference artifact**

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

## What Changes in Rust

| Python Concept | Rust Equivalent | Key Difference |
|---------------|----------------|---------------|
| `multiprocessing.Process` | `std::thread::spawn` | Threads share address space — no IPC needed for basic coordination |
| `multiprocessing.Value("b")` | `Arc<AtomicBool>` | Same semantics (shared flag, atomic access) but no special setup |
| `multiprocessing.Value("d")` heartbeat | Not needed | Threads live/die with the process — no orphan problem |
| `WorkerRegistry` with escalating shutdown | `Vec<JoinHandle<T>>` + channel drop | Dropping a channel sender unblocks receivers; join handles collected in a Vec |
| Child monitor thread | Not needed | If a thread panics and it's not handled, the process can decide to abort; `JoinHandle` naturally reports exit status |
| Heartbeat thread | Not needed | Threads share fate with the process — no parent/child process split |
| `freeze_support()` + staggered spawn | Not needed | Rust has no equivalent of `spawn` re-import — `thread::spawn` just runs the closure |
| `atexit` safety net | `Drop` impls | Deterministic, no registration needed, compiler guarantees they run |
| SIGTERM/SIGINT handlers in children | Not needed for threads; signal handling stays in main | Only the process needs signal handlers; threads don't receive signals |
| `ensure_bytecode_compiled()` | Not needed | Rust is compiled ahead-of-time; no .pyc equivalent |
| `beartype` runtime checking | Compile-time type system | Types are checked at build time, zero runtime cost |
| `log_queue.cancel_join_thread()` | Not needed | Rust logging can use channels or lock-free approaches that don't block on drop |
| FastAPI app lifespan | Axum `Router` with explicit startup/shutdown in `main()` | Axum doesn't have a lifespan context manager; startup/shutdown are just code before/after `axum::serve` |
| `multiprocessing.Queue` for logs | `tracing` crate with subscriber | Structured, async-aware logging built into the ecosystem |

---

## Functionality That Must Be Preserved

1. **Single global kill switch** — Setting one flag must cause all camera threads to stop gracefully
2. **Escalating shutdown** — If a thread doesn't stop within a timeout, force-stop it
3. **Child crash → parent aware** — If a camera thread panics, the server must know and react (either shutdown or restart that group)
4. **Idempotent shutdown** — Calling shutdown multiple times must be safe
5. **Clean exit** — All resources (camera handles, ffmpeg subprocesses, temp files) must be released on shutdown
6. **Windows compatibility** — Must work on Windows (no `fork()`, no Unix signals for threads)
7. **Graceful SIGTERM/SIGINT handling** — Ctrl+C must trigger clean shutdown
8. **Startup port check** — Kill stale process on the server port before binding
