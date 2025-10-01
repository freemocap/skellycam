import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
import time
from dataclasses import dataclass
import tempfile
from io import BytesIO
from PIL import Image


@dataclass
class BenchmarkResult:
    """Store benchmark results for a single test."""
    test_name: str
    write_time: float
    read_time: float
    file_size_mb: float
    data_shape: tuple[int, ...]
    compression: str
    storage_format: str  # 'parquet' or 'jpeg'


def benchmark_write_parquet_binary(
        *,
        data: np.ndarray,
        filepath: Path,
        compression: str = "snappy"
) -> float:
    """Benchmark write operation storing raw binary data."""
    start = time.perf_counter()

    # Store each frame as a binary blob
    df = pd.DataFrame(data={
        'frame_id': np.arange(data.shape[0]),
        'data': [frame.tobytes() for frame in data]
    })

    df.to_parquet(path=filepath, compression=compression, engine="pyarrow")
    end = time.perf_counter()
    return end - start


def benchmark_read_parquet_binary(*, filepath: Path, shape: tuple[int, ...]) -> float:
    """Benchmark read operation and reconstruct array."""
    start = time.perf_counter()
    df = pd.read_parquet(path=filepath, engine="pyarrow")

    # Reconstruct the array
    dtype = np.uint8 if len(shape) == 4 else np.uint16
    _ = np.array(
        [np.frombuffer(data, dtype=dtype).reshape(shape[1:]) for data in df['data']],
        dtype=dtype
    )
    end = time.perf_counter()
    return end - start


def benchmark_write_parquet_jpeg(
        *,
        data: np.ndarray,
        filepath: Path,
        compression: str = "snappy",
        jpeg_quality: int = 95
) -> float:
    """Benchmark write operation with JPEG encoding."""
    start = time.perf_counter()

    jpeg_blobs: list[bytes] = []
    for frame in data:
        # Convert to PIL Image and encode as JPEG
        if frame.shape[-1] == 1:
            # Grayscale
            img = Image.fromarray(obj=frame.squeeze(), mode='L')
        else:
            # RGB
            img = Image.fromarray(obj=frame, mode='RGB')

        buffer = BytesIO()
        img.save(fp=buffer, format='JPEG', quality=jpeg_quality)
        jpeg_blobs.append(buffer.getvalue())

    df = pd.DataFrame(data={
        'frame_id': np.arange(data.shape[0]),
        'jpeg_data': jpeg_blobs
    })

    df.to_parquet(path=filepath, compression=compression, engine="pyarrow")
    end = time.perf_counter()
    return end - start


def benchmark_read_parquet_jpeg(*, filepath: Path, shape: tuple[int, ...]) -> float:
    """Benchmark read operation with JPEG decoding."""
    start = time.perf_counter()
    df = pd.read_parquet(path=filepath, engine="pyarrow")

    # Decode JPEG blobs
    frames: list[np.ndarray] = []
    for jpeg_data in df['jpeg_data']:
        buffer = BytesIO(jpeg_data)
        img = Image.open(fp=buffer)
        frame = np.array(img)
        if len(shape) == 4 and shape[-1] == 1:
            frame = frame.reshape(shape[1:])
        frames.append(frame)

    _ = np.array(frames)
    end = time.perf_counter()
    return end - start


def get_file_size_mb(*, filepath: Path) -> float:
    """Get file size in megabytes."""
    return filepath.stat().st_size / (1024 * 1024)


def create_3d_volume_data(
        *,
        shape: tuple[int, int, int],
        dtype: type = np.uint16
) -> np.ndarray:
    """Create synthetic 3D volume data (e.g., medical imaging, volumetric data)."""
    return np.random.randint(low=0, high=4096, size=shape, dtype=dtype)


def create_camera_frames(
        *,
        num_frames: int,
        height: int,
        width: int,
        channels: int = 3,
        dtype: type = np.uint8
) -> np.ndarray:
    """Create synthetic camera frame data."""
    return np.random.randint(
        low=0, high=256, size=(num_frames, height, width, channels), dtype=dtype
    )


