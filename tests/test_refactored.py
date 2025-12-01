# tests/test_refactored.py

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# 确保 src 在路径中，以便导入模块
# 如果你已经 pip install -e . 安装了项目，这一步可能不是必须的，但加上更稳健
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from flatcode.core.scanner import ProjectScanner
from flatcode.core.ignore import load_ignore_rules, is_path_ignored
from flatcode.core.tree import generate_project_tree
from flatcode.cli import main

# --- Fixtures: 搭建测试用的临时文件系统 ---

@pytest.fixture
def complex_project(tmp_path):
    """
    创建一个包含多种情况的复杂文件结构：
    1. 普通代码文件 (.py)
    2. 被忽略的文件 (logs/)
    3. 二进制文件 (.png)
    4. 强制包含的文件 (!important.log)
    5. .mergeignore 文件
    """
    # 1. 创建目录
    src = tmp_path / "src"
    src.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    assets = tmp_path / "assets"
    assets.mkdir()

    # 2. 创建文本文件
    (src / "main.py").write_text("print('main')", encoding="utf-8")
    (src / "utils.py").write_text("def util(): pass", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Project", encoding="utf-8")

    # 3. 创建被忽略的文件
    (logs / "app.log").write_text("error...", encoding="utf-8")
    (logs / "important.log").write_text("SAVE ME", encoding="utf-8") # 我们将强制包含这个

    # 4. 创建二进制文件 (模拟图片)
    # 注意：使用 'wb' 写入随机字节，确保它无法被 utf-8 解码
    (assets / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    # 5. 创建 .mergeignore
    ignore_content = """
    logs/
    *.png
    !logs/important.log
    """
    (tmp_path / ".mergeignore").write_text(ignore_content, encoding="utf-8")

    return tmp_path

# --- Test 1: Core - Ignore Logic ---

def test_ignore_logic_parsing(tmp_path):
    """验证 .mergeignore 规则解析的正确性"""
    ignore_file = tmp_path / ".mergeignore"
    ignore_file.write_text("node_modules/\n!src/keep.js", encoding="utf-8")
    
    rules = load_ignore_rules(ignore_file)
    
    # 验证是否解析出了排除和包含规则
    assert ("node_modules/", False) in rules
    assert ("src/keep.js", True) in rules

def test_is_path_ignored_logic():
    """验证具体的路径匹配逻辑"""
    rules = [
        ("logs/", False),          # Exclude logs folder
        ("*.tmp", False),          # Exclude tmp files
        # [FIX] 去掉这里的 '!'。is_path_ignored 期望的是清洗后的 pattern 和 is_inclusion=True
        ("logs/important.txt", True) 
    ]
    
    # 应该被忽略
    # Rule 1 ("logs/") 匹配 -> ignored = True
    assert is_path_ignored(Path("logs/debug.log"), rules) is True
    
    # Rule 2 ("*.tmp") 匹配 -> ignored = True
    assert is_path_ignored(Path("temp.tmp"), rules) is True
    
    # 不应该被忽略
    # 没有规则匹配 -> default ignored = False
    assert is_path_ignored(Path("src/main.py"), rules) is False
    
    # 强制包含 (Whitelist)
    # Step 1: 匹配 "logs/" -> ignored = True
    # Step 2: 匹配 "logs/important.txt" (is_inclusion=True) -> ignored = False (覆盖生效)
    assert is_path_ignored(Path("logs/important.txt"), rules) is False
# --- Test 2: Core - Scanner Logic (核心测试) ---

def test_scanner_wildcard_behavior(complex_project):
    """
    测试 Scanner 在 '*' 模式下的表现：
    1. 应包含 src/main.py (普通文本)
    2. 应跳过 assets/image.png (二进制文件，虽然未在ignore中显式排除，但读取失败应静默跳过)
       *注：这里我们在 fixture 的 .mergeignore 里显式排除了 *.png，为了测试二进制跳过，我们需要临时修改规则
    """
    
    # 准备规则：我们故意不忽略 .png，看看 Scanner 是否会因为 UnicodeDecodeError 炸掉
    # 仅忽略 logs/ 目录
    ignore_rules = [("logs/", False)] 
    extensions = {"*"} # 通配符模式

    scanner = ProjectScanner(complex_project, ignore_rules, extensions)
    results = list(scanner.scan())
    
    paths = [f.rel_path for f in results]
    
    # 验证：
    assert "src/main.py" in paths
    assert "README.md" in paths
    
    # 验证二进制文件即使没被忽略，也被静默跳过（不在结果中）
    # 如果代码没有处理 UnicodeDecodeError，这里会抛出异常失败
    assert "assets/image.png" not in paths
    
    # 验证忽略规则生效
    assert "logs/app.log" not in paths

def test_scanner_specific_extensions(complex_project):
    """测试指定后缀模式"""
    # 仅扫描 .py
    ignore_rules = []
    extensions = {".py"}
    
    scanner = ProjectScanner(complex_project, ignore_rules, extensions)
    results = list(scanner.scan())
    paths = [f.rel_path for f in results]
    
    assert "src/main.py" in paths
    assert "src/utils.py" in paths
    assert "README.md" not in paths # 应该被过滤掉

# --- Test 3: Core - Tree Generation ---

def test_tree_generation():
    paths = [
        "src/main.py",
        "src/utils/helper.py",
        "README.md"
    ]
    tree_str = generate_project_tree(paths, root_name="my_project")
    
    # 简单的字符串包含检查
    assert "my_project/" in tree_str
    assert "src" in tree_str
    assert "├── main.py" in tree_str or "└── main.py" in tree_str

# --- Test 4: Integration - CLI Entry Point ---

def test_cli_integration(complex_project, monkeypatch, capsys):
    """
    模拟完整的命令行调用
    """
    output_file = complex_project / "output.txt"
    
    # 模拟参数: flatcode [root] -o output.txt -y
    # 使用 -y 跳过确认
    test_args = [
        "flatcode", 
        str(complex_project), 
        "-o", output_file.name,
        "-y"
    ]
    
    # Mock sys.argv
    with patch.object(sys, "argv", test_args):
        # Mock input 避免 bootstrap 过程中的交互 (虽然 -y 跳过最后的确认，但 bootstrap 可能仍需确认复制 gitignore)
        # 这里我们假设 bootstrap 逻辑中如果存在 gitignore 可能会问。
        # 让 input 永远返回 'n' 以跳过复制
        monkeypatch.setattr("builtins.input", lambda _: "n")
        
        main()
    
    # 验证输出文件是否生成
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    
    # 验证内容
    assert "--- File: src/main.py ---" in content
    assert "# Project" in content
    # 验证被忽略的没进来
    assert "logs/app.log" not in content
    # 验证二进制没进来
    assert "PNG" not in content
