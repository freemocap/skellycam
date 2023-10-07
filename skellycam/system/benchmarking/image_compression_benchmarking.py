import itertools
import time
import timeit
from collections import defaultdict
from io import BytesIO
from typing import List, Tuple

import cv2
import numpy as np
import pandas as pd
from PIL import Image
from skimage import io as skimage_io
from tabulate import tabulate
from tqdm import tqdm

from skellycam.backend.utilities.magic_nested_dict import MagicTreeDict


def grab_sample_frames(resolutions,
                       number_of_frames: int,
                       camera_number: int = 0):
    cap = cv2.VideoCapture(camera_number)
    images_and_durations_by_resolution = MagicTreeDict()
    for resolution in resolutions:
        print(f"Grabbing frame at {resolution}")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
        success, img = cap.read()

        images = []
        grab_durations = []

        for _ in range(number_of_frames):
            start_time = time.process_time()
            success, img = cap.read()
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            if not success:
                raise Exception(f"Failed to read frame from camera - {resolution}!")
            images.append(img)
            grab_durations.append(elapsed_ms)
        images_and_durations_by_resolution[resolution]["images"] = images
        images_and_durations_by_resolution[resolution]["grab_durations"] = grab_durations

    cap.release()
    return images_and_durations_by_resolution


def encode_cv2(img: np.ndarray, quality: int, format: str):
    if format == 'jpg':
        use_format = '.jpg'
    elif format == 'png':
        use_format = '.png'
    else:
        raise ValueError(f"Format {format} not recognized")

    success, encoded_img = cv2.imencode(use_format, img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    cv2_size = len(encoded_img.tobytes()) / 1000  # in kB
    return cv2_size


def encode_pillow(img: np.ndarray, quality: int, format: str):
    if format == 'jpg':
        use_format = 'JPEG'
    elif format == 'png':
        use_format = 'PNG'
    else:
        raise ValueError(f"Format {format} not recognized")

    pil_img = Image.fromarray(img)
    pil_img_bytes = BytesIO()
    pil_img.save(pil_img_bytes, use_format, quality=quality)
    pil_size = len(pil_img_bytes.getvalue()) / 1000  # in kB
    return pil_size


def encode_skimage(img: np.ndarray, quality: int, format: str):
    if format == 'jpg':
        use_format = 'jpeg'
    elif format == 'png':
        use_format = 'png'
    else:
        raise ValueError(f"Format {format} not recognized")

    with BytesIO() as buffer:
        skimage_io.imsave(buffer, img, format=use_format)
        buffer.seek(0)
        skimage_size = len(buffer.read()) / 1000  # size in kilobytes
    return skimage_size


encoding_functions = {
    'encode_cv2': encode_cv2,
    'encode_pillow': encode_pillow,
    'encode_skimage': encode_skimage
}


def read_and_encode_image(image: np.ndarray, library: str, format: str, quality: int):
    start_time = timeit.default_timer()
    buffer_size = encoding_functions[f'encode_{library}'](image, quality, format)
    elapsed_sec = timeit.default_timer() - start_time
    elapsed_ms = elapsed_sec * 1000
    return elapsed_ms, buffer_size


def create_nested_dict() -> defaultdict:
    return defaultdict(create_nested_dict)


def defaultdict_to_dict(d):
    if isinstance(d, defaultdict):
        d = {k: defaultdict_to_dict(v) for k, v in d.items()}
    return d


def calculate_tree_stats(data_tree: MagicTreeDict,
                         libraries: List[str],
                         qualities: List[int],
                         resolutions: List[Tuple[int, int]], image_formats: List[str]) -> MagicTreeDict:
    stats_tree = MagicTreeDict()
    for library, resolution, quality, format_ in itertools.product(libraries, resolutions, qualities, image_formats):
        leaf = data_tree[library][resolution][quality][format_]
        leaf['mean_time'] = np.mean(leaf['times'])
        leaf['std_time'] = np.std(leaf['times'])

        leaf['mean_size'] = np.mean(leaf['sizes'])
        leaf['std_size'] = np.std(leaf['sizes'])
    return stats_tree


def image_compression_benchmark() -> defaultdict:
    resolutions = [(1920, 1080), (1280, 720), (640, 480)]
    libraries = ['cv2', 'pillow', 'skimage']
    image_formats = ['jpg']
    qualities = [20, 60, 100]

    images_and_durations_by_resolution = grab_sample_frames(resolutions=resolutions, number_of_frames=30)

    compression_results = MagicTreeDict()
    camera_stats_results = MagicTreeDict()

    total_iterations = len(libraries) * len(image_formats) * len(qualities) * len(resolutions)
    progress_bar = tqdm(total=total_iterations, dynamic_ncols=True)

    for library, format_, quality, resolution in itertools.product(libraries, image_formats, qualities, resolutions):
        progress_bar.set_postfix({'library': library, 'format': format_, 'quality': quality, 'resolution': resolution},
                                 refresh=True)

        images, grab_duration_ms = images_and_durations_by_resolution[resolution].items()
        times_and_sizes = [read_and_encode_image(image, library, format_, quality) for image in images[1]]

        compression_results[library][resolution][quality][format_] = {'times': [entry[0] for entry in times_and_sizes],
                                                                      'sizes': [entry[1] for entry in times_and_sizes]}

        camera_stats_results[library][resolution][quality] = {'grab_duration_ms': grab_duration_ms}

        progress_bar.update()

    progress_bar.close()

    processed_results = calculate_means_and_stds(compression_results, libraries, qualities, resolutions, image_formats)

    df = pd.DataFrame(processed_results).transpose()
    df.index.names = ['library', 'format', 'quality', 'resolution']

    print("\n---------------------------------------------------\nSummary Table:")
    print(tabulate(df.reset_index(), headers='keys', tablefmt='grid'))

    return compression_results


if __name__ == "__main__":
    print("Starting the test...")
    benchmarking_results = image_compression_benchmark()
