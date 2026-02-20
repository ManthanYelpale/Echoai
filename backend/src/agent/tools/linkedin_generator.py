"""
src/agent/tools/linkedin_generator.py
LLM-driven LinkedIn post generator. No hardcoded templates.
All posts generated dynamically by Ollama based on candidate profile.
"""
import json
from src.agent.brain.groq_client import GroqClient
from src.agent.brain.logger import get_logger
from src.agent.memory.database import Database

logger = get_logger("linkedin_gen")

POST_TYPES = {
    "open_to_work": "Open to work announcement targeting recruiters",
    "skill_spotlight": "Deep-dive post about a specific technical skill or project",
    "learning_update": "Weekly learning journey update",
    "achievement_story": "Story-based post about a project or accomplishment",
    "recruiter_magnet": "Direct post targeting hiring managers with strong CTA",
    "market_insight": "Share an observation about the tech industry",
}


class LinkedInGenerator:
    def __init__(self):
        self.llm = GroqClient()
        self.db = Database()

    async def generate(self, post_type: str = "open_to_work",
                        target_role: str = None, topic: str = None) -> dict:
        """Generate a LinkedIn post using Cloud LLM (Groq). Fully dynamic."""
        resume = self.db.get_active_resume()
        name = resume.get("name","") if resume else ""
        skills = (resume.get("skills",[]) + resume.get("tech_stack",[]))[:12] if resume else []
        roles = target_role or (resume.get("target_roles",["Python Developer"])[0] if resume else "Python Developer")
        grad_year = resume.get("education",{}).get("graduation_year",2025) if resume else 2025

        type_desc = POST_TYPES.get(post_type, post_type)
        topic_str = f"Topic/Focus: {topic}" if topic else ""

        prompt = f"""Write a LinkedIn post for an Indian tech fresher.

POST TYPE: {type_desc}
TARGET ROLE: {roles}
{topic_str}
CANDIDATE NAME: {name or 'a 2025 graduate'}
SKILLS: {', '.join(skills)}
GRADUATION YEAR: {grad_year}

RULES:
- Start with a powerful hook (first line must make someone stop scrolling)
- 200-280 words
- First person, authentic voice, NOT corporate or cringe
- Include 1 specific project/achievement (make something realistic up if needed)
- End with a call-to-action
- Mention open to opportunities in India (all locations)
- DO NOT add hashtags in the content (they'll be added separately)
- Make it feel human, not AI-written
- Use line breaks for readability

Write ONLY the post content, nothing else:"""

        content = await self.llm.chat([{"role": "user", "content": prompt}], temperature=0.75)
        if not content or len(content) < 50:
            content = await self._fallback_post(post_type, roles, skills, name)

        hashtags = await self._generate_hashtags(post_type, roles, topic)
        hook = content.split("\n")[0][:120] if content else ""
        engagement = self._predict_engagement(content)

        post = {
            "post_type": post_type,
            "target_role": roles,
            "topic": topic or "",
            "content": content,
            "hook": hook,
            "hashtags": hashtags,
            "engagement": engagement,
        }
        post["id"] = self.db.save_post(post)
        return post

    async def _generate_hashtags(self, post_type: str, role: str, topic: str = None) -> list:
        """Dynamically generate relevant hashtags via LLM."""
        prompt = f"""Generate 8-10 relevant LinkedIn hashtags for a post about:
Role: {role}
Post type: {post_type}
Topic: {topic or 'general career'}
Context: Indian tech fresher 2025

Return ONLY a JSON array of hashtag strings starting with #:
["#Python", "#DataScience", ...]"""

        try:
            response = await self.llm.chat([{"role": "user", "content": prompt}], json_mode=True)
            result = json.loads(response)
            if isinstance(result, list):
                return result[:10]
            if isinstance(result, dict) and "hashtags" in result:
                return result["hashtags"][:10]
        except:
            pass
            
        # Safe fallback
        return ["#OpenToWork", "#FreshGraduate", "#TechJobs", "#India", "#Python",
                "#DataScience", "#AIEngineer", "#HiringFreshers", "#2025Graduate"]

    async def _fallback_post(self, post_type, role, skills, name) -> str:
        """Simpler generation fallback."""
        prompt = f"""Write a short LinkedIn post (150 words) for {name or 'a fresher'} 
seeking {role} roles in India. Skills: {', '.join(skills[:6])}.
Type: {post_type}. Make it authentic and professional. No hashtags."""
        return await self.llm.chat([{"role": "user", "content": prompt}]) or "Excited to begin my tech career journey! Looking for opportunities in India as a fresher. Let's connect!"

    def _predict_engagement(self, content: str) -> str:
        score = 0
        if "?" in content: score += 2
        if any(w in content.lower() for w in ["built", "learned", "project", "achieved"]): score += 2
        if len(content) > 150: score += 1
        if any(w in content.lower() for w in ["dm", "connect", "comment", "share"]): score += 1
        return "high" if score >= 5 else ("medium" if score >= 3 else "low")

    async def generate_weekly_batch(self) -> list:
        """Generate one of each post type for the week."""
        results = []
        resume = self.db.get_active_resume()
        roles = resume.get("target_roles", ["AI Engineer","Data Analyst"]) if resume else ["AI Engineer"]

        tasks = [
            ("open_to_work", roles[0] if roles else "AI Engineer", None),
            ("skill_spotlight", roles[0] if roles else "Python Developer", "LangChain"),
            ("recruiter_magnet", roles[1] if len(roles) > 1 else "Data Analyst", None),
            ("learning_update", roles[0] if roles else "AI Engineer", "RAG Pipelines"),
            ("achievement_story", roles[0] if roles else "Python Developer", None),
        ]
        results = []
        
        # Sequentially generate to avoid rate limits on free tier
        for ptype, role, topic in tasks:
            post = await self.generate(post_type=ptype, target_role=role, topic=topic)
            results.append(post)
            import asyncio
            await asyncio.sleep(1) # Polite delay
            
        return results
