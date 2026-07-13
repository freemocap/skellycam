"""Estimate raw in-RAM memory for an unbounded per-frame recording buffer.

Does not allocate anything -- pure arithmetic, for sizing decisions and for
reasoning about the memory-repair sprint's regression tests.
"""
import argparse
from dataclasses import dataclass


@dataclass
class RecordingMemoryEstimate:
    frame_bytes: int
    frames_per_camera: int
    total_frames: int
    raw_bytes: int
    raw_with_copy_multiplier_bytes: int

    @property
    def raw_gib(self) -> float:
        return self.raw_bytes / (1024 ** 3)

    @property
    def raw_with_copy_multiplier_gib(self) -> float:
        return self.raw_with_copy_multiplier_bytes / (1024 ** 3)


def estimate_recording_memory(
        width: int,
        height: int,
        channels: int,
        fps: float,
        duration_seconds: float,
        camera_count: int,
        copy_multiplier: float,
) -> RecordingMemoryEstimate:
    """copy_multiplier accounts for transient duplicates (e.g. deepcopy() at
    Stop) that coexist with the original buffer for a period of time. Use
    1.0 for steady-state accumulation only, 2.0 to model a single full
    deepcopy of the buffer existing alongside the original."""
    frame_bytes = width * height * channels
    frames_per_camera = round(fps * duration_seconds)
    total_frames = frames_per_camera * camera_count
    raw_bytes = frame_bytes * total_frames
    raw_with_copy_multiplier_bytes = round(raw_bytes * copy_multiplier)

    return RecordingMemoryEstimate(
        frame_bytes=frame_bytes,
        frames_per_camera=frames_per_camera,
        total_frames=total_frames,
        raw_bytes=raw_bytes,
        raw_with_copy_multiplier_bytes=raw_with_copy_multiplier_bytes,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--channels", type=int, default=3)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--duration", type=float, default=89.0,
                         help="recording duration in seconds")
    parser.add_argument("--cameras", type=int, default=1)
    parser.add_argument("--copy-multiplier", type=float, default=1.0,
                         help="1.0 = steady-state buffer only; "
                              "2.0 = models a full deepcopy() coexisting "
                              "with the original at Stop")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    estimate = estimate_recording_memory(
        width=args.width,
        height=args.height,
        channels=args.channels,
        fps=args.fps,
        duration_seconds=args.duration,
        camera_count=args.cameras,
        copy_multiplier=args.copy_multiplier,
    )

    print(f"Frame size: {estimate.frame_bytes:,} bytes "
          f"({estimate.frame_bytes / (1024 ** 2):.2f} MiB)")
    print(f"Frames per camera: {estimate.frames_per_camera:,}")
    print(f"Total frames ({args.cameras} camera(s)): {estimate.total_frames:,}")
    print(f"Estimated raw buffer: {estimate.raw_bytes:,} bytes "
          f"({estimate.raw_gib:.2f} GiB)")
    if args.copy_multiplier != 1.0:
        print(f"With copy_multiplier={args.copy_multiplier}: "
              f"{estimate.raw_with_copy_multiplier_bytes:,} bytes "
              f"({estimate.raw_with_copy_multiplier_gib:.2f} GiB)")


if __name__ == "__main__":
    main()
