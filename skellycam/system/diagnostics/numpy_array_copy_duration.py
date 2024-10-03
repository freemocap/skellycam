import time

import numpy as np

# Create a fake 1080p image with random values
fake_image = np.random.randint(0, 256, (1080, 1920, 3), dtype=np.uint8)

# Array to store durations
copy_durations = np.zeros(int(1e3), dtype=np.int64)
loop_durations = np.zeros(int(1e3), dtype=np.int64)
loop_minus_copy_durations = np.zeros(int(1e3), dtype=np.int64)

loop_start_time = time.perf_counter_ns()
for i in range(int(1e3)):
    start_time = time.perf_counter_ns()
    copied_image = fake_image.copy()
    end_time = time.perf_counter_ns()
    copy_durations[i] = end_time - start_time
    loop_durations[i] = end_time - loop_start_time
    loop_start_time = end_time

loop_minus_copy_durations = loop_durations - copy_durations

# Calculate statistics using numpy
mean_copy_duration_us = np.mean(copy_durations) / 1e3
median_copy_duration_us = np.median(copy_durations) / 1e3
std_copy_duration_us = np.std(copy_durations) / 1e3
mad_copy_duration_us = np.median(np.abs(copy_durations - np.median(copy_durations))) / 1e3

mean_loop_duration_us = np.mean(loop_durations) / 1e3
median_loop_duration_us = np.median(loop_durations) / 1e3
std_loop_duration_us = np.std(loop_durations) / 1e3
mad_loop_duration_us = np.median(np.abs(loop_durations - np.median(loop_durations))) / 1e3

mean_loop_minus_copy_duration_us = np.mean(loop_minus_copy_durations) / 1e3
median_loop_minus_copy_duration_us = np.median(loop_minus_copy_durations) / 1e3
std_loop_minus_copy_duration_us = np.std(loop_minus_copy_durations) / 1e3
mad_loop_minus_copy_duration_us = np.median(np.abs(loop_minus_copy_durations - np.median(loop_minus_copy_durations))) / 1e3

# Print the results
print(f"Copy duration statistics (us):")
print(f"Mean: {mean_copy_duration_us:.3f}us")
print(f"Median: {median_copy_duration_us:.3f}us")
print(f"Standard Deviation: {std_copy_duration_us:.3f}us")
print(f"Mean Absolute Deviation: {mad_copy_duration_us:.3f}us")

print(f"\nLoop duration statistics (us):")
print(f"Mean: {mean_loop_duration_us:.3f}us")
print(f"Median: {median_loop_duration_us:.3f}us")
print(f"Standard Deviation: {std_loop_duration_us:.3f}us")
print(f"Mean Absolute Deviation: {mad_loop_duration_us:.3f}us")

print(f"\nLoop duration minus Copy duration statistics (us):")
print(f"Mean: {mean_loop_minus_copy_duration_us:.3f}us")
print(f"Median: {median_loop_minus_copy_duration_us:.3f}us")
print(f"Standard Deviation: {std_loop_minus_copy_duration_us:.3f}us")
print(f"Mean Absolute Deviation: {mad_loop_minus_copy_duration_us:.3f}us")

