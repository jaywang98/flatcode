# src/flatcode/models.py
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class FileContext:
    """Immutable data class holding file information."""
    path: Path
    rel_path: str
    content: str
    token_count: int
