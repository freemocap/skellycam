# Camera Module Refactor — Handoff for camera_group Agent

This document describes the refactor just completed in the camera module, to
guide the refactor of the sibling `camera_group/` module. Focus is on the
current state and the design philosophy, not a chronological changelog.

## Core Philosophical Shift

**Old model:** The `Camera<S>` was a generic type-state machine. Each lifecycle
state was a distinct Rust type (`Disconnected`, `Enumerated`, `Configuring`,
`Streaming`, `ShuttingDown`, `Faulted`). Transitions consumed `self` and
returned a new `Camera<NewState>`. The thread handle was a field inside some
of those states, meaning state transitions could drop/orphan threads.

**New model:** The camera thread IS the camera. The `Camera` struct is a plain
handle (no generics, no type-state) that communicates with a persistent OS
thread via channels. The thread owns the COM context (which is thread-affine)
and persists for the device's entire lifetime.

**Why:** openpnp-capture's `CapContext` is COM thread-affine — it must be
created, used, and destroyed on the same OS thread. The type-state pattern
forced the thread handle to move between types and get dropped on transitions,
which orphaned threads and broke COM affinity. A plain handle over channels
is both simpler and correct.

## What the Camera Module Looks Like Now

### File structure

```
src/camera/
  camera_README.md    ← single source of truth for architecture docs
  CLAUDE.md           ← thin instruction set only (see note at bottom)
  mod.rs              ← module declarations + re-exports
  camera.rs           ← THE public interface: Camera handle struct
  camera_thread.rs    ← thread spawn + internal state machine + capture loop
  frame_loop.rs       ← FrameStateMachine for hot-loop timestamps (internal)
  detect.rs           ← hardware discovery (detect_cameras())
  ffi.rs              ← raw C bindings to openpnp-capture
  types.rs            ← shared data types (config, identity, frame packets, channels)
```

### Public API surface (what camera_group should use)

```rust
// Detection
pub fn detect_cameras() -> anyhow::Result<Vec<CameraIdentity>>

// Camera handle — the only type you need
pub struct Camera { /* fields private */ }

impl Camera {
    pub fn start(identity: CameraIdentity, config: CameraConfig, barrier: Arc<BreakableBarrier>)
        -> anyhow::Result<Self>
    pub fn configure(&self, config: CameraConfig)   // &self, not &mut self
    pub fn try_recv_frame(&self) -> Result<FramePacket, TryRecvError>
    pub fn try_recv_event(&self) -> Result<CameraEvent, TryRecvError>
    pub fn shutdown(self) -> Result<(), String>     // consumes self, joins thread
    pub fn identity(&self) -> &CameraIdentity
    pub fn config(&self) -> &CameraConfig
    pub fn frame_receiver(&self) -> &mpsc::Receiver<FramePacket>  // for select!
}
```

### What NO LONGER EXISTS

- `Camera<S>` generic — now `Camera` (no type parameter)
- `Disconnected`, `Enumerated`, `Configuring`, `Streaming`, `ShuttingDown`, `Faulted` — all type-state markers are gone
- `LifecycleTransition` — audit log removed
- `StateDiagram` trait — Mermaid diagram lives in camera_README.md
- `enumerate_directshow_cameras()` — renamed to `detect_cameras()`
- `spawn_camera_thread()` — renamed to `spawn()` in the `camera_thread` module
- `forget()`, `reconfigure()`, `fault()`, `retry()`, `abandon()` — these type-state methods are gone
- `state_machine.rs`, `enumerate.rs`, `thread.rs` — deleted

### Renames that affect camera_group imports

| Old import | New import |
|---|---|
| `crate::camera::enumerate_directshow_cameras` | `crate::camera::detect_cameras` |
| `crate::camera::Configuring` | Does not exist — use `Camera` handle |
| `crate::camera::Streaming` | Does not exist — use `Camera` handle |
| `crate::camera::StateDiagram` | Does not exist — diagram in README |
| `crate::camera::Camera::<Disconnected>::new()` | `Camera::start(identity, config, barrier)` |
| `crate::camera::LifecycleTransition` | Does not exist |
| `crate::camera::spawn_camera_thread` | `crate::camera::spawn` (internal, prefer `Camera::start`) |

### What stays the same

