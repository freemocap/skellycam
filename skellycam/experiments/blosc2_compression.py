import blosc2
import numpy as np
import time
from tabulate import tabulate

# Initialize data for different resolutions
resolutions = {
    '480p': (480, 640, 3),
    '720p': (720, 1280, 3),
    '1080p': (1080, 1920, 3)
}

# Prepare table
table = [["Resolution", "Original Size (kB)", "Compressed Size (kB)", "Compression Ratio", "Compression Time (ms)"]]

for res, shape in resolutions.items():
    dummy_image = np.random.randint(0, 256, shape, dtype=np.uint8)
    cparams = {"typesize": 1}

    # Compress dummy_image - start timing
    start_time = time.perf_counter()
    compressed = blosc2.pack_tensor(dummy_image)
    elapsed_time = time.perf_counter() - start_time

    # Calculate sizes and compression ratio
    original_size = dummy_image.nbytes / 1024
    compressed_size = len(compressed) / 1024
    compression_ratio = original_size / compressed_size

    # Append to table
    table.append([res, original_size, compressed_size, compression_ratio, elapsed_time * 1000])

# Output table
print(tabulate(table, headers='firstrow', tablefmt='pretty'))