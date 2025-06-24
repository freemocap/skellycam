import enum
from typing import Hashable

from pydantic import BaseModel



class ImageResolution(BaseModel):
    height: int
    width: int

    @classmethod
    def from_string(cls, tuple_str: str, delimiter: str = "x") -> "ImageResolution":
        """
        Create a `VideoResolution` from a string like "(720x1280)" or "(1080x1920)" consistent with  rows-by-columns
        """
        height, width = tuple_str.replace("(", "").replace(")", "").split(delimiter)
        return cls(height=int(height), width=int(width))


    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height



    @property
    def as_tuple(self) -> tuple:
        return self.width, self.height

    def __hash__(self) -> Hashable:
        return hash((self.height, self.width))

    def __lt__(self, other: object) -> bool:
        """
        Define this so we can sort a list of `VideoResolution`s
        """
        if not isinstance(other, ImageResolution):
            return False
        return self.width * self.height < other.width * other.height

    def __eq__(self, other: object) -> bool:
        """
        Define this so we can compare `VideoResolution`s
        """
        if not isinstance(other, ImageResolution):
            return False
        return self.width == other.width and self.height == other.height

    def __str__(self) -> str:
        return f"({self.height}x{self.width})"

