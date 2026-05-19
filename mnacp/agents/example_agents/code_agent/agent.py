"""Python kod çalıştırma ve analiz ajanı."""
from __future__ import annotations

import re
from typing import Any

from mnacp.agents.base_agent.agent import BaseAgent
from mnacp.mcp_servers.code_tools.tools import (
    TOOL_HANDLERS,
    AnalyzeCodeParams,
    ExecutePythonParams,
    analyze_code,
    execute_python,
)
from mnacp.protocol.schemas import ToolSchema


def _extract_code_block(text: str) -> str | None:
    """Markdown ``` bloğu veya girintili kod bloğu yakala."""
    # ```python ... ``` veya ``` ... ```
    m = re.search(r"```(?:python)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # 4-boşlukla girintili blok
    lines = text.splitlines()
    code_lines = [ln[4:] for ln in lines if ln.startswith("    ")]
    if len(code_lines) >= 2:
        return "\n".join(code_lines)
    return None


class CodeAgent(BaseAgent):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 9004,
        registry_url: str = "http://localhost:8000",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name="CodeAgent",
            description=(
                "Python kodu yazan, çalıştıran, test eden ve analiz eden yazılım geliştirme ajanı. "
                "Kod üretme, kod çalıştırma (execute_python), hesaplama, algoritma testi, "
                "birim test yazma, kod kalite analizi, karmaşıklık ölçme, sözdizimi kontrolü, "
                "matematiksel hesaplama, istatistik, veri dönüşümü görevleri için kullanılır. "
                "Fibonacci, sıralama, arama algoritmaları ve her türlü programlama görevi."
            ),
            host=host,
            port=port,
            registry_url=registry_url,
            tags=[
                "code", "python", "programming", "execution", "algorithm",
                "testing", "analysis", "compute", "math", "execute_python",
                "analyze_code", "format_code", "calculate", "script",
            ],
            **kwargs,
        )

    def define_tools(self) -> list[ToolSchema]:
        return [
            ToolSchema(
                name="execute_python",
                description="Python kodunu güvenli sandbox'ta çalıştırır ve stdout/stderr döndürür",
                parameters={"code": "string", "timeout": "integer", "stdin": "string"},
            ),
            ToolSchema(
                name="analyze_code",
                description="Python kodunun yapısını analiz eder: fonksiyonlar, sınıflar, karmaşıklık",
                parameters={"code": "string"},
            ),
            ToolSchema(
                name="format_code",
                description="Python kodunu standart formata getirir",
                parameters={"code": "string", "indent": "integer"},
            ),
            ToolSchema(
                name="extract_functions",
                description="Koddaki tüm fonksiyon tanımlarını ve kaynak kodlarını çıkarır",
                parameters={"code": "string"},
            ),
        ]

    async def execute_tool(self, tool_name: str, parameters: dict[str, Any]) -> Any:
        if tool_name not in TOOL_HANDLERS:
            raise ValueError(f"CodeAgent: bilinmeyen araç '{tool_name}'")
        param_cls, handler = TOOL_HANDLERS[tool_name]
        params = param_cls(**parameters)
        result = handler(params)
        if hasattr(result, "__await__"):
            return await result
        return result

    async def _process_delegated_task(self, task: str, context: dict[str, Any]) -> Any:
        task_lower = task.lower()
        code = (
            context.get("code")
            or _extract_code_block(task)
            or _extract_code_block(context.get("original_task", ""))
            or ""
        )

        # Analiz isteği (kod da varsa önce çalıştır, sonra analiz et)
        if any(k in task_lower for k in ("analiz", "analyze", "incele", "karmaşıklık", "complexity")) and not any(
            k in task_lower for k in ("çalıştır", "run", "execute", "yaz")
        ):
            if not code:
                return {"error": "Analiz edilecek kod bulunamadı"}
            return analyze_code(AnalyzeCodeParams(code=code))

        # Kod ya da kod üretme görevi
        if not code:
            code = self._generate_code_for_task(task, context)

        if code:
            result = execute_python(ExecutePythonParams(code=code, timeout=10))
            return {**result, "code": code}

        return {"error": "Çalıştırılacak veya analiz edilecek kod bulunamadı", "task": task}

    @staticmethod
    def _generate_code_for_task(task: str, context: dict[str, Any]) -> str:
        """Tanınan algoritma/hesaplama görevleri için çalıştırılabilir kod üret."""
        t = task.lower()

        # Fibonacci
        m = re.search(r"fibonacci.*?(\d+)|(\d+).*?fibonacci", t)
        if m:
            n = int(m.group(1) or m.group(2))
            return (
                "def fib(n):\n"
                "    a, b = 0, 1\n"
                "    for _ in range(n): a, b = b, a + b\n"
                "    return a\n"
                f"print(f'Fibonacci({n}) = {{fib({n})}}')\n"
            )

        # Bubble sort
        if "bubble" in t or ("kabarcık" in t and "sort" in t):
            return (
                "def bubble_sort(arr):\n"
                "    n = len(arr)\n"
                "    for i in range(n):\n"
                "        swapped = False\n"
                "        for j in range(n - i - 1):\n"
                "            if arr[j] > arr[j+1]:\n"
                "                arr[j], arr[j+1] = arr[j+1], arr[j]\n"
                "                swapped = True\n"
                "        if not swapped:\n"
                "            break\n"
                "    return arr\n\n"
                "data = [64, 34, 25, 12, 22, 11, 90]\n"
                "print('Unsorted:', data)\n"
                "print('Sorted:  ', bubble_sort(data))\n"
            )

        # Quick sort
        if "quick" in t or "hizli" in t or "hızlı" in t:
            return (
                "def quicksort(arr):\n"
                "    if len(arr) <= 1:\n"
                "        return arr\n"
                "    pivot = arr[len(arr) // 2]\n"
                "    left = [x for x in arr if x < pivot]\n"
                "    mid  = [x for x in arr if x == pivot]\n"
                "    right= [x for x in arr if x > pivot]\n"
                "    return quicksort(left) + mid + quicksort(right)\n\n"
                "data = [64, 34, 25, 12, 22, 11, 90]\n"
                "print('Unsorted:', data)\n"
                "print('Sorted:  ', quicksort(data))\n"
            )

        # Merge sort
        if "merge" in t:
            return (
                "def merge_sort(arr):\n"
                "    if len(arr) <= 1:\n"
                "        return arr\n"
                "    mid = len(arr) // 2\n"
                "    left = merge_sort(arr[:mid])\n"
                "    right = merge_sort(arr[mid:])\n"
                "    result, i, j = [], 0, 0\n"
                "    while i < len(left) and j < len(right):\n"
                "        if left[i] <= right[j]:\n"
                "            result.append(left[i]); i += 1\n"
                "        else:\n"
                "            result.append(right[j]); j += 1\n"
                "    return result + left[i:] + right[j:]\n\n"
                "data = [64, 34, 25, 12, 22, 11, 90]\n"
                "print('Unsorted:', data)\n"
                "print('Sorted:  ', merge_sort(data))\n"
            )

        # Asal sayı kontrolü
        m = re.search(r"(\d+).*?(asal|prime)|(?:asal|prime).*?(\d+)", t)
        if m:
            n = int(next(g for g in m.groups() if g and g.isdigit()))
            return (
                "def is_prime(n):\n"
                "    if n < 2: return False\n"
                "    for i in range(2, int(n**0.5)+1):\n"
                "        if n % i == 0: return False\n"
                "    return True\n"
                f"print(f'is_prime({n}) = {{is_prime({n})}}')\n"
            )

        # Faktöriyel
        m = re.search(r"(\d+)[^\d]*(?:faktöriyel|faktoryel|factorial)|(?:faktöriyel|faktoryel|factorial)[^\d]*(\d+)", t)
        if m:
            n = int(next(g for g in m.groups() if g))
            return f"import math\nprint(f'factorial({n}) = {{math.factorial({n})}}')\n"

        # Basit aritmetik ifade
        m = re.search(r"\b(\d[\d\s\+\-\*\/\(\)\.]*\d)\b", t)
        if m:
            expr = m.group(1).strip()
            try:
                compile(expr, "<string>", "eval")
                return f"result = {expr}\nprint(f'{expr} = {{result}}')\n"
            except SyntaxError:
                pass

        return ""


if __name__ == "__main__":
    import asyncio
    asyncio.run(CodeAgent().run())
