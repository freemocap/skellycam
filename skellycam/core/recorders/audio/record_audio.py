import wave

import pyaudio
from skellycam.core.audio.detect_microphone_devices import list_microphones


def record_audio(filename: str, duration: int, device_index: int, rate: int = 44100, channels: int = 2, chunk: int = 1024) -> None:
    """
    Record audio from the specified microphone and save it to a file.

    Parameters
    ----------
    filename : str
        The name of the file to save the recorded audio.
    duration : int
        The duration of the recording in seconds.
    device_index : int
        The index of the microphone device to use for recording.
    rate : int, optional
        The sampling rate (default is 44100).
    channels : int, optional
        The number of audio channels (default is 2).
    chunk : int, optional
        The size of the audio buffer (default is 1024).
    """
    audio = pyaudio.PyAudio()

    stream = audio.open(format=pyaudio.paInt16,
                        channels=channels,
                        rate=rate,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=chunk)

    print("Recording...")
    frames = []

    for _ in range(0, int(rate / chunk * duration)):
        data = stream.read(chunk)
        frames.append(data)

    print("Recording finished.")

    stream.stop_stream()
    stream.close()
    audio.terminate()

    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))

if __name__ == "__main__":
    mics = list_microphones()
    if mics:
        try:
            chosen_mic = int(input("Enter the Device ID of the microphone you want to use: "))
            if chosen_mic not in mics:
                raise ValueError("Invalid Device ID chosen.")
            record_audio(filename="output.wav", duration=10, device_index=chosen_mic)
        except ValueError as e:
            print(f"Error: {e}")
    else:
        print("No microphones found.")