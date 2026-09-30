"""Extract the full public API surface of the watermarklab package via AST.

Stdlib only -- no imports of the target package, so torch/transformers are not needed.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

PKG_ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("watermarklab")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("api_dump.json")


def fmt_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Rebuild a readable signature string from an ast.arguments node."""
    a = node.args
    parts: list[str] = []
    posonly = getattr(a, "posonlyargs", []) or []
    defaults = list(a.defaults)
    # align defaults to the tail of positional args
    positional = posonly + list(a.args)
    offset = len(positional) - len(defaults)

    for i, arg in enumerate(positional):
        s = arg.arg
        if arg.annotation is not None:
            s += ": " + ast.unparse(arg.annotation)
        if i >= offset:
            s += " = " + ast.unparse(defaults[i - offset])
        parts.append(s)
        if posonly and i == len(posonly) - 1:
            parts.append("/")

    if a.vararg is not None:
        s = "*" + a.vararg.arg
        if a.vararg.annotation is not None:
            s += ": " + ast.unparse(a.vararg.annotation)
        parts.append(s)
    elif a.kwonlyargs:
        parts.append("*")

    for kwarg, kwdefault in zip(a.kwonlyargs, a.kw_defaults):
        s = kwarg.arg
        if kwarg.annotation is not None:
            s += ": " + ast.unparse(kwarg.annotation)
        if kwdefault is not None:
            s += " = " + ast.unparse(kwdefault)
        parts.append(s)

    if a.kwarg is not None:
        s = "**" + a.kwarg.arg
        if a.kwarg.annotation is not None:
            s += ": " + ast.unparse(a.kwarg.annotation)
        parts.append(s)

    ret = ""
    if node.returns is not None:
        ret = " -> " + ast.unparse(node.returns)
    return f"({', '.join(parts)}){ret}"


def decorators(node: ast.AST) -> list[str]:
    return [ast.unparse(d) for d in getattr(node, "decorator_list", [])]


def summarize_class(node: ast.ClassDef) -> dict:
    methods = []
    inner = []
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(
                {
                    "name": child.name,
                    "kind": "method",
                    "signature": fmt_signature(child),
                    "decorators": decorators(child),
                    "lineno": child.lineno,
                    "docstring": ast.get_docstring(child),
                }
            )
        elif isinstance(child, ast.ClassDef):
            inner.append(summarize_class(child))

    return {
        "name": node.name,
        "kind": "class",
        "lineno": node.lineno,
        "bases": [ast.unparse(b) for b in node.bases],
        "keywords": [ast.unparse(k) for k in node.keywords],
        "decorators": decorators(node),
        "docstring": ast.get_docstring(node),
        "methods": methods,
        "nested_classes": inner,
    }


def summarize_function(node) -> dict:
    return {
        "name": node.name,
        "kind": "function",
        "signature": fmt_signature(node),
        "decorators": decorators(node),
        "lineno": node.lineno,
        "docstring": ast.get_docstring(node),
    }


def module_dotted(path: Path, root: Path) -> str:
    rel = path.relative_to(root.parent).with_suffix("")
    bits = [b for b in rel.parts if b != "__init__"]
    return ".".join(bits)


def main() -> None:
    files = sorted(p for p in PKG_ROOT.rglob("*.py") if "__pycache__" not in p.parts)
    modules = []
    for path in files:
        src = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(src)
        except SyntaxError as exc:  # pragma: no cover - defensive
            modules.append({"file": str(path), "error": f"SyntaxError: {exc}"})
            continue

        all_names = None
        for stmt in tree.body:
            if isinstance(stmt, ast.Assign):
                for tgt in stmt.targets:
                    if isinstance(tgt, ast.Name) and tgt.id == "__all__":
                        try:
                            all_names = ast.literal_eval(stmt.value)
                        except Exception:
                            pass

        classes, functions = [], []
        for stmt in tree.body:
            if isinstance(stmt, ast.ClassDef):
                classes.append(summarize_class(stmt))
            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(summarize_function(stmt))

        if not classes and not functions and ast.get_docstring(tree) is None and all_names is None:
            continue  # pure re-export shim with nothing to document at module level

        modules.append(
            {
                "file": str(path.relative_to(PKG_ROOT.parent)).replace("\\", "/"),
                "module": module_dotted(path, PKG_ROOT),
                "lineno": 1,
                "docstring": ast.get_docstring(tree),
                "all": all_names,
                "classes": classes,
                "functions": functions,
            }
        )

    payload = {
        "package": PKG_ROOT.name,
        "module_count": len(modules),
        "class_count": sum(len(m.get("classes", [])) for m in modules),
        "function_count": sum(len(m.get("functions", [])) for m in modules),
        "modules": modules,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"modules={payload['module_count']} classes={payload['class_count']} functions={payload['function_count']}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
