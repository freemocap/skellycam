# Raw MJPEG diagnostic: `Cap_captureFrameRaw` returns zeroed data after stabilization

## Environment

- OS: Windows 11 x86_64
- Camera: USB Camera, vid_0c45 pid_6366, 1280x720 @30fps MJPG (format index 3)
- openpnp-capture: build.2 (latest release from jonmatthis/openpnp-capture)
- Calling code: Rust FFI via `skellycam-rust/src/camera/ffi.rs` + `thread.rs`

## FFI declarations used

```rust
pub fn Cap_openStreamRaw(ctx: CapContext, index: CapDeviceID, format_id: CapFormatID) -> CapStream;
pub fn Cap_getFrameSize(ctx: CapContext, stream: CapStream, out_bytes: *mut u32) -> CapResult;
pub fn Cap_captureFrameRaw(ctx: CapContext, stream: CapStream, buf: *mut u8, buf_size: u32, out_bytes: *mut u32) -> CapResult;
```

These match the header shipped with build.2.

## What works

### Stream open
`Cap_openStreamRaw(ctx, index=0, format_id=3)` returns `stream=0`. Log output:
```
Camera USB Camera [007e6c]: raw MJPEG stream opened (format=3 stream=0 1280x720)
```

### Stabilization (30 frames, immediately after open)
Uses `Cap_hasNewFrame` → `Cap_getFrameSize` → `Cap_captureFrameRaw`. All 30 frames produce valid, varying-size data:

```
raw stabilize frame 0: 30216 bytes
raw stabilize frame 1: 69504 bytes
raw stabilize frame 2: 69872 bytes
raw stabilize frame 3: 72728 bytes
raw stabilize frame 4: 72728 bytes
raw stabilize frame 5: 69408 bytes
... (sizes vary between 30KB and 73KB — consistent with MJPEG)
```

This strongly suggests the DirectShow graph is configured correctly and
the camera is producing valid MJPEG frames.

## What fails

### Capture loop (after stabilization)
Same API sequence: `Cap_hasNewFrame` → `Cap_getFrameSize` → `Cap_captureFrameRaw`.
`Cap_getFrameSize` returns CAPRESULT_OK with varying sizes. `Cap_captureFrameRaw`
returns CAPRESULT_OK with `out_bytes` matching the reported frame size.
**But the buffer is all zeros** — every byte is 0x00.

```
Frame sizes from capture loop: consistently ~107KB (106,920 to 107,296 bytes)
First bytes: 00 00 00 00 00 00 00 00 ... (all zeros)
JPEG magic check (0xFF 0xD8): FAIL
```

The capture loop frame sizes (107KB) are notably LARGER and more consistent
than the stabilization frame sizes (30-73KB, varying per frame).

## Key anomaly

The stabilization phase and the capture loop use identical API calls, but:

| Phase | Frame sizes | Data |
|---|---|---|
| Stabilize | 30-73KB (varying) | Presumed valid (not explicitly hex-dumped) |
| Capture loop | ~107KB (consistent) | All zeros |

The capture loop runs on the same thread, same context, same stream handle.
The only difference is timing — stabilize runs in a tight loop immediately
after stream open; the capture loop has a barrier synchronization delay
between frames (waiting for other camera threads + gatherer).

## Hypotheses

1. **Frame buffer pointer mismatch**: `Cap_captureFrameRaw` might be writing
   to an internal buffer in the Sample Grabber but copying from a different
   (uninitialized) location. The ~107KB size might be the internal buffer's
   allocated capacity rather than the actual frame size.

2. **State change after stabilize**: Something in the DirectShow graph
   changes state after the first ~30 frames (e.g., the Sample Grabber
   switches from buffered to callback mode, or the allocator renegotiates).

3. **`Cap_getFrameSize` reporting wrong value**: If the function returns the
   buffer's allocated size (107KB) rather than the actual frame size, the
   capture copy would read uninitialized memory. The stabilize phase uses
   the same function but the buffer might be in a different state.

4. **Buffer ownership issue**: Maybe the raw frame data is in a DirectShow
   media sample that needs to be locked/accessed differently than the RGB
   path, and `Cap_captureFrameRaw` isn't handling that correctly.

## Requested fixes for openpnp-capture

1. **Add print statements throughout the raw capture path** — specifically
   in the Windows DirectShow implementation of `Cap_openStreamRaw`,
   `Cap_getFrameSize`, and `Cap_captureFrameRaw`. Print:
   - The media type actually negotiated (width, height, subtype FOURCC)
   - The Sample Grabber buffer state (buffer size, number of samples queued)
   - The actual bytes being copied in `Cap_captureFrameRaw` (first 16 bytes as hex)
   - The actual frame size vs allocated buffer size

2. **Add a version stamp** — print the library version and build tag on
   first `Cap_createContext()` call. Something like:
   ```
   [openpnp-capture] build.2 | jonmatthis/fork | compiled 2026-05-14
   ```
   This confirms we're using the expected binary and not a stale cached copy.

3. **Add a `Cap_getVersion()` function** or a compile-time version string
   that the FFI can query, so the caller can verify at runtime which
   version of the library is loaded.

4. **Investigate the zeroed-buffer-after-stabilization issue** — specifically
   check whether the Sample Grabber's internal buffer is being correctly
   managed after the first N frames. The fact that stabilize works but the
   capture loop doesn't suggests a subtle state change.

## Verification steps the caller can do

Add a hex dump of the first 16 bytes of every raw frame (both in stabilize
and capture loop), not just the frame size. Compare to confirm stabilize
produces valid JPEG (0xFF 0xD8 ...) while capture produces zeros.

## How to reproduce

1. Check out `jonmatthis/openpnp-capture` tag `build.2`
2. Build for Windows x86_64
3. Use the Rust FFI declarations above
4. Open camera index 0 with `Cap_openStreamRaw(ctx, 0, format_id_for_1280x720_MJPG)`
5. Call `Cap_captureFrameRaw` after stabilization — observe zeroed buffer
