# SkellyCam agent guidance

SkellyCam owns standalone capture, camera configuration, synchronization,
recording and camera streaming. It must operate without FreeMoCap, SkellyTracker
or SkellyForge imports, including tests. Core coordinates the combined application;
component-specific lifecycle and transport remain here.

## Task continuity

Camera frame-rate comparisons must allow the driver's documented frame-interval
quantization. Reuse `frame_rates_equal` in `camera_config.py` for nominal rate
equality. A 60 fps request may read back as 60.0002 fps. Validate genuine mixed
rates such as 60 and 59.94 separately. Group startup tests must include negotiated
readbacks from heterogeneous devices, not only equal integer requests.

For client-facing actions, follow the workspace's stable-control recovery rule.
A failed command remains diagnostic information and never changes a normal action
into a saved retry or prevents a fresh command. Current server observations
supersede old client assumptions after failure and reconnect.

At milestones, checkpoint the objective, decisions and reasons, exact checkout,
existing interfaces, relevant plan stage, verification evidence and next action.
Include the paths and questions needed to recover that action. After compaction
or handoff, read the checkpoint and this file, then the relevant sources below
and current diff before editing. Continue under existing authorization once the
purpose, owner and validation are clear. Search existing abstractions before
creating replacements; ask only for unresolved consequential intent.

- Camera lifecycle/backend selection: [backend development](RUST-BACKEND-DEVELOPMENT.md)
  and [camera groups](skellycam/core/camera_group/).
- Shared group operations: [camera-group tasks](docs/camera-group-tasks.md);
  preserve the manager/interface boundary rather than duplicating a task in each backend.
- Recording completion and timing: [recorders](skellycam/core/recorders/)
  and [timestamps](skellycam/core/timestamps/).
- Public behavior and setup: [README](README.md); check current `pyproject.toml`
  and task bodies before running commands. Documentation commands alone do not
  authorize installations or environment changes.

Follow containing workspace policy when present. Preserve user edits and follow the workspace Git authorization and repository-scope policy. Verify this repository ignores generated outputs before
creating them, or use external temporary storage. Hardware-dependent checks need
available cameras; historical pass statements are not current test results.
For external source attribution, follow [CITATIONS.md](CITATIONS.md).
