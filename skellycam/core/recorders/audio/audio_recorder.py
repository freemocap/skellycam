import json
import logging
import threading
import time
import wave

import pyaudio

from skellycam.core.recorders.timestamps.utc_to_perfcounter_mapping import UtcToPerfCounterMapping

logger = logging.getLogger(__name__)


class AudioRecorder:
    def __init__(self,
                 audio_file_path: str,
                 mic_device_index: int,
                 rate: int = 44100,
                 channels: int = 2,
                 chunk_size: int = 1024):
        if not audio_file_path.endswith('.wav'):
            audio_file_path += '.wav'
        self.audio_filename = audio_file_path
        self.mic_device_index = mic_device_index

        self.recording_thread = threading.Thread(target=AudioRecorder._record, args=(self,))
        self.rate = rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.stop_event = threading.Event()
        self.frames = []
        self.audio_data = {
            'file_path': self.audio_filename,
            'file_name': self.audio_filename.split('/')[-1],
            'utc_to_perf_counter_ns_mapping': UtcToPerfCounterMapping().model_dump(),
            'audio_chunks': []
        }
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(format=pyaudio.paInt16,
                                      channels=self.channels,
                                      rate=self.rate,
                                      input=True,
                                      input_device_index=self.mic_device_index,
                                      frames_per_buffer=self.chunk_size)
        logger.debug(
            f"Initialized AudioRecorder with file path: {self.audio_filename}, mic device index: {self.mic_device_index}")

    def start_recording(self):

        self.recording_thread.start()
        logger.debug(f"Started audio recording thread for file: {self.audio_filename}")

    def stop_recording(self):
        self.stop_event.set()
        self.recording_thread.join()
        logger.trace("Audio recording stopped.")

    def _record(self):

        logger.trace("Audio recording started...")
        start_time = time.perf_counter_ns()
        logger.trace(f"Recording started at {start_time} ns.")
        while not self.stop_event.is_set():
            chunk_start_time = time.perf_counter_ns()
            data = self.stream.read(self.chunk_size)
            chunk_end_time = time.perf_counter_ns()
            self.frames.append(data)
            self.audio_data['audio_chunks'].append({'chunk_start_time': chunk_start_time,
                                                    'chunk_end_time': chunk_end_time})
            logger.loop(f"Recorded chunk with duration {(chunk_end_time - chunk_start_time) / 1e9 :.4f} sec")
        logger.debug(f"Audio recording finished! Total duration: {(time.perf_counter_ns() - start_time) / 1e9 :.4f} sec")
        self._save_audio()
        self._save_timestamps()

    def _save_audio(self):
        self.stream.stop_stream()
        self.stream.close()
        self.audio.terminate()
        with wave.open(self.audio_filename, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(self.frames))
        logger.debug(f"Audio saved to {self.audio_filename}")

    def _save_timestamps(self):
        timestamps_filename = f"{self.audio_filename.replace('.wav', '_timestamps.json')}"
        with open(timestamps_filename, 'w') as f:
            f.write(json.dumps(self.audio_data, indent=4))
        logger.debug(f"Audio timestamps saved to {timestamps_filename}")



if __name__ == "__main__":
    from skellycam.system.device_detection.detect_microphone_devices import get_available_microphone_devices
    from pprint import pprint

    mics = get_available_microphone_devices()
    pprint(mics)
    if mics:
        try:
            chosen_mic = int(input("Enter the Device ID of the microphone you want to use: "))
            if chosen_mic not in mics:
                raise ValueError("Invalid Device ID chosen.")
            audio_recorder = AudioRecorder(audio_file_path="output.wav",
                                                  mic_device_index=chosen_mic)
            audio_recorder.start_recording()
            time.sleep(1)
            input("Press Enter to stop recording...")
            audio_recorder.stop_recording()

        except ValueError as e:
            print(f"Error: {e}")
    else:
        print("No microphones found.")
