"""
src/agent/tools/resume_analyzer.py
Fully dynamic resume analysis via Ollama LLM.
No hardcoded skill lists — LLM extracts everything from the actual resume.
"""
import json
from pathlib import Path
from typing import Optional
from src.agent.brain.groq_client import GroqClient
from src.agent.brain.logger import get_logger
from src.agent.memory.database import Database
from src.agent.memory.vector_store import VectorStore

logger = get_logger("resume_analyzer")


class ResumeAnalyzer:
    def __init__(self):
        self.llm = GroqClient()
        self.db = Database()
        self.vs = VectorStore()

    async def analyze(self, file_path: str = None, raw_text: str = None) -> dict:
        """
        Full async resume analysis pipeline.
        Accepts either file path or raw text.
        All extraction done via Cloud LLM (Groq) — fully dynamic.
        """
        # 1. Extract text
        if raw_text:
            text = raw_text
            filename = "pasted_text"
        elif file_path:
            text = self._extract_text(Path(file_path))
            filename = Path(file_path).name
        else:
            # Try default path from env
            from config.settings import get_settings
            default = Path(get_settings().sqlite_path).parent / "resume.pdf"
            if default.exists():
                text = self._extract_text(default)
                filename = default.name
            else:
                logger.warning("No resume provided. Using empty profile.")
                return {}

        if not text.strip():
            logger.error("Empty resume text")
            return {}

        logger.info(f"Analyzing resume: {filename} ({len(text)} chars)")

        # 2. LLM extraction — let the model figure out everything
        extracted = await self._llm_extract(text)
        if not extracted:
            extracted = {}

        extracted["filename"] = filename
        extracted["raw_text"] = text

        # 3. Identify skill gaps by comparing to job market
        gaps = await self._identify_gaps(extracted)
        extracted["market_gaps"] = gaps

        # 4. Save to DB
        self.db.save_resume(extracted)
        logger.info(f"Resume saved. Skills: {len(extracted.get('skills', []))}")

        # 5. Generate and save embedding — using FastEmbed (CPU)
        embed_text = self._build_embed_text(extracted)
        if not embed_text.strip():
            # Fallback: embed raw resume text so job matching always works
            embed_text = text[:2000]
            
        embedding = await self.llm.embed(embed_text)
        if embedding:
            self.vs.save_resume_vector(embedding)
        else:
            logger.warning("Embedding failed")

        return extracted

    async def _llm_extract(self, text: str) -> Optional[dict]:
        """Use Groq to extract structured data from resume text."""
        prompt = f"""Analyze this resume and extract all information. Return ONLY valid JSON.

RESUME TEXT:
{text[:3500]}

Return this exact JSON structure (fill all fields based on the resume):
{{
  "name": "candidate full name",
  "email": "email if found",
  "phone": "phone if found",
  "skills": ["skill1", "skill2", ...],
  "tech_stack": ["Python", "SQL", ...],
  "experience_years": 0,
  "education": {{
    "degree": "B.Tech",
    "branch": "Computer Science",
    "college": "college name",
    "graduation_year": 2025,
    "cgpa": 8.5
  }},
  "projects": [
    {{
      "name": "project name",
      "description": "what it does",
      "tech": ["Python", "ML"]
    }}
  ],
  "certifications": ["cert1", "cert2"],
  "industry_tags": ["Machine Learning", "Data Analytics"],
  "target_roles": ["AI Engineer", "Data Analyst"],
  "strengths": ["strength1", "strength2"],
  "summary": "2 sentence professional summary",
  "experience_level": "fresher"
}}"""

        try:
            response = await self.llm.chat([{"role": "user", "content": prompt}], json_mode=True)
            return json.loads(response)
        except Exception as e:
            logger.error(f"Resume extraction failed: {e}")
            return {}

    async def _identify_gaps(self, profile: dict) -> list:
        """Dynamically find skill gaps by asking LLM about market trends."""
        skills = profile.get("skills", []) + profile.get("tech_stack", [])
        target_roles = profile.get("target_roles", ["Software Developer"])

        prompt = f"""You are a career advisor for Indian tech job market 2025.

This candidate has these skills: {", ".join(skills[:20])}
They are targeting: {", ".join(target_roles[:3])}
Experience: {profile.get('experience_level', 'fresher')}

What are the TOP 10 skills they should learn to get hired faster in India?
Focus on skills actively demanded in Indian job postings right now.

Return ONLY valid JSON:
{{
  "gaps": [
    {{"skill": "LangChain", "priority": "high", "category": "ai", "reason": "why important"}},
    ...
  ]
}}"""

        try:
            response = await self.llm.chat([{"role": "user", "content": prompt}], json_mode=True)
            result = json.loads(response)
            
            if result and "gaps" in result:
                # Save each gap to DB
                for gap in result["gaps"]:
                    self.db.bump_skill(
                        gap.get("skill",""),
                        level="none",
                        category=gap.get("category","general")
                    )
                return result["gaps"]
        except:
            return []
        return []

    def _extract_text(self, path: Path) -> str:
        """Extract plain text from PDF, DOCX, or TXT."""
        suffix = path.suffix.lower()
        try:
            if suffix == ".txt":
                return path.read_text(encoding="utf-8", errors="ignore")
            elif suffix == ".pdf":
                try:
                    import pypdf
                    reader = pypdf.PdfReader(str(path))
                    return "\n".join(p.extract_text() or "" for p in reader.pages)
                except ImportError:
                    import pdfminer.high_level
                    return pdfminer.high_level.extract_text(str(path))
            elif suffix in [".docx", ".doc"]:
                import docx
                doc = docx.Document(str(path))
                return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            logger.error(f"Text extraction failed for {path}: {e}")
        return ""

    def _build_embed_text(self, data: dict) -> str:
        """Build rich text for embedding — combines key resume signals."""
        parts = []
        if data.get("summary"):
            parts.append(data["summary"])
        if data.get("industry_tags"):
            parts.append(f"Domains: {', '.join(data['industry_tags'])}")
        if data.get("skills"):
            parts.append(f"Skills: {', '.join(data['skills'][:20])}")
        if data.get("tech_stack"):
            parts.append(f"Tech: {', '.join(data['tech_stack'][:15])}")
        if data.get("target_roles"):
            parts.append(f"Seeking: {', '.join(data['target_roles'])}")
        if data.get("experience_level"):
            parts.append(f"Level: {data['experience_level']} 2025 graduate")
        return "\n".join(parts)

    async def get_gap_report(self) -> str:
        """Generate a natural language skill gap report via LLM."""
        resume = self.db.get_active_resume()
        gaps = self.db.get_skill_gaps(12)

        if not resume:
            return "No resume analyzed yet. Please upload your resume first."

        prompt = f"""Create a skill gap analysis report for this Indian tech fresher (2025).

Their skills: {", ".join(resume.get("skills", [])[:15])}
Their tech stack: {", ".join(resume.get("tech_stack", [])[:10])}
Top missing skills from job market: {", ".join(g["skill_name"] for g in gaps[:8])}
Target roles: {", ".join(resume.get("target_roles", [])[:3])}

Write a helpful, actionable report with:
1. Current strong points
2. Critical gaps to fill (with learning time estimates)
3. Specific learning path for India market 2025
4. Resources to learn each skill (free resources only)

Keep it practical, 300 words max."""

        return await self.llm.chat([{"role": "user", "content": prompt}])
