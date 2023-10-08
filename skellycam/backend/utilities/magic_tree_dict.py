import collections
import sys
from collections import defaultdict
from typing import Any
from typing import List, Union

import numpy as np
import rich.tree
from rich.console import Console
from rich.tree import Tree


class TreePrinter:
    def __init__(self, tree: 'MagicTreeDict'):
        self.tree = tree

    def __str__(self):
        console = Console()
        with console.capture() as capture:
            rich_tree = Tree(":seedling:")
            self._add_branch(rich_tree, dict(self.tree))
            console.print(rich_tree)
        return capture.get()

    def _add_branch(self, rich_tree: rich.tree.Tree, subdict):
        for key, value in subdict.items():
            if isinstance(value, dict):
                branch = rich_tree.add(key)
                self._add_branch(branch, value)
            else:
                rich_tree.add(f"{key}: {value}")


class TreeCalculator:
    def __init__(self, tree: 'MagicTreeDict'):
        self.tree = tree

    def calculate_stats(self,
                        metrics: List[str] = None,
                        data_keys: List[str] = None) -> 'MagicTreeDict':
        """
        Calculates the mean and standard deviation of all leaf nodes in the tree.

        If `add_leaves` is True, then the calculated stats are added to the existing tree.

        If `add_leaves` is False, then the calculated stats are returned in a new tree.

        :param metrics: list of metrics to calculate. Options are 'mean' and 'std'
        :param data_keys: list of data keys to calculate stats for. If 'ALL', then all data names are used
        """
        metrics = metrics or ['mean', 'std']
        data_keys = data_keys or ['ALL']

        stats_tree = MagicTreeDict()

        leaf_paths = self.tree.get_leaf_paths()
        for path in leaf_paths:
            leaf_orig = self.tree.data_from_path(path)
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


class MagicTreeDict(defaultdict):
    """
    A class that integrates `defaultdict` with added functionality.

    The `MagicTreeDict` class allows for representing a nested dictionary
    in a tree-like structure. It provides methods for traversing the tree,
    and getting or setting data using a list of keys, and also calculates stats
    and prints information about the leaves.
    """

    def __init__(self):
        super().__init__(self.create_nested_dict)

    @staticmethod
    def create_nested_dict():
        return defaultdict(MagicTreeDict.create_nested_dict)

    def get_leaf_paths(self):
        """
        Returns a list of all the paths to the leaves in the tree.
        """
        leaf_paths = []
        self._traverse_tree(lambda path, value: leaf_paths.append(path))
        return leaf_paths

    def data_from_path(self, path: List[str], current=None) -> Union['MagicTreeDict', Any]:
        """
        Returns the data at the given path, be it a leaf(endpoint) or a branch (i.e. a sub-tree/dict)

        Either returns the data at the given path, or creates a new empty sub-tree dictionary at that location and returns that

        """
        if current is None:
            current = self
        return current if len(path) == 0 else self.data_from_path(path[1:], current=current[path[0]])

    def calculate_tree_stats(self,
                             metrics: List[str] = None,
                             data_keys: List[str] = None) -> 'MagicTreeDict':
        stats = TreeCalculator(self).calculate_stats(metrics=metrics,
                                                     data_keys=data_keys)
        return stats

    def print_leaf_info(self, current=None, path=None):
        """Prints the information about all the leaves of the tree."""
        console = Console()
        tree = Tree(":seedling:")
        self._get_leaf_info()
        print(self._leaf_info)

    def _get_leaf_info(self, current=None, path=None):
        if current is None:
            self._leaf_info = MagicTreeDict()
            current = self
        if path is None:
            path = []
        for key, value in current.items():
            new_path = path + [key]

            type_ = type(value).__name__
            info = str(value)[:20] + (str(value)[20:] and '..')
            nbytes = sys.getsizeof(value)
            memory_address = hex(id(value))

            if isinstance(value, defaultdict):
                self._get_leaf_info(current=value,
                                    path=new_path)
            else:
                self._leaf_info[new_path].update({"type": type_,
                                                  "info": info,
                                                  "nbytes": nbytes,
                                                  "memory_address": memory_address})

    def _traverse_tree(self, callback, current=None, path=None):
        if current is None:
            current = self
        if path is None:
            path = []
        for key, value in current.items():
            new_path = path + [key]
            if isinstance(value, defaultdict):
                self._traverse_tree(callback, value, new_path)
            else:
                callback(new_path, value)

    def __str__(self):
        return TreePrinter(self).__str__()

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

    stats = magic_tree.calculate_tree_stats()
    print(f"Calculate tree stats and return in new MagicTreeDict:\n{stats}\n")
    print(f"Original MagicTreeDict (again) :\n{magic_tree}\n")
    return magic_tree



if __name__ == "__main__":
    tree = test_magic_tree_dict()
    tree.print_leaf_info()

# # Expected output (2023-10-08):
# Original MagicTreeDict:
# 🌱
# └── a
#     ├── b
#     │   ├── c
#     │   │   ├── woo: [1, 2, 13]
#     │   │   ├── woo2: ✨
#     │   │   └── hey: [71, 8, 9]
#     │   └── ??️: [[1. 0. 0.]
#     │        [0. 1. 0.]
#     │        [0. 0. 1.]]
#     └── c
#         └── bang: [4, 51, 6]
#
#
# Calculate tree stats and return in new MagicTreeDict:
# 🌱
# └── a
#     ├── b
#     │   └── c
#     │       ├── woo
#     │       │   ├── data: [1, 2, 13]
#     │       │   ├── mean: 5.333333333333333
#     │       │   └── std: 5.436502143433364
#     │       └── hey
#     │           ├── data: [71, 8, 9]
#     │           ├── mean: 29.333333333333332
#     │           └── std: 29.465610840812758
#     └── c
#         └── bang
#             ├── data: [4, 51, 6]
#             ├── mean: 20.333333333333332
#             └── std: 21.69997439834639
#
#
# Original MagicTreeDict (again) :
# 🌱
# └── a
#     ├── b
#     │   ├── c
#     │   │   ├── woo: [1, 2, 13]
#     │   │   ├── woo2: ✨
#     │   │   └── hey: [71, 8, 9]
#     │   └── ??️: [[1. 0. 0.]
#     │        [0. 1. 0.]
#     │        [0. 0. 1.]]
#     └── c
#         └── bang: [4, 51, 6]
#
#
# 🌱
# └── a
#     ├── b
#     │   ├── c
#     │   │   ├── woo
#     │   │   │   ├── type: list
#     │   │   │   ├── info: [1, 2, 13]
#     │   │   │   ├── nbytes: 88
#     │   │   │   └── memory_address: 0x1f33561d6c0
#     │   │   ├── woo2
#     │   │   │   ├── type: str
#     │   │   │   ├── info: ✨
#     │   │   │   ├── nbytes: 76
#     │   │   │   └── memory_address: 0x1f303fb4990
#     │   │   └── hey
#     │   │       ├── type: list
#     │   │       ├── info: [71, 8, 9]
#     │   │       ├── nbytes: 88
#     │   │       └── memory_address: 0x1f3355d5b40
#     │   └── ??️
#     │       ├── type: ndarray
#     │       ├── info: [[1. 0. 0.]
#     │       │    [0. 1. ..
#     │       ├── nbytes: 200
#     │       └── memory_address: 0x1f3352bbc30
#     └── c
#         └── bang
#             ├── type: list
#             ├── info: [4, 51, 6]
#             ├── nbytes: 88
#             └── memory_address: 0x1f3355d5940
#
#
# Process finished with exit code 0
