# src/flatcode/cli.py

import os
import sys
import fnmatch
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Set

# Attempt to import the 'tiktoken' dependency
try:
    import tiktoken
except ImportError:
    print("Error: The 'tiktoken' library is required. Please install it.", file=sys.stderr)
    print("You can typically install dependencies with: pip install -e .", file=sys.stderr)
    sys.exit(1)

# --- .mergeignore Bootstrapper ---

# Default patterns used if .gitignore is not found or not used
DEFAULT_IGNORE_PATTERNS = [
    "# Default ignore patterns",
    ".git/",
    "node_modules/",
    "venv/",
    ".venv/",
    "__pycache__/",
    "dist/",
    "build/",
    ".vscode/",
    ".idea/",
    ".DS_Store",
    "*.log",
    "logs/",
]

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
            print("Using default ignore patterns.")
            patterns_to_write = DEFAULT_IGNORE_PATTERNS
        
        # Ensure the output file itself is always ignored
        if output_filename not in patterns_to_write:
            patterns_to_write.append(f"\n# Exclude this tool's output\n{output_filename}")

        with open(mergeignore_file, "w", encoding="utf-8") as f:
            f.write("\n".join(patterns_to_write))
        
        print(f"Successfully created: {mergeignore_file.name}")
        print("You can now edit this file to customize which files are merged.")
        print("Use '!' to force-include a file (e.g., !src/important.py).")
        input("Press Enter to continue...")
        return mergeignore_file

    except Exception as e:
        print(f"Error creating .mergeignore: {e}", file=sys.stderr)
        sys.exit(1)

# --- .mergeignore Parser ---

