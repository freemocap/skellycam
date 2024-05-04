import traceback
from typing import Optional

from pydantic import BaseModel

class BaseErrorResponse(BaseModel):
    exception: Exception
    traceback: str

    @property
    def error_type(self):
        return type(self.exception).__name__

    @classmethod
    def from_exception(cls, exception: Exception):
        return cls(exception=exception, traceback=traceback.format_exc())

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

