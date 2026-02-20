
import sys
import numpy as np
import faiss
from pathlib import Path

vs_path = Path("backend/data/vector_store")
idx_path = vs_path / "jobs.index"
resume_path = vs_path / "resume.npy"

print(f"Checking {vs_path}...")

if idx_path.exists():
    index = faiss.read_index(str(idx_path))
    print(f"FAISS Index Total: {index.ntotal}")
else:
    print("FAISS Index not found!")

if resume_path.exists():
    vec = np.load(str(resume_path))
    print(f"Resume vector shape: {vec.shape}")
else:
    print("Resume vector NOT found!")
