# Component #8: WebSocket Binary Protocol

Status: **ANALYZED — stable reference artifact**

Files analyzed:
- `skellycam/core/types/frontend_payload_bytearray.py` — `create_frontend_payload()`, dtype definitions, JPEG encoding

---

## Part 1: Binary Wire Format

The frontend receives binary WebSocket messages with this exact layout:

```
Byte 0
  ┌────────────────────────────────────────────────────┐
  │              PAYLOAD_HEADER (24 bytes)              │
  │  message_type:     u8  = 0    (offset 0)           │
  │  <padding>         7 bytes    (offsets 1-7)        │
  │  frame_number:     i64 LE     (offset 8)           │
  │  number_of_cameras: i32 LE    (offset 16)          │
  │  <padding>         4 bytes    (offsets 20-23)      │
  ├────────────────────────────────────────────────────┤
  │              FRAME_HEADER for camera 0              │
  │  message_type:      u8  = 1   (offset 0)           │
  │  <padding>          7 bytes   (offsets 1-7)        │
  │  frame_number:      i64 LE    (offset 8)           │
  │  camera_identifier: [u8; 16]  (offset 16, UTF-8)    │
  │  camera_index:      i32 LE    (offset 32)          │
  │  image_width:       i32 LE    (offset 36)          │
  │  image_height:      i32 LE    (offset 40)          │
  │  color_channels:    i32 LE    (offset 44)          │
  │  jpeg_string_length: i32 LE   (offset 48)          │
  │  <padding>          4 bytes   (offsets 52-55)      │
  │  Total: 56 bytes (C-aligned)                       │
  ├────────────────────────────────────────────────────┤
  │              JPEG bytes (variable length)            │
  │  Length = jpeg_string_length from frame header      │
  ├────────────────────────────────────────────────────┤
  │     ... repeat FRAME_HEADER + JPEG per camera ...   │
  ├────────────────────────────────────────────────────┤
  │              PAYLOAD_FOOTER (24 bytes)              │
  │  Same structure as PAYLOAD_HEADER                   │
  │  message_type:     u8  = 2                         │
  │  frame_number:     i64 LE                          │
  │  number_of_cameras: i32 LE                         │
  └────────────────────────────────────────────────────┘
```

### Memory Layout Detail

The Python code uses numpy structured dtypes with `align=True`, which follows C struct alignment rules. `#[repr(C)]` in Rust produces the same layout.

**PayloadHeaderFooter** (24 bytes):
```
Offset  Size  Type    Field
0       1     u8      message_type        // 0 = header, 2 = footer
1-7     7     —       padding (to align frame_number at 8)
8       8     i64     frame_number         // little-endian
16      4     i32     number_of_cameras    // little-endian
20-23   4     —       padding (to align struct to 8-byte boundary)
```

**FrameHeader** (56 bytes):
```
Offset  Size  Type      Field
0       1     u8        message_type        // always 1
1-7     7     —         padding (to align frame_number at 8)
8       8     i64       frame_number        // little-endian
16      16    [u8; 16]  camera_identifier   // UTF-8, null-padded if < 16 bytes
32      4     i32       camera_index        // little-endian
36      4     i32       image_width         // little-endian, AFTER resize
40      4     i32       image_height        // little-endian, AFTER resize
44      4     i32       color_channels      // typically 3 (BGR)
48      4     i32       jpeg_string_length  // little-endian, length of following JPEG data
52-55   4     —         padding (to align struct to 8-byte boundary)
```

### Message Type Values

| Value | Meaning | Contains |
|-------|---------|----------|
| 0 | Payload header | Marks start of a multi-frame payload. `frame_number` is the multiframe number. `number_of_cameras` is total cameras in this payload. |
| 1 | Frame header | Marks start of a single camera's frame data. Followed immediately by JPEG bytes. |
| 2 | Payload footer | Marks end of the multi-frame payload. Same `frame_number` and `number_of_cameras` as the header. Frontend uses this to validate message completeness. |

### Rust Struct Definitions

```rust
/// Payload header/footer — 24 bytes, #[repr(C)] matches numpy align=True.
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct PayloadHeaderFooter {
    pub message_type: u8,
    _padding_1: [u8; 7],     // align frame_number to offset 8
    pub frame_number: i64,    // little-endian
    pub number_of_cameras: i32,  // little-endian
    _padding_2: [u8; 4],     // align struct to 8-byte boundary
}

/// Per-camera frame header — 56 bytes, #[repr(C)] matches numpy align=True.
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct FrameHeader {
    pub message_type: u8,
    _padding_1: [u8; 7],          // align frame_number to offset 8
    pub frame_number: i64,         // little-endian
    pub camera_identifier: [u8; 16], // UTF-8, null-padded
    pub camera_index: i32,         // little-endian
    pub image_width: i32,          // little-endian, after resize
    pub image_height: i32,         // little-endian, after resize
    pub color_channels: i32,       // little-endian
    pub jpeg_string_length: i32,   // little-endian, length of following JPEG
    _padding_2: [u8; 4],          // align struct to 8-byte boundary
}
```

