"""
src/agent/scrapers/job_scraper.py
Multi-source async job scraper — read-only, polite, no auto-apply.
Sources: Naukri, Indeed India, Internshala, Wellfound, Cutshort
All config (delays, retries, roles, locations) from .env + DB preferences.
"""
import hashlib
import random
import re
import asyncio
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from config.settings import get_settings
from src.agent.brain.logger import get_logger
from src.agent.memory.database import Database

logger = get_logger("scraper")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class BaseScraper:
    """Base async scraper with polite request handling."""
    source = "unknown"

    def __init__(self):
        self.db = Database()
        s = get_settings()
        self.delay = s.scrape_delay_seconds
        self.max_retries = s.scrape_max_retries
        self.random_delay = s.scrape_random_delay
        # Get roles/locations from DB preferences (user can change via chat)
        self.roles = self.db.get_pref("target_roles", [
            "AI Engineer", "Python Developer", "Data Analyst",
            "Data Scientist", "ML Engineer"
        ])
        self.locations = self.db.get_pref("target_locations", [
            "Bangalore", "Hyderabad", "Pune", "Chennai", "Gurgaon", "India"
        ])
        self.exp_max = self.db.get_pref("max_experience_years", 2)

    async def _get(self, url: str, params: dict = None) -> Optional[str]:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
            "Connection": "keep-alive",
        }
        for attempt in range(self.max_retries):
            sleep_time = self.delay + (random.uniform(0, 2) if self.random_delay else 0)
            await asyncio.sleep(sleep_time)
            try:
                async with httpx.AsyncClient(
                    headers=headers, timeout=15, follow_redirects=True
                ) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        return resp.text
                    elif resp.status_code == 429:
                        logger.warning(f"Rate limited on {self.source}. Sleeping 30s...")
                        await asyncio.sleep(30)
                    elif resp.status_code in [403, 404]:
                        return None
            except Exception as e:
                logger.debug(f"{self.source} request failed (attempt {attempt+1}): {e}")
        return None

    def _make_id(self, *parts) -> str:
        raw = f"{self.source}:" + ":".join(str(p) for p in parts)
        return hashlib.md5(raw.encode()).hexdigest()[:20]

    def _clean(self, text: str) -> str:
        return re.sub(r'\s+', ' ', text or "").strip()[:4000]

    def _salary_lpa(self, text: str) -> tuple:
        if not text or "not" in text.lower():
            return None, None
        m = re.search(r'(\d+\.?\d*)\s*(?:to|-|–)\s*(\d+\.?\d*)\s*(?:lpa|l|lakh)', text, re.I)
        if m:
            return float(m.group(1)), float(m.group(2))
        m = re.search(r'(\d+\.?\d*)\s*(?:lpa|l|lakh)', text, re.I)
        if m:
            v = float(m.group(1))
            return v, v
        return None, None

    def _work_mode(self, text: str) -> str:
        t = (text or "").lower()
        if "remote" in t:
            return "remote"
        if "hybrid" in t:
            return "hybrid"
        return "onsite"

    def _company_type(self, company: str) -> str:
        # Use LLM preference stored in DB, not hardcoded list
        known_mncs = self.db.get_pref("known_mncs", [
            "tcs", "infosys", "wipro", "accenture", "capgemini", "ibm", "hcl",
            "cognizant", "tech mahindra", "ltimindtree", "deloitte", "ey", "kpmg"
        ])
        c = company.lower()
        if any(m in c for m in known_mncs):
            return "mnc"
        return "startup"

    async def scrape(self) -> list:
        raise NotImplementedError

    def save(self, jobs: list) -> int:
        saved = sum(1 for j in jobs if self.db.upsert_job(j))
        return saved


class NaukriScraper(BaseScraper):
    source = "naukri"
    BASE = "https://www.naukri.com"

    async def scrape(self) -> list:
        jobs = []
        for role in self.roles[:4]:
            for loc in self.locations[:3]:
                role_slug = role.lower().replace(" ", "-")
                loc_slug = loc.lower().replace(" ", "-")
                html = await self._get(f"{self.BASE}/{role_slug}-jobs-in-{loc_slug}")
                if html:
                    jobs.extend(self._parse(html, role))
        logger.info(f"Naukri: {len(jobs)} jobs")
        return jobs

    def _parse(self, html: str, role: str) -> list:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for card in soup.select(".jobTuple, article.jobTuple, .cust-job-tuple")[:12]:
            try:
                title_el = card.select_one(".title, .jobTitle, h2 a")
                title = self._clean(title_el.get_text() if title_el else "")
                company_el = card.select_one(".company-name, .comp-name")
                company = self._clean(company_el.get_text() if company_el else "")
                location_el = card.select_one(".location, .loc, .locWdth")
                location = self._clean(location_el.get_text() if location_el else "")
                link_el = card.select_one("a[href*='/job-listings']")
                if not title or not link_el:
                    continue
                link = link_el.get("href","")
                if link.startswith("/"):
                    link = self.BASE + link
                salary_el = card.select_one(".salary")
                salary = self._clean(salary_el.get_text() if salary_el else "")
                sal_min, sal_max = self._salary_lpa(salary)

                results.append({
                    "external_id": self._make_id(company, title, link),
                    "title": title, "company": company,
                    "company_type": self._company_type(company),
                    "location": location,
                    "work_mode": self._work_mode(location + title),
                    "salary_min_lpa": sal_min, "salary_max_lpa": sal_max,
                    "experience_min": 0, "experience_max": self.exp_max,
                    "description": "", "skills_required": [],
                    "apply_url": link, "source": self.source,
                })
            except Exception:
                continue
        return results


