from pprint import pprint
from typing import Dict

import pyaudio


def get_available_microphone_devices() -> Dict[int, str]:
    """
    List available unique microphone devices.

    Returns
    -------
    list
        A list of device indices for available microphones.
    """
    audio = pyaudio.PyAudio()
    device_count = audio.get_device_count()
    unique_names = set()
    microphones = {}

    for i in range(device_count):
        device_info = audio.get_device_info_by_index(i)
        device_name = device_info['name']
        if device_info['maxInputChannels'] > 0 and device_name not in unique_names:
            # unique_names.add(device_name)
            # print(f"\nDevice ID {i}: {device_name}")
            # print(pprint(device_info))
            if device_name not in microphones.values():
                microphones[i] = device_name

    audio.terminate()
    return microphones


if __name__ == "__main__":
    from pprint import pprint
    pprint(get_available_microphone_devices())