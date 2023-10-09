from skellycam.frontend.app_state.app_singletons.get_or_create_app_state_manager import \
    get_or_create_app_state


class AppStateManager:
    """
    This class is responsible for managing the state of the application, as represented by the AppState Pydantic BaseModel
    """
    def __init__(self):
        super().__init__()
        self._app_state = get_or_create_app_state()

    def run(self):
        pass

    @property
    def app_state(self):
        return self._app_state

    @Slot
    def update(self):
        self._app_state = app_state