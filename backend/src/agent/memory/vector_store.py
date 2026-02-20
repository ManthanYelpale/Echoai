"""
src/agent/memory/vector_store.py
FAISS vector store using Ollama's nomic-embed-text (free, local).
No sentence-transformers dependency — pure Ollama embeddings.
"""
import json
import pickle
import asyncio
import numpy as np
from pathlib import Path
from typing import Optional, List
from config.settings import get_settings
from src.agent.brain.logger import get_logger

logger = get_logger("vector_store")


class VectorStore:
    def __init__(self):
        s = get_settings()
        self.store_dir = s.vs_path
        self.dim = s.embedding_dim
        self.index = None
        self.id_map: dict[int, int] = {}      # faiss_idx -> job_id
        self.meta: dict[int, dict] = {}
        self.next_idx = 0
        self._init()

    def _init(self):
        try:
            import faiss
            self._faiss = faiss
        except ImportError:
            raise ImportError("Install faiss: pip install faiss-cpu")

        idx_path = self.store_dir / "jobs.index"
        meta_path = self.store_dir / "meta.pkl"

        if idx_path.exists() and meta_path.exists():
            logger.info("Loading existing FAISS index...")
            self.index = self._faiss.read_index(str(idx_path))
            with open(meta_path, "rb") as f:
                data = pickle.load(f)
                self.id_map = data.get("id_map", {})
                self.meta = data.get("meta", {})
                self.next_idx = data.get("next_idx", 0)
            logger.info(f"Loaded {self.next_idx} vectors")
        else:
            logger.info("Creating new FAISS index (IndexFlatIP for cosine sim)")
            self.index = self._faiss.IndexFlatIP(self.dim)

    def _save(self):
        self._faiss.write_index(self.index, str(self.store_dir / "jobs.index"))
        with open(self.store_dir / "meta.pkl", "wb") as f:
            pickle.dump({
                "id_map": self.id_map, "meta": self.meta, "next_idx": self.next_idx
            }, f)

    def _normalize(self, vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        if norm == 0:
            return vec
        return vec / norm

    def add_job_vector(self, job_id: int, embedding: List[float], metadata: dict = None) -> int:
        """Add one job embedding to the index."""
        vec = np.array(embedding, dtype=np.float32)
        if len(vec) != self.dim:
            logger.warning(f"Embedding dim mismatch: got {len(vec)}, expected {self.dim}")
            # Pad or truncate
            if len(vec) < self.dim:
                vec = np.pad(vec, (0, self.dim - len(vec)))
            else:
                vec = vec[:self.dim]
        vec = self._normalize(vec).reshape(1, -1)
        self.index.add(vec)
        idx = self.next_idx
        self.id_map[idx] = job_id
        self.meta[idx] = metadata or {}
        self.next_idx += 1
        if self.next_idx % 50 == 0:
            self._save()
        return idx

    def save_resume_vector(self, embedding: List[float]):
        """Save resume embedding separately."""
        vec = np.array(embedding, dtype=np.float32)
        if len(vec) != self.dim:
            vec = vec[:self.dim] if len(vec) > self.dim else np.pad(vec, (0, self.dim - len(vec)))
        vec = self._normalize(vec)
        np.save(str(self.store_dir / "resume.npy"), vec)
        logger.info("Resume vector saved ✓")

    def get_resume_vector(self) -> Optional[np.ndarray]:
        path = self.store_dir / "resume.npy"
        return np.load(str(path)) if path.exists() else None

    def match_resume(self, top_k: int = 50) -> List[dict]:
        """Find jobs most similar to the resume vector."""
        resume_vec = self.get_resume_vector()
        if resume_vec is None:
            return []
        if self.index.ntotal == 0:
            return []

        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(resume_vec.reshape(1, -1), k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            results.append({
                "job_id": self.id_map.get(idx),
                "score": float(score),
                "meta": self.meta.get(idx, {}),
            })
        return sorted(results, key=lambda x: x["score"], reverse=True)

    def get_stats(self) -> dict:
        return {
            "total_vectors": self.index.ntotal if self.index else 0,
            "has_resume": (self.store_dir / "resume.npy").exists(),
            "dim": self.dim,
        }

    def flush(self):
        self._save()
        logger.info("Vector store flushed")
