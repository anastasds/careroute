"""Unit tests for the Medical Practitioner LLM-as-a-Judge Evaluation Suite."""

import pytest
from careroute.agents.coordinator import coordinator_agent
from careroute.config import settings
from careroute.core.models import DrugInteractionResult, PersonalizedCarePlan, SeverityLevel
from careroute.memory.personalization import personalization_memory
from evals.llm_judge import MedicalPractitionerJudge


def test_llm_judge_on_approved_care_plan():
    """Validates that a clinician-approved care plan passes the medical judge evaluation."""
    patient_id = "PT-94821"
    result = coordinator_agent.process_patient_intake(
        session_id="judge-test-session-001",
        patient_id=patient_id,
        user_message="I'm heading home today. Please prepare my recovery guide.",
        auto_approve_hitl=True
    )
    assert result["status"] == "completed"

    care_plan = PersonalizedCarePlan.model_validate(result["care_plan"])
    profile = personalization_memory.get_profile(patient_id)

    report = MedicalPractitionerJudge.evaluate_plan(
        care_plan=care_plan,
        known_contraindications=care_plan.safety_contraindications_flagged,
        patient_behavioral_traits=profile.behavioral_traits,
    )

    assert report.passed is True
    assert report.overall_score >= 3.0
    assert len(report.clinical_frameworks_referenced) >= 3
    assert report.dimension_scores["MedicationSafetyAndReconciliation"] >= 3.0
    assert report.dimension_scores["PersonalizationAndAdherenceSupport"] >= 3.0


def test_llm_judge_on_unsafe_care_plan():
    """Validates that a care plan with an unmitigated critical contraindication is rejected by the judge."""
    unsafe_plan = PersonalizedCarePlan(
        patient_id="PT-UNSAFE-001",
        plain_language_summary="Short plan.",
        medication_schedule=[
            {"medication": "Warfarin 5mg", "when_to_take": "Morning", "instructions": "Take with water", "tip": ""},
            {"medication": "Ibuprofen 400mg", "when_to_take": "Morning", "instructions": "Take for pain", "tip": ""},
        ],
        behavioral_nudges=[],
        red_flag_symptoms=["Chest pain"],
        followup_appointments=[],
        safety_contraindications_flagged=[]
    )

    ddi = [
        DrugInteractionResult(
            drug_a="Warfarin",
            drug_b="Ibuprofen",
            severity=SeverityLevel.CRITICAL_CONTRAINDICATION,
            mechanism="GI bleeding",
            clinical_risk="Hemorrhage",
            recommended_action="Discontinue Ibuprofen",
            alternative_therapies=["Acetaminophen"]
        )
    ]

    report = MedicalPractitionerJudge.evaluate_plan(
        care_plan=unsafe_plan,
        known_contraindications=ddi,
        patient_behavioral_traits=[],
    )

    # Must fail because MedicationSafetyAndReconciliation drops below threshold
    assert report.dimension_scores["MedicationSafetyAndReconciliation"] <= 2.5
    assert report.passed is False


def test_llm_judge_raises_error_without_mock(monkeypatch):
    """Validates that running evaluation without live LLM raises RuntimeError."""
    unsafe_plan = PersonalizedCarePlan(
        patient_id="PT-UNSAFE-002",
        plain_language_summary="Short plan.",
        medication_schedule=[],
        behavioral_nudges=[],
        red_flag_symptoms=[],
        followup_appointments=[],
        safety_contraindications_flagged=[]
    )

    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-key")
    settings._api_key = None

    with pytest.raises(RuntimeError, match="LLM Judge evaluation failed"):
        MedicalPractitionerJudge.evaluate_plan(
            care_plan=unsafe_plan,
        )
