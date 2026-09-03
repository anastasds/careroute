"""Persistent Session and Conversation Store using Google ADK and Firestore.

Provides persistent multi-turn history, clinical state management, and audit logging
using ADK session/memory services with robust fallback caching.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from careroute.core.adk_config import adk_session_service, adk_memory_service

logger = logging.getLogger("careroute.storage")

class CareRouteADKStore:
    """Persistent storage adapter supporting ADK Vertex AI Services and Firestore."""

    def __init__(self):
        self.session_service = adk_session_service
        self.memory_service = adk_memory_service
        self._local_turns: Dict[str, List[Dict[str, Any]]] = {}
        self._local_plans: Dict[str, Dict[str, Any]] = {}
        self._firestore_db = None
        self._init_firestore()

    def _init_firestore(self) -> None:
        """Initializes Firestore client if GCP project is configured."""
        try:
            from google.cloud import firestore
            self._firestore_db = firestore.Client()
            logger.info("Connected to Google Cloud Firestore.")
        except Exception as e:
            logger.debug(f"Firestore client not initialized (using in-memory cache): {e}")

    async def append_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Appends a conversational turn to the session log."""
        turn = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }
        if session_id not in self._local_turns:
            self._local_turns[session_id] = []
        self._local_turns[session_id].append(turn)

        if self._firestore_db:
            try:
                self._firestore_db.collection("sessions").document(session_id).collection("turns").add(turn)
            except Exception as e:
                logger.warning(f"Failed to persist turn to Firestore: {e}")

    async def get_session_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves past turns for the given session with fallback to local cache."""
        # 1. Attempt retrieval from Vertex AI Session Service with correct keyword arguments
        try:
            user_id = session_id.split("___")[-1] if "___" in session_id else "default-user"
            session = await self.session_service.get_session(
                app_name="coordinator",
                user_id=user_id,
                session_id=session_id
            )
            if session and session.events:
                return [
                    {
                        "role": e.author,
                        "content": e.content.parts[0].text if e.content and e.content.parts else ""
                    }
                    for e in session.events[-limit:]
                ]
        except Exception as e:
            logger.debug(f"ADK session service lookup returned no events: {e}")

        # 2. Check Firestore
        if self._firestore_db:
            try:
                docs = (
                    self._firestore_db.collection("sessions")
                    .document(session_id)
                    .collection("turns")
                    .order_by("timestamp")
                    .limit(limit)
                    .stream()
                )
                turns = [d.to_dict() for d in docs]
                if turns:
                    return turns
            except Exception as e:
                logger.debug(f"Firestore session lookup fallback: {e}")

        # 3. Fallback to local in-memory turns
        return self._local_turns.get(session_id, [])[-limit:]

    async def save_care_plan(self, patient_id: str, care_plan_dict: Dict[str, Any]) -> None:
        """Persists the finalized patient care plan."""
        self._local_plans[patient_id] = care_plan_dict

        if self._firestore_db:
            try:
                self._firestore_db.collection("care_plans").document(patient_id).set(care_plan_dict)
                logger.info(f"Persisted care plan for patient {patient_id} to Firestore.")
            except Exception as e:
                logger.warning(f"Failed to persist care plan to Firestore: {e}")

    async def get_care_plan(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a stored care plan for a patient."""
        # 1. Check local cache
        if patient_id in self._local_plans:
            return self._local_plans[patient_id]

        # 2. Check Firestore
        if self._firestore_db:
            try:
                doc = self._firestore_db.collection("care_plans").document(patient_id).get()
                if doc.exists:
                    return doc.to_dict()
            except Exception as e:
                logger.debug(f"Firestore care plan lookup failed: {e}")

        return None


# Singleton instance
session_store = CareRouteADKStore()
