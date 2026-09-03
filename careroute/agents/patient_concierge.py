from careroute.core.adk_config import create_safe_model
"""Patient Concierge Agent (Gemini Flash) for CareRoute.

Translates clinical discharge plans into personalized, empathetic, 6th-grade reading level
patient recovery guides, incorporating per-user behavioral memory (e.g., forgetfulness habits).
"""

from typing import Any
from google.adk.agents import Agent
from careroute.core.constitution import PATIENT_CONCIERGE_SYSTEM_PROMPT
from careroute.core.models import PersonalizedCarePlan
from careroute.core.router import TaskComplexity, router
from careroute.memory.personalization import personalization_memory


def get_patient_profile(patient_id: str) -> str:
    """Retrieves the longitudinal behavioral personalization profile for a given patient.

    Fetches patient-specific adherence traits, cognitive memory habits (e.g., forgetfulness),
    daily routine anchors (breakfast and dinner times), and environmental cues for plan synthesis.

    Args:
        patient_id: Unique patient tracking identifier (e.g., 'PT-94821').

    Returns:
        str: JSON-serialized PatientPersonalizationProfile containing health literacy targets and daily habits.
    """
    return personalization_memory.get_profile(patient_id).model_dump_json()


concierge_agent = Agent(
        name="PatientConciergeAgent",
    instruction=PATIENT_CONCIERGE_SYSTEM_PROMPT,
    model=create_safe_model(router.select_model_for_task(TaskComplexity.TEXT_SIMPLIFICATION)),
    tools=[get_patient_profile],
    mode="task",
    output_schema=PersonalizedCarePlan
)
