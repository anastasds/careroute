from careroute.core.adk_config import create_safe_model
"""Medication Safety and Clinical Interaction Agent (Gemini Pro) for CareRoute.

Specialized in deep pharmacological reasoning, RxNorm knowledge graph cross-referencing,
contraindication detection, and evidence-based therapeutic substitution recommendations.
"""

from typing import List
from pydantic import BaseModel

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from careroute.core.models import DrugInteractionResult, SeverityLevel
from careroute.observability.tracing import tracer
from careroute.memory.knowledge_graph import knowledge_graph

from google.adk.agents import Agent

from careroute.core.constitution import MEDICATION_SAFETY_SYSTEM_PROMPT
from careroute.core.models import DrugInteractionResult
from careroute.core.router import TaskComplexity, router

class MedicationSafetyReport(BaseModel):
    has_critical_contraindication: bool
    contraindications: List[DrugInteractionResult]


def check_prescription_contraindications(patient_id: str, medications: list[str]) -> dict:
    """Check the provided list of medications for contraindications."""
    return _check_prescription_contraindications({"patient_id": patient_id, "medications": medications})


class MedicationCheckOutput(BaseModel):
    status: str = Field(..., description="'success' or 'error'")
    total_medications_checked: int = Field(..., description="Number of evaluated medications")
    contraindications_found: List[DrugInteractionResult] = Field(
        default_factory=list,
        description="List of detected interactions with clinical mechanisms and alternatives"
    )
    has_critical_contraindication: bool = Field(
        default=False,
        description="Flag indicating if any lethal or severe contraindication was detected"
    )
    recovery_suggestion: Optional[str] = Field(
        default=None,
        description="Actionable instruction provided to the LLM when errors or conflicts occur"
    )

def check_prescription_contraindications(medications: List[str], patient_id: Optional[str] = None) -> Dict[str, Any]:
    with tracer.span("Tool:check_prescription_contraindications", {"medications": medications}):
        drugs = medications
        interactions = knowledge_graph.find_contraindications(drugs)
        has_critical = any(i.severity == SeverityLevel.CRITICAL_CONTRAINDICATION for i in interactions)

        recovery_suggestion = None
        if has_critical:
            recovery_suggestion = (
                "CRITICAL CONTRAINDICATION DETECTED. You MUST trigger a Human-in-the-Loop approval request "
                "via `request_clinician_approval` before finalizing the discharge plan, and substitute contraindicated drugs."
            )

        output = MedicationCheckOutput(
            status="success",
            total_medications_checked=len(drugs),
            contraindications_found=interactions,
            has_critical_contraindication=has_critical,
            recovery_suggestion=recovery_suggestion,
        )
        return output.model_dump()

safety_agent = Agent(
        name="MedicationSafetyAgent",
    instruction=MEDICATION_SAFETY_SYSTEM_PROMPT,
    model=create_safe_model(router.select_model_for_task(TaskComplexity.CLINICAL_REASONING)),
    tools=[check_prescription_contraindications],
    mode="task",
    output_schema=MedicationSafetyReport
)
