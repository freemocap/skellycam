# from typing import Optional
#
# from pydantic import BaseModel, PrivateAttr
#
# from skellycam import logger
# from skellycam.models.app_state.app_state import AppState
#
# _APP_STATE = None
# _APP_STATE_MANAGER = None
#
# def get_or_create_app_state():
#     global _APP_STATE
#     if _APP_STATE is None:
#         logger.info(f"Creating AppState...")
#         _APP_STATE = AppState()
#     return _APP_STATE
#
# def get_or_create_app_state_manager():
#     global _APP_STATE_MANAGER
#     if _APP_STATE_MANAGER is None:
#         logger.info(f"Creating AppStateManager...")
#         _APP_STATE_MANAGER = AppStateManager(app_state=get_or_create_app_state())
#     return _APP_STATE_MANAGER
#
#
# class AppStateManager(BaseModel):
#     """
#     This class is responsible for managing the state of the application, as represented by the AppState Pydantic BaseModel
#     """
#     _app_state: AppState = PrivateAttr()
#     _state_changed: bool = PrivateAttr(default=False)
#
#     def __init__(self, app_state):
#         super().__init__()
#         self._app_state = app_state
#
#     @property
#     def app_state(self) -> AppState:
#         """
#         Returns the current _app_state and resets "_state_changed" to "False"
#         """
#         self._state_changed = False
#         return self._app_state
#
#     def update(self, update: Update) -> Optional[AppState]:
#         """
#         Updates the AppState with the data from the UpdateModel
#
#         Args:
#             update (MainWindowClosed): The update to apply to the AppState
#
#         Returns:
#             Optional[AppState]: The updated AppState, or None if the AppState was not changed
#
#         """
#         logger.debug(f"Updating AppState with: {update}")
#
#         for key, value in update.data.items():
#             if hasattr(self._app_state, key):
#                 current_value = getattr(self._app_state, key)
#                 if current_value != value:
#                     logger.debug(f"Updating AppState.{key} from `{current_value}` to `{value}`")
#                     setattr(self._app_state, key, value)
#                     self._state_changed = True
#             else:
#                 logger.warning(f"WARNING - Key `{key}` not found AppState!")
#                 # raise AttributeError(f"Key `{key}` not found AppState!")
#
#         if self._state_changed:
#             return self._app_state
#
#
