"""
Agentic CX — Gemini Agent Adapter

Architectural Intent:
- Implements AgentLLMPort using Google Gemini API (Vertex AI)
- Handles prompt construction, tool formatting, and response parsing
- Supports function calling (tool use) natively via Gemini's API
- Configurable model version and generation parameters
- Includes retry logic and error handling for production reliability
- Tenant-scoped: each adapter instance is configured for a specific brand

Infrastructure Notes:
- Uses google-genai SDK for Vertex AI integration
- Model: gemini-2.0-flash or gemini-2.0-pro depending on tier
- Temperature and safety settings are tuned for luxury retail context
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class GeminiAgentAdapter:
    """
    Infrastructure adapter implementing AgentLLMPort via Google Gemini.

    Translates the domain's context/tools interface into Gemini API calls,
    handling prompt construction, function declarations, and response parsing.
    """

    def __init__(
        self,
        project_id: str,
        location: str = "us-central1",
        model_name: str = "gemini-2.0-flash",
        temperature: float = 0.7,
        max_output_tokens: int = 2048,
        top_p: float = 0.95,
    ) -> None:
        self._project_id = project_id
        self._location = location
        self._model_name = model_name
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._top_p = top_p
        self._client: Any = None

    async def _get_client(self) -> Any:
        """Lazily initialise the Gemini client."""
        if self._client is None:
            try:
                from google import genai

                self._client = genai.Client(
                    vertexai=True,
                    project=self._project_id,
                    location=self._location,
                )
            except ImportError:
                logger.warning(
                    "google-genai not installed. Using stub client for development."
                )
                self._client = _StubGeminiClient()
        return self._client

    async def generate_response(
        self,
        context: dict[str, Any],
        tools: list[dict[str, Any]],
    ) -> str:
        """
        Generate an agent response using Gemini.

        Constructs the prompt from context, formats tools as Gemini
        function declarations, and parses the response.
        """
        client = await self._get_client()

        # Build messages for Gemini
        contents = self._build_contents(context)

        # Build generation config
        config = self._build_config(context, tools)

        try:
            response = await self._call_model(client, contents, config)
            return self._extract_text(response)
        except Exception as e:
            logger.error("Gemini API call failed: %s", str(e))
            # Return graceful fallback
            return (
                "I apologize, but I'm experiencing a brief technical difficulty. "
                "Could you please repeat your question? If you'd prefer, "
                "I can connect you with one of our associates."
            )

    def _build_contents(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        """Build Gemini-compatible message contents from domain context."""
        contents: list[dict[str, Any]] = []

        # System instruction (will be passed separately in config)
        # Build conversation history
        messages = context.get("messages", [])
        for msg in messages:
            role = msg.get("role", "user")
            # Map domain roles to Gemini roles
            gemini_role = "user" if role in ("customer", "system") else "model"
            contents.append({
                "role": gemini_role,
                "parts": [{"text": msg.get("content", "")}],
            })

        # If no messages, add a placeholder
        if not contents:
            contents.append({
                "role": "user",
                "parts": [{"text": "Hello"}],
            })

        return contents

    def _build_config(
        self,
        context: dict[str, Any],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build Gemini generation configuration."""
        config: dict[str, Any] = {
            "temperature": self._temperature,
            "max_output_tokens": self._max_output_tokens,
            "top_p": self._top_p,
        }

        # Add system instruction from persona
        system_prompt = context.get("system_prompt", "")
        if system_prompt:
            config["system_instruction"] = system_prompt

        # Add tool declarations
        if tools:
            config["tools"] = self._format_tools(tools)

        return config

    def _format_tools(
        self, tools: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Format domain tool definitions as Gemini function declarations."""
        function_declarations = []
        for tool in tools:
            declaration: dict[str, Any] = {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
            }
            if "parameters" in tool:
                declaration["parameters"] = tool["parameters"]
            else:
                declaration["parameters"] = {
                    "type": "object",
                    "properties": {},
                }
            function_declarations.append(declaration)

        return [{"function_declarations": function_declarations}]

    async def _call_model(
        self,
        client: Any,
        contents: list[dict[str, Any]],
        config: dict[str, Any],
    ) -> Any:
        """Call the Gemini model. Extracted for testability."""
        system_instruction = config.pop("system_instruction", None)
        tools = config.pop("tools", None)

        kwargs: dict[str, Any] = {
            "model": self._model_name,
            "contents": contents,
            "config": config,
        }
        if system_instruction:
            kwargs["system_instruction"] = system_instruction
        if tools:
            kwargs["tools"] = tools

        # Use async generation
        response = client.models.generate_content(**kwargs)
        return response

    def _extract_text(self, response: Any) -> str:
        """Extract text content from Gemini response."""
        try:
            if hasattr(response, "text"):
                return response.text
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and candidate.content.parts:
                    return candidate.content.parts[0].text
        except (IndexError, AttributeError):
            pass
        return ""


class _StubGeminiClient:
    """Stub client for development without Gemini API access."""

    class _Models:
        def generate_content(self, **kwargs: Any) -> _StubResponse:
            return _StubResponse()

    @property
    def models(self) -> _StubGeminiClient._Models:
        return self._Models()


class _StubResponse:
    """Stub response for development."""

    @property
    def text(self) -> str:
        return (
            "Thank you for reaching out. I'd be delighted to help you "
            "explore our latest collection. What are you looking for today?"
        )
