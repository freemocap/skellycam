# Framerate Metric Definitions

This document explains the metrics printed in the `GATHERER STATISTICS` block
at the end of a SkellyCam Rust capture run (e.g.
`cargo run --release -- --cameras 3 --max-loops 10`).

The terminal output prints the numbers in tables; this file explains what
each metric means, the timestamp formulas behind them, and the methodology
behind the warmup / cooldown exclusion windows.

---

## Methodology Notes

### T=0 (the performance-clock anchor)

All timestamps shown in the stats block are nanoseconds since T=0. T=0 is the
wall-clock moment `init_logging()` was first called in this process (see
[`src/lib.rs`](src/lib.rs) and
[`src/timestamps/performance.rs`](src/timestamps/performance.rs)). The
wall-clock equivalent of T=0 is printed in the header of every stats block so
the relative-ns timestamps can be correlated with external logs.

The clock is `std::time::Instant`, which is monotonic, immune to NTP slew,
DST, and leap seconds. The wall-clock equivalent is captured atomically with
the `Instant` so the correlation is accurate to within a few nanoseconds.

### Per-camera vs. across-camera statistics

Per-camera rows compute their statistics over that camera's retained samples
only. Across-camera rows compute their statistics over the per-camera
**medians** (NOT over the raw pooled samples) — we want to see how cameras
compare, not what the noise of the pooled distribution looks like.

For example, with 3 cameras and 8 retained multiframes:

- Each per-camera row's `n = 8` (8 samples from that camera).
- The across-cameras row's `CV%` is computed from the 3 per-camera medians
  (`n = 3`).

### CV% (coefficient of variation)

`CV% = std / mean × 100`. Dimensionless; lets you compare variability across
metrics of different scales (sub-ms JPEG extract vs tens-of-ms Cycle total).
A low CV% indicates consistent behavior, a high CV% indicates jitter or
instability.

### Warmup window

The first N multiframes (default: 3) are excluded from statistics because
cameras open their capture streams at staggered wall-clock times — the first
few multiframes are not representative of steady-state behavior. Reasons the
first multiframes can be noisy:

- Cameras come online at different times during initialization (often
  hundreds of milliseconds apart).
- USB driver buffers may not be fully primed.
- The first frame from each camera has incomplete prior-iteration data in
  the FSM.

If you need to override the default warmup count, edit
`STATS_WARMUP_MULTIFRAMES` in
[`src/camera_group/gatherer.rs`](src/camera_group/gatherer.rs).

### Cooldown window

The last N multiframes (default: 1) are excluded because cameras may be in
the middle of being torn down during the final multiframe(s). The shutdown
sequence can distort the timings of the last iteration's channel send or
gatherer barrier wait.

If you need to override the default cooldown count, edit
`STATS_COOLDOWN_MULTIFRAMES` in
[`src/camera_group/gatherer.rs`](src/camera_group/gatherer.rs).

### % of cycle

The `% of cycle` column in per-camera tables expresses each metric as a
fraction of that camera's `Cycle total` median.

**Important:** the measured per-camera stages (`Wait for frame`,
`JPEG extract`, `Channel send wait`) will NOT sum to 100%. The remainder is
dominated by the time each camera spent inside `barrier.wait()`, which is
not measured per-camera (see the next section). Per-camera barrier wait can
be **inferred** from `Cycle total` minus the sum of the measured stages.

### Why is per-camera barrier wait not measured?

A camera's barrier wait would be the time between its `pre_barrier_ns`
(just before calling `barrier.wait()`) and `post_barrier_ns` (just after the
barrier returns). The camera, however, sends its frame packet downstream
BEFORE entering the barrier — so any barrier timestamps stamped in the FSM
after the send happens cannot be included in the packet that already left.

In an earlier version of this code the camera DID stamp `pre_barrier_ns` /
`post_barrier_ns` into the FSM (which persists across iterations), and the
gatherer computed `barrier_wait` from the values in each packet. But because
the FSM is reused across iterations, the packet for frame N contained the
**previous** iteration's barrier timestamps — an off-by-one attribution bug
that mixed data from two iterations in a single packet's computation.

The fix was to remove `pre_barrier_ns` and `post_barrier_ns` from
`FrameLifecycleTimestamps` entirely. Every field in
`FrameLifecycleTimestamps` now belongs to exactly one iteration — no
cross-iteration computations within a single packet.

The gatherer's OWN barrier wait IS measured (see `Gatherer barrier wait`
below), because for the gatherer thread, the relevant timestamps are stamped
within the same iteration.

---

## Throughput metrics

### Multiframe FPS

**Formula:** `1_000_000_000 / multiframe_interval_ns`

How fast the gatherer is producing assembled multiframes downstream (to the
recorder, GUI, or Python). Computed from the gap between successive
`frame_available_ns` values on the first camera in the gatherer's recv
order.

At 30 fps each multiframe is ~33 ms apart.

### Multiframe duration

**Formula:** difference between successive `frame_available_ns` values on
the first camera in the gatherer's recv order (the inverse of Multiframe
FPS, expressed as period instead of rate).

