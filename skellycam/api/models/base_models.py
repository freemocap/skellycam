import sys
import traceback
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class BaseErrorResponse(BaseModel):
    error_type: str
    exception: str
    traceback: str

    @classmethod
    def from_exception(cls, exception: Exception) -> "BaseErrorResponse":
        traceback_str = traceback.format_exc()
        if traceback_str == "":
            raise ValueError(
                "No traceback found for exception, " "this creation method must be called from an `except` block"
            )
        cls._remove_home_dir_from_traceback(traceback_str)
        return cls(
            error_type=type(exception).__name__,
            exception=str(exception),
            traceback=traceback_str,
        )

    @staticmethod
    def _remove_home_dir_from_traceback(traceback_str: str) -> str:
        home_dir_path = Path.home()

        if sys.platform == "win32":
            traceback_str = traceback_str.replace(str(home_dir_path),
                                                  "%USERPROFILE%")
        else:
            traceback_str = traceback_str.replace(str(home_dir_path), "~")
        return traceback_str

    def __str__(self) -> str:
        return f"{self.error_type}: {self.exception}"


class BaseRequest(BaseModel):
    pass


class BaseResponse(BaseModel):
    success: bool = True
    error: Optional[BaseErrorResponse] = None

    @classmethod
    def from_exception(cls, exception: Exception) -> "BaseResponse":
        return cls(success=False, error=BaseErrorResponse.from_exception(exception))
