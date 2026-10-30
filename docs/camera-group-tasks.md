# Camera-group tasks

Application-level camera operations belong above capture implementations. Use
`CameraBackendManager.create_or_update_camera_group(configs, backend=...)` for
creation and settings changes. It keeps the selected backend and runs shared
tasks after the group starts streaming.

`RECOMMEND` requests a one-time exposure search. The manager opens the requested
cameras with manual settings, then calls `recommend_exposure`. The task needs
only the `ExposureCameraGroup` interface: configurations, fresh frame snapshots,
and asynchronous configuration updates. It imports neither capture backend.
Future group tasks can define similarly small interfaces without adding a
general task scheduler.

The same search tests exposures from -12 through -4, waits for ten distinct
frames at each setting, and chooses mean pixel brightness nearest 127.5 for
each requested camera. It applies a -1 offset, bounded to the search range,
to favor a shorter exposure. Other cameras keep their settings. A five-second
fresh-frame timeout prevents stalled capture from hanging the search; failures
and cancellation restore the starting settings. Configuration changes, closure,
and recording startup are serialized against recommendation.

`AUTO` is different: it asks the device to manage exposure continuously. Device
drivers retain responsibility for AUTO/MANUAL translation and exposure limits.
Rust uses device-reported limits instead of a fixed camera-specific clamp.
The existing Linux automatic-exposure fallback is preserved because the search
values use the Windows log2 exposure convention, not V4L2 absolute units.

Lower-level capture configuration must receive AUTO or MANUAL, not RECOMMEND.
Consumers working directly with a camera group can call `recommend_exposure`
after creating a manual group and must serialize concurrent settings changes.

Validation: `test_recommend_exposure.py` checks independent per-camera choices,
unchanged cameras, stale frames, cancellation, and routing through both backend
factories. Live validation additionally requires an available physical camera.
