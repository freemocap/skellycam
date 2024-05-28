from typing import Any, Callable, Type


def singleton(cls: Type[Any]) -> Callable[..., Any]:
    instances = {}

    def get_instance(*args: Any, **kwargs: Any) -> Any:
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance


if __name__ == "__main__":
    @singleton
    class SingletonClass:
        def __init__(self, value: int) -> None:
            self.value = value


    # Usage
    singleton1 = SingletonClass(1)
    singleton2 = SingletonClass(2)

    print(singleton1.value)  # Output: 1
    print(singleton2.value)  # Output: 1
    print(singleton1 is singleton2)  # Output: True