class IndeedScraper(BaseScraper):
    source = "indeed_india"
    BASE = "https://in.indeed.com"

    async def scrape(self) -> list:
        jobs = []
        for role in self.roles[:3]:
            html = await self._get(f"{self.BASE}/jobs", params={
                "q": f"{role} fresher 0-2 years",
                "l": "India",
                "fromage": "7",
                "sort": "date",
            })
            if html:
                jobs.extend(self._parse(html))
        logger.info(f"Indeed India: {len(jobs)} jobs")
        return jobs

    def _parse(self, html: str) -> list:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for card in soup.select(".job_seen_beacon, .tapItem")[:10]:
            try:
                title_el = card.select_one("h2 span, .jobTitle span")
                company_el = card.select_one(".companyName")
                location_el = card.select_one(".companyLocation")
                link_el = card.select_one("a[data-jk], a[href*='/rc/clk']")
                if not title_el or not link_el:
                    continue
                title = self._clean(title_el.get_text())
                company = self._clean(company_el.get_text() if company_el else "")
                location = self._clean(location_el.get_text() if location_el else "India")
                href = link_el.get("href","")
                link = self.BASE + href if href.startswith("/") else href
                results.append({
                    "external_id": self._make_id(company, title, link),
                    "title": title, "company": company,
                    "company_type": self._company_type(company),
                    "location": location,
                    "work_mode": self._work_mode(location + title),
                    "salary_min_lpa": None, "salary_max_lpa": None,
                    "experience_min": 0, "experience_max": self.exp_max,
                    "description": "", "skills_required": [],
                    "apply_url": link, "source": self.source,
                })
            except Exception:
                continue
        return results


class InternshalaJobsScraper(BaseScraper):
    source = "internshala"
    BASE = "https://internshala.com"

    async def scrape(self) -> list:
        jobs = []
        cats = ["computer-science-jobs", "data-science-jobs", "machine-learning-jobs"]
        for cat in cats[:2]:
            html = await self._get(f"{self.BASE}/jobs/{cat}")
            if html:
                jobs.extend(self._parse(html))
        logger.info(f"Internshala: {len(jobs)} jobs")
        return jobs

    def _parse(self, html: str) -> list:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for card in soup.select(".internship_meta, .individual_internship")[:10]:
            try:
                title_el = card.select_one(".profile, .job-title, h3")
                company_el = card.select_one(".company-name, .company_name")
                link_el = card.select_one("a[href*='/job/detail'], a[href*='/jobs/detail']")
                if not title_el:
                    continue
                title = self._clean(title_el.get_text())
                company = self._clean(company_el.get_text() if company_el else "")
                href = link_el.get("href","") if link_el else ""
                link = self.BASE + href if href.startswith("/") else href
                results.append({
                    "external_id": self._make_id(company, title, link),
                    "title": title, "company": company,
                    "company_type": "startup",
                    "location": "India", "work_mode": "hybrid",
                    "salary_min_lpa": None, "salary_max_lpa": None,
                    "experience_min": 0, "experience_max": 1,
                    "description": "", "skills_required": [],
                    "apply_url": link or f"{self.BASE}/jobs",
                    "source": self.source,
                })
            except Exception:
                continue
        return results


class WellfoundScraper(BaseScraper):
    source = "wellfound"
    BASE = "https://wellfound.com"

    async def scrape(self) -> list:
        jobs = []
        paths = [
            "/role/r/software-engineer?job_listing_type=full_time&country=IN",
            "/role/r/data-scientist?job_listing_type=full_time&country=IN",
            "/role/r/machine-learning-engineer?job_listing_type=full_time&country=IN",
        ]
        for path in paths[:2]:
            html = await self._get(self.BASE + path)
            if html:
                jobs.extend(self._parse(html))
        logger.info(f"Wellfound: {len(jobs)} jobs")
        return jobs

    def _parse(self, html: str) -> list:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for card in soup.select("[data-test='JobListing'], .styles_jobListingCard__")[:10]:
            try:
                title_el = card.select_one("h2, h3, [data-test='JobTitle']")
                company_el = card.select_one("[data-test='company-name'], .styles_company__")
                link_el = card.select_one("a[href*='/jobs']")
                if not title_el:
                    continue
                title = self._clean(title_el.get_text())
                company = self._clean(company_el.get_text() if company_el else "")
                href = link_el.get("href","") if link_el else ""
                link = self.BASE + href if href.startswith("/") else href
                results.append({
                    "external_id": self._make_id(company, title, link),
                    "title": title, "company": company,
                    "company_type": "startup",
                    "location": "India", "work_mode": "hybrid",
                    "salary_min_lpa": None, "salary_max_lpa": None,
                    "experience_min": 0, "experience_max": 2,
                    "description": "", "skills_required": [],
                    "apply_url": link or self.BASE,
                    "source": self.source,
                })
            except Exception:
                continue
        return results


class ScraperOrchestrator:
    """Runs all scrapers, saves results, returns summary."""
    SCRAPERS = [NaukriScraper, IndeedScraper, InternshalaJobsScraper, WellfoundScraper]

    def __init__(self):
        self.db = Database()

    async def run_all(self) -> dict:
        results = {"total": 0, "by_source": {}, "errors": []}
        for ScraperClass in self.SCRAPERS:
            name = ScraperClass.source
            try:
                logger.info(f"Running {name}...")
                scraper = ScraperClass()
                jobs = await scraper.scrape()
                saved = scraper.save(jobs)
                results["by_source"][name] = {"scraped": len(jobs), "saved": saved}
                results["total"] += len(jobs)
            except Exception as e:
                results["errors"].append(f"{name}: {e}")
                logger.error(f"Scraper {name} failed: {e}")

        self.db.set_pref("last_scrape_time", __import__('datetime').datetime.now().isoformat())
        logger.info(f"Scraping done: {results['total']} total")
        return results
