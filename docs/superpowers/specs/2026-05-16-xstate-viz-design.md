# XState v5 Interactive State Machine Visualizations

Two standalone HTML files that provide interactive, executable state machine
visualizations for the Camera and CameraGroup state machines, living alongside
the existing Mermaid markdown documentation in `docs/state_machines/`.

## Motivation

The current state machine documentation uses Mermaid `stateDiagram-v2` diagrams
in markdown files. These are static — you can read them but you cannot interact
with them. XState v5 (MIT licensed, available via esm.sh CDN) lets us define
executable state machines that you can click through, seeing each transition
fire and the state update live.

## Files

- `docs/state_machines/camera_state_machine.html` — Camera lifecycle
- `docs/state_machines/camera_group_state_machine.html` — CameraGroup lifecycle

## Dependencies

- **XState v5** from `esm.sh/xstate@5` (MIT) — machine definition and execution
- **Mermaid.js** from CDN (MIT) — static reference diagram rendering
- No npm, no build step, no SaaS services. Open the .html file in a browser.

## Architecture (per file)

Three vertical sections:

### 1. Interactive Stepper (top)
- Top-level states as a horizontal flow of connected cards
- Current state pulses green
- Available transition events as clickable buttons below the flow
- Clicking a state card opens a detail panel showing its substates
- Running transition log on the right (state changes with timestamps)
- Reset button returns to initial state

### 2. XState v5 Machine (invisible, drives the stepper)
- Defined in an inline `<script type="module">` block
- Mirrors the Rust state machine exactly: same states, same transitions
- `createActor(machine).start()` + `.send(event)` for interaction
- Context holds transition log, error info, timestamps

### 3. Mermaid Diagram (bottom)
- Rendered client-side by mermaid.js
- Same diagram as the .md files, kept as static reference

## Camera State Machine States

**Top-level (compile-time in Rust):**
Disconnected, Enumerated, Configured, Streaming, ShuttingDown, Faulted

**Streaming substates (runtime in Rust):**
WaitingForFrame, FrameAvailable, AtBarrier, Capturing, Sending

## CameraGroup State Machine States

**Top-level:** Empty, Configured, Streaming, ShuttingDown, Stopped

**Streaming orthogonal regions (parallel in XState):**
- Capture: Active, Paused
- Recording: NotRecording, Recording
- Gatherer: WaitingAtBarrier, CollectingFrames, AssemblingPayload, SendingDownstream

## Non-Goals
- No changes to Rust source code
- No automatic extraction from Rust type-state pattern
- No @statelyai/inspect (avoids SaaS dependency)
- The XState definitions are manually authored to match the Mermaid diagrams
  and Rust state definitions; they are documentation companions, not generated
