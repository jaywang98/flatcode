# tests/test_refactored.py

import sys
import pytest
from pathlib import Path
import pathspec

# 确保 src 在路径中
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from flatcode.core.scanner import ProjectScanner
# [Change] load_ignore_rules -> load_ignore_spec, is_path_ignored is removed
from flatcode.core.ignore import load_ignore_spec
from flatcode.core.tree import generate_project_tree
from flatcode.cli import main
from unittest.mock import patch

# --- Fixtures ---

@pytest.fixture
def complex_project(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("print('hello')", encoding="utf-8")
    
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "app.log").write_text("error", encoding="utf-8")
    
    (tmp_path / ".mergeignore").write_text("logs/\n", encoding="utf-8")
    
    return tmp_path

# --- 1. Ignore Logic Tests (Using PathSpec) ---

def test_ignore_spec_loading(tmp_path):
    """验证 PathSpec 对象的正确加载"""
    ignore_file = tmp_path / ".mergeignore"
    ignore_file.write_text("node_modules/\n*.log", encoding="utf-8")
    
    spec = load_ignore_spec(ignore_file)
    
    # PathSpec 测试
    assert spec.match_file("node_modules/") is True
    assert spec.match_file("app.log") is True
    assert spec.match_file("src/main.py") is False

def test_ignore_spec_extra_patterns(tmp_path):
    """验证额外的模式（如 output file）是否被包含"""
    ignore_file = tmp_path / ".mergeignore"
    ignore_file.write_text("", encoding="utf-8") # Empty file
    
    # 模拟 CLI 传入 output filename
    spec = load_ignore_spec(ignore_file, extra_patterns=["output.txt"])
    
    assert spec.match_file("output.txt") is True

# --- 2. Scanner Tests ---

def test_scanner_pruning_performance(tmp_path):
    """
    验证 os.walk 配合 PathSpec 的剪枝能力。
    """
    ign_dir = tmp_path / "node_modules"
    deep_dir = ign_dir / "deep" / "nested"
    deep_dir.mkdir(parents=True)
    (deep_dir / "index.js").write_text("console.log('heavy')", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('ok')", encoding="utf-8")
    
    # 构造 Spec
    spec = pathspec.PathSpec.from_lines("gitwildmatch", ["node_modules/"])
    extensions = {"*"}
    
    scanner = ProjectScanner(tmp_path, spec, extensions)
    results = list(scanner.scan())
    paths = [f.rel_path for f in results]
    
    assert "main.py" in paths
    assert "node_modules/deep/nested/index.js" not in paths

def test_scanner_wildcard_glob(tmp_path):
    """
    [New] 验证 pathspec 的高级匹配能力 (** 递归)
    """
    src = tmp_path / "src"
    src.mkdir()
    (src / "test.js").write_text("...", encoding="utf-8")
    (src / "ignore_me.js").write_text("...", encoding="utf-8")
    
    # 规则：忽略所有目录下的 ignore_*.js
    spec = pathspec.PathSpec.from_lines("gitwildmatch", ["**/ignore_*.js"])
    extensions = {"*"}
    
    scanner = ProjectScanner(tmp_path, spec, extensions)
    results = list(scanner.scan())
    paths = [f.rel_path for f in results]
    
    assert "src/test.js" in paths
    assert "src/ignore_me.js" not in paths

def test_scanner_binary_guard(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "info.txt").write_text("text", encoding="utf-8")
    (assets / "logo.png").write_bytes(b"PNG\x00\x00") # Binary

    spec = pathspec.PathSpec.from_lines("gitwildmatch", []) # Nothing ignored
    extensions = {"*"}
    
    scanner = ProjectScanner(tmp_path, spec, extensions)
    results = list(scanner.scan())
    paths = [f.rel_path for f in results]
    
    assert "assets/info.txt" in paths
    assert "assets/logo.png" not in paths

# --- 3. CLI Integration ---

def test_cli_integration(complex_project, monkeypatch):
    output_file = complex_project / "output.txt"
    test_args = ["flatcode", str(complex_project), "-o", output_file.name, "-y"]
    
    with patch.object(sys, "argv", test_args):
        monkeypatch.setattr("builtins.input", lambda _: "n")
        main()
    
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "src/main.py" in content
    assert "logs/app.log" not in content


def test_cli_dynamic_naming(complex_project, monkeypatch):
    """
    [New] 验证未指定 -o 时，是否根据目录名动态生成文件名
    """
    # complex_project 是一个临时目录，比如 /tmp/pytest-of-user/pytest-1/complex_project0
    dir_name = complex_project.name
    expected_filename = f"{dir_name}_context.txt"
    expected_file_path = complex_project / expected_filename
    
    # 不传 -o 参数
    test_args = ["flatcode", str(complex_project), "-y"]
    
    with patch.object(sys, "argv", test_args):
        monkeypatch.setattr("builtins.input", lambda _: "n")
        main()
    
    assert expected_file_path.exists()
    print(f"Successfully generated dynamic file: {expected_file_path.name}")