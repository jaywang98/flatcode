# src/flatcode/cli.py
import sys
import argparse
import os
from pathlib import Path

# Module imports
from flatcode.core.ignore import bootstrap_mergeignore, load_ignore_spec
from flatcode.core.scanner import ProjectScanner
from flatcode.core.tree import generate_project_tree
from flatcode.models import FileContext

def create_arg_parser():
    parser = argparse.ArgumentParser(
        description="A smart CLI tool to 'flatten' your project's code into a single, LLM-friendly context file."
    )
    parser.add_argument("root_dir", type=str, nargs="?", default=os.getcwd(), help="Project root directory")
    
    # [Modify] 默认值改为 None，以便在 main 中动态生成
    parser.add_argument(
        "-o", "--output", 
        type=str, 
        default=None, 
        help="Output filename (default: {folder_name}_context.txt)"
    )
    
    parser.add_argument("-e", "--extensions", type=str, default="*", help="Comma-separated file extensions or '*' for all")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")
    return parser

def get_default_output_name(root_dir: Path) -> str:
    """Generates a dynamic filename based on the directory name."""
    # 获取目录名称 (如 'backend')
    folder_name = root_dir.name
    
    # 边界情况：如果是根目录或无法获取名称
    if not folder_name:
        folder_name = "project"
        
    # 简单的清理（可选）：将空格替换为下划线，防止文件名带空格
    safe_name = folder_name.replace(" ", "_")
    
    return f"{safe_name}_context.txt"

def main():
    try:
        # 1. Setup
        parser = create_arg_parser()
        args = parser.parse_args()
        
        root_dir = Path(args.root_dir).resolve()
        if not root_dir.is_dir():
            print(f"Error: Invalid directory '{root_dir}'", file=sys.stderr)
            sys.exit(1)

        # [Modify] 动态计算输出文件名
        if args.output:
            output_file_name = args.output
        else:
            output_file_name = get_default_output_name(root_dir)
            
        output_file = root_dir / output_file_name
        
        # Parse extensions
        raw_exts = args.extensions.strip()
        extensions = {"*"} if raw_exts == "*" else {e.strip() for e in raw_exts.split(",")}

        print(f"--- flatcode ---")
        print(f"Scanning: {root_dir}")
        print(f"Output:   {output_file.name}") # 提示用户输出文件名
        print(f"Mode:     {'All non-ignored text files' if '*' in extensions else f'Extensions {extensions}'}")

        # 2. Ignore Rules (Using PathSpec)
        # 传入 output_file_name 而不是 args.output，确保动态生成的文件名被添加到 ignore
        mergeignore_file = bootstrap_mergeignore(root_dir, output_file_name)
        
        # Load spec and inject the output filename as an extra pattern to ignore
        ignore_spec = load_ignore_spec(mergeignore_file, extra_patterns=[output_file_name])

        # 3. Scanning
        scanner = ProjectScanner(root_dir, ignore_spec, extensions)
        files_to_merge: list[FileContext] = list(scanner.scan())
        
        if not files_to_merge:
            print("No matching files found.")
            return

        # 4. Review & Stats
        files_to_merge.sort(key=lambda x: x.token_count, reverse=True)
        total_tokens = sum(f.token_count for f in files_to_merge)

        print("\n--- Top 10 Largest Files (Est. Tokens) ---")
        print(f"{'Rank':<5} | {'Tokens':<10} | {'File Path'}")
        print("-" * 60)
        for i, f in enumerate(files_to_merge[:10]):
            print(f"{i+1:<5} | {f.token_count:<10} | {f.rel_path}")
        print("-" * 60)
        print(f"Total files: {len(files_to_merge)}")
        print(f"Total tokens: {total_tokens}")
        print("-" * 60)

        if not args.yes:
            pass 

        # 5. Output Generation
        tree_str = generate_project_tree([f.rel_path for f in files_to_merge], root_dir.name)
        
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"# --- flatcode Context ---\n")
                f.write(f"# Files: {len(files_to_merge)} | Tokens: {total_tokens}\n")
                f.write(f"# --- Project Tree ---\n")
                f.write(tree_str)
                f.write(f"# --- Context Start ---\n\n")
                
                for fc in files_to_merge:
                    f.write(f"--- File: {fc.rel_path} ---\n\n")
                    f.write(fc.content)
                    f.write(f"\n\n--- End: {fc.rel_path} ---\n\n")
            print(f"\nSuccess! Context written to: {output_file.name}")
            
        except IOError as e:
            print(f"Error writing file: {e}", file=sys.stderr)

    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)

    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()