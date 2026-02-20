import os
import asyncio
from typing import List, Dict, Any, Generator
from groq import Groq, AsyncGroq
from config.settings import get_settings

class GroqClient:
    _instance = None
    _embed_model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GroqClient, cls).__new__(cls)
            cls._instance._init_client()
        return cls._instance

    def _init_client(self):
        s = get_settings()
        if not s.groq_api_key:
            print("  ⚠️  WARNING: GROQ_API_KEY is missing! AI features will fail.")
        
        # Initialize Groq (Async)
        self.client = AsyncGroq(api_key=s.groq_api_key)
        self.model = s.ai_model
        
        # Initialize Embeddings (FastEmbed - Lighter for Render)
        try:
            from fastembed import TextEmbedding
            # We use a lightweight model by default if not specified
            self._embed_model_name = s.embed_model or "BAAI/bge-small-en-v1.5"
            self.embed_model = TextEmbedding(model_name=self._embed_model_name)
            print(f"  🧠 AI Client: Groq ({self.model}) + FastEmbed ({self._embed_model_name})")
        except ImportError:
            print("  ⚠️  FastEmbed not installed. Embeddings will fail.")
            self.embed_model = None

    async def chat(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = None,
        json_mode: bool = False
    ) -> str:
        """
        Get completion from Groq.
        """
        if not self.client:
            return "Error: Groq client not initialized."

        try:
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature or get_settings().ai_temperature,
                "max_tokens": get_settings().ai_max_tokens,
            }
            if json_mode:
                params["response_format"] = {"type": "json_object"}

            response = await self.client.chat.completions.create(**params)
            return response.choices[0].message.content
        except Exception as e:
            print(f"  ❌ Groq Chat Error: {e}")
            return ""

    async def embed(self, text: str) -> List[float]:
        """
        Generate embedding using FastEmbed (CPU optimized).
        """
        if not self.embed_model:
            return []
            
        try:
            # fastembed returns a generator of numpy arrays/lists
            embeddings = list(self.embed_model.embed([text]))
            if embeddings:
                return embeddings[0].tolist() # Convert numpy/list to standard float list
            return []
        except Exception as e:
            print(f"  ❌ Embedding Error: {e}")
            return []

    async def chat(self, 
                   messages: List[Dict[str, str]], 
                   temperature: float = None,
                   json_mode: bool = False) -> str:
        """Send a chat completion request to Groq."""
        s = get_settings()
        try:
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature or s.ai_temperature,
                "max_tokens": s.ai_max_tokens,
            }
            if json_mode:
                params["response_format"] = {"type": "json_object"}

            response = await self.client.chat.completions.create(**params)
            return response.choices[0].message.content
        except Exception as e:
            print(f"  ❌ Groq Error: {e}")
            return ""

    async def extract_json(self, prompt: str) -> Dict[str, Any]:
        """Extract structured JSON from a prompt using Groq's JSON mode."""
        import json
        try:
            msgs = [{"role": "user", "content": prompt}]
            response_text = await self.chat(msgs, json_mode=True)
            return json.loads(response_text)
        except Exception as e:
            print(f"  ❌ JSON Extraction Error: {e}")
            return {}

    async def stream_chat(self, messages: List[Dict[str, str]], system: str = None) -> Generator[str, None, None]:
        """Stream chat response from Groq."""
        s = get_settings()
        try:
            msgs = []
            if system:
                msgs.append({"role": "system", "content": system})
            msgs.extend(messages)

            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=msgs,
                temperature=s.ai_temperature,
                max_tokens=s.ai_max_tokens,
                stream=True
            )

            async for chunk in stream:
                 content = chunk.choices[0].delta.content
                 if content:
                     yield content

        except Exception as e:
            print(f"  ❌ Groq Stream Error: {e}")
            yield f"[Error: {e}]"

    async def is_available(self) -> bool:
        """Check if Groq is configured and reachable."""
        return self.client.api_key is not None

    async def list_models(self) -> List[Dict[str, Any]]:
        """Return supported models."""
        # Static list since we successfully vetted them
        return [
            {"name": "llama-3.3-70b-versatile", "details": "Llama 3.3 70B (Recommended)"},
            {"name": "llama-3.1-8b-instant", "details": "Llama 3.1 8B (Fast)"},
            {"name": "mixtral-8x7b-32768", "details": "Mixtral 8x7B"},
        ]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts using FastEmbed."""
        if not self.embed_model:
            return []
        try:
            embeddings = list(self.embed_model.embed(texts))
            return [e.tolist() for e in embeddings]
        except Exception as e:
            print(f"  ❌ Batch Embedding Error: {e}")
            return []
