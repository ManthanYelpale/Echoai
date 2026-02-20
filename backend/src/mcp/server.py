"""
src/mcp/server.py
MCP (Model Context Protocol) server for Echo.
Exposes career agent tools to any MCP-compatible client (Claude Desktop, etc.)
"""
import json
import asyncio
import sys
from datetime import datetime
from src.agent.memory.database import Database
from src.agent.tools.job_matcher import JobMatcher
from src.agent.tools.resume_analyzer import ResumeAnalyzer
from src.agent.tools.linkedin_generator import LinkedInGenerator
from src.agent.scrapers.job_scraper import ScraperOrchestrator
from src.agent.brain.logger import get_logger

logger = get_logger("mcp")

# MCP Tool definitions
TOOLS = [
    {
        "name": "get_top_jobs",
        "description": "Get top job matches from the career database",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10, "description": "Number of jobs to return"},
                "work_mode": {"type": "string", "enum": ["remote","hybrid","onsite"], "description": "Filter by work mode"},
                "company_type": {"type": "string", "enum": ["startup","mnc","mid_size"], "description": "Filter by company type"},
                "min_score": {"type": "number", "default": 0.55, "description": "Minimum match score"}
            }
        }
    },
    {
        "name": "explain_job_match",
        "description": "Explain why a specific job matches the candidate's profile",
        "inputSchema": {
            "type": "object",
            "required": ["job_id"],
            "properties": {
                "job_id": {"type": "integer", "description": "Job ID from the database"}
            }
        }
    },
    {
        "name": "get_skill_gaps",
        "description": "Analyze skill gaps between candidate's profile and job market",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10}
            }
        }
    },
    {
        "name": "generate_linkedin_post",
        "description": "Generate a LinkedIn post for job searching",
        "inputSchema": {
            "type": "object",
            "properties": {
                "post_type": {
                    "type": "string",
                    "enum": ["open_to_work","skill_spotlight","learning_update","achievement_story","recruiter_magnet"],
                    "default": "open_to_work"
                },
                "target_role": {"type": "string", "description": "Target role for the post"},
                "topic": {"type": "string", "description": "Specific skill or topic to highlight"}
            }
        }
    },
    {
        "name": "scrape_jobs",
        "description": "Start job scraping from all configured sources",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "run_matching",
        "description": "Run the job matching algorithm against the current resume",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_agent_stats",
        "description": "Get statistics about the career agent's activity",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_resume",
        "description": "Get the current candidate resume profile",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "set_preference",
        "description": "Update agent preference (target roles, locations, etc.)",
        "inputSchema": {
            "type": "object",
            "required": ["key", "value"],
            "properties": {
                "key": {"type": "string", "description": "Preference key (e.g. target_roles, target_locations)"},
                "value": {"description": "Value to set"}
            }
        }
    },
]


class EchoMCPServer:
    """MCP server that exposes Echo's tools via stdio JSON-RPC."""

    def __init__(self):
        self.db = Database()
        self.matcher = JobMatcher()
        self.analyzer = ResumeAnalyzer()
        self.post_gen = LinkedInGenerator()
        self.scraper = ScraperOrchestrator()

    async def handle_request(self, request: dict) -> dict:
        method = request.get("method","")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "echo-career-agent", "version": "1.0.0"}
                }
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"tools": TOOLS}
            }

        elif method == "tools/call":
            tool_name = params.get("name","")
            tool_input = params.get("arguments", {})
            result = await self._call_tool(tool_name, tool_input)
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                }
            }

        return {
            "jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }

    async def _call_tool(self, name: str, args: dict) -> dict:
        """Dispatch tool calls to agent functions."""
        try:
            if name == "get_top_jobs":
                jobs = self.db.get_top_matches(
                    limit=args.get("limit", 10),
                    min_score=args.get("min_score", 0.55),
                    work_mode=args.get("work_mode"),
                    company_type=args.get("company_type"),
                )
                return {"jobs": jobs, "count": len(jobs)}

            elif name == "explain_job_match":
                explanation = await self.matcher.explain(args["job_id"])
                return {"explanation": explanation}

            elif name == "get_skill_gaps":
                gaps = self.db.get_skill_gaps(args.get("limit", 10))
                report = await self.analyzer.get_gap_report()
                return {"gaps": gaps, "report": report}

            elif name == "generate_linkedin_post":
                post = await self.post_gen.generate(
                    post_type=args.get("post_type","open_to_work"),
                    target_role=args.get("target_role"),
                    topic=args.get("topic"),
                )
                return post

            elif name == "scrape_jobs":
                result = await self.scraper.run_all()
                return result

            elif name == "run_matching":
                result = await self.matcher.run()
                return result

            elif name == "get_agent_stats":
                return self.db.get_stats()

            elif name == "get_resume":
                resume = self.db.get_active_resume()
                return resume or {"error": "No resume uploaded"}

            elif name == "set_preference":
                self.db.set_pref(args["key"], args["value"])
                return {"success": True, "key": args["key"], "value": args["value"]}

            else:
                return {"error": f"Unknown tool: {name}"}

        except Exception as e:
            logger.error(f"Tool {name} error: {e}")
            return {"error": str(e)}

    async def run_stdio(self):
        """Run MCP server over stdio (JSON-RPC 2.0)."""
        logger.info("Echo MCP Server starting on stdio...")
        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                request = json.loads(line.strip())
                response = await self.handle_request(request)
                print(json.dumps(response), flush=True)
            except json.JSONDecodeError as e:
                error = {"jsonrpc":"2.0","id":None,"error":{"code":-32700,"message":str(e)}}
                print(json.dumps(error), flush=True)
            except Exception as e:
                logger.error(f"MCP error: {e}")


async def main():
    server = EchoMCPServer()
    await server.run_stdio()

if __name__ == "__main__":
    asyncio.run(main())
