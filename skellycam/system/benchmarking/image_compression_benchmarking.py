import itertools
import timeit
from io import BytesIO

import cv2
import numpy as np
import pandas as pd
from PIL import Image
from skimage import io as skimage_io
from tqdm import tqdm


def encode_cv2(img: np.ndarray, quality: int, format: str):
    if format == 'jpg':
        use_format = '.jpg'
    elif format == 'png':
        use_format = '.png'
    else:
        raise ValueError(f"Format {format} not recognized")

    success, encoded_img = cv2.imencode(use_format, img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    cv2_size = len(encoded_img.tobytes()) / 1000  # in kb
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
    pil_size = len(pil_img_bytes.getvalue()) / 1000  # in kb
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
    'encode_cv2' : encode_cv2,
    'encode_pillow': encode_pillow,
    'encode_skimage': encode_skimage
}


def read_and_encode_image(img, library, format, quality):
    assert img is not None, "Img cannot be None!"

    start_time = timeit.default_timer()
    buffer_size = encoding_functions[f'encode_{library}'](img, quality, format)
    elapsed = timeit.default_timer() - start_time
    return elapsed


def image_compression_benchmark():
    cap = cv2.VideoCapture(0)

    resolutions = [(1920, 1080), (1280, 720), (640, 480)]
    images = {}

    for resolution in resolutions:
        print(f"Grabbing frame at {resolution}")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])

        success, img = cap.read()

        if not success:
            raise Exception(f"Failed to read frame from camera - {resolution}!")

        images[resolution] = img

    cap.release()

    libraries = ['cv2', 'pillow', 'skimage']
    formats = ['jpg']  # , 'png']
    qualities =[20,  60, 100]  # Quality/compression levels (10-100)

    results = []
    total_iterations = len(libraries) * len(formats) * len(qualities) * len(resolutions)
    progress_bar = tqdm(total=total_iterations, dynamic_ncols=True)

    for library, image_format, quality, resolution in itertools.product(libraries, formats, qualities, resolutions):
        progress_bar.set_postfix({'library': library, 'format': image_format, 'quality': quality, 'resolution': resolution},
                                 refresh=True)
        img = images[resolution]
        times = [read_and_encode_image(img, library, image_format, quality) for _ in range(30)]
        results.append((library, image_format, quality, resolution, min(times), max(times), sum(times) / len(times)))
        progress_bar.update()

    progress_bar.close()

    df = pd.DataFrame(results,
                      columns=['Library', 'Format', 'Quality', 'Resolution', 'Min Time', 'Max Time', 'Avg Time'])
    print(df)


if __name__ == "__main__":
    print("Starting the test...")
    image_compression_benchmark()
