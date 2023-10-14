from pydantic import BaseModel


class VideoResolution(BaseModel):
    width: int
    height: int

    def __lt__(self, other: "VideoResolution") -> bool:
        """
        Define this so we can sort a list of `VideoResolution`s
        """
        return self.width * self.height < other.width * other.height
