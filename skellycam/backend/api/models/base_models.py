import traceback
from typing import Optional

from pydantic import BaseModel


class BaseErrorResponse(BaseModel):
    error_type: str
    exception: str
    traceback: str

    @classmethod
    def from_exception(cls, exception: Exception):
        traceback_str = traceback.format_exc()
        if traceback_str == "":
            raise ValueError(
                "No traceback found for exception, "
                "this creation method must be called from an `except` block")
        return cls(
            error_type=type(exception).__name__,
            exception=str(exception),
            traceback=traceback_str,
        )

    def __str__(self):
        return f"{self.error_type}: {self.exception}"


class BaseRequest(BaseModel):
    pass


class BaseResponse(BaseModel):
    success: bool = True
    error: Optional[BaseErrorResponse] = None

    @classmethod
    def from_exception(cls, exception: Exception):
        return cls(success=False, error=BaseErrorResponse.from_exception(exception))
