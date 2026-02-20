"""
src/api/main.py
FastAPI backend — REST API + WebSocket chat + SSE streaming
Echo career agent API
"""
from __future__ import annotations
import asyncio
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from config.settings import get_settings
from src.agent.brain.groq_client import GroqClient
from src.agent.brain.logger import get_logger
from src.agent.memory.database import Database
from src.agent.tools.resume_analyzer import ResumeAnalyzer
from src.agent.tools.job_matcher import JobMatcher
from src.agent.tools.linkedin_generator import LinkedInGenerator
from src.agent.scrapers.job_scraper import ScraperOrchestrator

logger = get_logger("api")
s = get_settings()

app = FastAPI(
    title="Echo — Career Intelligence API",
    description="Autonomous career agent for India tech freshers",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=s.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Singletons ───────────────────────────────────────────────
db = Database()
groq = GroqClient()
analyzer = ResumeAnalyzer()
matcher = JobMatcher()
post_gen = LinkedInGenerator()
scraper = ScraperOrchestrator()

# ── CHAT SYSTEM PROMPT ───────────────────────────────────────
ECHO_SYSTEM = """You are Echo the chat bot, an intelligent career AI agent specializing in the Indian tech job market.
You help freshers (2025 graduates) find jobs in AI, Python, Data Science, and related roles.

You have access to:
- Candidate's resume and skill profile
- Scraped job listings from Naukri, Indeed, Internshala, Wellfound
- Skill gap analysis
- LinkedIn post generation

PERSONALITY: Helpful, warm, concise, practical. You speak like a smart friend who knows the tech industry.
Use specific India context (LPA salary, companies like TCS/Zoho/Sarvam AI, cities like Bangalore/Hyderabad).
Keep responses under 200 words unless the user asks for detail.
When you detect an action request (show jobs, generate post, etc.), you call the appropriate tool."""

# ── REQUEST MODELS ───────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = ""

class PreferenceUpdate(BaseModel):
    key: str
    value: object

class PostGenRequest(BaseModel):
    post_type: str = "open_to_work"
    target_role: Optional[str] = None
    topic: Optional[str] = None

# ── TOOL ROUTER ──────────────────────────────────────────────

async def route_to_tool(message: str, session_id: str) -> Optional[dict]:
    """
    Use LLM to determine if message needs a tool call.
    Returns tool result or None (for pure chat).
    """
    intent_prompt = f"""Classify this user message into one of these actions or 'chat':

Message: "{message}"

Actions:
- show_jobs: user wants to see job matches
- explain_job: user asks about a specific job (extract job_id if mentioned)
- skill_gaps: user asks about missing skills or what to learn
- generate_post: user wants a LinkedIn post
- run_scrape: user wants to start job scraping now
- upload_resume: user mentions resume
- show_stats: user wants agent statistics
- set_preference: user wants to change role/location/settings
- weekly_posts: user wants all post types generated
- chat: general question, career advice, other

Return JSON only:
{{"action": "show_jobs", "params": {{}}}}"""

    result = await groq.extract_json(intent_prompt)
    if not result:
        return None

    action = result.get("action", "chat")
    params = result.get("params", {})

    if action == "show_jobs":
        jobs = db.get_top_matches(
            limit=params.get("limit", 10),
            work_mode=params.get("work_mode"),
            company_type=params.get("company_type"),
        )
        return {"type": "jobs", "data": jobs}

    elif action == "explain_job":
        job_id = params.get("job_id")
        if job_id:
            explanation = await matcher.explain(int(job_id))
            return {"type": "explanation", "data": explanation}

    elif action == "skill_gaps":
        gaps = db.get_skill_gaps(12)
        report = await analyzer.get_gap_report()
        return {"type": "skill_gaps", "data": {"gaps": gaps, "report": report}}

    elif action == "generate_post":
        post = await post_gen.generate(
            post_type=params.get("post_type", "open_to_work"),
            target_role=params.get("target_role"),
            topic=params.get("topic"),
        )
        return {"type": "linkedin_post", "data": post}

    elif action == "run_scrape":
        asyncio.create_task(_run_scrape_background())
        return {"type": "info", "data": "Scraping started in background! This takes 3-5 minutes. I'll update you when done."}

    elif action == "show_stats":
        stats = db.get_stats()
        return {"type": "stats", "data": stats}

    elif action == "set_preference":
        key = params.get("key","")
        val = params.get("value")
        if key and val:
            db.set_pref(key, val)
            return {"type": "info", "data": f"Preference updated: {key} = {val}"}

    elif action == "weekly_posts":
        posts = await post_gen.generate_weekly_batch()
        return {"type": "weekly_posts", "data": posts}

    return None


async def _run_scrape_background():
    """Background task: scrape → match → report."""
    try:
        await scraper.run_all()
        await matcher.run()
        db.set_pref("last_cycle_time", datetime.now().isoformat())
        logger.info("Background scrape+match cycle complete")
    except Exception as e:
        logger.error(f"Background cycle failed: {e}")


# ── API ROUTES ───────────────────────────────────────────────

@app.get("/")
async def root():
    return {"name": "Echo Career API", "version": "1.0.0", "status": "running"}

@app.get("/health")
async def health():
    groq_ok = await groq.is_available()
    stats = db.get_stats()
    return {
        "status": "healthy",
        "groq": groq_ok,
        "model": groq.model,
        "stats": stats,
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/api/ai/models")
async def get_models():
    models = await groq.list_models()
    return {"models": models, "current": groq.model}

@app.post("/api/ai/model")
async def set_model(body: dict):
    model = body.get("model","")
    if model:
        groq.model = model
        db.set_pref("selected_model", model)
    return {"model": groq.model}

# Chat — streaming SSE
@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())

    async def generate():
        # Check for tool call first
        tool_result = await route_to_tool(req.message, session_id)

        if tool_result:
            # Stream tool result as JSON event
            yield f"data: {json.dumps({'type': 'tool', 'result': tool_result})}\n\n"
            # Also generate natural language summary
            history = db.get_history(session_id, 6)
            msgs = [{"role": m["role"], "content": m["content"]} for m in history]
            msgs.append({"role": "user", "content": req.message})

            summary_prompt = f"The tool returned this result: {json.dumps(tool_result)[:500]}. Summarize it naturally in 1-2 sentences."
            async for chunk in groq.stream_chat(msgs, system=ECHO_SYSTEM + f"\n{summary_prompt}"):
                yield f"data: {json.dumps({'type': 'text', 'chunk': chunk})}\n\n"
        else:
            # Pure chat with history
            history = db.get_history(session_id, 10)
            msgs = [{"role": m["role"], "content": m["content"]} for m in history]
            msgs.append({"role": "user", "content": req.message})

            full_response = ""
            async for chunk in groq.stream_chat(msgs, system=ECHO_SYSTEM):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'text', 'chunk': chunk})}\n\n"

            # Save to history
            db.save_message(session_id, "user", req.message)
            db.save_message(session_id, "assistant", full_response)

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