def run_benchmark_parquet(
        *,
        test_name: str,
        data: np.ndarray,
        shape: tuple[int, ...],
        compression: str = "snappy",
        temp_dir: Path
) -> BenchmarkResult:
    """Run a benchmark test with raw binary storage."""
    filepath = temp_dir / f"{test_name.replace(' ', '_').replace('(', '').replace(')', '')}_raw.parquet"

    write_time = benchmark_write_parquet_binary(data=data, filepath=filepath, compression=compression)
    file_size = get_file_size_mb(filepath=filepath)
    read_time = benchmark_read_parquet_binary(filepath=filepath, shape=shape)

    filepath.unlink()

    return BenchmarkResult(
        test_name=test_name,
        write_time=write_time,
        read_time=read_time,
        file_size_mb=file_size,
        data_shape=shape,
        compression=compression,
        storage_format="parquet-raw"
    )


def run_benchmark_parquet_jpeg(
        *,
        test_name: str,
        data: np.ndarray,
        shape: tuple[int, ...],
        compression: str = "snappy",
        temp_dir: Path,
        jpeg_quality: int = 95
) -> BenchmarkResult:
    """Run a benchmark test with JPEG encoding."""
    filepath = temp_dir / f"{test_name.replace(' ', '_').replace('(', '').replace(')', '')}_jpeg.parquet"

    write_time = benchmark_write_parquet_jpeg(
        data=data,
        filepath=filepath,
        compression=compression,
        jpeg_quality=jpeg_quality
    )
    file_size = get_file_size_mb(filepath=filepath)
    read_time = benchmark_read_parquet_jpeg(filepath=filepath, shape=shape)

    filepath.unlink()

    return BenchmarkResult(
        test_name=test_name,
        write_time=write_time,
        read_time=read_time,
        file_size_mb=file_size,
        data_shape=shape,
        compression=compression,
        storage_format="parquet-jpeg"
    )


def print_results_table(*, results: list[BenchmarkResult]) -> None:
    """Print a nicely formatted results table."""
    rows: list[dict[str, str | float]] = []

    for r in results:
        num_frames = r.data_shape[0]

        # Calculate per-frame metrics
        write_fps = num_frames / r.write_time if r.write_time > 0 else 0
        read_fps = num_frames / r.read_time if r.read_time > 0 else 0
        write_ms_per_frame = (r.write_time * 1000) / num_frames if num_frames > 0 else 0
        read_ms_per_frame = (r.read_time * 1000) / num_frames if num_frames > 0 else 0

        # Calculate data size
        element_size = 1 if len(r.data_shape) == 4 else 2
        data_size_mb = np.prod(r.data_shape) * element_size / (1024 * 1024)
        compression_ratio = data_size_mb / r.file_size_mb if r.file_size_mb > 0 else 0

        rows.append({
            "Test": r.test_name,
            "Format": r.storage_format,
            "Frames": num_frames,
            "Write FPS": f"{write_fps:.1f}",
            "Read FPS": f"{read_fps:.1f}",
            "Write ms/frame": f"{write_ms_per_frame:.2f}",
            "Read ms/frame": f"{read_ms_per_frame:.2f}",
            "Size (MB)": f"{r.file_size_mb:.2f}",
            "Ratio": f"{compression_ratio:.2f}x"
        })

    df = pd.DataFrame(data=rows)

    print("\n" + "=" * 140)
    print("PARQUET vs JPEG PERFORMANCE BENCHMARK - PER FRAME METRICS")
    print("=" * 140)
    print(df.to_string(index=False))
    print("=" * 140)
    print(f"\nTotal tests: {len(results)}")

    # Group by format
    parquet_raw = [r for r in results if r.storage_format == "parquet-raw"]
    parquet_jpeg = [r for r in results if r.storage_format == "parquet-jpeg"]

    if parquet_raw:
        avg_write_fps = np.mean([r.data_shape[0] / r.write_time for r in parquet_raw])
        avg_read_fps = np.mean([r.data_shape[0] / r.read_time for r in parquet_raw])
        print(f"\nParquet-Raw Average: {avg_write_fps:.1f} write FPS, {avg_read_fps:.1f} read FPS")

    if parquet_jpeg:
        avg_write_fps = np.mean([r.data_shape[0] / r.write_time for r in parquet_jpeg])
        avg_read_fps = np.mean([r.data_shape[0] / r.read_time for r in parquet_jpeg])
        print(f"Parquet-JPEG Average: {avg_write_fps:.1f} write FPS, {avg_read_fps:.1f} read FPS")

    print("=" * 140 + "\n")


