# src/flatcode/core/scanner.py
import sys
import os
from pathlib import Path
from typing import Iterator, Set
import pathspec

from flatcode.models import FileContext
from flatcode.utils.tokenizer import Tokenizer

class ProjectScanner:
    def __init__(self, root_dir: Path, ignore_spec: pathspec.PathSpec, extensions: Set[str]):
        self.root_dir = root_dir
        self.ignore_spec = ignore_spec
        self.extensions = extensions
        self.match_all = "*" in extensions

    def _is_binary_file(self, path: Path) -> bool:
        """
        Reads the first 1024 bytes to check for null bytes.
        Returns True if likely binary, False if likely text.
        """
        try:
            with path.open("rb") as f:
                chunk = f.read(1024)
                return b'\0' in chunk
        except Exception:
            return True

    def scan(self) -> Iterator[FileContext]:
        """
        Walks the directory tree, pruning ignored directories efficiently,
        and yields FileContext objects for valid text files.
        """
        for root, dirs, files in os.walk(self.root_dir):
            root_path = Path(root)
            
            # --- 1. Prune Directories ---
            # Remove ignored directories from 'dirs' to prevent descending into them.
            # Iterating backwards or over a copy to allow safe removal.
            for d in list(dirs):
                dir_abs_path = root_path / d
                try:
                    dir_rel_path = dir_abs_path.relative_to(self.root_dir)
                except ValueError:
                    continue

                # IMPORTANT: We append '/' to tell pathspec this is a directory.
                # Git rules like "node_modules/" match directories specifically.
                check_path = dir_rel_path.as_posix() + "/"
                
                if self.ignore_spec.match_file(check_path):
                    dirs.remove(d)

            # --- 2. Process Files ---
            for f in files:
                file_abs_path = root_path / f
                try:
                    rel_path = file_abs_path.relative_to(self.root_dir)
                except ValueError:
                    continue
                
                rel_path_str = rel_path.as_posix()

                # A. Ignore Check (PathSpec)
                if self.ignore_spec.match_file(rel_path_str):
                    continue

                # B. Extension Check
                if not self.match_all:
                    # Using path suffix check
                    if not (file_abs_path.suffix in self.extensions or file_abs_path.name in self.extensions):
                        continue

                # C. Binary Check
                if self._is_binary_file(file_abs_path):
                    continue

                try:
                    content = file_abs_path.read_text(encoding="utf-8")
                    tokens = Tokenizer.count(content)
                    yield FileContext(
                        path=file_abs_path,
                        rel_path=rel_path_str,
                        content=content,
                        token_count=tokens
                    )
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    print(f"  > [Warning] Skipping {rel_path_str} (read error: {e})", file=sys.stderr)