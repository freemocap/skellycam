from collections import defaultdict
from typing import List

import numpy as np
from rich.console import Console
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

    def calculate_tree_stats(self,
                             metrics: List[str] = None,
                             data_names: List[str] = None,
                             make_new_tree: bool = True):
        metrics = metrics or ['mean', 'std']
        data_names = data_names or ['ALL']
        leaf_paths = self.get_leaf_paths()

        stats_tree = MagicTreeDict() if make_new_tree else self

        for path in leaf_paths:
            leaf_orig = self.data_from_path(path)
            data_name = path[-1]

            if isinstance(leaf_orig, list) and (data_name in data_names or data_names == ['ALL']):
                stats_tree.data_from_path(path)[data_name] = leaf_orig  # preserve the original list

                if 'mean' in metrics:
                    stats_tree.data_from_path(path)[f'{data_name}_mean'] = np.mean(leaf_orig)

                if 'std' in metrics:
                    stats_tree.data_from_path(path)[f'{data_name}_std'] = np.std(leaf_orig)

        return stats_tree

    def data_from_path(self, path: List[str], current=None):
        if current is None:
            current = self
        return current if len(path) == 0 else self.data_from_path(path[1:], current=current[path[0]])

    def __repr__(self):
        return repr(dict(self))

    def __str__(self):
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


def test_magic_tree_dict():
    magic_dict = MagicTreeDict()
    magic_dict['a']['b']['c']['woo'] = [1, 2, 13]
    magic_dict['a']['b']['c']['bang'] = [4, 51, 6]
    magic_dict['a']['b']['d']['hey'] = [71, 8, 9]

    print(f"Original MagicTreeDict:\n{magic_dict}\n")

    stats = magic_dict.calculate_tree_stats()
    print(f"MagicTreeDict with mean and std calculations:\n{stats}\n")

    just_stats = magic_dict.calculate_tree_stats(make_new_tree=True)
    print(f"MagicTreeDict with ONLY  mean and std calculations:\n{just_stats}\n")


if __name__ == "__main__":
    test_magic_tree_dict()
