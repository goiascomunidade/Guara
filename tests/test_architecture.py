"""Architectural boundary tests for hexagonal dependency rules.

Rules enforced:
1. core/ must not import from adapters/, transport/, or runtime/
2. adapters/ must not import from transport/
3. transport/ must not import from adapters/
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _collect_imports(package_dir: Path) -> list[tuple[str, str]]:
    """Return list of (file_path, imported_module) for all .py files in package_dir."""
    results: list[tuple[str, str]] = []
    if not package_dir.exists():
        return results
    for py_file in sorted(package_dir.rglob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
            continue
        relative = str(py_file.relative_to(PROJECT_ROOT))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    results.append((relative, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    results.append((relative, node.module))
    return results


def _violations(imports: list[tuple[str, str]], forbidden_prefixes: list[str]) -> list[str]:
    """Return human-readable violation messages."""
    msgs: list[str] = []
    for file_path, module in imports:
        for prefix in forbidden_prefixes:
            if module == prefix or module.startswith(prefix + "."):
                msgs.append(f"{file_path} imports {module}")
    return msgs


class TestArchitecturalBoundaries(unittest.TestCase):
    def test_core_has_no_external_imports(self) -> None:
        """core/ must not import from adapters/, transport/, or runtime/."""
        imports = _collect_imports(PROJECT_ROOT / "core")
        violations = _violations(imports, ["adapters", "transport", "runtime"])
        self.assertEqual(violations, [], f"core/ boundary violations:\n" + "\n".join(violations))

    def test_adapters_does_not_import_transport(self) -> None:
        """adapters/ must not import from transport/."""
        imports = _collect_imports(PROJECT_ROOT / "adapters")
        violations = _violations(imports, ["transport"])
        self.assertEqual(violations, [], f"adapters/ boundary violations:\n" + "\n".join(violations))

    def test_transport_does_not_import_adapters(self) -> None:
        """transport/ must not import from adapters/."""
        imports = _collect_imports(PROJECT_ROOT / "transport")
        violations = _violations(imports, ["adapters"])
        self.assertEqual(violations, [], f"transport/ boundary violations:\n" + "\n".join(violations))

    def test_plugins_does_not_import_runtime_or_transport(self) -> None:
        """plugins/ must not import from runtime/ or transport/."""
        imports = _collect_imports(PROJECT_ROOT / "plugins")
        violations = _violations(imports, ["runtime", "transport"])
        self.assertEqual(violations, [], f"plugins/ boundary violations:\n" + "\n".join(violations))
