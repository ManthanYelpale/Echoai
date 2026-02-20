#!/usr/bin/env python3
"""
run.py — Echo Career AI Backend
Usage (run from backend/ directory):
  python run.py api     → Start FastAPI backend (port 8000)
  python run.py agent   → Run autonomous agent loop
  python run.py mcp     → Start MCP server (stdio)
  python run.py setup   → First-time setup wizard
"""
import sys
import asyncio
from pathlib import Path


def start_api():
    """Start FastAPI backend on port 8000."""
    import uvicorn
    from config.settings import get_settings
    s = get_settings()
    print(f"\n✦ Echo API → http://{s.api_host}:{s.api_port}")
    print("  Frontend → http://localhost:5173  (run: cd ../frontend && npm run dev)\n")
    uvicorn.run(
        "src.api.main:app",
        host=s.api_host,
        port=s.api_port,
        reload=s.api_reload,
        log_level="info",
    )



async def run_agent():
    """Start autonomous agent loop."""
    from src.agent.brain.groq_client import GroqClient
    from src.agent.scrapers.job_scraper import ScraperOrchestrator
    from src.agent.tools.job_matcher import JobMatcher
    from src.agent.tools.resume_analyzer import ResumeAnalyzer
    from src.agent.tools.linkedin_generator import LinkedInGenerator
    from src.agent.memory.database import Database
    from config.settings import get_settings
    import time

    print("\n✦ Echo Autonomous Agent starting...")
    s = get_settings()
    db = Database()
    scraper = ScraperOrchestrator()
    matcher = JobMatcher()
    analyzer = ResumeAnalyzer()
    post_gen = LinkedInGenerator()
    groq = GroqClient()

    print(f"  Model: {groq.model}")

    resume = db.get_active_resume()
    if not resume:
        print("  ⚠️  No resume found. Upload via the web UI first.")
    else:
        print(f"  Resume: {resume.get('filename','unknown')} | Skills: {len(resume.get('skills',[]))}")

    interval = s.agent_loop_hours * 3600
    print(f"  Loop interval: {s.agent_loop_hours}h\n")

    while True:
        paused = db.get_pref("agent_paused", False)
        if paused:
            print("  ⏸ Agent paused. Sleeping 60s...")
            await asyncio.sleep(60)
            continue

        print(f"\n{'='*50}")
        print(f"  🔄 Agent Cycle — {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*50}")

        t = time.time()
        scrape_result = await scraper.run_all()
        print(f"  ✅ Scraped: {scrape_result['total']} jobs")

        match_result = await matcher.run()
        print(f"  ✅ Matched: {match_result['matched']} jobs")

        post = await post_gen.generate()
        print(f"  ✅ Post generated: {post.get('post_type','')}")

        stats = db.get_stats()
        print(f"\n  📊 {stats['total_jobs']} jobs | {stats['total_matched']} matched | {stats['avg_score']:.0%} avg")
        print(f"  ⏱  Cycle: {time.time()-t:.0f}s | 😴 Sleeping {s.agent_loop_hours}h...")
        await asyncio.sleep(interval)


async def run_mcp():
    """Start MCP server."""
    from src.mcp.server import EchoMCPServer
    server = EchoMCPServer()
    await server.run_stdio()


async def setup():
    """First-time setup wizard."""
    print("""
╔══════════════════════════════════════════════════════╗
║          ECHO — First Time Setup                     ║
╚══════════════════════════════════════════════════════╝
""")
    # Data directories
    from config.settings import get_settings
    s = get_settings()
    
    # Check Groq
    print("\n  Checking Configuration...")
    if not s.groq_api_key:
         print("  ❌ GROQ_API_KEY missing in .env")
    else:
         print(f"  ✅ Groq Key found: {s.groq_api_key[:6]}...")

    # Data directories
    for d in ["data/uploads", "data/reports", "data/logs", "data/vector_store"]:
        Path(d).mkdir(parents=True, exist_ok=True)
    print("  ✅ Data directories ready")

    print("""
✅ Setup complete!

  cd backend && python run.py api     → Start API (port 8000)
  cd frontend && npm run dev          → Start UI  (port 5173)

Or just run start.bat from the project root.
""")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "api"

    if mode == "api":
        start_api()
    elif mode == "agent":
        asyncio.run(run_agent())
    elif mode == "mcp":
        asyncio.run(run_mcp())
    elif mode == "setup":
        asyncio.run(setup())
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python run.py [api|agent|mcp|setup]")
