# src/flatcode/utils/tokenizer.py
import sys
from functools import lru_cache

try:
    import tiktoken
except ImportError:
    # 这里的错误处理通常在 CLI 层做，但在 Utils 层若缺失可抛出 ImportError
    tiktoken = None

class Tokenizer:
    _encoding = None

    @classmethod
    def get_encoding(cls):
        if cls._encoding is None:
            if tiktoken is None:
                raise ImportError("tiktoken not installed")
            try:
                cls._encoding = tiktoken.get_encoding("cl100k_base")
            except Exception:
                # Fallback
                cls._encoding = tiktoken.get_encoding("p50k_base")
        return cls._encoding

    @staticmethod
    def count(text: str) -> int:
        """Estimates token count for a given text."""
        try:
            encoding = Tokenizer.get_encoding()
            return len(encoding.encode(text))
        except Exception:
            # Fallback estimation strategy
            return len(text) // 4
