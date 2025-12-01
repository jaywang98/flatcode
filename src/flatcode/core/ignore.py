# src/flatcode/core/ignore.py
import sys
import fnmatch
from pathlib import Path
from typing import List, Tuple
from flatcode.config import DEFAULT_IGNORE_PATTERNS

def bootstrap_mergeignore(root_dir: Path, output_filename: str) -> Path:
    """Checks for .mergeignore; creates one if it doesn't exist."""
    mergeignore_file = root_dir / ".mergeignore"
    if mergeignore_file.exists():
        print(f"Found existing: {mergeignore_file.name}")
        return mergeignore_file

    print(f"'{mergeignore_file.name}' not found. Initializing...")
    gitignore_file = root_dir / ".gitignore"
    
    try:
        patterns_to_write = []
        if gitignore_file.exists():
            choice = input(f"> Found .gitignore. Copy rules to .mergeignore? (Y/n): ").strip().lower()
            if choice != 'n':
                with open(gitignore_file, "r", encoding="utf-8") as f_git:
                    patterns_to_write.extend(f_git.read().splitlines())
                print(f"Copied rules from .gitignore.")
        
        if not patterns_to_write:
            patterns_to_write = DEFAULT_IGNORE_PATTERNS
        
        # Ensure the output file itself is always ignored
        if output_filename not in patterns_to_write:
            patterns_to_write.append(f"\n# Exclude this tool's output\n{output_filename}")

        with open(mergeignore_file, "w", encoding="utf-8") as f:
            f.write("\n".join(patterns_to_write))
        
        print(f"Successfully created: {mergeignore_file.name}")
        return mergeignore_file

    except Exception as e:
        print(f"Error creating .mergeignore: {e}", file=sys.stderr)
        sys.exit(1)

def load_ignore_rules(mergeignore_file: Path) -> List[Tuple[str, bool]]:
    rules = []
    if not mergeignore_file.exists():
        return rules
    
    with open(mergeignore_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("!"):
                rules.append((line[1:].strip(), True))
            else:
                rules.append((line.strip(), False))
    return rules

def is_path_ignored(rel_path: Path, rules: List[Tuple[str, bool]], is_directory: bool = False) -> bool:
    """
    Checks if a path should be ignored.
    :param is_directory: Hint to help match patterns ending in '/' against directory paths without the slash.
    """
    rel_path_posix = rel_path.as_posix()
    
    # If checking a directory "venv" against "venv/", we append a slash to force matching logic
    if is_directory and not rel_path_posix.endswith("/"):
        check_path = rel_path_posix + "/"
    else:
        check_path = rel_path_posix

    ignored = False
    
    for pattern, is_inclusion in rules:
        match = False
        
        # 1. Directory-specific pattern (ends with /)
        if pattern.endswith('/'):
            # If pattern is "venv/", matches "venv/" (directory) or "venv/lib/..."
            if check_path.startswith(pattern) or check_path == pattern:
                match = True
        
        # 2. General pattern (glob)
        else:
            # Match full path or file name
            # e.g. "*.log" matches "logs/app.log" (via name)
            if fnmatch.fnmatch(rel_path_posix, pattern) or fnmatch.fnmatch(rel_path.name, pattern):
                match = True
        
        if match:
            ignored = not is_inclusion
            
    return ignored