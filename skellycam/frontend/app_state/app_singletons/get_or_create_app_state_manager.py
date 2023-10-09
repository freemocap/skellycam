from pydantic import BaseModel

APP_STATE = None
def get_or_create_app_state_manager():
    global APP_STATE
    if APP_STATE is None:
        APP_STATE = {"app": "state"}
    return APP_STATE


