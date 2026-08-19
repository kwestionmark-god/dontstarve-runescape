#!/usr/bin/env python3
"""Scan all __init__.py files for hygiene violations.

Rules:
- No class definitions
- No function definitions with >10 lines of body (non-import, non-docstring)
- Total file should be <= 80 lines

Usage: python tools/check_init_hygiene.py [root_dir]
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def check_file(path: Path) -> list[str]:
    """Return list of violation descriptions for one __init__.py."""
    violations: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [f"{path}: unreadable"]

    lines = text.splitlines()
    if len(lines) > 80:
        violations.append(f"{path}: {len(lines)} lines (max 80)")

    try:
        tree = ast.parse(text, str(path))
    except SyntaxError as e:
        violations.append(f"{path}: syntax error — {e}")
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            violations.append(f"{path}: class '{node.name}' defined in __init__.py")
        if isinstance(node, ast.FunctionDef) and node.name not in ("__all__",):
            # Count non-trivial lines in function body
            body_lines = 0
            for child in ast.walk(node):
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    continue  # docstring
                body_lines += 1
            if body_lines > 10:
                violations.append(
                    f"{path}: function '{node.name}' has {body_lines} body lines (max ~10)"
                )

    return violations


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    violations_found = False
    for init in root.rglob("__init__.py"):
        # Skip __pycache__
        if "__pycache__" in init.parts:
            continue
        v = check_file(init)
        if v:
            violations_found = True
            for msg in v:
                print(msg)
    if not violations_found:
        print("All __init__.py files pass hygiene checks.")
        return 0
    print(f"\nViolations found in {len([i for i in root.rglob('__init__.py') if '__pycache__' not in i.parts and check_file(i)])} files.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
