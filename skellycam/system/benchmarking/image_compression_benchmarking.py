import itertools
import time
import timeit
from io import BytesIO
from typing import List

import cv2
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from PIL import Image
from skimage import io as skimage_io
from tqdm import tqdm

def grab_sample_frames(resolutions,
                       number_of_frames:int,
                       camera_number:int=0):

    cap = cv2.VideoCapture(camera_number)
    images_and_durations_by_resolution = {}
    for resolution in resolutions:
        print(f"Grabbing frame at {resolution}")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
        success, img = cap.read()

        images_and_durations_by_resolution[resolution] = {"images":[],
                                            "grab_duration_ns":[]}

        for _ in range(number_of_frames):
            start_time = time.process_time_ns()
            success, img = cap.read()
            elapsed_ns = time.perf_counter_ns() - start_time

            if not success:
                raise Exception(f"Failed to read frame from camera - {resolution}!")
            images_and_durations_by_resolution[resolution]["images"].append(img)
            images_and_durations_by_resolution[resolution]["grab_duration_ns"].append(elapsed_ns)


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


def read_and_encode_image(image:np.ndarray, library:str, format:str, quality:int):

    start_time = timeit.default_timer()
    buffer_size = encoding_functions[f'encode_{library}'](image, quality, format)
    elapsed_sec = timeit.default_timer() - start_time
    elapsed_ms = elapsed_sec * 1000
    return elapsed_ms, buffer_size


def image_compression_benchmark():
    resolutions = [(1920, 1080), (1280, 720), (640, 480)]
    libraries = ['cv2', 'pillow', 'skimage']
    image_formats = ['jpg']#, 'png']
    qualities = [20, 60, 100]  # Quality/compression levels (10-100)


    images_and_durations_by_resolution = grab_sample_frames(resolutions = resolutions,
                                              number_of_frames=30)

    results = {}
    total_iterations = len(libraries) * len(image_formats) * len(qualities) * len(resolutions)
    progress_bar = tqdm(total=total_iterations, dynamic_ncols=True)

    for library, image_format, quality, resolution in itertools.product(libraries, image_formats, qualities, resolutions):
        progress_bar.set_postfix(
            {'library': library, 'format': image_format, 'quality': quality, 'resolution': resolution},
            refresh=True)

        images, _ = images_and_durations_by_resolution[resolution].items()

        times_and_sizes = [read_and_encode_image(image, library, image_format, quality) for image in images[1]]
        if library not in results:
            results[library] = {}
        results[library][image_format] = {
            'quality': quality,
            'resolution': resolution,
            'times': [entry[0] for entry in times_and_sizes],
            'sizes': [entry[1] for entry in times_and_sizes],
        }

        progress_bar.update()

    progress_bar.close()


    df = pd.DataFrame.from_dict(results, orient="index")

    print(df)

    # caluclate means and std and print in a nicely formatted table
    for library in libraries:
        for image_format in image_formats:
            df.loc[library, image_format, 'mean_time'] = df.loc[library, image_format, 'times'].mean()
            df.loc[library, image_format, 'std_time'] = df.loc[library, image_format, 'times'].std()
            df.loc[library, image_format, 'mean_size'] = df.loc[library, image_format, 'sizes'].mean()
            df.loc[library, image_format, 'std_size'] = df.loc[library, image_format, 'sizes'].std()
    #now print just a nice summary table with means and stds
    print("\n---------------------------------------------------\n"
          "Summary Table:")
    print(df.loc[:, :, ['mean_time', 'std_time', 'mean_size', 'std_size']])

    return results




def plot_image_compression_benchmarks(results: dict):
    fig = go.Figure()

    marker_dict = {'jpg': 'circle', 'png': 'square'}

    for library, library_results in results.items():
        for image_format, format_results in library_results.items():
            fig.add_trace(go.Scatter(
                x=format_results['times'],
                y=format_results['sizes'],
                mode='markers',
                marker=dict(
                    size=10,
                    symbol=marker_dict[image_format]
                ),
                name=f'{library} - {image_format}'
            ))
    fig.update_layout(
        title='Image Compression Times/Sizes By Library and Format',
        xaxis_title='Time (sec)',
        yaxis_title='Size (bytes)',
        showlegend=True,
    )
    fig.show()
    f = 9


if __name__ == "__main__":
    print("Starting the test...")
    benchmarking_results = image_compression_benchmark()
    plot_image_compression_benchmarks(benchmarking_results)