# Non-streaming chat
@app.post("/api/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    tool_result = await route_to_tool(req.message, session_id)

    if tool_result:
        return {"session_id": session_id, "tool_result": tool_result, "text": None}

    history = db.get_history(session_id, 10)
    msgs = [{"role": m["role"], "content": m["content"]} for m in history]
    msgs.append({"role": "user", "content": req.message})
    
    # We need to construct messages properly for Groq
    # If system prompt is needed, add it to messages list if not using wrapper
    # But our GroqClient wrapper handles it via system param if we implemented stream_chat with system param
    # Wait, for regular chat, GroqClient.chat doesn't take 'system' param in my implementation?
    # Let me check GroqClient.chat signature: async def chat(self, messages, temperature=None, json_mode=False)
    # The 'system' param is missing in GroqClient.chat. I should prepend it to messages.
    
    chat_msgs = [{"role": "system", "content": ECHO_SYSTEM}] + msgs
    response = await groq.chat(chat_msgs)

    db.save_message(session_id, "user", req.message)
    db.save_message(session_id, "assistant", response)

    return {"session_id": session_id, "text": response, "tool_result": None}

# Resume upload
@app.post("/api/resume/upload")
async def upload_resume(file: UploadFile = File(...)):
    allowed = {".pdf", ".docx", ".doc", ".txt"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    save_path = Path("data/uploads") / file.filename
    save_path.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    save_path.write_bytes(content)

    result = await analyzer.analyze(file_path=str(save_path))
    
    # Trigger matching immediately
    await matcher.run()
    
    return {
        "success": True,
        "filename": file.filename,
        "skills_found": len(result.get("skills", [])),
        "name": result.get("name", ""),
        "target_roles": result.get("target_roles", []),
        "education": result.get("education", {}),
        "summary": result.get("summary", ""),
    }

# Jobs
@app.get("/api/jobs")
async def get_jobs(limit: int = 20, min_score: float = 0.5,
                    work_mode: str = None, company_type: str = None):
    jobs = db.get_top_matches(limit=limit, min_score=min_score,
                               work_mode=work_mode, company_type=company_type)
    return {"jobs": jobs, "total": len(jobs)}

@app.get("/api/jobs/{job_id}/explain")
async def explain_job(job_id: int):
    explanation = await matcher.explain(job_id)
    return {"job_id": job_id, "explanation": explanation}

@app.post("/api/agent/run")
async def run_agent():
    asyncio.create_task(_run_scrape_background())
    return {"status": "started", "message": "Agent cycle started in background"}

@app.post("/api/agent/pause")
async def pause_agent():
    db.set_pref("agent_paused", True)
    return {"paused": True}

@app.post("/api/agent/resume")
async def resume_agent():
    db.set_pref("agent_paused", False)
    return {"paused": False}

# LinkedIn posts
@app.post("/api/posts/generate")
async def generate_post(req: PostGenRequest):
    post = await post_gen.generate(
        post_type=req.post_type,
        target_role=req.target_role,
        topic=req.topic,
    )
    return post

@app.post("/api/posts/weekly")
async def weekly_posts():
    posts = await post_gen.generate_weekly_batch()
    return {"posts": posts}

@app.get("/api/posts")
async def get_posts(limit: int = 10):
    return {"posts": db.get_recent_posts(limit)}

# Skills
@app.get("/api/skills/gaps")
async def skill_gaps(limit: int = 15):
    gaps = db.get_skill_gaps(limit)
    report = await analyzer.get_gap_report()
    return {"gaps": gaps, "report": report}

@app.get("/api/resume")
async def get_resume():
    resume = db.get_active_resume()
    if not resume:
        return JSONResponse({"error": "No resume uploaded yet"}, status_code=404)
    return resume

# Preferences
@app.get("/api/preferences")
async def get_prefs():
    return db.get_all_prefs()

@app.post("/api/preferences")
async def set_pref(req: PreferenceUpdate):
    db.set_pref(req.key, req.value)
    return {"key": req.key, "value": req.value}

# Stats
@app.get("/api/stats")
async def stats():
    return db.get_stats()
