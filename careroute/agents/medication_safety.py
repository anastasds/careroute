from careroute.core.adk_config import create_safe_model
"""Medication Safety and Clinical Interaction Agent (Gemini Pro) for CareRoute.

Specialized in deep pharmacological reasoning, RxNorm knowledge graph cross-referencing,
contraindication detection, and evidence-based therapeutic substitution recommendations.
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from careroute.core.models import DrugInteractionResult, SeverityLevel
from careroute.observability.tracing import tracer
from careroute.memory.knowledge_graph import knowledge_graph

from google.adk.agents import Agent
from careroute.core.constitution import MEDICATION_SAFETY_SYSTEM_PROMPT
from careroute.core.router import TaskComplexity, router


class MedicationSafetyReport(BaseModel):
    has_critical_contraindication: bool
    contraindications: List[DrugInteractionResult]


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


class DosageScheduleOutput(BaseModel):
    status: str = Field(..., description="'success' or 'error'")
    drug_name: str = Field(..., description="Name of the medication")
    dosage: str = Field(..., description="Prescribed dose amount")
    scheduled_time: str = Field(..., description="Concrete clock time anchored to patient routine")
    food_instruction: str = Field(..., description="Dietary relationship e.g. with meals or empty stomach")
    recovery_suggestion: Optional[str] = Field(default=None)


def check_prescription_contraindications(
    medications: Union[List[str], Dict[str, Any]],
    patient_id: Optional[str] = None
) -> Dict[str, Any]:
    """Audits a patient's medication regimen against the RxNorm/FDA Drug-Drug Interaction Knowledge Graph.

    Cross-references all active medications, detecting lethal, major, or moderate interactions,
    elucidating physiological mechanisms, and suggesting evidence-based therapeutic substitutions.

    Args:
        medications: List of medication names (e.g., ['Warfarin', 'Ibuprofen']) or a dict containing 'medications'.
        patient_id: Optional unique patient identifier for clinical telemetry correlation.

    Returns:
        Dict[str, Any]: A structured audit report containing:
            - status (str): 'success' or 'error'.
            - total_medications_checked (int): Count of validated medications.
            - contraindications_found (List[DrugInteractionResult]): Detected conflicts with mechanisms and alternatives.
            - has_critical_contraindication (bool): True if severe/fatal interactions exist.
            - recovery_suggestion (Optional[str]): Actionable guidance for clinician review when conflicts exist.
    """
    with tracer.span("Tool:check_prescription_contraindications", {"patient_id": patient_id}):
        # Handle dict wrapping if passed by legacy callers or schemas
        if isinstance(medications, dict):
            med_list = medications.get("medications", [])
            pid = medications.get("patient_id", patient_id)
        else:
            med_list = medications
            pid = patient_id

        if not med_list or not isinstance(med_list, list):
            return MedicationCheckOutput(
                status="error",
                total_medications_checked=0,
                contraindications_found=[],
                has_critical_contraindication=False,
                recovery_suggestion="Input validation failed: 'medications' must be a non-empty list of drug names."
            ).model_dump()

        drugs = [m if isinstance(m, str) else str(m) for m in med_list]
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


def calculate_dosage_schedule(
    drug_info: Optional[Dict[str, Any]] = None,
    drug_name: Optional[str] = None,
    dosage: Optional[str] = None,
    frequency: Optional[str] = None,
    routine_anchors: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Calculates a concrete daily administration schedule anchored to patient daily routines.

    Converts technical medical abbreviations into precise times and routine anchors
    (e.g., matching morning medications to breakfast or evening medications to dinner).

    Args:
        drug_info: Optional dictionary containing drug_name, dosage, frequency, and routine_anchors.
        drug_name: Brand or generic medication name (e.g., 'Warfarin').
        dosage: Quantitative strength and unit (e.g., '5mg').
        frequency: Prescription frequency instructions (e.g., 'once daily in evening').
        routine_anchors: Patient routine timetable (e.g., {'breakfast': '8:30 AM', 'dinner': '7:30 PM'}).

    Returns:
        Dict[str, Any]: Structured schedule payload containing:
            - status (str): 'success' or 'error'.
            - drug_name (str): The medication name.
            - dosage (str): The confirmed dose.
            - scheduled_time (str): Calculated clock time based on routine anchors.
            - food_instruction (str): Clear instruction regarding food intake timing.
            - recovery_suggestion (Optional[str]): Actionable guidance if input is missing.
    """
    with tracer.span("Tool:calculate_dosage_schedule", {"drug_name": drug_name}):
        if isinstance(drug_info, dict):
            d_name = drug_info.get("drug_name", drug_name or "Unknown")
            d_dose = drug_info.get("dosage", dosage or "As prescribed")
            d_freq = drug_info.get("frequency", frequency or "daily")
            anchors = drug_info.get("routine_anchors", routine_anchors or {})
        else:
            d_name = drug_name or "Unknown"
            d_dose = dosage or "As prescribed"
            d_freq = frequency or "daily"
            anchors = routine_anchors or {}

        freq_lower = d_freq.lower()
        if "evening" in freq_lower or "dinner" in freq_lower or "bedtime" in freq_lower:
            scheduled_time = anchors.get("dinner", "7:00 PM")
            food_instruction = "Take with dinner or evening meal"
        elif "morning" in freq_lower or "breakfast" in freq_lower:
            scheduled_time = anchors.get("breakfast", "8:00 AM")
            food_instruction = "Take in the morning with breakfast"
        else:
            scheduled_time = anchors.get("breakfast", "9:00 AM")
            food_instruction = "Take with food as directed"

        return DosageScheduleOutput(
            status="success",
            drug_name=d_name,
            dosage=d_dose,
            scheduled_time=scheduled_time,
            food_instruction=food_instruction
        ).model_dump()


safety_agent = Agent(
    name="MedicationSafetyAgent",
    instruction=MEDICATION_SAFETY_SYSTEM_PROMPT,
    model=create_safe_model(router.select_model_for_task(TaskComplexity.CLINICAL_REASONING)),
    tools=[check_prescription_contraindications, calculate_dosage_schedule],
    mode="task",
    output_schema=MedicationSafetyReport
)
