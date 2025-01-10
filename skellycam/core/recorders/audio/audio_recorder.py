import json
import logging
import multiprocessing
import threading
import time
import wave
from pathlib import Path
from typing import Optional, List

import numpy as np
import pyaudio
from pydantic import BaseModel

from skellycam.core.recorders.timestamps.full_timestamp import FullTimestamp
from skellycam.core.recorders.timestamps.utc_to_perfcounter_mapping import UtcToPerfCounterMapping

logger = logging.getLogger(__name__)

class AudioChunk(BaseModel):
    audio_chunk_number: int
    chunk_duration_seconds: float
    start_time_in_seconds_from_zero: int
    end_time_in_seconds_from_zero: int
    start_time_perf_counter_ns: int
    end_time_perf_counter_ns: int

class AudioRecordingInfo(BaseModel):
    file_name: str
    utc_to_perf_counter_ns_mapping: dict
    audio_record_start_time: dict
    rate: int
    channels: int
    chunk_size: int
    audio_record_duration_seconds: Optional[float] = None
    audio_record_end_time: Optional[dict] = None
    mean_chunk_duration_seconds: Optional[float] = None
    std_chunk_duration_seconds: Optional[float] = None
    number_of_audio_chunks_recorded: Optional[int] = None
    audio_chunks: List[AudioChunk] = []

class AudioRecorder:
    def __init__(self,
                 audio_file_path: str,
                 mic_device_index: int,
                 rate: int = 44100,
                 channels: int = 2,
                 chunk_size: int = 2048):
        if not audio_file_path.endswith('.wav'):
            audio_file_path += '.wav'
        self.audio_filename = audio_file_path
        self.mic_device_index = mic_device_index
        self.should_continue = multiprocessing.Value('b', True)
        self.recording_thread = threading.Thread(target=AudioRecorder._record,
                                                 args=(self,
                                                       self.should_continue),
                                                 daemon=True)
        self.rate = rate
        self.channels = self._validate_channel_input(channel_input=channels)
        self.chunk_size = chunk_size
        self.frames = []
        self.audio_recording_info: Optional[AudioRecordingInfo] = None
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(format=pyaudio.paInt16,
                                      channels=self.channels,
                                      rate=self.rate,
                                      input=True,
                                      input_device_index=self.mic_device_index,
                                      frames_per_buffer=self.chunk_size)
        logger.debug(
            f"Initialized AudioRecorder with file path: {self.audio_filename}, mic device index: {self.mic_device_index}")

    def start(self):
        logger.debug("Starting audio recording thread...")
        self.recording_thread.start()

    def stop(self):
        logger.debug("Stopping audio recording thread...")
        self.should_continue.value = False
        self.recording_thread.join()



    def _record(self, should_continue: multiprocessing.Value):

        logger.trace("Audio recording started...")
        start_time = time.perf_counter_ns()
        logger.trace(f"Recording started at {start_time} ns.")
        self._initialize_audio_data()

        while should_continue.value:
            chunk_start_time = time.perf_counter_ns()
            data = self.stream.read(self.chunk_size)
            chunk_end_time = time.perf_counter_ns()
            self.frames.append(data)
            self.audio_recording_info.audio_chunks.append(AudioChunk(
                audio_chunk_number=len(self.audio_recording_info.audio_chunks),
                chunk_duration_seconds=(chunk_end_time - chunk_start_time) / 1e9,
                start_time_in_seconds_from_zero=chunk_start_time - start_time,
                end_time_in_seconds_from_zero=chunk_end_time - start_time,
                start_time_perf_counter_ns=chunk_start_time,
                end_time_perf_counter_ns=chunk_end_time
            ))
            logger.loop(f"Recorded Audio chunk with duration {(chunk_end_time - chunk_start_time) / 1e9 :.4f} sec")

        logger.debug(
            f"Audio recording finished! Total duration: {(time.perf_counter_ns() - start_time) / 1e9 :.4f} sec")
        self._finalize_audio_data()
        self._save_audio()
        self._save_timestamps()

    def _initialize_audio_data(self):
        self.audio_recording_info = AudioRecordingInfo(
            file_name=self.audio_filename.replace(str(Path.home()), "~"),
            utc_to_perf_counter_ns_mapping=UtcToPerfCounterMapping().model_dump(),
            audio_record_start_time=FullTimestamp.now().model_dump(),
            rate=self.rate,
            channels=self.channels,
            chunk_size=self.chunk_size,
            audio_chunks=[]
        )

    def _finalize_audio_data(self):
        self.audio_recording_info.audio_record_duration_seconds = (self.audio_recording_info.audio_chunks[-1].end_time_perf_counter_ns - self.audio_recording_info.audio_chunks[0].start_time_perf_counter_ns) / 1e9
        self.audio_recording_info.audio_record_end_time = FullTimestamp.now().model_dump()
        self.audio_recording_info.mean_chunk_duration_seconds = np.mean([chunk.chunk_duration_seconds for chunk in self.audio_recording_info.audio_chunks])
        self.audio_recording_info.std_chunk_duration_seconds = np.std([chunk.chunk_duration_seconds for chunk in self.audio_recording_info.audio_chunks])
        self.audio_recording_info.number_of_audio_chunks_recorded = len(self.audio_recording_info.audio_chunks)
        logger.trace(f"Audio data finalized: {self.audio_recording_info.model_dump(exclude={'audio_chunks'})}")

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
            f.write(json.dumps(self.audio_recording_info.model_dump(), indent=4))
        logger.debug(f"Audio timestamps saved to {timestamps_filename}")

    def _validate_channel_input(self, channel_input: int) -> int:
        device_info = pyaudio.get_device_info_by_index(self.mic_device_index)
        max_input_channels = device_info['maxInputChannels']
        if channel_input > max_input_channels:
            logger.debug(
                f"Number of audio channels chosen ({channel_input}) exceeds device maximum"
                f" - Defaulting to device maximum ({max_input_channels}) channels")
            return max_input_channels
        else:
            return channel_input



if __name__ == "__main__":
    from skellycam.system.device_detection.detect_microphone_devices import get_available_microphones
    from pprint import pprint

    mics = get_available_microphones()
    pprint(mics)
    if mics:
        try:
            chosen_mic = int(input("Enter the Device ID of the microphone you want to use: "))
            if chosen_mic not in mics:
                raise ValueError("Invalid Device ID chosen.")
            audio_recorder = AudioRecorder(audio_file_path="output.wav",
                                           mic_device_index=chosen_mic)
            audio_recorder.start()
            time.sleep(1)
            input("Press Enter to stop recording...")
            audio_recorder.stop()

        except ValueError as e:
            print(f"Error: {e}")
    else:
        print("No microphones found.")
