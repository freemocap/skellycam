import io
import time
from io import BytesIO
from typing import Tuple, List, Dict

import cv2
import numpy as np
import pandas as pd
import requests
from PIL import Image, ImageDraw, ImageFont


def generate_dummy_image(width: int, height: int) -> np.ndarray:
    return np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)


def load_high_res_image(url: str) -> np.ndarray:
    response = requests.get(url)
    img = Image.open(BytesIO(response.content))
    img_4k = img.resize((3840, 2160))
    return np.array(img_4k)


def compress_image_pil(image: Image.Image, quality: int) -> Tuple[float, np.ndarray]:
    buffer = io.BytesIO()
    start_time = time.perf_counter_ns()
    image.save(buffer, "JPEG", quality=quality)
    end_time = time.perf_counter_ns()
    buffer.seek(0)
    compressed_image = np.array(Image.open(buffer))
    elapsed_time_ms = (end_time - start_time) / 1e6
    return elapsed_time_ms, compressed_image


def compress_image_cv2(image: np.ndarray, quality: int) -> Tuple[float, np.ndarray]:
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    start_time = time.perf_counter_ns()
    _, encoded_img = cv2.imencode('.jpg', image, encode_param)
    end_time = time.perf_counter_ns()
    compressed_image = cv2.imdecode(encoded_img, cv2.IMREAD_COLOR)
    elapsed_time_ms = (end_time - start_time) / 1e6
    return elapsed_time_ms, compressed_image


def calculate_mean_difference(original: np.ndarray, compressed: np.ndarray) -> float:
    difference = np.mean(np.abs(original.astype(np.uint8) - compressed.astype(np.uint8)))
    return difference


def measure_compression_times(image: np.ndarray, qualities: List[int], iterations: int = 100) -> List[Dict[str, float]]:
    results = []
    pil_image = Image.fromarray(image)
    for quality in qualities:
        pil_times = []
        pil_diffs = []
        cv2_times = []
        cv2_diffs = []
        for _ in range(iterations):
            elapsed_time_ms, compressed_pil = compress_image_pil(pil_image, quality)
            pil_times.append(elapsed_time_ms)
            pil_diffs.append(calculate_mean_difference(image, compressed_pil))

            elapsed_time_ms, compressed_cv2 = compress_image_cv2(image, quality)
            cv2_times.append(elapsed_time_ms)
            cv2_diffs.append(calculate_mean_difference(image, compressed_cv2))

        pil_mean = np.mean(pil_times)
        pil_std = np.std(pil_times)
        pil_diff = np.mean(pil_diffs)
        cv2_mean = np.mean(cv2_times)
        cv2_std = np.std(cv2_times)
        cv2_diff = np.mean(cv2_diffs)
        results.append({'Quality': quality, 'PIL_Time(ms)': f"{pil_mean:.2f} ({pil_std:.2f})",
                        'PIL_Difference': pil_diff, 'CV2_Time(ms)': f"{cv2_mean:.2f} ({cv2_std:.2f})",
                        'CV2_Difference': cv2_diff})
        print(f"Quality: {quality}, PIL Time: {pil_mean:.2f} ({pil_std:.2f}) ms, PIL Diff: {pil_diff:.2f}, "
              f"CV2 Time: {cv2_mean:.2f} ({cv2_std:.2f}) ms, CV2 Diff: {cv2_diff:.2f} over {iterations} iterations")
    return results


def create_composite_image(original: np.ndarray, compressed_images: List[Tuple[str, np.ndarray]],
                           output_path: str) -> None:
    height, width, _ = original.shape
    composite_width = width * (len(compressed_images) + 1)
    composite_height = height

    composite_image = Image.new('RGB', (composite_width, composite_height))
    draw = ImageDraw.Draw(composite_image)

    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font = ImageFont.load_default()

    original_pil = Image.fromarray(original)
    composite_image.paste(original_pil, (0, 0))
    draw.text((10, 10), "Original", (255, 255, 255), font=font)

    for i, (label, img) in enumerate(compressed_images):
        img_pil = Image.fromarray(img)
        composite_image.paste(img_pil, ((i + 1) * width, 0))
        draw.text(((i + 1) * width + 10, 10), label, (255, 255, 255), font=font)

    composite_image.save(output_path)


if __name__ == "__main__":
    sizes = [(640, 480), (1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)]  # Different resolutions
    qualities = [10, 30, 50, 70, 90]
    iterations = 20  # Number of iterations to average the time
    print("Measuring compression times for different image sizes and qualities...")

    # Measure with a real image
    print("\n--- Measuring with Real Images ---")
    sample_image_url = 'https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57723/globe_west_2048.jpg'
    sample_image = load_high_res_image(sample_image_url)
    sample_image_resized = [cv2.resize(sample_image, (width, height)) for width, height in sizes]
    data_real = []
    for img, (width, height) in zip(sample_image_resized, sizes):
        print(f"\nMeasuring compression times for image size {width}x{height}...")
        compression_times = measure_compression_times(img, qualities, iterations)
        for result in compression_times:
            result.update({'Width': width, 'Height': height})
            data_real.append(result)
    results_df_real = pd.DataFrame(data_real)

    print("\n--- Compression times DataFrame for Real Images ---")
    print(results_df_real.to_string(index=False))

    # Create and save composite images for one of the sizes
    width, height = sizes[-1]  # Use the largest size for the composite image
    img = cv2.resize(sample_image, (width, height))
    compressed_images = []
    for quality in qualities:
        _, compressed_pil = compress_image_pil(Image.fromarray(img), quality)
        compressed_images.append((f'PIL {quality}', compressed_pil))

        _, compressed_cv2 = compress_image_cv2(img, quality)
        compressed_images.append((f'CV2 {quality}', compressed_cv2))

    create_composite_image(img, compressed_images, "/tmp/composite_image.jpg")