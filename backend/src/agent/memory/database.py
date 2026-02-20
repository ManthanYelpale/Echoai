"""
src/agent/memory/database.py
Full SQLite schema + async-compatible DB manager.
All paths from .env via settings.
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List
from config.settings import get_settings
from src.agent.brain.logger import get_logger

logger = get_logger("database")

SCHEMA = """
-- ─── JOBS ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id     TEXT UNIQUE,
    title           TEXT NOT NULL,
    company         TEXT NOT NULL,
    company_type    TEXT DEFAULT 'unknown',
    location        TEXT,
    work_mode       TEXT DEFAULT 'onsite',
    salary_min_lpa  REAL,
    salary_max_lpa  REAL,
    experience_min  INTEGER DEFAULT 0,
    experience_max  INTEGER DEFAULT 2,
    description     TEXT,
    skills_required TEXT DEFAULT '[]',
    apply_url       TEXT NOT NULL,
    source          TEXT,
    scraped_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active       BOOLEAN DEFAULT 1
);

-- ─── MATCHES ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS job_matches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    embed_score     REAL NOT NULL,
    llm_score       REAL,
    final_score     REAL NOT NULL,
    match_reasons   TEXT DEFAULT '[]',
    skill_overlap   TEXT DEFAULT '[]',
    skill_gaps      TEXT DEFAULT '[]',
    llm_reasoning   TEXT DEFAULT '',
    matched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    seen            BOOLEAN DEFAULT 0
);

-- ─── RESUME ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS resume_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    version         INTEGER NOT NULL,
    filename        TEXT,
    raw_text        TEXT,
    skills          TEXT DEFAULT '[]',
    tech_stack      TEXT DEFAULT '[]',
    experience_years REAL DEFAULT 0,
    education       TEXT DEFAULT '{}',
    industry_tags   TEXT DEFAULT '[]',
    projects        TEXT DEFAULT '[]',
    certifications  TEXT DEFAULT '[]',
    summary         TEXT DEFAULT '',
    target_roles    TEXT DEFAULT '[]',
    strengths       TEXT DEFAULT '[]',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active       BOOLEAN DEFAULT 1
);

-- ─── SKILL GAPS ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS skill_gaps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name      TEXT NOT NULL UNIQUE,
    frequency       INTEGER DEFAULT 1,
    our_level       TEXT DEFAULT 'none',
    priority        TEXT DEFAULT 'medium',
    category        TEXT DEFAULT 'general',
    last_seen       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── LINKEDIN POSTS ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS linkedin_posts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    post_type       TEXT NOT NULL,
    target_role     TEXT,
    topic           TEXT,
    content         TEXT NOT NULL,
    hook            TEXT,
    hashtags        TEXT DEFAULT '[]',
    engagement_pred TEXT DEFAULT 'medium',
    used            BOOLEAN DEFAULT 0,
    generated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── AGENT DECISIONS ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    action          TEXT NOT NULL,
    reasoning       TEXT DEFAULT '',
    status          TEXT DEFAULT 'pending',
    duration_secs   REAL DEFAULT 0,
    output          TEXT DEFAULT '{}',
    error_msg       TEXT DEFAULT '',
    decided_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── DAILY REPORTS ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS daily_reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date     DATE NOT NULL UNIQUE,
    total_scraped   INTEGER DEFAULT 0,
    total_matched   INTEGER DEFAULT 0,
    avg_score       REAL DEFAULT 0,
    top_job_ids     TEXT DEFAULT '[]',
    top_skill_gaps  TEXT DEFAULT '[]',
    report_markdown TEXT DEFAULT '',
    generated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── CHAT HISTORY ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chat_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    tool_call       TEXT DEFAULT '',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── USER PREFERENCES (dynamic, no hardcoding) ───────────────
