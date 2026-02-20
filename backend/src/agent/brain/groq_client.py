import os
import asyncio
from typing import List, Dict, Any, Generator
from groq import Groq, AsyncGroq
# fallback to sentence-transformers since fastembed failed on Windows/Py3.14
from sentence_transformers import SentenceTransformer
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
        
        # Initialize Embeddings (Lazy load)
        # We override the model name to a known good small model for sentence-transformers
        self._embed_model_name = "all-MiniLM-L6-v2" 
        print(f"  🧠 AI Client: Groq ({self.model}) + SentenceTransformers (CPU)")

    def get_embed_model(self):
        """Lazy load the embedding model only when needed."""
        if self._embed_model is None:
            print(f"  ⏳ Loading embedding model: {self._embed_model_name}...")
            # This downloads ~80MB once
            self._embed_model = SentenceTransformer(self._embed_model_name)
            print("  ✅ Embedding model loaded.")
        return self._embed_model

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

    async def embed(self, text: str) -> List[float]:
        """Generate embedding using SentenceTransformer (CPU)."""
        model = self.get_embed_model()
        # encode returns numpy array, convert to list
        params = {"convert_to_numpy": True, "show_progress_bar": False}
        return model.encode(text, **params).tolist()

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        model = self.get_embed_model()
        params = {"convert_to_numpy": True, "show_progress_bar": False}
        return model.encode(texts, **params).tolist()
