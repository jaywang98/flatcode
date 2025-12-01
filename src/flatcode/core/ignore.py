# src/flatcode/core/ignore.py
import sys
from pathlib import Path
from typing import List, Optional
import pathspec
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
            # In a real app, dependency injection for input() is better
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

def load_ignore_spec(mergeignore_file: Path, extra_patterns: Optional[List[str]] = None) -> pathspec.PathSpec:
    """
    Loads rules from .mergeignore and creates a PathSpec object.
    Includes any extra patterns (like the output filename).
    """
    lines = []
    
    # 1. Read file if exists
    if mergeignore_file.exists():
        with open(mergeignore_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    
    # 2. Add extra patterns (e.g., output file)
    if extra_patterns:
        lines.extend(extra_patterns)

    # 3. Create spec using GitWildMatch (standard git behavior)
    try:
        spec = pathspec.PathSpec.from_lines("gitwildmatch", lines)
        return spec
    except Exception as e:
        print(f"Error parsing ignore rules: {e}", file=sys.stderr)
        # Return an empty spec on failure to prevent crash, though risky
        return pathspec.PathSpec.from_lines("gitwildmatch", [])