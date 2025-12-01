# src/flatcode/core/scanner.py
import sys
import os
from pathlib import Path
from typing import Iterator, Set, List, Tuple

from flatcode.models import FileContext
from flatcode.core.ignore import is_path_ignored
from flatcode.utils.tokenizer import Tokenizer

class ProjectScanner:
    def __init__(self, root_dir: Path, ignore_rules: List[Tuple[str, bool]], extensions: Set[str]):
        self.root_dir = root_dir
        self.ignore_rules = ignore_rules
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
            # If we can't read it (permission, etc), treat as unsafe/binary
            return True

    def scan(self) -> Iterator[FileContext]:
        """
        Walks the directory tree, pruning ignored directories efficiently,
        and yields FileContext objects for valid text files.
        """
        # 使用 os.walk 可以让我们修改 dirs 列表，从而阻止进入被忽略的目录 (Pruning)
        for root, dirs, files in os.walk(self.root_dir):
            root_path = Path(root)
            
            # --- 1. Prune Directories (In-place modification of dirs) ---
            # 这里的 dirs 是一个列表，os.walk 会根据它决定下一步进入哪里。
            # 我们通过倒序遍历安全地移除元素。
            for d in list(dirs):
                dir_abs_path = root_path / d
                try:
                    dir_rel_path = dir_abs_path.relative_to(self.root_dir)
                except ValueError:
                    continue # Should not happen in standard walk

                # Check if directory should be ignored
                # We pass is_directory=True to handle "venv/" vs "venv" matching
                if is_path_ignored(dir_rel_path, self.ignore_rules, is_directory=True):
                    dirs.remove(d)
                    # Optional: Debug output
                    # print(f"  [Debug] Pruning directory: {dir_rel_path}")

            # --- 2. Process Files ---
            for f in files:
                file_abs_path = root_path / f
                try:
                    rel_path = file_abs_path.relative_to(self.root_dir)
                except ValueError:
                    continue

                # A. Ignore Check
                if is_path_ignored(rel_path, self.ignore_rules, is_directory=False):
                    continue

                # B. Extension Check (Skip if match_all is True)
                if not self.match_all:
                    if not (file_abs_path.suffix in self.extensions or file_abs_path.name in self.extensions):
                        continue

                # C. Binary Check & Read
                if self._is_binary_file(file_abs_path):
                    # Silently skip binary files (or log in verbose mode)
                    continue

                try:
                    content = file_abs_path.read_text(encoding="utf-8")
                    tokens = Tokenizer.count(content)
                    yield FileContext(
                        path=file_abs_path,
                        rel_path=rel_path.as_posix(),
                        content=content,
                        token_count=tokens
                    )
                except UnicodeDecodeError:
                    # Double safety: mostly caught by _is_binary_file, but just in case
                    continue
                except Exception as e:
                    print(f"  > [Warning] Skipping {rel_path.as_posix()} (read error: {e})", file=sys.stderr)