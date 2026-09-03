"""CareRoute Core: Constitution, Data Models, Model Router, and Guardrails."""

from careroute.core.constitution import (
    SYSTEM_CONSTITUTION,
    COORDINATOR_SYSTEM_PROMPT,
    EHR_EXTRACTOR_SYSTEM_PROMPT,
    MEDICATION_SAFETY_SYSTEM_PROMPT,
    PATIENT_CONCIERGE_SYSTEM_PROMPT,
)
from careroute.core.models import (
    SeverityLevel,
    TriageUrgency,
    MedicationItem,
    VitalSigns,
    PatientPersonalizationProfile,
    DrugInteractionResult,
    ClinicalIntakeRecord,
    ClinicianApprovalRequest,
    PersonalizedCarePlan,
)
from careroute.core.router import router, StrategicModelRouter, TaskComplexity
from careroute.core.guardrails import (
    EmergencyTriageGuardrail,
    PromptInjectionGuardrail,
    )

__all__ = [
    "SYSTEM_CONSTITUTION",
    "COORDINATOR_SYSTEM_PROMPT",
    "EHR_EXTRACTOR_SYSTEM_PROMPT",
    "MEDICATION_SAFETY_SYSTEM_PROMPT",
    "PATIENT_CONCIERGE_SYSTEM_PROMPT",
    "SeverityLevel",
    "TriageUrgency",
    "MedicationItem",
    "VitalSigns",
    "PatientPersonalizationProfile",
    "DrugInteractionResult",
    "ClinicalIntakeRecord",
    "ClinicianApprovalRequest",
    "PersonalizedCarePlan",
    "router",
    "StrategicModelRouter",
    "TaskComplexity",
    "EmergencyTriageGuardrail",
    "PromptInjectionGuardrail",
    ]

