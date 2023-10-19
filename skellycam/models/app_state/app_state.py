from pydantic import BaseModel, PrivateAttr

from skellycam.models.timestamp import Timestamp


class AppTimeState(BaseModel):
    _start: Timestamp = PrivateAttr()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._start = Timestamp.now()

    @property
    def current(self):
        """
        The current time as a Timestamp object, calculated at the time of calling this property
        """
        return Timestamp.now()

    @property
    def start(self):
        """
        The time at which the application was started
        """
        return self._start


class AppState(BaseModel):
    time_state: AppTimeState = AppTimeState() #`start` time is set when the code hits this line
    session_started: bool = False

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            Timestamp: lambda v: v.dict()
        }
