import json
from config.settings import get_settings
from src.agent.brain.groq_client import GroqClient
from src.agent.brain.logger import get_logger
from src.agent.memory.database import Database
from src.agent.memory.vector_store import VectorStore

logger = get_logger("matcher")


class JobMatcher:
    def __init__(self):
        self.db = Database()
        self.vs = VectorStore()
        self.llm = GroqClient()
        s = get_settings()
        self.threshold = s.match_threshold
        self.top_n = s.match_top_n
        self.rerank = s.llm_rerank_enabled
        self.rerank_min = s.llm_rerank_min
        self.rerank_max = s.llm_rerank_max

    async def run(self) -> dict:
        """Full async matching pipeline."""
        logger.info("Starting job matching pipeline...")

        # 1. Index unmatched jobs
        unmatched = self.db.get_unmatched_jobs(200)
        if not unmatched:
            logger.info("No new jobs to index, proceeding to matching...")
        
        indexed = 0
        if unmatched:
            logger.info(f"Embedding {len(unmatched)} new jobs...")

        for job in unmatched:
            text = self._job_to_text(job)
            # Use FastEmbed (CPU) via GroqClient wrapper
            embedding = await self.llm.embed(text)
            if embedding:
                self.vs.add_job_vector(job["id"], embedding, {
                    "title": job["title"], "company": job["company"]
                })
                indexed += 1

        self.vs.flush()
        logger.info(f"Indexed {indexed} jobs")

        # 2. Match against resume
        results = self.vs.match_resume(top_k=200)
        if not results:
            logger.warning("No vector results — is resume embedded?")
            return {"matched": 0, "indexed": indexed}

        # 3. Score, filter, optionally LLM re-rank
        matched = 0
        resume = self.db.get_active_resume()

        for r in results:
            score = r["score"]
            if score < (self.threshold - 0.1):
                continue

            job = self.db.get_job_by_id(r["job_id"])
            if not job:
                continue

            match = self._build_match(job, score, resume)

            # LLM re-rank for borderline scores (Groq Cloud)
            if self.rerank and self.rerank_min <= score <= self.rerank_max:
                llm_result = await self._llm_rerank(job, score, resume)
                if llm_result:
                    match.update(llm_result)

            match["final_score"] = self._final_score(score, match.get("llm_score"))

            if match["final_score"] >= self.threshold:
                self.db.save_match(match)
                # Track skill gaps
                for gap in match.get("skill_gaps", []):
                    self.db.bump_skill(gap)
                matched += 1

        logger.info(f"Matched: {matched}")
        return {"matched": matched, "indexed": indexed}

    def _job_to_text(self, job: dict) -> str:
        parts = [
            f"Title: {job.get('title','')}",
            f"Company: {job.get('company','')}",
            f"Location: {job.get('location','')}",
        ]
        skills = job.get("skills_required", [])
        if isinstance(skills, str):
            try:
                skills = json.loads(skills)
            except:
                skills = []
        if skills:
            parts.append(f"Skills: {', '.join(skills)}")
        if job.get("description"):
            parts.append(f"Description: {job['description'][:800]}")
        return "\n".join(parts)

    def _build_match(self, job: dict, score: float, resume: dict) -> dict:
        r_skills = set((s.lower() for s in (resume or {}).get("skills", []) + (resume or {}).get("tech_stack", [])))

        skills_raw = job.get("skills_required", [])
        if isinstance(skills_raw, str):
            try:
                skills_raw = json.loads(skills_raw)
            except:
                skills_raw = []
        j_skills = set(s.lower() for s in skills_raw)

        overlap = list(r_skills & j_skills)
        gaps = list(j_skills - r_skills)[:6]

        reasons = []
        if overlap:
            reasons.append(f"Skill match: {', '.join(overlap[:4])}")
        if score > 0.7:
            reasons.append("Strong semantic alignment with your profile")
        if "fresher" in (job.get("description","") or "").lower():
            reasons.append("Open to freshers")

        # Calculate role match score
        role_score, role_reason = self._calculate_role_match(job.get("title", ""), resume)
        if role_reason:
            reasons.append(role_reason)

        final_score = score + role_score

        return {
            "job_id": job["id"],
            "embed_score": score,
            "llm_score": None,
            "final_score": final_score,
            "match_reasons": reasons,
            "skill_overlap": overlap[:8],
            "skill_gaps": gaps,
            "llm_reasoning": "",
        }

    def _calculate_role_match(self, title: str, resume: dict) -> tuple:
        """Returns (score_modifier, reason)"""
        if not title:
            return 0.0, None
            
        title_lower = title.lower()
        target_roles = [r.lower() for r in (resume or {}).get("target_roles", [])]
        
        # 1. Direct match with target role
        for role in target_roles:
            if role in title_lower:
                return 0.15, f"Matches target role: {role}"
                
        # 2. Penalty for unrelated roles (unless requested)
        unrelated = ["trainer", "sales", "hr", "recruiter", "marketing", "business development", "bpo", "customer support"]
        for bad in unrelated:
            if bad in title_lower:
                # Only penalize if they didn't ask for it
                if not any(bad in t for t in target_roles):
                    logger.info(f"Penalizing '{title}' for '{bad}'")
                    return -0.5, f"Role mismatch: {bad}"
                    
        return 0.0, None

    async def _llm_rerank(self, job: dict, score: float, resume: dict) -> dict:
        prompt = f"""Rate this job's suitability for a 2025 fresher candidate.

CANDIDATE: skills={', '.join((resume or {}).get('skills', [])[:12])}
JOB: {job.get('title')} at {job.get('company')}, {job.get('location')}
Description: {(job.get('description') or '')[:400]}
Embedding score: {score:.2f}

Return JSON only:
{{"llm_score": 0.75, "reasoning": "one sentence"}}"""

        # Groq JSON mode
        try:
            response_text = await self.llm.chat(
                [{"role": "user", "content": prompt}], 
                json_mode=True
            )
            result = json.loads(response_text)
            return {
                "llm_score": result.get("llm_score", score),
                "llm_reasoning": result.get("reasoning", ""),
            }
        except:
            return {}

    def _final_score(self, embed: float, llm) -> float:
        if llm is not None:
            return round(0.6 * embed + 0.4 * float(llm), 4)
        return round(embed, 4)

    async def explain(self, job_id: int) -> str:
        """Generate natural language explanation for a match."""
        job = self.db.get_job_by_id(job_id)
        if not job:
            return f"Job #{job_id} not found."
        resume = self.db.get_active_resume()

        prompt = f"""Explain why this job is (or isn't) a good match for this candidate.

JOB: {job.get('title')} at {job.get('company')}, {job.get('location')}
Description: {(job.get('description') or '')[:600]}

CANDIDATE SKILLS: {', '.join((resume or {}).get('skills', [])[:15])}
CANDIDATE LEVEL: 2025 fresher

Give a 3-4 sentence honest assessment. Be specific about skill matches and gaps."""

        return await self.llm.chat([{"role": "user", "content": prompt}])
