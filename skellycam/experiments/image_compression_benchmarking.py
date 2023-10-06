import cv2
import time
from PIL import Image
import numpy as np
import io
import pandas as pd

from skellycam import configure_logging
import logging

configure_logging()
logger = logging.getLogger(__name__)

resolutions = [(1920, 1080), (1280, 720), (640, 480)]
benchmark_values = {
    "Resolution": [],
    "Original Size": [],
    "OpenCV-duration": [],
    "OpenCV-size": [],
    "Pillow-duration": [],
    "Pillow-size": []
}

cap = cv2.VideoCapture(0)

for width, height in resolutions:
    logger.info(f"Setting resolution to ({width}, {height})...")

    benchmark_values["Resolution"].append(f'{width}x{height}')

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    success, img = cap.read()

    if not success:
        raise Exception(f"Failed to read frame from camera - ({width}, {height})!")
    assert img.shape == (height, width, 3), f"img shape: {img.shape}, should be ({height}, {width}, 3)"
    logger.success(f"Successfully read frame from camera - img.shape: {img.shape}")

    benchmark_values["Original Size"].append(len(img.tobytes()))

    # OpenCV Benchmark
    tik = time.perf_counter()
    success, encoded_img = cv2.imencode(".jpg", img)
    tok = time.perf_counter()
    cv2_duration = tok - tik
    assert success, f"Failed to encode img to JPEG using cv2!"
    logger.success(
        f"Successfully encoded img to JPEG using cv2,"
        f" duration: {cv2_duration:.3f} seconds,"
        f" final size: {len(encoded_img)} bytes")

    benchmark_values["OpenCV-duration"].append(cv2_duration)
    benchmark_values["OpenCV-size"].append(len(encoded_img))

    # Pillow benchmark
    tik_pil = time.perf_counter()
    pil_img = Image.fromarray(img)
    pil_img_bytes = io.BytesIO()
    pil_img.save(pil_img_bytes, format='JPEG')

    tok_pil = time.perf_counter()
    pil_duration = tok_pil - tik_pil
    logger.success(
        f"Successfully created PIL Image from img, "
        f"duration: {tok_pil - tik_pil:.3f} seconds,"
        f" final size: {len(pil_img_bytes.getvalue())} bytes")

    benchmark_values["Pillow-duration"].append(pil_duration)
    benchmark_values["Pillow-size"].append(len(pil_img_bytes.getvalue()))


df = pd.DataFrame(benchmark_values)
print(df.to_string(index=False))