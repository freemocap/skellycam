from collections import defaultdict
from copy import deepcopy
from typing import List, Dict, Any

from pydantic import BaseModel

from skellycam.backend.models.timestamp import Timestamp


class AppState(defaultdict):
    def __init__(self):
        super().__init__(dict)
        self.app_started_at: Timestamp = Timestamp().now()
        self.app_state_changed: Timestamp = Timestamp().now()
        self.seconds_since_update: float = 0

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key, value)
        now = Timestamp().now()
        self.seconds_since_update = (
            now.perf_counter_ns - self.app_started_at.perf_counter_ns
        ) / 1e9
        self.app_state_changed = Timestamp().now()


class AppStateManager:
    current_state: AppState
    history: List[AppState]

    def __init__(self):
        self.current_state = AppState()

    def update(self, key: str, value: any):
        self.history.append(deepcopy(self.current_state))
        self.current_state[key] = value


if __name__ == "__main__":
    from collections import defaultdict
    from pprint import pprint

    dd = defaultdict(dict)
    dd["key1"]["nested_key1"] = "value1"
    pprint(dd)

    dd["dd"] = 2

    pprint(dd)