**Important**: These structs use `#[repr(C)]`, NOT `#[repr(C, packed)]`. `packed` would remove padding and break the layout the frontend expects. The padding bytes (`_padding_1`, `_padding_2`) are explicit in the struct definition so the compiler doesn't warn about unused fields, but they could also be unnamed: `_reserved: [u8; 7]`.

**Serialization**: Convert to bytes via `bytemuck` or unsafe `std::mem::transmute` + `std::slice::from_raw_parts`:

```rust
fn payload_header_to_bytes(header: &PayloadHeaderFooter) -> &[u8] {
    bytemuck::bytes_of(header)  // safe: Pod types, repr(C)
}
```

`bytemuck` provides safe transmutation for `Pod` (plain old data) types. All fields are primitives with no invalid bit patterns, so `PayloadHeaderFooter` and `FrameHeader` are `Pod`.

---

## Part 2: Image Processing Pipeline (per camera)

Before JPEG encoding, each camera's frame goes through:

### Step 1: Compute Grab Timestamp Midpoint

```python
frame_timestamps.append(
    np.mean([pre_frame_grab_ns, post_frame_grab_ns])
)
```

In Rust:
```rust
let grab_midpoint_nanoseconds =
    (timestamps.pre_frame_grab_nanoseconds + timestamps.post_frame_grab_nanoseconds) / 2;
```

This midpoint is the best proxy for "when were these photons captured." All cameras' midpoints are averaged to produce the multiframe timestamp.

### Step 2: Rotate (if needed)

```python
if rotation != -1:
    rotated_image = cv2.rotate(src=image, rotateCode=rotation)
else:
    rotated_image = image
```

The `rotation` value comes from `frame_metadata.camera_info.rotation` and uses OpenCV rotate codes:
- `-1` = no rotation
- `cv2.ROTATE_90_CLOCKWISE` (0)
- `cv2.ROTATE_180` (1)
- `cv2.ROTATE_90_COUNTERCLOCKWISE` (2)

In Rust using the `image` crate:
```rust
use image::imageops;

let rotated = match rotation {
    0 => imageops::rotate90(&image),
    1 => imageops::rotate180(&image),
    2 => imageops::rotate270(&image),
    _ => image,  // -1 or anything else: no rotation
};
```

### Step 3: Resize

```python
if display_image_sizes is None or camera_id not in display_image_sizes:
    resize_height = int(image.shape[0] * 0.5)
    resize_width = int(image.shape[1] * 0.5)
else:
    resize_height = int(display_image_sizes[camera_id]['height'])
    resize_width = int(display_image_sizes[camera_id]['width'])

resized = cv2.resize(src=rotated, dsize=(width, height), interpolation=cv2.INTER_LINEAR)
```

Default: 50% of rotated dimensions. If `displayImageSizes` was sent by the frontend, use those exact dimensions.

In Rust:
```rust
use image::imageops::FilterType;

let (width, height) = match display_sizes {
    Some(sizes) => (sizes.width as u32, sizes.height as u32),
    None => (
        (rotated.width() as f64 * 0.5) as u32,
        (rotated.height() as f64 * 0.5) as u32,
    ),
};
let resized = imageops::resize(&rotated, width, height, FilterType::Triangle);
```

`FilterType::Triangle` is the closest match to `cv2.INTER_LINEAR` (bilinear interpolation).

### Step 4: JPEG Encode

```python
_, jpeg_data = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, 80])
jpeg_bytes = jpeg_data.tobytes()
```

Quality 80, standard JPEG.

In Rust:
```rust
use image::codecs::jpeg::JpegEncoder;
use std::io::Cursor;

let mut jpeg_bytes = Vec::new();
let mut encoder = JpegEncoder::new_with_quality(&mut Cursor::new(&mut jpeg_bytes), 80);
encoder.encode_image(&resized)?;
```

**Potential incompatibility**: OpenCV's JPEG encoder and Rust's `image` crate JPEG encoder may produce different byte streams from the same input pixels. Both produce valid JPEG files, but the bytes differ due to encoder implementation details (quantization table rounding, Huffman table choices, etc.).

If the frontend does ANY byte-level validation, this breaks. If the frontend only decodes the JPEG and displays it, both are fine.

Decision needed: test with actual frontend. If bit-identical output is required, use the `opencv` crate's `imgcodecs::imencode` in Rust, or use `ffmpeg` to encode JPEG, or ship a pure-Rust JPEG encoder with the same quantization tables as OpenCV.

---

## Part 3: Multiframe Timestamp

