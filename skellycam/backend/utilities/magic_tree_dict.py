import collections
import sys
from collections import defaultdict
from typing import Any
from typing import List, Union

import numpy as np
import pandas as pd
import rich.tree
from rich.console import Console
from rich.tree import Tree
from tabulate import tabulate


class TreePrinter:
    def __init__(self, tree: 'MagicTreeDict'):
        self.tree = tree

    def __str__(self):
        try:
            console = Console()
            with console.capture() as capture:
                rich_tree = Tree(":seedling:")
                self._add_branch(rich_tree, dict(self.tree))
                console.print(rich_tree)
            return capture.get()
        except Exception as e:
            print(f"Failed to print tree: {e}")
            raise e

    def _add_branch(self, rich_tree: rich.tree.Tree, subdict):
        try:
            for key, value in subdict.items():
                if isinstance(value, dict):
                    branch = rich_tree.add(str(key))
                    self._add_branch(branch, value)
                else:
                    value = str(value)  # try to convert it to a string
                    rich_tree.add(f"{key}: {value}")
        except Exception as e:
            print(f"Failed to add branch: {e}")
            raise e

    def print_table(self, leaf_keys: Union[str, List[str]]):
        df = self.tree.to_dataframe(leaf_keys=leaf_keys)
        print(tabulate(df, headers='keys', tablefmt='psql'))


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

    def get_leaf_keys(self):
        """
        Returns all the keys of leaf nodes in the tree.
        """
        leaf_keys = []
        self._traverse_tree(lambda path, value: leaf_keys.append(path[-1]))
        return leaf_keys

    def get_path_to_leaf(self, leaf_key: str) -> List[str]:
        """
        Returns the path to a specified leaf in the tree.
        """
        leaf_paths = []
        self._traverse_tree(lambda path, value: leaf_paths.append(path) if path[-1] == leaf_key else None)

        if not leaf_paths:
            raise KeyError(f"Leaf key '{leaf_key}' not found in tree.")

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

    def print_table(self, keys: Union[str, List[str]] = None):
        if isinstance(keys, str):
            keys = [keys]
        TreePrinter(tree=self).print_table(keys)

    def get_paths_for_keys(self, keys):
        paths = []
        self._traverse_tree(lambda path, value: paths.append(path) if path[-1] in keys else None)
        return paths

    def filter_tree(self, target_key, current=None, path=None):
        """
        Returns a new tree containing only the branches and leaves that contain the target key.
        """
        new_tree = MagicTreeDict()
        paths = self.get_paths_for_keys(keys=[target_key])
        if len(paths) == 0:
            raise KeyError(f"'{target_key}' not found in tree...")

        for path in paths:
            new_tree[path] = self.data_from_path(path)

        return new_tree

    def to_dataframe(self, leaf_keys: Union[str, List[str]] = None):
        if leaf_keys is None:
            leaf_keys = self.get_leaf_keys()

        paths = [self.get_path_to_leaf(leaf_key=key) for key in leaf_keys]
        paths = [path for sublist in paths for path in sublist]  # flatten list

        table_dict = {}
        leaf_lengths = set()

        for path in paths:
            data = self.data_from_path(path)
            if hasattr(data, '__iter__'):
                leaf_lengths.add(len(data))
            else:
                leaf_lengths.add(1)

            if tuple(path) in table_dict:
                raise ValueError(
                    f"Error at path level {path} - Path is not unique. Ensure each path in your tree is unique - exisiting paths: {table_dict.keys()}")
            table_dict[tuple(path)] = data

        if len(leaf_lengths) > 1:
            raise ValueError(
                f"Error at {path} level -  Leaf node data lengths are inconsistent. Ensure all leaf data have the same length or are scalar. Found lengths: {leaf_lengths}")

        return pd.DataFrame.from_dict(table_dict, orient='index').transpose()

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
            callback(new_path, value)
            if isinstance(value, defaultdict):
                self._traverse_tree(callback, value, new_path)

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

    def __dict__(self):
        def convert(default_dict):
            if isinstance(default_dict, defaultdict):
                default_dict = {k: convert(v) for k, v in default_dict.items()}
            return default_dict

        return convert(self)



