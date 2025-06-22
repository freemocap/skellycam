import multiprocessing

from pydantic import BaseModel, ConfigDict, SkipValidation, Field


class RecordingManagerStatus(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    is_recording_frames_flag: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value('b', False))
    should_record: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value('b', False))
    is_running_flag: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value('b', False))
    finishing: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    updating: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    closed: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    error: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))

    @property
    def recording(self) -> bool:
        return self.is_recording_frames_flag.value and self.should_record.value
