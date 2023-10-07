import io
import logging
import time
from pathlib import Path

import cv2
import pandas as pd
from PIL import Image
from skimage import io as skimage_io

from skellycam import configure_logging
from skellycam.system.environment.default_paths import get_benchmarking_path

configure_logging()
logger = logging.getLogger(__name__)


def benchmark():
    number_of_frames = 30
    resolutions = [(1920, 1080), (1280, 720), (640, 480)]
    image_save_path = Path(get_benchmarking_path())

    benchmarks_by_resolution = {}

    cap = cv2.VideoCapture(0)

    for resolution in resolutions:
        benchmark_frame_values = {
            "Original Size (kB)": [],
            "OpenCV-duration (ms)": [],
            "OpenCV-size (kB)": [],
            "Pillow-duration (ms)": [],
            "Pillow-size (kB)": [],
            "skimage-duration (ms)": [],
            "skimage-size (kB)": [],
        }
        benchmarks_by_resolution[str(resolution)] = benchmark_frame_values

        width, height = resolution
        logger.info(f"Setting resolution to ({width}, {height})...")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        for _ in range(number_of_frames):
            success, img = cap.read()

            if not success:
                raise Exception(f"Failed to read frame from camera - ({width}, {height})!")
            assert img.shape == (height, width, 3), f"img shape: {img.shape}, should be ({height}, {width}, 3)"

            original_size = len(img.tobytes()) / 1000  # in kilobytes
            benchmark_frame_values["Original Size (kB)"].append(original_size)

            # OpenCV Benchmark
            tik = time.perf_counter_ns()
            success, encoded_img = cv2.imencode(".jpg", img)
            tok = time.perf_counter_ns()
            assert success, f"Failed to encode img to JPEG using cv2!"

            cv2_duration = (tok - tik) / 1e6  # convert to ms
            cv2_size = len(encoded_img.tobytes()) / 1000  # in kilobytes
            benchmark_frame_values["OpenCV-duration (ms)"].append(cv2_duration)
            benchmark_frame_values["OpenCV-size (kB)"].append(cv2_size)

            # Pillow benchmark
            tik = time.perf_counter_ns()
            pil_img = Image.fromarray(img)
            pil_img_bytes = io.BytesIO()
            pil_img.save(pil_img_bytes, format='JPEG')
            tok = time.perf_counter_ns()
            assert pil_img_bytes is not None, f"Failed to encode img to JPEG using Pillow!"

            pil_duration = (tok - tik) / 1e6  # convert to ms
            pil_size = len(pil_img_bytes.getvalue()) / 1000  # in kilobytes
            benchmark_frame_values["Pillow-duration (ms)"].append(pil_duration)
            benchmark_frame_values["Pillow-size (kB)"].append(pil_size)

            # scikit-image benchmark
            tik = time.perf_counter_ns()

            # Compress the image and save it into memory
            with io.BytesIO() as buffer:
                skimage_io.imsave(buffer, img, format='jpeg')
                buffer.seek(0)
                skimage_size = len(buffer.read()) / 1000  # size in kilobytes

            tok = time.perf_counter_ns()

            skimage_duration = (tok - tik) / 1e6  # convert to ms
            benchmark_frame_values["skimage-duration (ms)"].append(skimage_duration)
            benchmark_frame_values["skimage-size (kB)"].append(skimage_size)
    cap.release()

    df = pd.DataFrame.from_dict(benchmarks_by_resolution, orient='index')
    averages = df.map(lambda x: pd.Series(x).mean())
    std_devs = df.map(lambda x: pd.Series(x).std())

    # Set the float format to 2 decimal places
    pd.options.display.float_format = '{:.2f}'.format

    # Use to_string() for pretty print
    print("Means:\n", averages.to_string(), "\n")
    # print("Standard Deviations:\n", std_devs.to_string())


if __name__ == "__main__":
    benchmark()
