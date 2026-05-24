# SkellyCam: A Worked Example

This directory contains the output of applying the [re-architecture methodology](../rearchitecture-playbook/) to the SkellyCam multi-camera capture backend.

Each document covers one architectural component:

| # | Document | What It Covers |
|---|----------|---------------|
| 01 | [System Startup](./01-system-startup.md) | Process model, lifecycle, graceful shutdown |
| 02 | [Camera Group Manager](./02-camera-group-manager.md) | Group lifecycle, camera management, config updates |
| 03 | [Camera Sync Gate](./03-camera-sync-gate.md) | Multi-camera lockstep, capture loop, config mid-stream |
| 04 | [Frame Fan-Out](./04-frame-fanout.md) | From gathered frames to frontend + recorder |
| 05 | [Recording Pipeline](./05-recording-pipeline.md) | Video encoding, frame metadata, finalization |
| 06 | [Timestamp Pipeline](./06-timestamp-pipeline.md) | Per-frame timing, performance clock, statistics |
| 07 | [HTTP API Surface](./07-http-api-surface.md) | Endpoints, request/response shapes, error handling |
| 08 | [WebSocket Binary Protocol](./08-websocket-binary-protocol.md) | Wire format, image processing, frontend encoding |
| 09 | [Channel Architecture](./09-channel-architecture.md) | PubSub→channels, thread communication, sync primitives |

Each document follows the same structure:
- **The abstract problem** — what must this component achieve?
- **Python's solution** — how the Python codebase solved it, and why
- **Rust's solution** — how the Rust implementation solved it, and why differently
- **What was preserved and what changed** — invariants met, design decisions diverged

These documents were originally written as planning artifacts during the port. They have been audited against the working Rust implementation (2026-05-23) and reframed as comparative architecture documentation.
