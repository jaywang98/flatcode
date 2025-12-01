# src/flatcode/core/ignore.py
import sys
from pathlib import Path
from typing import List, Optional
import pathspec
from flatcode.config import DEFAULT_IGNORE_PATTERNS

def bootstrap_mergeignore(root_dir: Path, output_filename: str) -> Path:
    """
    Checks for .mergeignore.
    1. If missing, create it with defaults + output_filename.
    2. If exists, check if output_filename is ignored. If not, append it.
    """
    mergeignore_file = root_dir / ".mergeignore"
    
    # --- Case 1: Create new .mergeignore ---
    if not mergeignore_file.exists():
        print(f"'{mergeignore_file.name}' not found. Initializing...")
        gitignore_file = root_dir / ".gitignore"
        
        try:
            patterns_to_write = []
            if gitignore_file.exists():
                # Side-effect: input() for interactive mode
                choice = input(f"> Found .gitignore. Copy rules to .mergeignore? (Y/n): ").strip().lower()
                if choice != 'n':
                    with open(gitignore_file, "r", encoding="utf-8") as f_git:
                        patterns_to_write.extend(f_git.read().splitlines())
                    print(f"Copied rules from .gitignore.")
            
            if not patterns_to_write:
                patterns_to_write = list(DEFAULT_IGNORE_PATTERNS) # Copy list
            
            # Add the output file explicitly
            if output_filename not in patterns_to_write:
                patterns_to_write.append(f"\n# Exclude this tool's output\n{output_filename}")

            with open(mergeignore_file, "w", encoding="utf-8") as f:
                f.write("\n".join(patterns_to_write))
            
            print(f"Successfully created: {mergeignore_file.name}")
            return mergeignore_file

        except Exception as e:
            print(f"Error creating .mergeignore: {e}", file=sys.stderr)
            sys.exit(1)

    # --- Case 2: Update existing .mergeignore ---
    else:
        try:
            # Check if the current output filename is already ignored by existing rules
            with open(mergeignore_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            spec = pathspec.PathSpec.from_lines("gitwildmatch", lines)
            
            # If the output file is NOT ignored by current rules, append it.
            if not spec.match_file(output_filename):
                print(f"Updating .mergeignore: Adding '{output_filename}' to ignore list.")
                with open(mergeignore_file, "a", encoding="utf-8") as f:
                    f.write(f"\n# Auto-added output file\n{output_filename}\n")
            
        except Exception as e:
            print(f"Warning: Could not update .mergeignore: {e}", file=sys.stderr)
        
        return mergeignore_file

def load_ignore_spec(mergeignore_file: Path, extra_patterns: Optional[List[str]] = None) -> pathspec.PathSpec:
    """
    Loads rules from .mergeignore and creates a PathSpec object.
    Includes any extra patterns (like the output filename) for runtime safety.
    """
    lines = []
    
    if mergeignore_file.exists():
        with open(mergeignore_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    
    if extra_patterns:
        lines.extend(extra_patterns)

    try:
        spec = pathspec.PathSpec.from_lines("gitwildmatch", lines)
        return spec
    except Exception as e:
        print(f"Error parsing ignore rules: {e}", file=sys.stderr)
        return pathspec.PathSpec.from_lines("gitwildmatch", [])