def main() -> None:
    """Run all benchmarks."""
    results: list[BenchmarkResult] = []

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        print("Starting Parquet vs JPEG benchmarks...\n")

        # Test 1: Camera frames - 100 frames of 1920x1080 RGB
        print("Test 1: Camera 1080p (100 frames) - Raw binary...")
        camera_data = create_camera_frames(
            num_frames=100,
            height=1080,
            width=1920,
            channels=3
        )
        results.append(run_benchmark_parquet(
            test_name="Camera 1080p RGB",
            data=camera_data,
            shape=(100, 1080, 1920, 3),
            compression="snappy",
            temp_dir=temp_path
        ))

        print("Test 1b: Camera 1080p (100 frames) - JPEG encoded...")
        results.append(run_benchmark_parquet_jpeg(
            test_name="Camera 1080p RGB",
            data=camera_data,
            shape=(100, 1080, 1920, 3),
            compression="snappy",
            temp_dir=temp_path,
            jpeg_quality=95
        ))

        # Test 2: Smaller camera frames
        print("\nTest 2: Camera 640x480 (100 frames) - Raw binary...")
        small_camera_data = create_camera_frames(
            num_frames=100,
            height=480,
            width=640,
            channels=3
        )
        results.append(run_benchmark_parquet(
            test_name="Camera 640x480 RGB",
            data=small_camera_data,
            shape=(100, 480, 640, 3),
            compression="snappy",
            temp_dir=temp_path
        ))

        print("Test 2b: Camera 640x480 (100 frames) - JPEG encoded...")
        results.append(run_benchmark_parquet_jpeg(
            test_name="Camera 640x480 RGB",
            data=small_camera_data,
            shape=(100, 480, 640, 3),
            compression="snappy",
            temp_dir=temp_path,
            jpeg_quality=95
        ))

        # Test 3: Grayscale camera
        print("\nTest 3: Camera 1080p Grayscale (100 frames) - Raw binary...")
        gray_camera_data = create_camera_frames(
            num_frames=100,
            height=1080,
            width=1920,
            channels=1
        )
        results.append(run_benchmark_parquet(
            test_name="Camera 1080p Grayscale",
            data=gray_camera_data,
            shape=(100, 1080, 1920, 1),
            compression="snappy",
            temp_dir=temp_path
        ))

        print("Test 3b: Camera 1080p Grayscale (100 frames) - JPEG encoded...")
        results.append(run_benchmark_parquet_jpeg(
            test_name="Camera 1080p Grayscale",
            data=gray_camera_data,
            shape=(100, 1080, 1920, 1),
            compression="snappy",
            temp_dir=temp_path,
            jpeg_quality=95
        ))

        # Test 4: High frame count
        print("\nTest 4: Camera 320x240 (1000 frames) - Raw binary...")
        many_frames_data = create_camera_frames(
            num_frames=1000,
            height=240,
            width=320,
            channels=3
        )
        results.append(run_benchmark_parquet(
            test_name="Camera 320x240 RGB",
            data=many_frames_data,
            shape=(1000, 240, 320, 3),
            compression="snappy",
            temp_dir=temp_path
        ))

        print("Test 4b: Camera 320x240 (1000 frames) - JPEG encoded...")
        results.append(run_benchmark_parquet_jpeg(
            test_name="Camera 320x240 RGB",
            data=many_frames_data,
            shape=(1000, 240, 320, 3),
            compression="snappy",
            temp_dir=temp_path,
            jpeg_quality=95
        ))

        # Test 5: Lower JPEG quality
        print("\nTest 5: Camera 640x480 (100 frames) - JPEG Q=85...")
        results.append(run_benchmark_parquet_jpeg(
            test_name="Camera 640x480 RGB (Q85)",
            data=small_camera_data,
            shape=(100, 480, 640, 3),
            compression="snappy",
            temp_dir=temp_path,
            jpeg_quality=85
        ))

        print("\nTest 6: Camera 640x480 (100 frames) - JPEG Q=75...")
        results.append(run_benchmark_parquet_jpeg(
            test_name="Camera 640x480 RGB (Q75)",
            data=small_camera_data,
            shape=(100, 480, 640, 3),
            compression="snappy",
            temp_dir=temp_path,
            jpeg_quality=75
        ))

    # Print results
    print_results_table(results=results)


if __name__ == "__main__":
    main()