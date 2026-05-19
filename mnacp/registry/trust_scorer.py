from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from mnacp.protocol.schemas import TrustEvent

TREND_WINDOW = 5  # son kaç skor değerlendirmeye alınır


@dataclass
class AgentStats:
    total: int = 0
    successes: int = 0
    total_latency_ms: float = 0.0
    consecutive_failures: int = 0
    score_history: list = None  # son TREND_WINDOW skoru tutar

    def __post_init__(self) -> None:
        if self.score_history is None:
            self.score_history = []


class TrustScorer:
    """
    Üstel ağırlıklı başarı oranı + gecikme cezası.

    Skor = success_rate * latency_factor
    success_rate = successes / total  (minimum 1 örnek)
    latency_factor = 1 / (1 + latency_ms / TARGET_MS)
    """

    TARGET_LATENCY_MS = 2000.0
    MIN_SCORE = 0.05
    MAX_SCORE = 1.0

    def __init__(self) -> None:
        self._stats: dict[str, AgentStats] = defaultdict(AgentStats)

    def record(self, event: TrustEvent) -> float:
        aid = str(event.agent_id)
        stats = self._stats[aid]
        stats.total += 1
        if event.success:
            stats.successes += 1
            stats.consecutive_failures = 0
        else:
            stats.consecutive_failures += 1

        if event.latency_ms is not None:
            stats.total_latency_ms += event.latency_ms

        current = self.score(event.agent_id)
        # Her gerçek delegasyon sonrası trend geçmişini güncelle
        stats.score_history.append(current)
        if len(stats.score_history) > TREND_WINDOW:
            stats.score_history.pop(0)
        return current

    def score(self, agent_id: UUID) -> float:
        aid = str(agent_id)
        stats = self._stats[aid]
        if stats.total == 0:
            return self.MAX_SCORE

        success_rate = stats.successes / stats.total
        if stats.successes > 0:
            avg_latency = stats.total_latency_ms / stats.successes
            latency_factor = 1.0 / (1.0 + avg_latency / self.TARGET_LATENCY_MS)
        else:
            latency_factor = 0.5

        # Ardışık hata cezası
        failure_penalty = 0.9 ** stats.consecutive_failures

        raw = success_rate * latency_factor * failure_penalty
        return max(self.MIN_SCORE, min(self.MAX_SCORE, raw))

    def get_trend(self, agent_id: UUID) -> str:
        """Son TREND_WINDOW skora bakarak 'improving', 'degrading' veya 'stable' döner."""
        aid = str(agent_id)
        history = self._stats[aid].score_history
        if len(history) < 3:
            return "stable"
        first_half = sum(history[: len(history) // 2]) / (len(history) // 2)
        second_half = sum(history[len(history) // 2 :]) / (len(history) - len(history) // 2)
        delta = second_half - first_half
        if delta > 0.05:
            return "improving"
        if delta < -0.05:
            return "degrading"
        return "stable"

    def get_all_scores(self) -> dict[str, float]:
        from uuid import UUID as _UUID
        return {aid: self.score(_UUID(aid)) for aid in self._stats}
