"""
src/agent/brain/ollama_client.py
Dynamic Ollama client — model, URL, params all from .env
Handles: chat, generate, embeddings, model listing
"""
from __future__ import annotations
import json
import re
from typing import AsyncGenerator, Optional
import httpx
from config.settings import get_settings
from src.agent.brain.logger import get_logger

logger = get_logger("ollama_client")


class OllamaClient:
    """
    Async Ollama client.
    All config loaded from environment — no hardcoding.
    """

    def __init__(self):
        s = get_settings()
        self.base_url = s.ollama_base_url
        self.model = s.ollama_model
        self.embed_model = s.ollama_embed_model
        self.temperature = s.ollama_temperature
        self.max_tokens = s.ollama_max_tokens
        self.timeout = s.ollama_timeout

    async def is_available(self) -> bool:
        """Check if Ollama is running."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """Return list of locally available model names."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    return [m.get("name", "") for m in models]
        except Exception as e:
            logger.warning(f"Could not list Ollama models: {e}")
        return []

    async def generate(self, prompt: str, system: str = "", temperature: float = None) -> str:
        """Non-streaming text generation."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature or self.temperature,
                "num_predict": self.max_tokens,
            }
        }
        if system:
            payload["system"] = system

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                )
                if resp.status_code == 200:
                    return resp.json().get("response", "").strip()
        except Exception as e:
            logger.error(f"Ollama generate failed: {e}")
        return ""

    async def chat(self, messages: list[dict], system: str = "") -> str:
        """Chat-style generation (multi-turn)."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            }
        }
        if system:
            payload["system"] = system

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                )
                if resp.status_code == 200:
                    return resp.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"Ollama chat failed: {e}")
        return ""

    async def stream_chat(self, messages: list[dict], system: str = "") -> AsyncGenerator[str, None]:
        """Streaming chat — yields chunks for real-time UI updates."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": self.temperature},
        }
        if system:
            payload["system"] = system

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/chat", json=payload
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line.strip():
                            try:
                                data = json.loads(line)
                                chunk = data.get("message", {}).get("content", "")
                                if chunk:
                                    yield chunk
                                if data.get("done"):
                                    break
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error(f"Ollama stream failed: {e}")
            yield ""

    async def embed(self, text: str) -> list[float]:
        """Generate embedding vector for text using Ollama embed model."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.embed_model, "prompt": text}
                )
                if resp.status_code == 200:
                    return resp.json().get("embedding", [])
        except Exception as e:
            logger.error(f"Ollama embed failed: {e}")
        return []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch embedding — sequential calls to Ollama."""
        results = []
        for text in texts:
            emb = await self.embed(text)
            results.append(emb)
        return results

    async def extract_json(self, prompt: str, system: str = "") -> Optional[dict]:
        """Generate and parse JSON from LLM response. Handles truncated output."""
        full_system = (system or "") + "\nYou MUST respond with valid JSON only. No markdown, no explanation."
        response = await self.generate(prompt, system=full_system)
        if not response:
            return None

        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?", "", response).strip().rstrip("`").strip()

        # Try direct parse first
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Try extracting the outermost JSON object
        start = cleaned.find("{")
        if start != -1:
            candidate = cleaned[start:]
            # Try as-is
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
            # Try repairing truncated JSON by closing open brackets
            repaired = candidate
            open_braces = repaired.count("{") - repaired.count("}")
            open_brackets = repaired.count("[") - repaired.count("]")
            # Close any open string (remove trailing incomplete value)
            repaired = re.sub(r',\s*"[^"]*$', "", repaired)
            repaired = re.sub(r',\s*\w+$', "", repaired)
            repaired += "]" * max(0, open_brackets) + "}" * max(0, open_braces)
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass

        logger.warning(f"Could not parse JSON from LLM response: {response[:200]}")
        return None


    async def auto_select_model(self) -> str:
        """
        Dynamically select best available model.
        Preference order: llama3.2 > mistral > phi3 > gemma2 > first available
        """
        available = await self.list_models()
        preference = ["llama3.2", "mistral", "phi3", "gemma2", "llama2", "tinyllama"]

        for pref in preference:
            for model in available:
                if pref in model.lower():
                    logger.info(f"Auto-selected model: {model}")
                    self.model = model
                    return model

        if available:
            self.model = available[0]
            logger.info(f"Using first available model: {available[0]}")
            return available[0]

        logger.warning("No Ollama models found. Install with: ollama pull llama3.2")
        return self.model
