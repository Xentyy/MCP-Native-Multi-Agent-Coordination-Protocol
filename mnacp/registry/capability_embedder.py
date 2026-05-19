from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from mnacp.protocol.schemas import AgentRegistration, ToolSchema

# Anthropic embedding boyutu yok; text-embedding-3-small yerine
# sklearn TF-IDF + SVD ile hafif yerel embedding kullanıyoruz.
# Prodüksiyon için bu sınıfı OpenAI/Voyage/Cohere embeddingi ile değiştir.

EMBEDDING_DIM = 256


def _text_for_agent(agent: "AgentRegistration") -> str:
    parts = [agent.name, agent.description]
    for tool in agent.tools:
        parts.append(tool.name)
        parts.append(tool.description)
    parts.extend(agent.tags)
    return " ".join(parts)


def _text_for_tool(tool: "ToolSchema") -> str:
    return f"{tool.name} {tool.description}"


class CapabilityEmbedder:
    """
    TF-IDF + truncated SVD tabanlı yetenek gömme.
    fit() çağrısından önce transform() çağrılamaz.
    """

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim
        self._vectorizer: object | None = None
        self._svd: object | None = None
        self._fitted = False

    def fit(self, texts: list[str]) -> None:
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vectorizer = TfidfVectorizer(max_features=4096, ngram_range=(1, 2))
        tfidf = self._vectorizer.fit_transform(texts)
        n_components = max(1, min(self.dim, tfidf.shape[1] - 1, tfidf.shape[0] - 1))
        self._svd = TruncatedSVD(n_components=n_components, random_state=42)
        self._svd.fit(tfidf)
        self._fitted = True

    def transform(self, texts: list[str]) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Embedder henüz fit edilmedi. Önce fit() çağır.")
        tfidf = self._vectorizer.transform(texts)
        vecs = self._svd.transform(tfidf)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        return (vecs / norms).astype(np.float32)

    def embed_agent(self, agent: "AgentRegistration") -> np.ndarray:
        return self.transform([_text_for_agent(agent)])[0]

    def embed_query(self, query: str) -> np.ndarray:
        return self.transform([query])[0]

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

    def top_k_agents(
        self,
        query_vec: np.ndarray,
        agent_vecs: dict[str, np.ndarray],
        k: int = 3,
        exclude_ids: list[str] | None = None,
    ) -> list[tuple[str, float]]:
        exclude = set(exclude_ids or [])
        scores = [
            (aid, self.cosine_similarity(query_vec, vec))
            for aid, vec in agent_vecs.items()
            if aid not in exclude
        ]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:k]