def create_sample_magic_tree():
    magic_tree = MagicTreeDict()
    magic_tree['a']['b']['c']['woo'] = [1, 2, 13]
    magic_tree['a']['b']['c']['woo2'] = '✨'
    magic_tree['a']['b']['??️'] = np.eye(
        3)  # TODO - doesn't handle this correctly - skips it in stats, and prints matrix poorly
    magic_tree['a']['c']['bang'] = [4, 51, 6]
    magic_tree['a']['b']['c']['hey'] = [71, 8, 9]

    return magic_tree


def test_magic_tree_dict():
    tree = create_sample_magic_tree()
    print(f"Print as regular dict:\n")
    print(tree.__dict__())
    print(dict(tree)) #TODO - this still includes the defaultdicts, will need to override __iter__ or items or soemthing to fix this ish

    print(f"Original MagicTreeDict:\n{tree}\n\n")
    print(f"Calculate tree stats and return in new MagicTreeDict:\n{tree.calculate_tree_stats()}\n\n")
    print(f"Print Table:\n")
    tree.print_table(['woo', 'bang', 'hey'])

    print(f"Filter tree on `c`:\n")
    c_tree = tree.filter_tree('c')
    print(c_tree)

    stats = tree.calculate_tree_stats()
    print(f"Calculate Tree Stats:\n{stats}\n\n")
    print(f"Print stats table:\n")
    stats.print_table(['mean', 'std'])


if __name__ == "__main__":
    test_magic_tree_dict()

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
#
# Calculate tree stats and return in new MagicTreeDict:
# 🌱
# └── a
#     ├── b
#     │   └── c
#     │       ├── woo
#     │       │   ├── mean: 5.333333333333333
#     │       │   └── std: 5.436502143433364
#     │       └── hey
#     │           ├── mean: 29.333333333333332
#     │           └── std: 29.465610840812758
#     └── c
#         └── bang
#             ├── mean: 20.333333333333332
#             └── std: 21.69997439834639
#
#
#
# Print Table:
#
# +----+--------------------------+----------------------+--------------------------+
# |    |   ('a', 'b', 'c', 'woo') |   ('a', 'c', 'bang') |   ('a', 'b', 'c', 'hey') |
# |----+--------------------------+----------------------+--------------------------|
# |  0 |                        1 |                    4 |                       71 |
# |  1 |                        2 |                   51 |                        8 |
# |  2 |                       13 |                    6 |                        9 |
# +----+--------------------------+----------------------+--------------------------+
# Calculate Tree Stats:
# 🌱
# └── a
#     ├── b
#     │   └── c
#     │       ├── woo
#     │       │   ├── mean: 5.333333333333333
#     │       │   └── std: 5.436502143433364
#     │       └── hey
#     │           ├── mean: 29.333333333333332
#     │           └── std: 29.465610840812758
#     └── c
#         └── bang
#             ├── mean: 20.333333333333332
#             └── std: 21.69997439834639
#
#
#
# Print stats table:
#
# +----+----------------------------------+----------------------------------+------------------------------+---------------------------------+---------------------------------+-----------------------------+
# |    |   ('a', 'b', 'c', 'woo', 'mean') |   ('a', 'b', 'c', 'hey', 'mean') |   ('a', 'c', 'bang', 'mean') |   ('a', 'b', 'c', 'woo', 'std') |   ('a', 'b', 'c', 'hey', 'std') |   ('a', 'c', 'bang', 'std') |
# |----+----------------------------------+----------------------------------+------------------------------+---------------------------------+---------------------------------+-----------------------------|
# |  0 |                          5.33333 |                          29.3333 |                      20.3333 |                          5.4365 |                         29.4656 |                        21.7 |
# +----+----------------------------------+----------------------------------+------------------------------+---------------------------------+---------------------------------+-----------------------------+
#
# Process finished with exit code 0
