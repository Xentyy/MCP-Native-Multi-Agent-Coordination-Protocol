"""
Delegasyon döngüsü ve kilitlenme tespiti.

Graf yapısı: düğüm = ajan_id, kenar = aktif delegasyon (from → to).
Döngü: DFS ile tespit edilir.
Deadlock: birbirini bekleyen ajan çifti/grubu.
"""
from __future__ import annotations

from collections import defaultdict
from uuid import UUID


class DeadlockDetector:
    def __init__(self) -> None:
        # from_agent → {to_agent, ...}
        self._graph: dict[str, set[str]] = defaultdict(set)

    # ------------------------------------------------------------------
    # Graf yönetimi
    # ------------------------------------------------------------------

    def add_delegation(self, from_id: UUID, to_id: UUID) -> None:
        self._graph[str(from_id)].add(str(to_id))

    def remove_delegation(self, from_id: UUID, to_id: UUID) -> None:
        self._graph[str(from_id)].discard(str(to_id))
        if not self._graph[str(from_id)]:
            del self._graph[str(from_id)]

    # ------------------------------------------------------------------
    # Döngü tespiti (zincir bazlı — anlık kontrol)
    # ------------------------------------------------------------------

    @staticmethod
    def has_cycle_in_chain(chain: list[UUID], new_target: UUID) -> bool:
        """
        Verilen delegasyon zincirinde new_target zaten varsa döngü var demektir.
        Örnek: chain=[A, B], new_target=A → A→B→A döngüsü.
        """
        return new_target in chain

    # ------------------------------------------------------------------
    # Graf genelinde döngü tespiti (DFS)
    # ------------------------------------------------------------------

    def has_global_cycle(self) -> bool:
        """Tüm aktif delegasyon grafında döngü var mı?"""
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in self._graph.get(node, set()):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        for node in list(self._graph.keys()):
            if node not in visited:
                if dfs(node):
                    return True
        return False

    def find_cycles(self) -> list[list[str]]:
        """Tüm döngüleri döndürür (Johnson algoritması basit versiyonu)."""
        cycles: list[list[str]] = []
        visited: set[str] = set()
        path: list[str] = []
        path_set: set[str] = set()

        def dfs(node: str) -> None:
            visited.add(node)
            path.append(node)
            path_set.add(node)
            for neighbor in self._graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in path_set:
                    idx = path.index(neighbor)
                    cycles.append(path[idx:] + [neighbor])
            path.pop()
            path_set.discard(node)

        for node in list(self._graph.keys()):
            if node not in visited:
                dfs(node)
        return cycles

    # ------------------------------------------------------------------
    # Deadlock tespiti (karşılıklı bekleme)
    # ------------------------------------------------------------------

    def find_deadlocked_agents(self) -> list[set[str]]:
        """
        Birbirini bekleyen ajan gruplarını (SCC) döndürür.
        Kosaraju algoritması ile güçlü bağlantılı bileşenler.
        """
        nodes = set(self._graph.keys())
        for targets in self._graph.values():
            nodes |= targets
        nodes = list(nodes)

        # 1. adım: topolojik sıralama
        visited: set[str] = set()
        finish_order: list[str] = []

        def dfs1(n: str) -> None:
            visited.add(n)
            for nb in self._graph.get(n, set()):
                if nb not in visited:
                    dfs1(nb)
            finish_order.append(n)

        for n in nodes:
            if n not in visited:
                dfs1(n)

        # 2. adım: ters grafta DFS
        rev: dict[str, set[str]] = defaultdict(set)
        for src, targets in self._graph.items():
            for tgt in targets:
                rev[tgt].add(src)

        visited2: set[str] = set()
        deadlocked: list[set[str]] = []

        def dfs2(n: str, component: set[str]) -> None:
            visited2.add(n)
            component.add(n)
            for nb in rev.get(n, set()):
                if nb not in visited2:
                    dfs2(nb, component)

        for n in reversed(finish_order):
            if n not in visited2:
                comp: set[str] = set()
                dfs2(n, comp)
                if len(comp) > 1:  # tek düğümlü SCC deadlock değil
                    deadlocked.append(comp)

        return deadlocked

    def is_safe_to_delegate(self, from_id: UUID, to_id: UUID, chain: list[UUID]) -> tuple[bool, str]:
        """
        Delegasyonun güvenli olup olmadığını tek noktada kontrol eder.
        False döndürürse ikinci eleman sebep açıklamasını içerir.
        """
        if self.has_cycle_in_chain(chain, to_id):
            return False, f"Döngüsel delegasyon: {to_id} zaten zincirde"

        # Geçici olarak kenarı ekle ve global döngü kontrolü yap
        self.add_delegation(from_id, to_id)
        cycle = self.has_global_cycle()
        self.remove_delegation(from_id, to_id)

        if cycle:
            return False, "Bu delegasyon global bir döngü oluşturuyor"

        return True, ""
