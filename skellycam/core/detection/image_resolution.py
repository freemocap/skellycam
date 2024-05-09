import numpy as np
from pydantic import BaseModel


class ImageResolution(BaseModel):
    width: int
    height: int

    @classmethod
    def from_string(cls, tuple_str: str, split_on: str = "x") -> "ImageResolution":
        """
        Create a `VideoResolution` from a string like "(1280, 720)"
        """
        width, height = tuple_str.replace("(", "").replace(")", "").split(split_on)
        return cls(width=int(width), height=int(height))

    @classmethod
    def from_image(cls, image: np.ndarray) -> "ImageResolution":
        """
        Create a `VideoResolution` from an image
        """
        return cls(width=image.shape[0], height=image.shape[1])

    @property
    def orientation(self) -> str:
        return "landscape" if self.width > self.height else "portrait"

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    def __hash__(self):
        return hash((self.width, self.height))

    def __lt__(self, other: "ImageResolution") -> bool:
        """
        Define this so we can sort a list of `VideoResolution`s
        """
        return self.width * self.height < other.width * other.height

    def __eq__(self, other: "ImageResolution") -> bool:
        """
        Define this so we can compare `VideoResolution`s
        """
        return self.width == other.width and self.height == other.height

    def __str__(self) -> str:
        return f"({self.width}x{self.height})"
