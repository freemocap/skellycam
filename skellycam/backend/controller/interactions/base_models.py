from typing import Dict, Any, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

from skellycam.models.timestamp import Timestamp

if TYPE_CHECKING:
    from skellycam.backend.controller.controller import Controller


class BaseMessage(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict, description="The data for this message")
    timestamp: Timestamp = Field(default_factory=Timestamp.now, description="The time this request was created")
    metadata: Dict[str, Any] = Field(default_factory=dict,
                                     description="Any metadata to include with this request "
                                                 "(i.e. stuff that might be useful, but which shouldn't be in `data`")

    def __str__(self):
        return self.__class__.__name__


class BaseRequest(BaseMessage):
    """
    A request from the frontend to the backend
    """

    @classmethod
    def create(cls, **kwargs):
        return cls(**kwargs)


class BaseResponse(BaseMessage):
    """
    A response from the backend to the frontend
    """
    success: bool = Field(default=False, description="Whether or not this request was successful")

    def __str__(self):
        return f"{self.__class__.__name__}: success = {self.success}"


class ErrorResponse(BaseResponse):
    success: bool
    data: Dict[str, Any]

    @classmethod
    def from_exception(cls, exception: Exception):
        return cls(success=False,
                   error=str(exception))


class BaseCommand(BaseModel):
    @classmethod
    def from_request(cls, request: BaseRequest):
        raise NotImplementedError

    def execute(self,
                controller: Optional["Controller"],
                **kwargs) -> BaseResponse:
        raise NotImplementedError

    def __str__(self):
        return {"name": self.__class__.__name__}


class BaseInteraction(BaseModel):
    """
    A request from the frontend to the backend, which will be trigger a command and then return a response
    """
    request: BaseRequest
    command: Optional[BaseCommand]
    response: Optional[BaseResponse]

    @classmethod
    def as_request(cls, **kwargs):
        return cls(request=cls.request.create(**kwargs))

    def execute_command(self, controller: Optional["Controller"], **kwargs) -> BaseResponse:
        self.command.from_request(self.request)
        self.response = self.command.execute(controller, **kwargs)
        return self.response

    def __str__(self):
        if self.command is None:
            return f"{self.__class__.__name__}: {self.request}"
        elif self.response is None:
            return f"{self.__class__.__name__}: {self.request} -> {self.command}"
        else:
            return f"{self.__class__.__name__}: {self.request} -> {self.command} -> {self.response}"
