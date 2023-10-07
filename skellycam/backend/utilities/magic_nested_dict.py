from collections import defaultdict

# Recursive function to create defaultdict
def create_nested_dict():
    return defaultdict(create_nested_dict)

def to_dict(d):
    return {k: to_dict(v) if isinstance(v, defaultdict) else v for k, v in d.items()}

class MagicNestedDict(defaultdict):
    def __init__(self):
        super().__init__(create_nested_dict)

    def __repr__(self):
        return repr(to_dict(self))

    def __str__(self):
        return str(to_dict(self))

# Usage
magic_dict = MagicNestedDict()
magic_dict['a']['b']['c'] = "hello"

print(magic_dict)  # Now properly prints: {'a': {'b': {'c': 'hello'}}}