# FlatBuffer IPC Benchmark - Tauri + Raw RGB

High-performance inter-process communication using FlatBuffers, memory-mapped files, and native Rust decoding.

## Architecture

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│    Python    │      │     Rust     │      │   Canvas     │
│    Server    │─────▶│   Backend    │─────▶│   Display    │
└──────────────┘      └──────────────┘      └──────────────┘
     500-2000 FPS        200-1000 FPS          55-60 FPS
     
  • Raw RGB write    • Native decode     • RAF render
  • mmap (no I/O)    • RGB→RGBA          • Pull model
  • Zero encoding    • Hold in memory    • ImageData
```

### Key Optimizations

1. **Raw RGB Format**: No JPEG encoding/decoding overhead
2. **Memory-Mapped Files**: Zero-copy IPC, no disk I/O
3. **Native Rust Decoding**: FlatBuffer decoding in compiled code
4. **Pull-Based Rendering**: Canvas requests frames when ready
5. **Direct GPU Upload**: Canvas ImageData bypasses DOM

## Setup

### 1. Install Dependencies

```bash
# macOS
brew install flatbuffers

# Linux
sudo apt-get install flatbuffers-compiler

# Windows
# Download from: https://github.com/google/flatbuffers/releases
```

### 2. Generate Code

```bash
./build-flatbuffers.sh
```

This generates:
- `server/generated/*.py` - Python FlatBuffer classes
- `src-tauri/src/generated/*.rs` - Rust FlatBuffer classes  
- `src/generated/*.ts` - TypeScript types (optional)

### 3. Python Server

```bash
cd server
pip install -r requirements.txt
python server.py
```

Server runs on `http://localhost:8009`

### 4. Tauri App

```bash
npm install
npm run tauri dev
```

## Performance Targets

| Stage | Target | Bottleneck |
|-------|--------|------------|
| Python Write | 500-2000+ FPS | CPU (NumPy operations) |
| Rust Read | 200-1000+ FPS | File polling (1ms timer) |
| Canvas Render | 55-60 FPS | Browser refresh rate |

## Why Raw RGB vs JPEG?

**JPEG** (what you had):
- ✅ Small: ~100KB for 720p
- ❌ Encode: ~1-2ms in Python
- ❌ Decode: ~1-2ms in Rust/JS
- ❌ Total overhead: ~2-4ms per frame

**Raw RGB** (recommended):
- ❌ Large: 2.7MB for 720p  
- ✅ No encoding
- ✅ No decoding
- ✅ Direct memory copy
- ✅ **Net 2-4ms faster per frame**

For memory-mapped files, size doesn't matter - it's just memory. The CPU time saved by avoiding encode/decode is significant.

## Expected Results

### Python Server
- **1280x720**: 1000-2000 FPS write
- **1920x1080**: 500-1000 FPS write

### Rust Backend  
- **Read + Decode**: 200-500 FPS
- **Bottleneck**: `setInterval(1ms)` polling precision

### Canvas Display
- **Target**: 60 FPS (browser limit)
- **Typical**: 55-60 FPS with `requestAnimationFrame`

## Troubleshooting

### Low Rust FPS (<100)

The 1ms polling might not be precise. Try:

```rust
// In lib.rs, replace thread::sleep with spin-wait
// (for benchmarking only - wastes CPU)
loop {
    let start = Instant::now();
    // ... process frame ...
    while start.elapsed() < poll_duration {}
}
```

### Low Canvas FPS (<30)

Check:
1. Browser GPU acceleration enabled
2. Canvas size matches frame size
3. No other heavy React renders
4. Monitor refresh rate is 60Hz

### Python FPS is low

Reduce frame size or channels:
```python
self.width = 640   # Instead of 1280
self.height = 480  # Instead of 720
```

## File Structure

```
.
├── schemas/
│   └── message.fbs           # FlatBuffer schema
├── server/
│   ├── generated/            # Generated Python code
│   ├── server.py             # Python mmap writer
│   └── requirements.txt
├── src-tauri/
│   ├── src/
│   │   ├── generated/        # Generated Rust code
│   │   ├── lib.rs            # Rust mmap reader + decoder
│   │   └── main.rs
│   └── Cargo.toml
├── src/
│   ├── CanvasRenderer.tsx    # Canvas display
│   ├── App.tsx               # Main UI
│   └── generated/            # Generated TS types
└── build-flatbuffers.sh      # Code generation
```

## Performance Monitoring

The UI shows three key metrics:

1. **Python Write FPS**: How fast the server generates frames
2. **Rust Read/Decode FPS**: How fast Rust processes frames  
3. **Canvas Render FPS**: How fast the UI displays frames

If Canvas is hitting 55-60 FPS consistently, you've achieved optimal performance!