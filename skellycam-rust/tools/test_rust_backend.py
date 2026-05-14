"""Quick smoke test: Rust camera backend (openpnp-capture via PyO3).

Creates a camera group from the specified indices, polls for JPEG frames
at ~100 Hz, prints frame metadata, then shuts down cleanly with full
gatherer statistics.

Usage:
    python tools/test_rust_backend.py                          # camera 0 only
    python tools/test_rust_backend.py --cameras 0,2,4          # specific indices
    python tools/test_rust_backend.py --cameras all            # every detected camera
    python tools/test_rust_backend.py --cameras first-3        # first 3 cameras
    python tools/test_rust_backend.py --cameras 0,1 --duration 10
"""

import argparse
import time

import _skellycam_rust


def resolve_indices(spec: str) -> list[int]:
    """Parse the --cameras argument into a list of camera indices.

    Formats:
        "0,2,4"      → [0, 2, 4]
        "all"        → every detected camera
        "first-N"    → first N detected cameras (e.g. "first-3" → [0, 1, 2])
    """
    spec = spec.strip()

    if spec.lower() == "all":
        cameras = _skellycam_rust.detect_cameras()
        return [c["camera_index"] for c in cameras]

    if spec.lower().startswith("first-"):
        n = int(spec.split("-")[1])
        cameras = _skellycam_rust.detect_cameras()
        return [c["camera_index"] for c in cameras[:n]]

    return [int(s.strip()) for s in spec.split(",")]


def main():
    parser = argparse.ArgumentParser(description="SkellyCam Rust backend smoke test")
    parser.add_argument(
        "--cameras",
        type=str,
        default="0",
        help="Camera spec: comma-separated indices, 'all', or 'first-N' (default: '0')",
    )
    parser.add_argument("--width", type=int, default=1280, help="Capture width")
    parser.add_argument("--height", type=int, default=720, help="Capture height")
    parser.add_argument(
        "--duration", type=float, default=5.0, help="Capture duration in seconds"
    )
    args = parser.parse_args()

    indices = resolve_indices(args.cameras)
    if not indices:
        print("No cameras found.")
        return

    print(f"SkellyCam Rust -- smoke test")
    print(f"  cameras      : {indices}")
    print(f"  resolution   : {args.width}x{args.height}")
    print(f"  duration     : {args.duration}s")
    print()

    mgr = _skellycam_rust.CameraGroupManager()

    configs = {}
    for idx in indices:
        configs[f"cam{idx}"] = {
            "camera_index": idx,
            "width": args.width,
            "height": args.height,
        }

    group_id = mgr.create_or_update_group(configs)
    print(f"Group created: {group_id}  ({len(indices)} camera(s))")
    print()

    print(f"Streaming for {args.duration}s...")
    print(f"{'time':>6s}  {'frame':>6s}  {'size':>7s}  {'timestamp':>12s}")
    print(f"{'-' * 6}  {'-' * 6}  {'-' * 7}  {'-' * 12}")

    start = time.time()
    last_fn = -1
    frame_count = 0

    while time.time() - start < args.duration:
        payloads = mgr.get_latest_frame_payloads()
        for gid, (fn, ts, jpeg_bytes) in payloads.items():
            if fn != last_fn:
                elapsed = time.time() - start
                print(
                    f"{elapsed:>5.1f}s  {fn:>6d}  "
                    f"{len(jpeg_bytes):>6d}B  {ts / 1e9:>9.3f}s"
                )
                last_fn = fn
                frame_count += 1
        time.sleep(0.01)

    elapsed = time.time() - start
    print()
    print(
        f"Capture complete: {frame_count} frames in {elapsed:.1f}s "
        f"({frame_count / elapsed:.1f} fps Python-side)"
    )
    print()

    mgr.close_all_groups()
    print("Shutdown complete.")


if __name__ == "__main__":
    main()