The return value `np.mean(frame_timestamps)` is the mean of all cameras' grab midpoints:

```python
frame_timestamps = [
    mean([camera_0.pre_grab, camera_0.post_grab]),
    mean([camera_1.pre_grab, camera_1.post_grab]),
    ...
]
multiframe_timestamp = mean(frame_timestamps)
```

In Rust:
```rust
let multiframe_timestamp: f64 = grab_midpoints.iter().sum::<f64>()
    / grab_midpoints.len() as f64;
```

This multiframe timestamp is used by the WebSocket server for:
- Server framerate calculation (from consecutive multiframe timestamps)
- Inter-camera sync measurement (range of grab midpoints within a multiframe)

---

## Part 4: Reusable Buffer Pattern

Python uses a module-level global `_reusable_bytes_payload: bytearray` to avoid allocating a new buffer on every frame:

```python
global _reusable_bytes_payload
# Pre-allocate: 1 MB per camera + config overhead
estimated_size = (number_of_cameras + 1) * ONE_MEGABYTE + config_overhead
if len(_reusable_bytes_payload) < estimated_size:
    _reusable_bytes_payload = bytearray(estimated_size)

# Write into the buffer, track position
current_pos = 0
# ... write header, per-camera headers + JPEG, footer ...
frontend_bytes = _reusable_bytes_payload[:current_pos]
```

In Rust, this is naturally handled by `Vec<u8>`:

```rust
pub struct PayloadEncoder {
    buffer: Vec<u8>,
}

impl PayloadEncoder {
    pub fn encode(
        &mut self,
        frame_number: i64,
        frames: &HashMap<String, CameraFrame>,
        display_sizes: Option<&HashMap<String, DisplaySize>>,
    ) -> (f64, &[u8]) {
        self.buffer.clear();

        // Write payload header
        self.buffer.extend_from_slice(bytemuck::bytes_of(&header));

        // Per camera
        for (camera_identifier, frame) in frames {
            // ... rotate, resize, JPEG encode ...
            self.buffer.extend_from_slice(bytemuck::bytes_of(&frame_header));
            self.buffer.extend_from_slice(&jpeg_bytes);
        }

        // Write payload footer
        self.buffer.extend_from_slice(bytemuck::bytes_of(&footer));

        (multiframe_timestamp, &self.buffer)
    }
}
```

`Vec<u8>::clear()` preserves the allocated capacity — no reallocation unless the payload grows. This is the same behavior as Python's reusable bytearray but without global mutable state (the `PayloadEncoder` owns its buffer).

---

## Part 5: Where This Gets Called

In the Python WebSocket server, `_frontend_image_relay` calls `get_latest_frontend_payloads()` every 10ms, which calls `create_frontend_payload()` on the latest multiframe from shared memory.

In Rust, the gatherer produces `Arc<MultiFramePayload>` and sends it via `watch::Sender::send_replace()`. The WebSocket task receives via `watch::Receiver::changed()`:

```rust
async fn frontend_image_relay(
    mut websocket_sender: SplitSink<WebSocket, Message>,
    mut watch_receiver: watch::Receiver<Arc<MultiFramePayload>>,
    mut encoder: PayloadEncoder,
) {
    loop {
        watch_receiver.changed().await.unwrap();
        let payload = watch_receiver.borrow();

        let (timestamp, bytes) = encoder.encode(
            payload.step as i64,
            &payload.frames,
            &display_sizes,
        );

        websocket_sender
            .send(Message::Binary(bytes.to_vec().into()))
            .await
            .unwrap();
    }
}
```

---

## Functionality That Must Be Preserved

1. **Exact binary layout** — header/footer and frame header structs with correct sizes (24 and 56 bytes), field offsets, and endianness
2. **Message type values** — 0 (header), 1 (frame), 2 (footer) — frontend uses these to parse the stream
3. **frame_number in header matches footer** — frontend validates
4. **camera_identifier 16-byte fixed width** — UTF-8, null-padded or truncated
5. **JPEG quality 80** — same encoding quality
6. **Default resize to 50%** — same scaling factor when no display sizes provided
7. **Rotation before resize** — same order of operations
8. **Grab midpoint as frame timestamp** — `(pre_grab + post_grab) / 2`
9. **Multiframe timestamp as mean of grab midpoints** — used for framerate tracking
10. **Per-camera JPEG encoding** — each camera's frame is independently encoded (not a stitched image)
11. **Footer validation** — frontend uses footer to confirm complete message received

---

## Open Question

| # | Question | Notes |
|---|----------|-------|
| 1 | JPEG encoder compatibility | Rust `image` crate vs OpenCV `cv2.imencode`. Both produce valid JPEG, but bytes differ. If frontend does byte-level checks, use `opencv` crate. If not, `image` crate is fine. Test with actual frontend. |
