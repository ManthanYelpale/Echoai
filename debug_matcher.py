
import asyncio
import sys
import os

# Switch to backend directory so paths work
os.chdir("backend")
sys.path.append(os.getcwd())

from src.agent.tools.job_matcher import JobMatcher

async def main():
    print("Force running matcher to apply new scoring...")
    matcher = JobMatcher()
    
    # We want to re-score everything, but matcher.run() only processes "unmatched" jobs usually.
    # However, since we just added the logic, we might need to clear existing matches or just accept that
    # it only affects NEW jobs unless we force it.
    
    # Force re-index all jobs
    import sqlite3
    with sqlite3.connect("data/echo_career.db") as conn:
        conn.execute("DELETE FROM job_matches")
        conn.commit()
    print("Cleared old matches.")

    # Get all active jobs to re-index
    jobs = matcher.db.get_all_jobs()
    print(f"Re-indexing {len(jobs)} jobs...")
    
    indexed = 0
    for job in jobs:
        text = matcher._job_to_text(job)
        embedding = await matcher.llm.embed(text)
        if embedding:
            matcher.vs.add_job_vector(job["id"], embedding, {
                "title": job["title"], "company": job["company"]
            })
            indexed += 1
    
    matcher.vs.flush()
    print(f"Indexed {indexed} jobs.")
    
    # Now run matching part only
    # We can't call matcher.run() easily because it tries to index again.
    # But since we populated VS, we can call match_resume logic or just call run() 
    # since we modified run() to proceed even if no new jobs.
    report = await matcher.run()
    print(f"Matcher done: {report}")

if __name__ == "__main__":
    asyncio.run(main())
