from typing import Any, Dict

from PySide6.QtCore import Slot

from skellycam.data_models.app_state.app_state import AppState
from skellycam.frontend.app_state.app_singletons.get_or_create_app_state_manager import \
    get_or_create_app_state


class AppStateManager:
    """
    This class is responsible for managing the state of the application, as represented by the AppState Pydantic BaseModel
    """

    def __init__(self):
        super().__init__()
        self._app_state:AppState = get_or_create_app_state()
        self._state_changed:bool = False
    def run(self):
        pass

    @property
    def app_state(self):
        """
        Returns the current _app_state and resets "_state_changed" to "False"
        """
        self._state_changed = False
        return self._app_state

    @property
    def changed(self):
        """
        Whether or not the app_state has changed since the last time it was access (via the `app_state` property)
        """
        return self._state_changed
    @Slot
    def update(self, update: Dict[str, Any] = None):
        if update is None:
            pass
        self._app_state.changed = True

        for key, value in update.items():
            try:
                setattr(self, key, value)
            except AttributeError as e:
                logger.error("")