CREATE TABLE IF NOT EXISTS preferences (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── INDICES ─────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_jobs_active      ON jobs(is_active, scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_source      ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_matches_score    ON job_matches(final_score DESC);
CREATE INDEX IF NOT EXISTS idx_matches_job      ON job_matches(job_id);
CREATE INDEX IF NOT EXISTS idx_gaps_freq        ON skill_gaps(frequency DESC);
CREATE INDEX IF NOT EXISTS idx_chat_session     ON chat_history(session_id, created_at);
"""


class Database:
    def __init__(self):
        self.db_path = get_settings().db_path
        self._init()
        logger.info(f"DB ready: {self.db_path}")

    def _init(self):
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _j(self, val) -> str:
        """Serialize to JSON string."""
        if isinstance(val, str):
            return val
        return json.dumps(val or [])

    def _d(self, val, default=None):
        """Deserialize JSON string."""
        if not val:
            return default
        try:
            return json.loads(val)
        except Exception:
            return default

    # ── JOBS ────────────────────────────────────────────────

    def upsert_job(self, job: dict) -> Optional[int]:
        try:
            with self._conn() as c:
                ex = c.execute(
                    "SELECT id FROM jobs WHERE external_id=?", (job.get("external_id"),)
                ).fetchone()
                if ex:
                    c.execute(
                        "UPDATE jobs SET is_active=1, scraped_at=CURRENT_TIMESTAMP WHERE id=?",
                        (ex["id"],)
                    )
                    return ex["id"]
                cur = c.execute("""
                    INSERT INTO jobs (external_id,title,company,company_type,location,
                        work_mode,salary_min_lpa,salary_max_lpa,experience_min,
                        experience_max,description,skills_required,apply_url,source)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    job.get("external_id"), job.get("title",""), job.get("company",""),
                    job.get("company_type","unknown"), job.get("location",""),
                    job.get("work_mode","onsite"), job.get("salary_min_lpa"),
                    job.get("salary_max_lpa"), job.get("experience_min",0),
                    job.get("experience_max",2), job.get("description",""),
                    self._j(job.get("skills_required",[])), job.get("apply_url",""),
                    job.get("source","")
                ))
                return cur.lastrowid
        except Exception as e:
            logger.error(f"upsert_job: {e}")
            return None

    def get_unmatched_jobs(self, limit: int = 200) -> List[dict]:
        with self._conn() as c:
            rows = c.execute("""
                SELECT j.* FROM jobs j
                LEFT JOIN job_matches m ON j.id=m.job_id
                WHERE m.id IS NULL AND j.is_active=1
                ORDER BY j.scraped_at DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_job_by_id(self, job_id: int) -> Optional[dict]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return dict(r) if r else None

    def get_all_jobs(self) -> List[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM jobs WHERE is_active=1").fetchall()
            return [dict(r) for r in rows]

    def get_top_matches(self, limit: int = 20, min_score: float = 0.50,
                         work_mode: str = None, company_type: str = None) -> List[dict]:
        query = """
            SELECT j.*, m.embed_score, m.llm_score, m.final_score,
                   m.match_reasons, m.skill_overlap, m.skill_gaps, m.llm_reasoning
            FROM job_matches m JOIN jobs j ON m.job_id=j.id
            WHERE m.final_score>=? AND j.is_active=1
        """
        params = [min_score]
        if work_mode:
            query += " AND j.work_mode=?"
            params.append(work_mode)
        if company_type:
            query += " AND j.company_type=?"
            params.append(company_type)
        query += " ORDER BY m.final_score DESC LIMIT ?"
        params.append(limit)

        with self._conn() as c:
            rows = c.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            for k in ["match_reasons","skill_overlap","skill_gaps","skills_required"]:
                d[k] = self._d(d.get(k), [])
            results.append(d)
        return results

    def save_match(self, match: dict) -> Optional[int]:
        try:
            with self._conn() as c:
                cur = c.execute("""
                    INSERT OR REPLACE INTO job_matches
                    (job_id,embed_score,llm_score,final_score,match_reasons,
                     skill_overlap,skill_gaps,llm_reasoning)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (
                    match["job_id"], match.get("embed_score",0),
                    match.get("llm_score"), match.get("final_score",0),
                    self._j(match.get("match_reasons",[])),
                    self._j(match.get("skill_overlap",[])),
                    self._j(match.get("skill_gaps",[])),
                    match.get("llm_reasoning",""),
                ))
                return cur.lastrowid
        except Exception as e:
            logger.error(f"save_match: {e}")
            return None

    # ── RESUME ──────────────────────────────────────────────

    def save_resume(self, data: dict) -> int:
        with self._conn() as c:
            c.execute("UPDATE resume_versions SET is_active=0")
            v = (c.execute("SELECT MAX(version) as v FROM resume_versions").fetchone()["v"] or 0) + 1
            cur = c.execute("""
                INSERT INTO resume_versions (version,filename,raw_text,skills,tech_stack,
                    experience_years,education,industry_tags,projects,certifications,
                    summary,target_roles,strengths)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                v, data.get("filename","resume"),
                data.get("raw_text",""), self._j(data.get("skills",[])),
                self._j(data.get("tech_stack",[])), data.get("experience_years",0),
                self._j(data.get("education",{})), self._j(data.get("industry_tags",[])),
                self._j(data.get("projects",[])), self._j(data.get("certifications",[])),
                data.get("summary",""), self._j(data.get("target_roles",[])),
                self._j(data.get("strengths",[])),
            ))
            return cur.lastrowid

    def get_active_resume(self) -> Optional[dict]:
        with self._conn() as c:
            r = c.execute(
                "SELECT * FROM resume_versions WHERE is_active=1 ORDER BY version DESC LIMIT 1"
            ).fetchone()
            if not r:
                return None
            d = dict(r)
            for k in ["skills","tech_stack","industry_tags","projects",
                       "certifications","target_roles","strengths"]:
                d[k] = self._d(d.get(k), [])
            d["education"] = self._d(d.get("education"), {})
            return d

    # ── SKILL GAPS ──────────────────────────────────────────

    def bump_skill(self, skill: str, level: str = "none", category: str = "general"):
        with self._conn() as c:
            ex = c.execute("SELECT id FROM skill_gaps WHERE skill_name=?", (skill,)).fetchone()
            if ex:
                c.execute(
                    "UPDATE skill_gaps SET frequency=frequency+1, last_seen=CURRENT_TIMESTAMP WHERE id=?",
                    (ex["id"],)
                )
            else:
                c.execute(
                    "INSERT INTO skill_gaps (skill_name,our_level,category) VALUES (?,?,?)",
                    (skill, level, category)
                )

    def get_skill_gaps(self, limit: int = 15) -> List[dict]:
        with self._conn() as c:
            rows = c.execute("""
                SELECT * FROM skill_gaps WHERE our_level IN ('none','basic')
                ORDER BY frequency DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ── PREFERENCES ─────────────────────────────────────────

    def set_pref(self, key: str, value):
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO preferences (key,value,updated_at) VALUES (?,?,CURRENT_TIMESTAMP)",
                (key, json.dumps(value))
            )

    def get_pref(self, key: str, default=None):
        with self._conn() as c:
            r = c.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
            return self._d(r["value"] if r else None, default)

    def get_all_prefs(self) -> dict:
        with self._conn() as c:
            rows = c.execute("SELECT key, value FROM preferences").fetchall()
            return {r["key"]: self._d(r["value"]) for r in rows}

    # ── CHAT HISTORY ────────────────────────────────────────

    def save_message(self, session_id: str, role: str, content: str, tool_call: str = ""):
        with self._conn() as c:
            c.execute(
                "INSERT INTO chat_history (session_id,role,content,tool_call) VALUES (?,?,?,?)",
                (session_id, role, content, tool_call)
            )

    def get_history(self, session_id: str, limit: int = 20) -> List[dict]:
        with self._conn() as c:
            rows = c.execute("""
                SELECT role,content,tool_call,created_at FROM chat_history
                WHERE session_id=? ORDER BY created_at DESC LIMIT ?
            """, (session_id, limit)).fetchall()
            return [dict(r) for r in reversed(rows)]

    # ── LINKEDIN POSTS ───────────────────────────────────────

    def save_post(self, post: dict) -> int:
        with self._conn() as c:
            cur = c.execute("""
                INSERT INTO linkedin_posts (post_type,target_role,topic,content,
                    hook,hashtags,engagement_pred)
                VALUES (?,?,?,?,?,?,?)
            """, (
                post.get("post_type",""), post.get("target_role",""),
                post.get("topic",""), post.get("content",""),
                post.get("hook",""), self._j(post.get("hashtags",[])),
                post.get("engagement","medium"),
            ))
            return cur.lastrowid

    def get_recent_posts(self, limit: int = 5) -> List[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM linkedin_posts ORDER BY generated_at DESC LIMIT ?", (limit,)
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["hashtags"] = self._d(d.get("hashtags"), [])
                result.append(d)
            return result

    # ── AGENT DECISIONS ─────────────────────────────────────

    def log_decision(self, action: str, reasoning: str = "", status: str = "success",
                      duration: float = 0, output: dict = None, error: str = ""):
        with self._conn() as c:
            c.execute("""
                INSERT INTO agent_decisions (action,reasoning,status,duration_secs,output,error_msg)
                VALUES (?,?,?,?,?,?)
            """, (action, reasoning, status, duration, json.dumps(output or {}), error))

    # ── REPORTS ─────────────────────────────────────────────

    def save_report(self, report: dict):
        with self._conn() as c:
            c.execute("""
                INSERT OR REPLACE INTO daily_reports
                (report_date,total_scraped,total_matched,avg_score,
                 top_job_ids,top_skill_gaps,report_markdown)
                VALUES (?,?,?,?,?,?,?)
            """, (
                report.get("date", datetime.now().strftime("%Y-%m-%d")),
                report.get("total_scraped",0), report.get("total_matched",0),
                report.get("avg_score",0), self._j(report.get("top_job_ids",[])),
                self._j(report.get("top_skill_gaps",[])), report.get("markdown",""),
            ))

    # ── STATS ────────────────────────────────────────────────

    def get_stats(self) -> dict:
        with self._conn() as c:
            return {
                "total_jobs":    c.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1").fetchone()[0],
                "total_matched": c.execute("SELECT COUNT(*) FROM job_matches").fetchone()[0],
                "avg_score":     c.execute("SELECT AVG(final_score) FROM job_matches").fetchone()[0] or 0,
                "total_posts":   c.execute("SELECT COUNT(*) FROM linkedin_posts").fetchone()[0],
                "top_gaps":      [r[0] for r in c.execute(
                    "SELECT skill_name FROM skill_gaps ORDER BY frequency DESC LIMIT 5"
                ).fetchall()],
                "agent_paused":  self.get_pref("agent_paused", False),
                "last_scrape":   self.get_pref("last_scrape_time", None),
            }

    def cleanup(self, days: int = 30):
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with self._conn() as c:
            c.execute("UPDATE jobs SET is_active=0 WHERE scraped_at<?", (cutoff,))
