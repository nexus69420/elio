from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Optional

from orchestrator.config import settings
from orchestrator.llm.client import llm_client
from orchestrator.runtime_llm import runtime_llm

logger = logging.getLogger(__name__)


class SemanticMemory:
    """Long-term semantic memory via Chroma (local persistent)."""

    def __init__(self) -> None:
        settings.ensure_dirs()
        self._collection = None
        self._collection_name: Optional[str] = None

    def _collection_name_for(self) -> str:
        # Isolate stub (8-d) from real embed models (e.g. nomic 768-d) so switching
        # ORCHESTRATOR_STUB_LLM never blows up with dimension mismatch.
        if settings.orchestrator_stub_llm or runtime_llm.get().get("stub"):
            return "agent_lessons_stub_d8"
        model = re.sub(r"[^a-zA-Z0-9]+", "_", runtime_llm.resolve_embed_model()).strip("_").lower()
        return f"agent_lessons_{model}"[:60] or "agent_lessons_default"

    def _get_collection(self):
        name = self._collection_name_for()
        if self._collection is not None and self._collection_name == name:
            return self._collection
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        client = chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine", "embed_model": settings.resolve_embed_model()},
        )
        self._collection_name = name
        return self._collection

    def _reset_collection(self) -> None:
        """Drop and recreate current collection (used after dimension mismatch)."""
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        name = self._collection_name_for()
        client = chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        try:
            client.delete_collection(name)
        except Exception:  # noqa: BLE001
            pass
        self._collection = None
        self._collection_name = None
        logger.warning("Reset Chroma collection %s after embed dimension mismatch", name)

    async def add_lesson(
        self,
        *,
        task_id: str,
        prompt: str,
        summary: str,
        approach: str,
        tools_used: list[str],
    ) -> dict[str, Any]:
        text = f"Task: {prompt}\nSummary: {summary}\nApproach: {approach}\nTools: {', '.join(tools_used)}"
        collection = self._get_collection()
        doc_id = hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]
        existing = collection.get(ids=[doc_id])
        if existing and existing.get("ids"):
            meta = existing["metadatas"][0] if existing.get("metadatas") else {}
            hits = int(meta.get("hit_count", 1)) + 1
            collection.update(ids=[doc_id], metadatas=[{**meta, "hit_count": hits}])
            return {"id": doc_id, "deduped": True, "hit_count": hits}

        embedding = (await llm_client.embed([text]))[0]
        try:
            collection.add(
                ids=[doc_id],
                documents=[text],
                embeddings=[embedding],
                metadatas=[
                    {
                        "task_id": task_id,
                        "hit_count": 1,
                        "tools": ",".join(tools_used),
                    }
                ],
            )
        except Exception as exc:  # noqa: BLE001
            if "dimension" in str(exc).lower():
                self._reset_collection()
                collection = self._get_collection()
                collection.add(
                    ids=[doc_id],
                    documents=[text],
                    embeddings=[embedding],
                    metadatas=[
                        {
                            "task_id": task_id,
                            "hit_count": 1,
                            "tools": ",".join(tools_used),
                        }
                    ],
                )
            else:
                raise
        return {"id": doc_id, "deduped": False, "hit_count": 1}

    async def retrieve(self, query: str, k: int = 3) -> list[dict[str, Any]]:
        try:
            collection = self._get_collection()
            if collection.count() == 0:
                return []
            embedding = (await llm_client.embed([query]))[0]
            try:
                result = collection.query(
                    query_embeddings=[embedding], n_results=min(k, collection.count())
                )
            except Exception as exc:  # noqa: BLE001
                if "dimension" in str(exc).lower():
                    self._reset_collection()
                    return []
                raise
            docs = result.get("documents", [[]])[0]
            metas = result.get("metadatas", [[]])[0]
            ids = result.get("ids", [[]])[0]
            distances = result.get("distances", [[]])[0]
            out = []
            for i, doc in enumerate(docs):
                out.append(
                    {
                        "id": ids[i],
                        "document": doc,
                        "metadata": metas[i],
                        "distance": distances[i] if distances else None,
                    }
                )
                meta = dict(metas[i] or {})
                meta["hit_count"] = int(meta.get("hit_count", 1)) + 1
                collection.update(ids=[ids[i]], metadatas=[meta])
            return out
        except Exception as exc:  # noqa: BLE001
            # Never let memory kill a run — HITL/agents still need to execute.
            logger.warning("Semantic retrieve skipped: %s", exc)
            return []

    def list_all(self, limit: int = 50) -> list[dict[str, Any]]:
        try:
            collection = self._get_collection()
            if collection.count() == 0:
                return []
            data = collection.get(limit=limit, include=["documents", "metadatas"])
            out = []
            for i, doc_id in enumerate(data.get("ids", [])):
                out.append(
                    {
                        "id": doc_id,
                        "document": data["documents"][i],
                        "metadata": data["metadatas"][i],
                    }
                )
            return out
        except Exception as exc:  # noqa: BLE001
            logger.warning("Semantic list_all skipped: %s", exc)
            return []


semantic_memory = SemanticMemory()
