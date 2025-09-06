def get_memory_usage():
    """Return current memory usage of this process in a human-readable format."""
    import os
    import psutil

    # Get the current process
    process = psutil.Process(os.getpid())

    # Get memory info in bytes
    memory_info = process.memory_info()

    # Convert to MB for readability
    rss_mb = memory_info.rss / (1024 * 1024)
    vms_mb = memory_info.vms / (1024 * 1024)

    return f"RSS: {rss_mb:.2f} MB, VMS: {vms_mb:.2f} MB"

if __name__ == "__main__":
    print("Current process memory usage:")
    print(get_memory_usage())