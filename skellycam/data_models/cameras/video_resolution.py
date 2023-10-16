from pydantic import BaseModel


class VideoResolution(BaseModel):
    width: int
    height: int

    def __lt__(self, other: "VideoResolution") -> bool:
        """
        Define this so we can sort a list of `VideoResolution`s
        """
        return self.width * self.height < other.width * other.height

    def __eq__(self, other: "VideoResolution") -> bool:
        """
        Define this so we can compare `VideoResolution`s
        """
        return self.width == other.width and self.height == other.height

    def __str__(self) -> str:
        return f"({self.width}x{self.height})"
