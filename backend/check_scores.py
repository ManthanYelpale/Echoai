
import sys
import os
import asyncio

# Ensure we can import from src and config
# Assuming we run this from backend/ directory
sys.path.append(os.getcwd())

from src.agent.memory.vector_store import VectorStore

async def main():
    try:
        vs = VectorStore()
        results = vs.match_resume(top_k=10)
        
        print(f"Top 10 raw match scores:")
        for r in results:
            print(f"Job ID: {r['job_id']} | Score: {r['score']:.4f} | Title: {r['meta'].get('title', 'Unknown')}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
