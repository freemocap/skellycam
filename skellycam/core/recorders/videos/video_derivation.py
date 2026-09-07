"""Frame-preserving source relationships carried inside derived video containers."""

from pathlib import Path, PureWindowsPath
from typing import ClassVar

import av
from pydantic import BaseModel, ConfigDict, Field, field_validator


class VideoDerivation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    metadata_prefix: ClassVar[str] = "skellycam.video_derivation:"
    source_video: str
    frame_count: int = Field(gt=0)

    @field_validator("source_video")
    @classmethod
    def validate_relative_source(cls, value: str) -> str:
        path = PureWindowsPath(value)
        if not value or path.drive or path.root or ".." in path.parts:
            raise ValueError("Derived video source must be relative to the recording folder")
        return value

    def to_container_metadata(self) -> dict[str, str]:
        return {"comment": self.metadata_prefix + self.model_dump_json()}

    @classmethod
    def from_video(cls, *, path: Path) -> "VideoDerivation | None":
        with av.open(str(path), mode="r") as container:
            metadata = {key.casefold(): value for key, value in container.metadata.items()}
            comment = metadata.get("comment", "")
        if not comment.startswith(cls.metadata_prefix):
            return None
        return cls.model_validate_json(comment[len(cls.metadata_prefix):])
