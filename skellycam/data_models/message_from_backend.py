from pydantic import BaseModel, Field


class MessageFromBackend(BaseModel):
    type: str = Field(default_factory=str, description="success, error, warning, etc.")
    message: str = Field(default_factory=str, description="A message to display to the user")
    data: dict = Field(default_factory=dict, description="Any data to send to the frontend")
