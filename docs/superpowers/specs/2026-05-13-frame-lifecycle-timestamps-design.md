# Frame Lifecycle Timestamps

## Purpose

Instrument every meaningful point in the frame capture pipeline with nanosecond-precision monotonic timestamps. This enables precise diagnosis of where time is spent: hardware wait, synchronization overhead, memory copy, channel backpressure.

## Architecture

### FrameLifecycleTimestamps

A struct carried on every `FramePacket`. All fields are `i64` nanoseconds from `performance_counter_nanoseconds()`. Fields initialized to 0; each pipeline stage stamps its own fields as the frame passes through.

**Camera thread stamps (8 fields):**

| Field | When stamped |
|-------|-------------|
| `loop_start_ns` | Top of the capture loop iteration |
| `frame_available_ns` | `Cap_hasNewFrame()` returned true |
| `pre_barrier_ns` | About to enter `barrier.wait()` |
| `post_barrier_ns` | Barrier released |
| `pre_capture_ns` | About to call `Cap_captureFrame()` |
| `post_capture_ns` | `Cap_captureFrame()` returned |
| `pre_send_ns` | About to call `frame_sender.send()` |
| `post_send_ns` | `send()` returned |

**Gatherer stamps (1 field):**

| Field | When stamped |
|-------|-------------|
| `gatherer_received_ns` | After `recv()` returns this frame |

### MultiFramePayload Timestamps

Payload-level timestamps on `MultiFramePayload` (4 fields):

| Field | When stamped |
|-------|-------------|
| `all_frames_received_ns` | After the last camera's `recv()` completes |
| `payload_assembled_ns` | After `MultiFramePayload` struct is built |
| `pre_send_downstream_ns` | Before `multi_frame_sender.send()` |
| `post_send_downstream_ns` | After `send()` returns |

### Derived Durations

Computed from raw timestamps during analysis (not stored):

| Duration | Formula | Meaning |
|----------|---------|---------|
| hardware wait | `frame_available - loop_start` | Waiting for sensor/driver to produce a frame |
| pre-barrier idle | `pre_barrier - frame_available` | Between frame availability and sync |
| barrier sync | `post_barrier - pre_barrier` | Blocked waiting for all cameras to sync |
| capture duration | `post_capture - pre_capture` | `Cap_captureFrame()` memcpy cost |
| pre-send idle | `pre_send - post_capture` | Between capture and channel send |
| channel backpressure | `post_send - pre_send` | Blocked waiting for gatherer to consume |
| total camera iteration | `post_send - loop_start` | Full camera thread cycle |

### Inter-Camera Spread

Computed from `frame_available_ns` across all cameras in a multiframe. This measures when the hardware reported each frame ready — the physically meaningful synchronization metric.

### Gatherer Statistics Output

A processing breakdown table printed on shutdown, showing per-stage durations (median, mean, standard deviation, min, max) and percentage of total frame time. Format mirrors the Python `RecordingTimestampsStats` output.

### CSV Output (Recording Mode)

When recording, the CSV writer outputs all raw timestamp fields per frame. Column naming uses full words with dot-separated hierarchy:

```
frame_number,
timestamps.loop_start_ns,
timestamps.frame_available_ns,
timestamps.pre_barrier_ns,
timestamps.post_barrier_ns,
timestamps.pre_capture_ns,
timestamps.post_capture_ns,
timestamps.pre_send_ns,
timestamps.post_send_ns,
timestamps.gatherer_received_ns
```

## Files to Create or Modify

| File | Action |
|------|--------|
| `src/camera/types.rs` | Add `FrameLifecycleTimestamps` struct. Replace `grab_timestamp_nanoseconds` field on `FramePacket` with `timestamps: FrameLifecycleTimestamps`. Update `MultiFramePayload` with payload-level timestamp fields and update spread computation. |
| `src/camera/thread.rs` | Stamp all 8 camera-thread timestamps at their respective points in the capture loop. |
| `src/camera_group/gatherer.rs` | Stamp `gatherer_received_ns` on each frame after `recv()`. Stamp payload-level timestamps. Update statistics to show per-stage duration breakdown. |
| `src/timestamps/csv_writer.rs` | Update CSV header and row writing to emit all timestamp columns. |
| `src/main.rs` | Update any code that reads frame timestamps (recording mode, multi-camera stats). |

## Success Criteria

- All 9 per-frame timestamp fields are populated with non-zero values during capture
- All 4 payload-level timestamps are populated
- Gatherer shutdown statistics show per-stage duration breakdown
- CSV output contains all timestamp columns
- Inter-camera spread is computed from `frame_available_ns`
