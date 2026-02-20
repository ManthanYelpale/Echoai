
import sys
import os
import asyncio

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from src.agent.tools.job_matcher import JobMatcher
except ImportError:
    # Fallback if running from root
    from backend.src.agent.tools.job_matcher import JobMatcher

async def main():
    print("🚀 Triggering Job Matcher (Groq + SentenceTransformers)...")
    try:
        matcher = JobMatcher()
        result = await matcher.run()
        print(f"✅ Match Result: {result}")
    except Exception as e:
        print(f"❌ Error during matching: {e}")

if __name__ == "__main__":
    asyncio.run(main())
