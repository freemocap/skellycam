from typing import Any, Dict

from pydantic import BaseModel, PrivateAttr

from skellycam import logger
from skellycam.data_models.app_state.app_state import AppState

_APP_STATE = None
_APP_STATE_MANAGER = None

def get_or_create_app_state():
    global _APP_STATE
    if _APP_STATE is None:
        logger.info(f"Creating AppState...")
        _APP_STATE = AppState()
    return _APP_STATE

def get_or_create_app_state_manager():
    global _APP_STATE_MANAGER
    if _APP_STATE_MANAGER is None:
        logger.info(f"Creating AppStateManager...")
        _APP_STATE_MANAGER = AppStateManager(app_state=get_or_create_app_state())
    return _APP_STATE_MANAGER


class AppStateManager(BaseModel):
    """
    This class is responsible for managing the state of the application, as represented by the AppState Pydantic BaseModel
    """
    _app_state: AppState = PrivateAttr()
    _state_changed: bool = PrivateAttr(default=False)

    def __init__(self, app_state):
        super().__init__()
        self._app_state = app_state

    @property
    def app_state(self) -> AppState:
        """
        Returns the current _app_state and resets "_state_changed" to "False"
        """
        self._state_changed = False
        return self._app_state

    def update(self, update: Dict[str, Any]):

        self._app_state.changed = True

        for key, value in update.items():
            try:
                setattr(self._app_state, key, value)
            except AttributeError as e:
                logger.error(f"Key `{key}` not found AppState!")
                raise AttributeError(f"Key `{key}` not found AppState!")
