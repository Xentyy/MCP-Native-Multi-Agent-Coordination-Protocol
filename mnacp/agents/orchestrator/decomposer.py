"""
Görev ayrıştırıcı — Claude API ile doğal dil görevini alt görevlere böler.

Çıktı: list[SubTask]  — her biri bağımsız olarak bir ajana delege edilebilir.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import anthropic
import httpx

logger = logging.getLogger(__name__)

DECOMPOSE_SYSTEM = """Sen bir çok-ajanlı sistem orkestratörüsün.
Kullanıcının görevini, sistemde KAYITLI ajanların gerçekten yapabileceği,
bağımsız alt görevlere ayır.

Aşağıda mevcut ajan kataloğunu göreceksin: hangi ajan ne yapıyor, hangi
araçları sunuyor, hangi etiketlerle anılıyor. Üreteceğin her alt görevin
required_capabilities listesi BU KATALOĞA UYGUN olmalı — uydurma
yetenek (örn. "creative_writing", "literature_review") icat etme,
mevcut araç adlarını veya etiketleri kullan. Eğer bir alt görev hiçbir
kayıtlı ajan tarafından yapılamayacaksa o alt görevi PLANA EKLEME — onu
zaten orkestratörün son aşaması (aggregate) doğal dilde halledecek.

Yanıtını SADECE aşağıdaki JSON formatında ver, başka hiçbir şey yazma:
{
  "subtasks": [
    {
      "id": "t1",
      "description": "Alt görev açıklaması",
      "required_capabilities": ["load_csv", "compute_statistics"],
      "depends_on": [],
      "parallel": true
    }
  ],
  "execution_order": ["t1", "t2"],
  "can_parallelize": false
}

Kurallar:
- depends_on: bu alt görev hangi id'lerin tamamlanmasını bekliyor
- parallel: bu görev diğerleriyle eş zamanlı çalışabilir mi
- required_capabilities: SADECE katalogdaki tool/tag isimleri
- Eğer görev tamamen bilgi/sentez gerektiriyorsa (örn. "şu kavramı anlat"),
  boş subtasks listesi döndürebilirsin — bu durumda orkestratör doğrudan
  kullanıcıya cevaplar.
"""


@dataclass
class SubTask:
    id: str
    description: str
    required_capabilities: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    parallel: bool = True
    result: Any = None
    error: str | None = None
    assigned_agent_id: str | None = None


@dataclass
class DecompositionPlan:
    subtasks: list[SubTask]
    execution_order: list[str]
    can_parallelize: bool
    original_task: str

    def get_subtask(self, sid: str) -> SubTask | None:
        return next((s for s in self.subtasks if s.id == sid), None)

    def ready_tasks(self, completed_ids: set[str]) -> list[SubTask]:
        """Bağımlılıkları tamamlanmış, henüz işlenmemiş görevleri döndür."""
        return [
            s for s in self.subtasks
            if s.id not in completed_ids
            and s.assigned_agent_id is None
            and s.error is None
            and s.result is None
            and all(dep in completed_ids for dep in s.depends_on)
        ]


class TaskDecomposer:
    def __init__(
        self,
        model: str = "claude-sonnet-4-5",
        registry_url: str | None = None,
    ) -> None:
        self._client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self._model = model
        self._registry_url = (registry_url or "").rstrip("/")

    async def _fetch_catalog(self) -> str:
        """Registry'den ajan kataloğunu çek, prompt'a gömmek için metin döndür."""
        if not self._registry_url:
            return "(katalog mevcut değil — registry URL verilmedi)"
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(f"{self._registry_url}/agents")
                r.raise_for_status()
                agents = r.json()
        except Exception as exc:
            logger.warning("Registry kataloğu alınamadı: %s", exc)
            return "(katalog alınamadı)"

        online = [a for a in agents if a.get("status") == "online"]
        if not online:
            return "(çevrimiçi ajan yok — sadece aggregate ile cevap üret)"

        lines = []
        for a in online:
            tools = ", ".join(t["name"] for t in a.get("tools", []))
            tags = ", ".join(a.get("tags", []))
            lines.append(
                f"- {a['name']}: {a.get('description', '')[:200]}\n"
                f"    araçlar: [{tools}]\n"
                f"    etiketler: [{tags}]"
            )
        return "Mevcut ajanlar:\n" + "\n".join(lines)

    async def decompose(self, task: str) -> DecompositionPlan:
        """Görevi Claude API ile alt görevlere ayır."""
        import asyncio
        catalog = await self._fetch_catalog()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._decompose_sync, task, catalog,
        )

    def _decompose_sync(self, task: str, catalog: str) -> DecompositionPlan:
        user_message = (
            f"{catalog}\n\n"
            f"Kullanıcı görevi:\n{task}\n\n"
            "Bu görevi yukarıdaki ajanların yapabileceği alt görevlere ayır."
        )
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=DECOMPOSE_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()

        # JSON bloğunu temizle
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Decomposer JSON parse hatası, tek görev planı kullanılıyor")
            data = {
                "subtasks": [{"id": "t1", "description": task,
                               "required_capabilities": [], "depends_on": [], "parallel": False}],
                "execution_order": ["t1"],
                "can_parallelize": False,
            }

        subtasks = [SubTask(**s) for s in data.get("subtasks", [])]
        return DecompositionPlan(
            subtasks=subtasks,
            execution_order=data.get("execution_order", [s.id for s in subtasks]),
            can_parallelize=data.get("can_parallelize", False),
            original_task=task,
        )
