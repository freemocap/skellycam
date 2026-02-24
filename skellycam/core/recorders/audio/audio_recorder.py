import json
import logging
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event

import numpy as np
import sounddevice as sd

from skellycam.core.timestamps.timebase_mapping import TimebaseMapping

logger = logging.getLogger(__name__)

AUDIO_SAMPLE_RATE = 44100
AUDIO_CHANNELS = 2
AUDIO_CHUNK_SIZE = 1024
AUDIO_SUBTYPE = "int16"


@dataclass
class AudioChunkTimestamp:
    chunk_number: int
    perf_counter_ns: int
    num_samples: int


@dataclass
class AudioRecorder:
    """Records audio from a microphone using sounddevice (PortAudio).

    Uses a callback-based InputStream for minimal latency and accurate timing.
    Audio chunks are timestamped with perf_counter_ns for sync with video frames.
    """
    audio_file_path: str = "audio.wav"
    mic_device_index: int = 0
    timebase_mapping: TimebaseMapping = field(default_factory=TimebaseMapping)
    sample_rate: int = AUDIO_SAMPLE_RATE
    channels: int = AUDIO_CHANNELS
    chunk_size: int = AUDIO_CHUNK_SIZE

    _stream: sd.InputStream | None = field(default=None, repr=False)
    _frames: list[np.ndarray] = field(default_factory=list, repr=False)
    _chunk_timestamps: list[AudioChunkTimestamp] = field(default_factory=list, repr=False)
    _stop_event: Event = field(default_factory=Event, repr=False)
    _start_perf_ns: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        if not self.audio_file_path.endswith(".wav"):
            self.audio_file_path += ".wav"
        Path(self.audio_file_path).parent.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        """Start recording audio in a callback-driven InputStream."""
        logger.info(f"Starting audio recording: device={self.mic_device_index}, "
                    f"rate={self.sample_rate}, channels={self.channels}")

        self._frames = []
        self._chunk_timestamps = []
        self._stop_event.clear()
        self._start_perf_ns = time.perf_counter_ns()

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=AUDIO_SUBTYPE,
            blocksize=self.chunk_size,
            device=self.mic_device_index,
            callback=self._audio_callback,
        )
        self._stream.start()
        logger.info("Audio recording started.")

    def stop(self) -> None:
        """Stop recording, save the WAV file and timestamp sidecar."""
        logger.info("Stopping audio recording...")
        self._stop_event.set()

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._frames:
            logger.warning("No audio frames captured — skipping save.")
            return

        self._save_wav()
        self._save_timestamps()
        logger.info(f"Audio saved: {len(self._frames)} chunks, "
                    f"{len(self._frames) * self.chunk_size / self.sample_rate:.2f}s")

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: dict,
        status: sd.CallbackFlags,
    ) -> None:
        """Called by PortAudio's audio thread for each buffer of samples."""
        if status:
            logger.warning(f"Audio callback status: {status}")
        if self._stop_event.is_set():
            return

        capture_ns = time.perf_counter_ns()
        self._frames.append(indata.copy())
        self._chunk_timestamps.append(AudioChunkTimestamp(
            chunk_number=len(self._chunk_timestamps),
            perf_counter_ns=capture_ns,
            num_samples=frames,
        ))

    def _save_wav(self) -> None:
        """Write captured audio frames to a WAV file."""
        audio_data = np.concatenate(self._frames, axis=0)
        with wave.open(self.audio_file_path, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit = 2 bytes
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data.tobytes())
        logger.debug(f"WAV saved to {self.audio_file_path}")

    def _save_timestamps(self) -> None:
        """Write per-chunk timestamps as a JSON sidecar file."""
        timestamps_path = self.audio_file_path.replace(".wav", "_timestamps.json")

        chunk_durations = []
        for i in range(1, len(self._chunk_timestamps)):
            dt_ns = self._chunk_timestamps[i].perf_counter_ns - self._chunk_timestamps[i - 1].perf_counter_ns
            chunk_durations.append(dt_ns / 1e9)

        info = {
            "audio_file": str(Path(self.audio_file_path).name),
            "mic_device_index": self.mic_device_index,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "chunk_size": self.chunk_size,
            "total_chunks": len(self._chunk_timestamps),
            "total_samples": sum(ct.num_samples for ct in self._chunk_timestamps),
            "start_perf_counter_ns": self._start_perf_ns,
            "end_perf_counter_ns": self._chunk_timestamps[-1].perf_counter_ns if self._chunk_timestamps else 0,
            "duration_seconds": (self._chunk_timestamps[-1].perf_counter_ns - self._start_perf_ns) / 1e9 if self._chunk_timestamps else 0,
            "mean_chunk_duration_seconds": float(np.mean(chunk_durations)) if chunk_durations else 0,
            "std_chunk_duration_seconds": float(np.std(chunk_durations)) if chunk_durations else 0,
            "timebase_mapping": {
                "utc_time_ns": self.timebase_mapping.utc_time_ns,
                "perf_counter_ns": self.timebase_mapping.perf_counter_ns,
                "local_time_utc_offset": self.timebase_mapping.local_time_utc_offset,
            },
            "chunk_timestamps_perf_ns": [ct.perf_counter_ns for ct in self._chunk_timestamps],
        }

        with open(timestamps_path, "w") as f:
            json.dump(info, f, indent=2)
        logger.debug(f"Audio timestamps saved to {timestamps_path}")


if __name__ == "__main__":
    recorder = AudioRecorder(
        audio_file_path="test.wav",
        timebase_mapping=TimebaseMapping()


    )
    recorder.start()
    time.sleep(10)
    recorder.stop()

    print( f"Audio recorder stopped, audio saved to: {recorder.audio_file_path}")
