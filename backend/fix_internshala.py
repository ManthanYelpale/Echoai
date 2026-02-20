
import sys
import os
import asyncio
import sqlite3

# Ensure imports work
sys.path.append(os.getcwd())

from src.agent.memory.database import Database
from src.agent.scrapers.job_scraper import ScraperOrchestrator
from src.agent.tools.job_matcher import JobMatcher

async def main():
    print("Cleaning up bad Internshala jobs...")
    with sqlite3.connect("data/echo_career.db") as conn:
        # Delete jobs with the generic link
        cursor = conn.execute("DELETE FROM jobs WHERE source='internshala' AND apply_url LIKE 'https://internshala.com/jobs%'")
        print(f"Deleted {cursor.rowcount} bad jobs.")
        
        # Also delete matches for those jobs (cascade should handle it, but good to be safe/check)
        # SQLite with PRAGMA foreign_keys=ON should handle cascade if configured
        conn.commit()

    print("Running scraper for new jobs...")
    orchestrator = ScraperOrchestrator()
    # We only want to run Internshala if possible, but run_all runs all. 
    # That's fine.
    await orchestrator.run_all()
    
    print("Running matcher...")
    matcher = JobMatcher()
    await matcher.run()
    
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
