"""Asynchronous Memory Consolidation Worker for CareRoute.

Runs expensive clinical memory synthesis, relationship extraction, and long-term
Firestore indexing in background async tasks to ensure sub-second UI response latency.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional
from careroute.memory.firestore_store import session_store
from careroute.memory.knowledge_graph import knowledge_graph
from careroute.memory.personalization import personalization_memory
from careroute.observability.logger import logger
from careroute.observability.tracing import tracer


class AsyncMemoryConsolidator:
    """Dispatches and coordinates background memory synthesis tasks."""

    def __init__(self) -> None:
        self._background_tasks: List[asyncio.Task] = []

    def schedule_session_consolidation(
        self,
        session_id: str,
        patient_id: str,
        recent_interactions: List[Dict[str, Any]],
    ) -> asyncio.Task:
        """Schedules non-blocking async task to synthesize and persist memory in the background."""
        task = asyncio.create_task(
            self._consolidate_memory_task(session_id, patient_id, recent_interactions)
        )
        self._background_tasks.append(task)
        logger.info(
            f"Scheduled async memory consolidation task for patient {patient_id}",
            extra={"session_id": session_id, "patient_id": patient_id}
        )
        return task

    async def _consolidate_memory_task(
        self,
        session_id: str,
        patient_id: str,
        interactions: List[Dict[str, Any]],
    ) -> None:
        """Background coroutine performing deep entity graph consolidation."""
        try:
            with tracer.span("AsyncMemoryConsolidation", {"patient_id": patient_id, "session_id": session_id}):
                from google import genai
                from google.genai import types
                from careroute.config import settings
                import json

                api_key = settings.gemini_api_key
                if api_key and api_key != "mock-gemini-key":
                    client = genai.Client(api_key=api_key)
                else:
                    client = genai.Client(
                        vertexai=True,
                        project=settings.gcp_project_id,
                        location=settings.gcp_location
                    )
                
                # Format interactions for LLM
                transcript = "\n".join([f"{item.get('role')}: {item.get('content')}" for item in interactions])
                
                prompt = f"""
Analyze the following conversation transcript for a patient.
Identify any behavioral adherence signals, traits, or preferences that could impact their care plan (e.g. forgetfulness, morning routine preferences, financial concerns).
Output a JSON array of strings containing the identified behavioral traits. If none, output an empty array [].

Transcript:
{transcript}
"""
                response = await client.aio.models.generate_content(
                    model=settings.flash_model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.0
                    )
                )
                
                traits = json.loads(response.text)
                patient_node_id = f"PATIENT:{patient_id}"

                if isinstance(traits, list):
                    for trait in traits:
                        personalization_memory.add_behavioral_trait(patient_id, trait)
                        # Sanitize trait for node ID
                        clean_id = "".join(c if c.isalnum() else "_" for c in trait[:15]).lower()
                        trait_node_id = f"BEHAVIOR:{clean_id}"
                        knowledge_graph.add_entity(trait_node_id, "BEHAVIOR", trait)
                        knowledge_graph.add_relation(patient_node_id, trait_node_id, "EXHIBITS_BEHAVIOR")

                # Persist updated state to Firestore
                profile = personalization_memory.get_profile(patient_id)
                session_store.append_turn(
                    session_id=session_id,
                    role="system",
                    content=f"Async memory consolidation completed for patient {patient_id}.",
                    metadata={"traits_count": len(profile.behavioral_traits)}
                )

                logger.info(
                    f"Background memory consolidation completed successfully for patient {patient_id}",
                    extra={"session_id": session_id, "patient_id": patient_id}
                )
        except Exception as exc:
            logger.error(
                f"Async memory consolidation failed for patient {patient_id}: {exc}",
                extra={"session_id": session_id, "error": str(exc)}
            )


# Singleton instance
async_consolidator = AsyncMemoryConsolidator()

