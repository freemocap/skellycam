import multiprocessing

from pydantic import BaseModel, ConfigDict, SkipValidation, Field


class MultiFrameBuilderStatus(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    building_mfs_flag: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value('b', False))
    is_running_flag: SkipValidation[multiprocessing.Value] = Field(
        default_factory=lambda: multiprocessing.Value('b', False))
    should_pause: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    is_paused: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    closed: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))
    error: SkipValidation[multiprocessing.Value] = Field(default_factory=lambda: multiprocessing.Value('b', False))

