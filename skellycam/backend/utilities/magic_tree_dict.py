import collections
import sys
from collections import defaultdict
from typing import List, Union, Any

import numpy as np
from rich import box
from rich.console import Console
from rich.table import Table
from rich.tree import Tree


class MagicTreeDict(defaultdict):
    def __init__(self):
        super().__init__(self.create_nested_dict)

    @staticmethod
    def create_nested_dict():
        return defaultdict(MagicTreeDict.create_nested_dict)

    def get_leaf_paths(self, current=None, path=None):
        if current is None:
            current = self
        if path is None:
            path = []
        leaf_paths = []
        for key, value in current.items():
            new_path = path + [key]
            if isinstance(value, defaultdict):
                leaf_paths.extend(self.get_leaf_paths(value, new_path))
            else:
                leaf_paths.append(new_path)
        return leaf_paths

    def data_from_path(self, path: List[str], current=None) -> Union['MagicTreeDict', Any]:
        """
        Returns the data at the given path, be it a leaf(endpoint) or a branch (i.e. a sub-tree/dict)

        Either returns the data at the given path, or creates a new empty sub-tree dictionary at that location and returns that

        """
        if current is None:
            current = self
        return current if len(path) == 0 else self.data_from_path(path[1:], current=current[path[0]])

    def print_leaf_info(self, current=None):
        types_to_print = {
            list: lambda x: (len(x), type(x[0]) if len(x) > 0 else None),
            np.ndarray: lambda x: (x.shape, x.dtype),
            str: lambda x: f"Length: {len(x)} Characters: {x[:12]}...{x[-12:]}" if len(x) > 25 else x,
            tuple: lambda x: (len(x), type(x[0]) if len(x) > 0 else None)
        }

        if current is None:
            current = self
            self._leaf_info_table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
            self._leaf_info_table.add_column("Node")
            self._leaf_info_table.add_column("Type")
            self._leaf_info_table.add_column("Info")
            self._leaf_info_table.add_column("Bytes")
            self._leaf_info_table.add_column("Memory address")

        for key, value in current.items():
            if isinstance(value, defaultdict):
                self.print_leaf_info(value)
            else:
                type_info = type(value)
                other_info = types_to_print.get(type_info, lambda x: 'Unsupported type')(value)
                self._leaf_info_table.add_row(key, str(type_info), str(other_info), str(sys.getsizeof(value)), str(id(value)))

        if current is self:
            console = Console()
            console.print(self._leaf_info_table)
            self._leaf_info_table = None

    def calculate_tree_stats(self,
                             metrics: List[str] = None,
                             data_keys: List[str] = None,
                             add_leaves: bool = True) -> 'MagicTreeDict':
        """
        Calculates the mean and standard deviation of all leaf nodes in the tree.

        If `add_leaves` is True, then the calculated stats are added to the existing tree.

        If `add_leaves` is False, then the calculated stats are returned in a new tree.

        :param metrics: list of metrics to calculate. Options are 'mean' and 'std'
        :param data_keys: list of data keys to calculate stats for. If 'ALL', then all data names are used
        """
        metrics = metrics or ['mean', 'std']
        data_keys = data_keys or ['ALL']
        leaf_paths = self.get_leaf_paths()

        stats_tree = self if add_leaves else MagicTreeDict()

        for path in leaf_paths:
            leaf_orig = self.data_from_path(path)
            data_name = path[-1]

            if isinstance(leaf_orig, list) and (data_name in data_keys or data_keys == ['ALL']):
                stats_tree[path] = {"data": leaf_orig}  # preserve the original leaf value under "data" key

                if 'mean' in metrics:
                    leaf_mean = np.mean(leaf_orig)
                    stats_tree[path]['mean'] = leaf_mean

                if 'std' in metrics:
                    leaf_std = np.std(leaf_orig)
                    stats_tree[path]['std'] = leaf_std
        return stats_tree

    def __setitem__(self, keys, value):
        """
        Allows for setting values using a list of keys, e.g. `magic_tree['a']['b']['c'] = 1`
        Checks if the input is a string, an integer, or an iterable.
        If it's a string or integer, it just sets the value at the given key, like a normal dict.
        If it's an iterable, it builds a path out of it and sets the value at that path.
        """
        if isinstance(keys, str) or isinstance(keys, int):
            super(MagicTreeDict, self).__setitem__(keys, value)
        elif isinstance(keys, collections.abc.Iterable):
            current_data = self
            for key in keys[:-1]:
                current_data = current_data[key]
            current_data[keys[-1]] = value
        else:
            raise TypeError("Invalid key type.")

    def __getitem__(self, keys):
        """
        Allows for getting values using a list of keys, e.g. `magic_tree['a']['b']['c']`
        Checks if the input is a string, an integer, or an iterable.
        If it's a string or integer, it just gets the value at the given key, like a normal dict.
        If it's an iterable, it builds a path out of it and gets the value at that path.

        """
        if isinstance(keys, str) or isinstance(keys, int):
            return super(MagicTreeDict, self).__getitem__(keys)
        elif isinstance(keys, collections.abc.Iterable):
            current_data = self
            for key in keys:
                current_data = current_data[key]
            return current_data
        else:
            raise TypeError("Invalid key type.")

    def __repr__(self):
        return repr(dict(self))

    def __str__(self):
        """
        Prints the tree in a nice format using rich
        """
        console = Console()

        def add_branch(tree: Tree, data: dict, level: int = 0, max_level: int = 6):
            colors = ['bright_yellow', 'bright_blue', 'bright_green', 'bright_red', 'bright_magenta', 'bright_cyan']
            for key, value in data.items():
                if isinstance(value, dict) and level < max_level:
                    branch = tree.add(f"[{colors[level % len(colors)]}]{key}")
                    add_branch(branch, value, level + 1)
                else:
                    tree.add(f"[{colors[level % len(colors)]}]{key} : {value}")

        tree = Tree(":seedling:")
        add_branch(tree, dict(self))
        with console.capture() as capture:
            console.print(tree)
        return capture.get()


