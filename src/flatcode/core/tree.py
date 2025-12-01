# src/flatcode/core/tree.py
from typing import List, Dict
from pathlib import Path

def generate_project_tree(file_paths: List[str], root_name: str) -> str:
    """Generates a string representation of the project tree."""
    tree_dict: Dict = {}
    for path in sorted(file_paths):
        parts = Path(path).parts
        current_level = tree_dict
        for part in parts:
            if part not in current_level:
                current_level[part] = {}
            current_level = current_level[part]

    lines = [f"{root_name}/"]

    def _generate_lines_recursive(subtree: Dict, prefix: str):
        entries = sorted(subtree.items())
        for i, (name, content) in enumerate(entries):
            is_last = (i == len(entries) - 1)
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{name}")
            
            if content:
                new_prefix = prefix + ("    " if is_last else "│   ")
                _generate_lines_recursive(content, new_prefix)

    _generate_lines_recursive(tree_dict, "")
    return "\n".join(lines) + "\n"
