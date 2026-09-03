"""Knowledge Graph + Summarization Compaction Engine for CareRoute.

Eliminates context bloat and token exhaustion by converting verbose multi-turn dialogues
into high-density Knowledge Graph entity-relation triples and structured Clinical State Briefs.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from careroute.memory.knowledge_graph import ClinicalKnowledgeGraph, knowledge_graph
from careroute.memory.personalization import personalization_memory
from careroute.observability.logger import logger
from careroute.observability.tracing import tracer


class KGSummarizationCompactor:
    """Combines Knowledge Graph relation extraction with hierarchical clinical state summarization."""

    def __init__(self, max_uncompacted_turns: int = 6):
        self.max_uncompacted_turns = max_uncompacted_turns

    def compact_history(
        self,
        session_id: str,
        turns: List[Dict[str, Any]],
        patient_id: str,
        kg: Optional[ClinicalKnowledgeGraph] = None,
    ) -> List[Dict[str, Any]]:
        """Compacts older turns into a Knowledge Graph Briefing turn while keeping recent turns intact.
        
        Args:
            session_id: Current session identifier.
            turns: List of raw turn dicts [{'role': 'user'/'assistant', 'content': '...'}].
            patient_id: Identifier of the patient.
            kg: Clinical Knowledge Graph instance.
            
        Returns:
            Compacted list of turns with high-density state summary replacing bloated history.
        """
        if len(turns) <= self.max_uncompacted_turns:
            return turns

        kg = kg or knowledge_graph

        with tracer.span("KGHistoryCompaction", {"session_id": session_id, "patient_id": patient_id}):
            logger.info(
                f"Triggering KG + Summarization Compaction on {len(turns)} turns",
                extra={"session_id": session_id, "original_turn_count": len(turns)}
            )

            # Split into historical turns to compact vs recent turns to preserve verbatim
            turns_to_compact = turns[:-self.max_uncompacted_turns]
            recent_turns = turns[-self.max_uncompacted_turns:]

            # 1. Extract clinical entities from the turns to compact
            extracted_facts = self._extract_entities_and_update_kg(turns_to_compact, patient_id, kg)

            # 2. Retrieve personalized behavioral traits and clinician notes
            profile_context = personalization_memory.format_context_for_agent(patient_id)

            # 3. Formulate structured Clinical State Briefing
            graph_summary = kg.get_patient_graph_summary(patient_id)
            relations_count = len(graph_summary.get("relations", []))

            briefing_content = (
                "=== COMPACTED CLINICAL STATE BRIEF (KNOWLEDGE GRAPH + SUMMARY) ===\n"
                f"Patient ID: {patient_id}\n"
                f"Extracted Diagnoses: {', '.join(extracted_facts.get('diagnoses', ['None identified']))}\n"
                f"Active Medications: {', '.join(extracted_facts.get('medications', ['None identified']))}\n"
                f"Known Allergies: {', '.join(extracted_facts.get('allergies', ['None identified']))}\n"
                f"Knowledge Graph Relations Linked: {relations_count} triples\n"
                f"{profile_context}\n"
                "=================================================================="
            )

            compacted_turn = {
                "role": "system",
                "content": briefing_content,
                "metadata": {
                    "is_compacted_brief": True,
                    "compacted_turns_count": len(turns_to_compact),
                    "extracted_facts": extracted_facts,
                }
            }

            compacted_history = [compacted_turn] + recent_turns
            logger.info(
                f"History compacted from {len(turns)} turns to {len(compacted_history)} turns",
                extra={"session_id": session_id, "new_turn_count": len(compacted_history)}
            )
            return compacted_history

    def _extract_entities_and_update_kg(
        self,
        turns: List[Dict[str, Any]],
        patient_id: str,
        kg: ClinicalKnowledgeGraph,
    ) -> Dict[str, List[str]]:
        """Extracts medical entities from conversation text and registers them in the Knowledge Graph via Agentic LLM."""
        diagnoses: List[str] = []
        medications: List[str] = []
        allergies: List[str] = []

        patient_node_id = f"PATIENT:{patient_id}"
        kg.add_entity(patient_node_id, "PATIENT", f"Patient {patient_id}")
        
        transcript = "\n".join([f"{t.get('role', 'unknown')}: {t.get('content', '')}" for t in turns])
        
        from google import genai
        from google.genai import types
        from careroute.config import settings
        import json

        api_key = settings.gemini_api_key
        if not api_key or api_key == "mock-gemini-key":
            logger.warning("No API key provided for compaction, returning empty extraction.")
            return {"diagnoses": [], "medications": [], "allergies": []}

        client = genai.Client(api_key=api_key)
        
        prompt = f"""
Analyze the following patient conversation transcript.
Extract all diagnoses/conditions, medications, and allergies mentioned.
Output MUST be a JSON object with strictly three keys:
- `diagnoses`: list of strings (e.g. ["Congestive Heart Failure"])
- `medications`: list of strings (e.g. ["Warfarin", "Lisinopril"])
- `allergies`: list of strings (e.g. ["Penicillin"])

Transcript:
{transcript}
"""
        try:
            response = client.models.generate_content(
                model=settings.flash_model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0
                )
            )
            data = json.loads(response.text)
            
            diagnoses = data.get("diagnoses", [])
            medications = data.get("medications", [])
            allergies = data.get("allergies", [])
            
            # Register to KG
            for cond in diagnoses:
                cond_id = f"COND:{''.join(c if c.isalnum() else '_' for c in cond[:20]).lower()}"
                kg.add_entity(cond_id, "CONDITION", cond)
                kg.add_relation(patient_node_id, cond_id, "HAS_CONDITION")
                
            for med in medications:
                med_id = f"DRUG:{''.join(c if c.isalnum() else '_' for c in med[:20]).lower()}"
                kg.add_entity(med_id, "MEDICATION", med)
                kg.add_relation(patient_node_id, med_id, "PRESCRIBED")
                
            for alg in allergies:
                alg_id = f"ALLERGY:{''.join(c if c.isalnum() else '_' for c in alg[:20]).lower()}"
                kg.add_entity(alg_id, "ALLERGY", alg)
                kg.add_relation(patient_node_id, alg_id, "HAS_ALLERGY")
                
        except Exception as exc:
            logger.error(f"Agentic KG Summarization Compaction failed: {exc}")

        return {
            "diagnoses": list(set(diagnoses)),
            "medications": list(set(medications)),
            "allergies": list(set(allergies)),
        }


# Singleton instance
compactor = KGSummarizationCompactor()

