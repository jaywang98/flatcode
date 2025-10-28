# tests/test_cli.py
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

# Import the functions from your CLI script
# We are in tests/, we need to go up and into src/
# (This assumes your PYTHONPATH is set up, which 'pip install -e .' does)
from flatcode.cli import is_path_ignored, main

# --- Test 1: Test the core ignore logic ---

@pytest.fixture
def sample_rules():
    """A fixture to provide sample .mergeignore rules."""
    return [
        ("*.log", False),          # Ignore all .log files
        ("venv/", False),          # Ignore the venv directory
        ("src/important.log", True), 
    ]

def test_is_path_ignored_simple(sample_rules):
    assert is_path_ignored(Path("app.log"), sample_rules) == True
    assert is_path_ignored(Path("src/app.log"), sample_rules) == True

def test_is_path_ignored_not_ignored(sample_rules):
    assert is_path_ignored(Path("src/main.py"), sample_rules) == False
    assert is_path_ignored(Path("README.md"), sample_rules) == False

def test_is_path_ignored_forced_inclusion(sample_rules):
    # This tests the "last match wins" logic
    assert is_path_ignored(Path("src/important.log"), sample_rules) == False

def test_is_path_ignored_directory(sample_rules):
    assert is_path_ignored(Path("venv/lib/python3.9"), sample_rules) == True


# --- Test 2: Test the full end-to-end run ---

def test_end_to_end_run(tmp_path, monkeypatch):
    """
    Simulates a full run of the 'flatcode' command in a temporary directory.
    - tmp_path: Creates a fake directory
    - monkeypatch: Allows us to safely change context (like 'input')
    """
    
    # 1. Setup: Create the fake project structure inside tmp_path
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("def hello():\n  print('hello')")
    (src_dir / "utils.py").write_text("# This is a utility")
    
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "app.log").write_text("ERROR: ...")
    
    (tmp_path / "README.md").write_text("# My Project")
    
    # 2. Setup: Create the .mergeignore file
    (tmp_path / ".mergeignore").write_text(
        "*.log\n"       # Ignore all logs
        "src/utils.py" # Ignore the utils file
    )
    
    # 3. Setup: Prepare arguments for the main() function
    # We will run: flatcode [tmp_path] --output test_merge.txt
    # We patch sys.argv to simulate command-line arguments
    test_args = ["flatcode", str(tmp_path), "--output", "test_merge.txt"]
    
    # 4. Setup: Mock the user confirmation input 'Y/n'
    # We patch 'builtins.input' to automatically return 'Y'
    monkeypatch.setattr('builtins.input', lambda _: 'Y')

    # 5. Execute: Run the main function
    with patch.object(sys, 'argv', test_args):
        main()

    # 6. Assert: Check the results
    output_file = tmp_path / "test_merge.txt"
    assert output_file.exists()
    
    content = output_file.read_text()
    
    # Check that the correct files are included
    assert "File: src/main.py" in content
    assert "def hello():" in content
    assert "File: README.md" in content
    assert "# My Project" in content
    
    # Check that the ignored files are NOT included
    assert "File: logs/app.log" not in content
    assert "File: src/utils.py" not in content