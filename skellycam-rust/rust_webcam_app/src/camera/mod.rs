//! Camera module — thread-per-camera architecture.
//!
//! ## Architecture overview
//!
//! The camera lives on its own dedicated thread.  The main thread communicates
//! with it through two MPSC channels:
//!
//! ```text
//!   Main Thread                         Camera Thread
//!   ──────────                         ──────────────
//!   command_sender ──── CameraCommand ──→ command_receiver
//!   event_receiver  ←── CameraEvent  ──── event_sender
//! ```
//!
//! This is the same pattern as Python's `queue.Queue` with producer/consumer
//! threads, but:
//!
//! 1. **Type safety**: Each channel carries exactly one enum type.  You can't
//!    accidentally send the wrong kind of message.
//!
//! 2. **No GIL contention**: The camera thread runs truly in parallel with the
//!    main thread.  Python threads can't run Python bytecode simultaneously
//!    due to the GIL (though C-extensions like OpenCV can release it).
//!
//! 3. **Ownership, not sharing**: The `FramePacket` transfers **ownership** of
//!    the `RgbImage` (and its backing `Vec<u8>`) across the channel — no
//!    reference counting, no `multiprocessing.shared_memory`, just a pointer
//!    move.
//!
//! ## `Send` and `Sync` — Rust's thread-safety markers
//!
//! These are **auto-derived traits** that the compiler uses to check thread
//! safety at compile time:
//!
//! - `Send`: a value of this type can be **transferred** to another thread
//!   (e.g., through a channel).  `RgbImage` is `Send` because `Vec<u8>` is
//!   `Send`.
//!
//! - `Sync`: a reference to this type can be **shared** between threads.
//!   `&T` is `Sync` if `T` is `Sync`.
//!
//! The `nokhwa::Camera` type is deliberately **not** `Send`, which is why we
//! must open and operate it entirely within the camera thread.
//!
//! ## Submodule layout
//!
//! - `types`: Channel protocol enums and metadata structs.
//! - `manager`: Thin wrapper around `nokhwa::Camera` for capture + controls.
//! - `ops`: Free functions: `list_cameras()`, `query_camera()`,
//!   `spawn_camera_thread()`.

mod types;
mod manager;
mod ops;

pub use types::{CameraEvent, CameraHandle};
pub use ops::{list_cameras, query_camera, spawn_camera_thread};
