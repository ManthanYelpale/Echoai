
import sys
import os
import asyncio

# Ensure we can import from src and config
sys.path.append(os.getcwd())

from src.agent.tools.job_matcher import JobMatcher

async def main():
    try:
        matcher = JobMatcher()
        print("Running Job Matcher...")
        result = await matcher.run()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
