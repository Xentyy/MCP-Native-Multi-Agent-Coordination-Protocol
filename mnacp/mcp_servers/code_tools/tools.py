"""Python kod çalıştırma ve analiz araçları — güvenli sandbox."""
from __future__ import annotations

import ast
import subprocess
import sys
import textwrap
from typing import Any

from pydantic import BaseModel, Field

# Yasaklı modüller — sandbox güvenliği
_BANNED_IMPORTS = frozenset({
    "os", "sys", "subprocess", "socket", "shutil", "pathlib",
    "importlib", "ctypes", "multiprocessing", "threading",
    "pickle", "shelve", "dbm", "signal", "pty",
})

# İzin verilen güvenli stdlib modülleri
_SAFE_IMPORTS = frozenset({
    "math", "statistics", "random", "itertools", "functools",
    "collections", "heapq", "bisect", "array", "decimal",
    "fractions", "json", "re", "string", "textwrap", "unicodedata",
    "datetime", "calendar", "time", "pprint", "copy", "dataclasses",
    "typing", "enum", "abc", "io", "base64", "hashlib", "hmac",
    "csv", "struct", "operator", "contextlib", "warnings",
    # Bilimsel (ajan container'ında yüklü olabilir)
    "numpy", "pandas", "scipy", "sklearn",
})


class ExecutePythonParams(BaseModel):
    code: str = Field(description="Çalıştırılacak Python kodu")
    timeout: int = Field(default=10, ge=1, le=30, description="Maksimum çalışma süresi (saniye)")
    stdin: str = Field(default="", description="Standart girdi")


class AnalyzeCodeParams(BaseModel):
    code: str = Field(description="Analiz edilecek Python kodu")


class FormatCodeParams(BaseModel):
    code: str = Field(description="Formatlanacak Python kodu")
    indent: int = Field(default=4, ge=2, le=8)


class ExtractFunctionsParams(BaseModel):
    code: str = Field(description="Fonksiyonları çıkarılacak Python kodu")


def _check_safety(code: str) -> list[str]:
    """AST analizi ile yasaklı pattern'leri tespit eder."""
    warnings: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"Sözdizimi hatası: {e}"]

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            for name in names:
                root = name.split(".")[0]
                if root in _BANNED_IMPORTS:
                    warnings.append(f"Yasaklı modül: {root}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec", "__import__", "compile"):
                warnings.append(f"Yasaklı fonksiyon: {node.func.id}()")
            elif isinstance(node.func, ast.Attribute) and node.func.attr in ("system", "popen", "run", "Popen"):
                warnings.append(f"Şüpheli çağrı: .{node.func.attr}()")

    return warnings


def execute_python(params: ExecutePythonParams) -> dict[str, Any]:
    """Python kodunu izole subprocess'te çalıştırır."""
    safety_issues = _check_safety(params.code)
    if safety_issues:
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "error": "Güvenlik ihlali: " + "; ".join(safety_issues),
            "exit_code": -1,
        }

    # Kodu geçici bir wrapper ile sar: print çıktısını yakala
    wrapper = textwrap.dedent(f"""
import sys, io
_stdout = io.StringIO()
_stderr = io.StringIO()
sys.stdout = _stdout
sys.stderr = _stderr
try:
{textwrap.indent(params.code, "    ")}
except Exception as _e:
    print(f"RuntimeError: {{_e}}", file=sys.stderr)
finally:
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    print(_stdout.getvalue(), end="")
    print(_stderr.getvalue(), end="", file=sys.stderr)
""").strip()

    try:
        result = subprocess.run(
            [sys.executable, "-c", wrapper],
            input=params.stdin,
            capture_output=True,
            text=True,
            timeout=params.timeout,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:4000],
            "stderr": result.stderr[:2000],
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Zaman aşımı ({params.timeout}s)",
            "error": "timeout",
            "exit_code": -1,
        }
    except Exception as exc:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(exc),
            "error": "execution_error",
            "exit_code": -1,
        }


def analyze_code(params: AnalyzeCodeParams) -> dict[str, Any]:
    """Kod yapısını AST ile analiz eder."""
    try:
        tree = ast.parse(params.code)
    except SyntaxError as e:
        return {"error": f"Sözdizimi hatası: {e}"}

    functions: list[dict] = []
    classes: list[str] = []
    imports: list[str] = []
    complexity = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            functions.append({
                "name": node.name,
                "args": [a.arg for a in node.args.args],
                "lineno": node.lineno,
                "async": isinstance(node, ast.AsyncFunctionDef),
                "docstring": ast.get_docstring(node) or "",
            })
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "?")
        elif isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.ExceptHandler)):
            complexity += 1

    safety_issues = _check_safety(params.code)
    lines = params.code.splitlines()

    return {
        "lines": len(lines),
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "cyclomatic_complexity": complexity + 1,
        "safety_issues": safety_issues,
        "has_syntax_error": False,
    }


def format_code(params: FormatCodeParams) -> str:
    """Kodu standart girintiye göre yeniden formatlar (basit)."""
    try:
        tree = ast.parse(params.code)
        # ast.unparse Python 3.9+
        if hasattr(ast, "unparse"):
            return ast.unparse(tree)
        return params.code
    except SyntaxError:
        return params.code


def extract_functions(params: ExtractFunctionsParams) -> list[dict[str, str]]:
    """Koddaki fonksiyonların kaynak kodunu çıkarır."""
    try:
        lines = params.code.splitlines()
        tree = ast.parse(params.code)
        result = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                end = getattr(node, "end_lineno", None)
                body = "\n".join(lines[node.lineno - 1: end]) if end else f"def {node.name}(...): ..."
                result.append({"name": node.name, "source": body})
        return result
    except SyntaxError as e:
        return [{"name": "error", "source": str(e)}]


TOOL_HANDLERS: dict[str, tuple[type[BaseModel], Any]] = {
    "execute_python": (ExecutePythonParams, execute_python),
    "analyze_code": (AnalyzeCodeParams, analyze_code),
    "format_code": (FormatCodeParams, format_code),
    "extract_functions": (ExtractFunctionsParams, extract_functions),
}