def load_ignore_rules(mergeignore_file: Path) -> List[Tuple[str, bool]]:
    """
    Loads .mergeignore rules.
    Returns a list of tuples: (pattern, is_inclusion)
    """
    rules = []
    if not mergeignore_file.exists():
        return rules
    
    with open(mergeignore_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            if line.startswith("!"):
                # Inclusion rule
                rules.append((line[1:].strip(), True))
            else:
                # Exclusion rule
                rules.append((line.strip(), False))
    return rules

def is_path_ignored(rel_path: Path, rules: List[Tuple[str, bool]]) -> bool:
    """
    Checks if a path should be ignored based on the .mergeignore rules.
    The last matching rule wins.
    """
    rel_path_posix = rel_path.as_posix()
    ignored = False  # Default: not ignored
    
    for pattern, is_inclusion in rules:
        match = False
        
        # Check for directory match (e.g., "venv/")
        if pattern.endswith('/'):
            if rel_path_posix.startswith(pattern):
                match = True
        
        # Check for file/path match
        else:
            if fnmatch.fnmatch(rel_path_posix, pattern) or fnmatch.fnmatch(rel_path.name, pattern):
                match = True
        
        if match:
            # Update ignore status based on the rule
            ignored = not is_inclusion
            
    return ignored

# --- Project Tree Generator ---

def generate_project_tree(file_paths: List[str], root_name: str) -> str:
    """Generates a string representation of the project tree from a list of file paths."""
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
            
            if content:  # It's a directory, recurse
                new_prefix = prefix + ("    " if is_last else "│   ")
                _generate_lines_recursive(content, new_prefix)

    _generate_lines_recursive(tree_dict, "")
    return "\n".join(lines) + "\n"

# --- Token Estimator ---

# Initialize a global tokenizer to avoid reloading
# "cl100k_base" is the standard for gpt-4, gpt-3.5-turbo
try:
    TOKENIZER = tiktoken.get_encoding("cl100k_base")
except Exception:
    print("Warning: Could not load 'cl100k_base' tokenizer. Defaulting to 'p50k_base'.", file=sys.stderr)
    try:
        TOKENIZER = tiktoken.get_encoding("p50k_base")
    except Exception as e:
        print(f"Fatal: Could not initialize tiktoken: {e}", file=sys.stderr)
        sys.exit(1)


def estimate_tokens(content: str) -> int:
    """Uses tiktoken for an accurate token count."""
    try:
        return len(TOKENIZER.encode(content))
    except Exception:
        # Fallback for encoding errors on specific files
        return int(len(content) / 4)

# --- Argument Parser ---

def create_arg_parser():
    """Creates the command-line argument parser"""
    parser = argparse.ArgumentParser(
        description="A smart CLI tool to 'flatten' your project's code into a single, LLM-friendly context file."
    )
    parser.add_argument(
        "root_dir",
        type=str,
        nargs="?",
        default=os.getcwd(),
        help="Project root directory (default: current directory)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="merged_code_context.txt",
        help="Output filename (default: merged_code_context.txt)"
    )
    parser.add_argument(
        "-e", "--extensions",
        type=str,
        default=".py,.js,.ts,.jsx,.tsx,.html,.css,.scss,.md,.json,.toml,.yaml,.yml,.sh,.bat,Dockerfile,.dockerfile",
        help="Comma-separated file extensions to include"
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Auto-confirm and skip the Top 10 approval step"
    )
    return parser

# --- Main Function ---

def main():
    try:
        # 1. Parse Arguments
        parser = create_arg_parser()
        args = parser.parse_args()

        root_dir = Path(args.root_dir).resolve()
        output_file_name = args.output
        output_file = root_dir / output_file_name
        include_extensions = {ext.strip() for ext in args.extensions.split(",")}
        
        if not root_dir.is_dir():
            print(f"Error: Path '{root_dir}' is not a valid directory.", file=sys.stderr)
            sys.exit(1)
            
        print(f"--- flatcode ---")
        print(f"Scanning project: {root_dir}")

        # 2. Bootstrap and load .mergeignore
        mergeignore_file = bootstrap_mergeignore(root_dir, output_file_name)
        ignore_rules = load_ignore_rules(mergeignore_file)
        
        # Ensure the output file itself is always ignored
        ignore_rules.append((output_file_name, False))

        # 3. Phase 1: Scan and Estimate
        # List to store tuples: (path_obj, relative_path_str, estimated_tokens, content_str)
        files_to_merge: List[Tuple[Path, str, int, str]] = []
        total_files_scanned = 0
        
        for path in root_dir.rglob("*"):
            total_files_scanned += 1
            
            if not path.is_file():
                continue
            
            rel_path = path.relative_to(root_dir)
            
            # Check if ignored by .mergeignore
            if is_path_ignored(rel_path, ignore_rules):
                continue
                
            # Check if it's one of the included extensions
            if not (path.suffix in include_extensions or path.name in include_extensions):
                continue

            # Read and estimate
            try:
                content = path.read_text(encoding="utf-8")
                tokens = estimate_tokens(content)
                files_to_merge.append((path, rel_path.as_posix(), tokens, content))
            except Exception as e:
                print(f"  > [Warning] Skipping {rel_path.as_posix()} (read error: {e})", file=sys.stderr)

        if not files_to_merge:
            print(f"\nScan complete. No matching files found to merge (scanned {total_files_scanned} items).")
            return

        # 4. Phase 1.5: Top 10 Review and Tree Generation
        files_to_merge.sort(key=lambda x: x[2], reverse=True)
        total_tokens = sum(f[2] for f in files_to_merge)

        print("\n--- Top 10 Largest Files (Est. Tokens) ---")
        print("-" * 70)
        print(f"{'Rank':<5} | {'Tokens (Est.)':<15} | {'File Path':<}")
        print("-" * 70)
        for i, (path, rel_path, tokens, content) in enumerate(files_to_merge[:10]):
            print(f"{i+1:<5} | {str(tokens):<15} | {rel_path}")
        print("-" * 70)
        print(f"Total files to merge: {len(files_to_merge)}")
        print(f"Total estimated tokens: {total_tokens}")
        print("-" * 70)
        
        # Generate the project tree string from the final list of files
        relative_paths_for_tree = [f[1] for f in files_to_merge]
        project_tree_str = generate_project_tree(relative_paths_for_tree, root_dir.name)

        # 5. Phase 2: Merge files
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"# --- flatcode: Project Context Snapshot --- #\n")
                f.write(f"# Root: {root_dir}\n")
                f.write(f"# Files: {len(files_to_merge)}\n")
                f.write(f"# Est. Tokens: {total_tokens}\n")
                f.write(f"# --- Project Tree --- #\n")
                f.write(project_tree_str)
                f.write(f"# --- Start of Context --- #\n\n")

                for path, rel_path, tokens, content in files_to_merge:
                    f.write(f"--- File: {rel_path} ---\n\n")
                    f.write(content)
                    f.write(f"\n\n--- End: {rel_path} ---\n\n")
            
        except IOError as e:
            print(f"\n*** Error writing to output file: {e} ***", file=sys.stderr)
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()