- `CameraConfig`, `CameraIdentity`, `CameraFormatInfo` — unchanged
- `FramePacket`, `FrameData`, `FrameLifecycleTimestamps`, `MultiFramePayload` — unchanged
- `CameraCommand` — `Reconfigure` variant renamed to `Configure { config }`
- `CameraEvent` — unchanged
- `CameraHandle` — still in types.rs, but may be replaceable by `Camera` now
- `FrameState`, `FrameStateMachine` — moved to `frame_loop.rs`, logic unchanged
- `BreakableBarrier` — unchanged
- `ffi.rs` — unchanged

### Internal thread state machine (for context, not public)

The thread runs a simple runtime enum (no type-state):

```
Configuring → Streaming → ShuttingDown
     ↓            ↓            ↓
   Faulted ◄──────┴────────────┘
```

Any state can transition to `Faulted` on error. `Streaming` can transition back
to `Configuring` when `configure()` is called (bidirectional: the thread applies
new settings then returns to `Streaming` on success, or to `Faulted` on failure).
`Faulted` can retry back to `Configuring`. See `camera_README.md` for the full
Mermaid diagram with all transition labels.

## Design Conventions to Carry Forward

### 1. Thread owns the camera resource

The pattern is: a persistent OS thread owns the thread-affine camera resource, and a
handle struct communicates with it via channels. `camera_group` should follow
the same pattern if it has any thread-affine resources.

### 2. Enum state machines over type-state

Type-state is elegant when state transitions are infrequent and the compiler
should enforce valid usage. But when a thread must persist across state
changes, type-state forces you to move the thread handle between types, which
breaks the ownership model. Use plain runtime enums inside persistent threads.

### 3. Public API should be obvious

The `Camera` handle has 7 public methods. No generic parameters. No trait
bounds. No consuming-self transitions (except `shutdown`, which genuinely
ends the camera's life). Someone should be able to read `camera.rs` and
understand the API in 30 seconds.

### 4. File-per-concept, named for what it DOES

- `detect.rs` — detects cameras (not "enumerate")
- `camera_thread.rs` — the thread the camera runs on (not just "thread")
- `frame_loop.rs` — the frame capture loop (not "frame_state")
- `camera.rs` — the camera itself

Each file name answers "what does this do?" in plain English.

### 5. README as single source of truth

Every module should have a README that is the authoritative documentation for
architecture, design decisions, and how to use the code. CLAUDE.md should only
contain thin working instructions and a pointer to the README. After any change,
check if the README needs updating.

### 6. Configure is a single operation

Whether it's the first configuration or a mid-stream change, it's the same
`configure(config)` method. No separate "reconfigure" path. The distinction
between first-config and re-config is an implementation detail of the thread,
not part of the API.

### 7. `&self` for channel-based operations

`configure(&self)` takes a shared reference because sending a message through
an `mpsc::Sender` only requires `&self`. This makes the API more ergonomic —
you can call `configure()` from any context that holds a `&Camera`, without
needing `&mut Camera` or consuming ownership.

## Notes on the CLAUDE.md Convention

The camera module's CLAUDE.md was stripped to ~25 lines:

- States that camera_README.md is the authoritative documentation
- Never write architecture info into CLAUDE.md — always update the README
- After any change to any file, check if the README needs updating
- Only contains build/test commands and scope instructions

The camera_group module should follow this same convention.

## What camera_group Needs to Fix

These are the known compilation errors from the camera_group side (from the
last `cargo check`):

1. `src/camera_group/state_machine.rs:29` — `use crate::camera::Configuring`
   → Does not exist. The type-state pattern is gone. Use `Camera` handle.

2. `src/camera_group/state_machine.rs:30` — `use crate::camera::Streaming`
   → Does not exist. Same as above.

3. `src/camera_group/state_machine.rs:553` — `use crate::camera::StateDiagram`
   → Does not exist. Mermaid diagram is in camera_README.md.

4. The entire camera_group state machine likely assumes the old type-state
   pattern and will need a similar handle-over-channels refactor.

The camera_group's conceptual relationship to the camera module is now:
- Camera group OWNS cameras (via `Camera` handles)
- Camera group OWNS the `BreakableBarrier` and manages synchronization
- Camera group orchestrates lifecycle: detect → start all → collect frames → shutdown all
- Camera group is the "gatherer" that participates in the barrier