The same throughput information as Multiframe FPS, but in time units rather
than rate units. Useful when comparing the cycle period against other
duration-valued metrics in the same block.

At 30 fps this is ~33.3 ms.

---

## Intra-multiframe alignment metrics

These are computed once per multiframe (not per camera).

### Frame arrival spread

**Formula:** `max − min` of `frame_available_ns` across the cameras in a
single multiframe.

In plain language: *"how far apart in wall-clock time did our software see
each camera's frame appear?"*

Most of this is USB bus scheduling order, driver buffering, and the
cameras' independent exposure clocks — no consumer USB webcam guarantees
lockstep frame delivery. The practical floor on consumer UVC webcams is up
to one frame period.

### Thread wakeup spread

**Formula:** `max − min` of `loop_start_ns` across the cameras in a single
multiframe.

Every camera thread stamps its `loop_start_ns` the instant it exits the
shared barrier — and they all exit the SAME barrier — so this is pure OS
scheduling jitter. It measures how evenly the operating system wakes the N
parallel camera threads after the synchronized release.

Expected: microseconds. Persistent millisecond values indicate CPU
contention, thread-priority misconfiguration, or a saturated CPU core.

---

## Per-camera lifecycle metrics

These are measured once per camera per multiframe. Each metric is reported
per camera (one row per camera) and across cameras (one summary row
computed over the per-camera medians).

Cameras are ordered by `camera_index` in the printed tables, NOT by the
gatherer's internal receive order.

### Wait for frame

**Formula:** `frame_available_ns − loop_start_ns` (per camera)

How long this camera thread spent spinning on `Cap_hasNewFrame` after
exiting the barrier, before the camera hardware reported a new frame was
ready. Absorbs the slack between barrier release and the next physical
frame arrival.

A high value here means this camera's hardware is the "slowest" — its next
frame is furthest in the future when the barrier releases.

### JPEG extract

**Formula:** `post_jpeg_extract_ns − frame_available_ns` (per camera)

Time spent inside `Cap_captureFrameRaw` plus the `to_vec()` copy that moves
the raw MJPEG bytes from the openpnp-capture device buffer into a
heap-owned `Vec<u8>`.

**This is the metric that justifies the architecture.** In the prior
OpenCV-based implementation, `VideoCapture::read()` bundled this raw
byte-copy together with a full JPEG decode into an RGB image (typically
5–15 ms at 1280×720). Pulling the raw JPEG out and deferring decode to a
downstream stage is the optimization being measured here.

Expect sub-millisecond at 1280×720 MJPEG.

### Channel send wait

**Formula:** `gatherer_received_ns − pre_send_ns` (per camera)

Time between the camera stamping `pre_send_ns` (just before
`frame_sender.send`) and the gatherer's `recv()` returning with that frame.

The camera-to-gatherer channel is `sync_channel(1)` (capacity 1), so the
camera blocks on send when the gatherer has not yet recv'd the previous
frame. Steady-state should be microseconds; persistent large values
indicate the gatherer is the bottleneck (or the camera at this position is
recv'd late in the gatherer's serial recv order).

### Cycle total

**Formula:** `loop_start_{N+1} − loop_start_N` (per camera, across two
consecutive packets)

End-to-end per-camera cycle: from the start of one iteration's capture
loop to the start of the next. In a steady-state lock-stepped run this
equals one frame period (~33 ms at 30 fps) for every camera, because the
barrier holds everyone together.

This is the denominator for the `% of cycle` columns in the per-camera
tables.

NB: this is the ONLY per-camera metric computed from two consecutive
packets — that is honest (one cycle IS by definition the gap between two
`loop_start` values). The removed per-camera barrier-wait metric instead
mixed two iterations WITHIN one packet, which was a logic bug.

---

## Gatherer loop metrics

These are the gatherer's own per-iteration timings (one sample per
multiframe). All single-iteration-clean: each metric is computed from two
timestamps within the same gatherer iteration.

### Frames collection time

**Formula:** `all_frames_received_ns − collecting_start_ns`

Time the gatherer spent in `receiver.recv()` for ALL cameras — i.e.
blocked waiting for the slowest camera to deliver its frame. Bounded below
by `Frame arrival spread` (you can't recv all frames faster than they
appear).

### Gatherer barrier wait

**Formula:** `gatherer post_barrier_ns − all_frames_received_ns`

Time the gatherer itself spent at `barrier.wait()`. The gatherer is the
(N+1)-th barrier participant and arrives AFTER all cameras send their
frames, so this is typically tiny — the gatherer hits the barrier last
and releases it immediately.

### Payload assembly

**Formula:** `payload_assembled_ns − gatherer post_barrier_ns`

Time spent building the `MultiFramePayload` struct after the barrier
releases. Should be microseconds — it's just packing frames into a Vec.

### Downstream send

**Formula:** `post_send_downstream_ns − pre_send_downstream_ns`

Time spent in `multi_frame_sender.send(payload)`. The downstream channel
is unbounded `mpsc::channel()`, so this should always be fast unless the
dispatcher is wedged. Useful for detecting downstream backpressure even
though the channel does not enforce it.
