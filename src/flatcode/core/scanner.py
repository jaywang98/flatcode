# src/flatcode/core/scanner.py
import sys
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

    def scan(self) -> Iterator[FileContext]:
        """Yields FileContext objects for valid files."""
        for path in self.root_dir.rglob("*"):
            if not path.is_file():
                continue
            
            rel_path = path.relative_to(self.root_dir)
            
            # 1. Ignore Check
            if is_path_ignored(rel_path, self.ignore_rules):
                continue
            
            # 2. Extension Check (Skip if match_all is True)
            if not self.match_all:
                if not (path.suffix in self.extensions or path.name in self.extensions):
                    continue
            
            # 3. Read & Tokenize
            try:
                content = path.read_text(encoding="utf-8")
                tokens = Tokenizer.count(content)
                yield FileContext(
                    path=path,
                    rel_path=rel_path.as_posix(),
                    content=content,
                    token_count=tokens
                )
            except UnicodeDecodeError:
                # Silently skip binary files
                continue
            except Exception as e:
                print(f"  > [Warning] Skipping {rel_path.as_posix()} (read error: {e})", file=sys.stderr)