def create_sample_magic_tree():
    magic_tree = MagicTreeDict()
    magic_tree['a']['b']['c']['woo'] = [1, 2, 13]
    magic_tree['a']['b']['c']['woo2'] = '✨'
    magic_tree['a']['b']['??️'] = np.eye(
        3)  # TODO - doesn't handle this correctly - skips it in stats, and prints matrix poorly
    magic_tree['a']['c']['bang'] = [4, 51, 6]
    magic_tree['a']['b']['c']['hey'] = [71, 8, 9]
    return magic_tree


def test_magic_tree_dict(magic_tree: MagicTreeDict = None):
    if magic_tree is None:
        magic_tree = create_sample_magic_tree()
    print(f"Original MagicTreeDict:\n{magic_tree}\n")

    stats = magic_tree.calculate_tree_stats(add_leaves=False)
    print(f"Calculate tree stats and return in new MagicTreeDict:\n{stats}\n")
    print(f"Original MagicTreeDict (again) :\n{magic_tree}\n")

    magic_tree.calculate_tree_stats()
    print(f"Calculate tree stats and update original MagicTreeDict:\n{magic_tree}\n")
    return magic_tree


if __name__ == "__main__":
    tree = test_magic_tree_dict()
    tree.print_leaf_info()

# Expected output (2023-10-08):
# Original MagicTreeDict:
# 🌱
# └── a
#     ├── b
#     │   ├── c
#     │   │   ├── woo : [1, 2, 13]
#     │   │   ├── woo2 : ✨
#     │   │   └── hey : [71, 8, 9]
#     │   └── ??️ : [[1. 0. 0.]
#     │        [0. 1. 0.]
#     │        [0. 0. 1.]]
#     └── c
#         └── bang : [4, 51, 6]
#
#
# Calculate tree stats and return in new MagicTreeDict:
# 🌱
# └── a
#     ├── b
#     │   └── c
#     │       ├── woo
#     │       │   ├── data : [1, 2, 13]
#     │       │   ├── mean : 5.333333333333333
#     │       │   └── std : 5.436502143433364
#     │       └── hey
#     │           ├── data : [71, 8, 9]
#     │           ├── mean : 29.333333333333332
#     │           └── std : 29.465610840812758
#     └── c
#         └── bang
#             ├── data : [4, 51, 6]
#             ├── mean : 20.333333333333332
#             └── std : 21.69997439834639
#
#
# Original MagicTreeDict (again) :
# 🌱
# └── a
#     ├── b
#     │   ├── c
#     │   │   ├── woo : [1, 2, 13]
#     │   │   ├── woo2 : ✨
#     │   │   └── hey : [71, 8, 9]
#     │   └── ??️ : [[1. 0. 0.]
#     │        [0. 1. 0.]
#     │        [0. 0. 1.]]
#     └── c
#         └── bang : [4, 51, 6]
#
#
# Calculate tree stats and update original MagicTreeDict:
# 🌱
# └── a
#     ├── b
#     │   ├── c
#     │   │   ├── woo
#     │   │   │   ├── data : [1, 2, 13]
#     │   │   │   ├── mean : 5.333333333333333
#     │   │   │   └── std : 5.436502143433364
#     │   │   ├── woo2 : ✨
#     │   │   └── hey
#     │   │       ├── data : [71, 8, 9]
#     │   │       ├── mean : 29.333333333333332
#     │   │       └── std : 29.465610840812758
#     │   └── ??️ : [[1. 0. 0.]
#     │        [0. 1. 0.]
#     │        [0. 0. 1.]]
#     └── c
#         └── bang
#             ├── data : [4, 51, 6]
#             ├── mean : 20.333333333333332
#             └── std : 21.69997439834639
#
#
#
# Process finished with exit code 0
