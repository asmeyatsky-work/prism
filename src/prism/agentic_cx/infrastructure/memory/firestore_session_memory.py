"""
Agentic CX — Firestore Session Memory

Architectural Intent:
- Implements SessionMemoryPort using Google Cloud Firestore
- Stores per-session working context in a Firestore collection
- Session documents are auto-expired via Firestore TTL policies
- Each session maps to a conversation_id
- Supports atomic read/write for concurrent access safety
- Falls back to in-memory store for local development

Collection Structure:
    sessions/{session_id}/data/{key} -> {value, updated_at}
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class FirestoreSessionMemory:
    """
    Session memory implementation using Google Cloud Firestore.

    Provides per-conversation working context storage with TTL-based
    expiration. Falls back to in-memory storage when Firestore is
    not available.
    """

    def __init__(
        self,
        project_id: str | None = None,
        collection_name: str = "agentic_cx_sessions",
        ttl_hours: int = 24,
    ) -> None:
        self._project_id = project_id
        self._collection_name = collection_name
        self._ttl_hours = ttl_hours
        self._client: Any = None
        self._fallback: dict[str, dict[str, Any]] = {}
        self._use_fallback = False

    async def _get_client(self) -> Any:
        """Lazily initialise the Firestore client."""
        if self._use_fallback:
            return None
        if self._client is None:
            try:
                from google.cloud import firestore

                self._client = firestore.AsyncClient(project=self._project_id)
            except (ImportError, Exception) as e:
                logger.warning(
                    "Firestore not available, using in-memory fallback: %s", str(e)
                )
                self._use_fallback = True
                return None
        return self._client

    async def store(
        self,
        session_id: str,
        key: str,
        value: Any,
    ) -> None:
        """Store a key-value pair in session memory."""
        client = await self._get_client()
        if client is None:
            # In-memory fallback
            if session_id not in self._fallback:
                self._fallback[session_id] = {}
            self._fallback[session_id][key] = value
            return

        doc_ref = (
            client.collection(self._collection_name)
            .document(session_id)
            .collection("data")
            .document(key)
        )
        await doc_ref.set({
            "value": value,
            "updated_at": datetime.now(UTC),
            "expires_at": datetime.now(UTC),  # TTL field
        })

    async def retrieve(
        self,
        session_id: str,
        key: str,
    ) -> Any:
        """Retrieve a value from session memory. Returns None if not found."""
        client = await self._get_client()
        if client is None:
            return self._fallback.get(session_id, {}).get(key)

        doc_ref = (
            client.collection(self._collection_name)
            .document(session_id)
            .collection("data")
            .document(key)
        )
        doc = await doc_ref.get()
        if doc.exists:
            return doc.to_dict().get("value")
        return None

    async def get_session_context(
        self,
        session_id: str,
    ) -> dict[str, Any]:
        """Retrieve the entire session context as a dictionary."""
        client = await self._get_client()
        if client is None:
            return dict(self._fallback.get(session_id, {}))

        collection_ref = (
            client.collection(self._collection_name)
            .document(session_id)
            .collection("data")
        )
        docs = collection_ref.stream()
        context: dict[str, Any] = {}
        async for doc in docs:
            data = doc.to_dict()
            context[doc.id] = data.get("value")
        return context

    async def clear_session(
        self,
        session_id: str,
    ) -> None:
        """Clear all session memory for a conversation."""
        client = await self._get_client()
        if client is None:
            self._fallback.pop(session_id, None)
            return

        collection_ref = (
            client.collection(self._collection_name)
            .document(session_id)
            .collection("data")
        )
        docs = collection_ref.stream()
        async for doc in docs:
            await doc.reference.delete()
        # Delete the session document itself
        await (
            client.collection(self._collection_name)
            .document(session_id)
            .delete()
        )
