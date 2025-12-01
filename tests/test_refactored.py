# tests/test_refactored.py

import sys
import pytest
from pathlib import Path

# 确保 src 在路径中
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from flatcode.core.scanner import ProjectScanner
from flatcode.core.ignore import load_ignore_rules, is_path_ignored
from flatcode.core.tree import generate_project_tree
from flatcode.cli import main
from unittest.mock import patch

# --- Fixtures ---

@pytest.fixture
def complex_project(tmp_path):
    """
    基础测试环境
    """
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("print('hello')", encoding="utf-8")
    
    # 模拟被忽略的目录
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "app.log").write_text("error", encoding="utf-8")
    
    # .mergeignore
    (tmp_path / ".mergeignore").write_text("logs/\n", encoding="utf-8")
    
    return tmp_path

# --- 1. Ignore Logic Tests (Enhanced) ---

def test_ignore_logic_parsing(tmp_path):
    """验证 .mergeignore 规则解析"""
    ignore_file = tmp_path / ".mergeignore"
    ignore_file.write_text("node_modules/\n!src/keep.js", encoding="utf-8")
    rules = load_ignore_rules(ignore_file)
    assert ("node_modules/", False) in rules
    assert ("src/keep.js", True) in rules

def test_ignore_directory_exact_match():
    """
    [New] 验证目录匹配逻辑。
    规则 'venv/' 应该匹配目录 'venv' (当 is_directory=True 时)。
    这是 os.walk 剪枝的关键。
    """
    rules = [("venv/", False)]
    
    # Case A: 检查目录本身
    # 如果不加 is_directory=True，"venv" 不匹配 "venv/" (因为 startswith 检查)
    assert is_path_ignored(Path("venv"), rules, is_directory=True) is True
    
    # Case B: 检查子文件
    # "venv/lib/site.py" starts with "venv/" -> True
    assert is_path_ignored(Path("venv/lib/site.py"), rules, is_directory=False) is True

def test_is_path_ignored_logic():
    """验证混合规则逻辑"""
    rules = [
        ("logs/", False),
        ("*.tmp", False),
        ("logs/important.txt", True) # Whitelist (注意：测试数据不含 '!')
    ]
    
    assert is_path_ignored(Path("logs/debug.log"), rules) is True
    assert is_path_ignored(Path("temp.tmp"), rules) is True
    assert is_path_ignored(Path("src/main.py"), rules) is False
    # Whitelist logic
    assert is_path_ignored(Path("logs/important.txt"), rules) is False

# --- 2. Scanner Tests (Performance & Safety) ---

def test_scanner_pruning_performance(tmp_path):
    """
    [New] 验证 os.walk 的剪枝能力。
    如果在目录层级就被忽略，Scanner 不应进入深层目录。
    """
    # 构造结构: node_modules/deep/nested/package/index.js
    # 如果 pruning 工作正常，Scanner 看到 node_modules 就会停止，
    # 根本不会去处理 deep/nested... 节省 I/O
    
    ign_dir = tmp_path / "node_modules"
    deep_dir = ign_dir / "deep" / "nested"
    deep_dir.mkdir(parents=True)
    
    deep_file = deep_dir / "index.js"
    deep_file.write_text("console.log('heavy')", encoding="utf-8")
    
    # 普通文件
    (tmp_path / "main.py").write_text("print('ok')", encoding="utf-8")
    
    rules = [("node_modules/", False)]
    extensions = {"*"}
    
    scanner = ProjectScanner(tmp_path, rules, extensions)
    results = list(scanner.scan())
    paths = [f.rel_path for f in results]
    
    assert "main.py" in paths
    assert "node_modules/deep/nested/index.js" not in paths
    # (在实际运行中，使用 os.walk 调试可以看到 dirs 被修改了)

def test_scanner_binary_guard(tmp_path):
    """
    [New] 验证二进制文件防御机制 (_is_binary_file)。
    """
    assets = tmp_path / "assets"
    assets.mkdir()
    
    # 1. 纯文本文件
    text_file = assets / "info.txt"
    text_file.write_text("Just text", encoding="utf-8")
    
    # 2. 伪造的二进制文件 (包含 NULL 字节)
    bin_file = assets / "logo.png"
    # 写入 NULL 字节，这会触发 b'\0' in chunk 检测
    bin_file.write_bytes(b"PNG\x00\x00\x00IHDR")
    
    # 3. 另一种二进制 (只有 NULL)
    null_file = assets / "data.bin"
    null_file.write_bytes(b"\x00" * 100)

    # 规则：不忽略 assets，包含所有扩展名
    rules = []
    extensions = {"*"}
    
    scanner = ProjectScanner(tmp_path, rules, extensions)
    results = list(scanner.scan())
    paths = [f.rel_path for f in results]
    
    assert "assets/info.txt" in paths
    assert "assets/logo.png" not in paths # 应该被 Binary Guard 拦截
    assert "assets/data.bin" not in paths # 应该被拦截

def test_scanner_wildcard_behavior(complex_project):
    """验证 '*' 通配符包含所有文本文件"""
    ignore_rules = [("logs/", False)] 
    extensions = {"*"}

    scanner = ProjectScanner(complex_project, ignore_rules, extensions)
    results = list(scanner.scan())
    paths = [f.rel_path for f in results]
    
    assert "src/main.py" in paths
    assert "logs/app.log" not in paths

# --- 3. Tree Generation ---

def test_tree_generation():
    paths = ["src/main.py", "README.md"]
    tree = generate_project_tree(paths, "root")
    assert "root/" in tree
    assert "├── main.py" in tree or "└── main.py" in tree

# --- 4. CLI Integration ---

def test_cli_integration(complex_project, monkeypatch):
    """集成测试：确保 CLI 能把所有模块串起来"""
    output_file = complex_project / "output.txt"
    test_args = ["flatcode", str(complex_project), "-o", output_file.name, "-y"]
    
    with patch.object(sys, "argv", test_args):
        # 模拟不覆盖/不复制 gitignore
        monkeypatch.setattr("builtins.input", lambda _: "n")
        main()
    
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "src/main.py" in content
    # 确保没有包含被忽略的文件
    assert "logs/app.log" not in content