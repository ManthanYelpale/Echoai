
import sys
import os
sys.path.append(os.getcwd())
import asyncio
from src.agent.memory.vector_store import VectorStore

vs = VectorStore()
results = vs.match_resume(top_k=10)

print(f"Top 10 raw match scores:")
for r in results:
    print(f"Job IDs: {r['job_id']} | Score: {r['score']:.4f}")
