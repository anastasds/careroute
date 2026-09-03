from google.genai import types
"""Unit tests for CareRoute multi-agent orchestration and strategic model routing."""

import pytest
from careroute.agents.coordinator import process_patient_intake, coordinator_agent
from careroute.agents.ehr_extractor import ehr_agent
from careroute.agents.medication_safety import safety_agent
from careroute.agents.patient_concierge import concierge_agent
from careroute.core.router import TaskComplexity, router


def test_strategic_model_routing():
    """Validates that tasks are strategically routed to Pro or Flash models based on cognitive load."""
    pro_model = router.select_model_for_task(TaskComplexity.CLINICAL_REASONING)
    assert "pro" in pro_model.lower()

    flash_model = router.select_model_for_task(TaskComplexity.FAST_EXTRACTION)
    assert "flash" in flash_model.lower()

    concierge_model = router.select_model_for_task(TaskComplexity.TEXT_SIMPLIFICATION)
    assert "flash" in concierge_model.lower()


@pytest.mark.asyncio
async def test_ehr_extractor_agent():
    """Validates EHRExtractorAgent document parsing."""
    from google.adk import Runner
    from careroute.core.adk_config import adk_session_service
    runner = Runner(agent=ehr_agent, app_name="ehr", session_service=adk_session_service, auto_create_session=True)
    final = None
    async for event in runner.run_async(user_id="test", session_id="test", new_message=types.Content(role="user", parts=[types.Part.from_text(text="Extract for PT-94821")])):
        if event.output:
            final = event.output
    assert final.patient_id == "PT-94821"
    assert final.clinical_record is not None

@pytest.mark.asyncio
async def test_medication_safety_agent_detection():
    """Validates MedicationSafetyAgent detecting hazardous combinations."""
    from google.adk import Runner
    from careroute.core.adk_config import adk_session_service
    runner = Runner(agent=safety_agent, app_name="safety", session_service=adk_session_service, auto_create_session=True)
    final = None
    async for event in runner.run_async(user_id="test", session_id="test", new_message=types.Content(role="user", parts=[types.Part.from_text(text="Check medications for PT-94821: Warfarin, Ibuprofen")])):
        if event.output:
            final = event.output
    assert final.has_critical_contraindication is True
    assert len(final.contraindications) >= 1

@pytest.mark.asyncio
async def test_coordinator_agent_end_to_end_pipeline():
    """Validates complete multi-agent care transition pipeline execution using ADK."""
    result = await process_patient_intake(
        session_id="test-e2e-session-001",
        patient_id="PT-94821",
        user_message="I am being discharged today. Please prepare my care schedule.",
        auto_approve_hitl=True
    )
    assert result["status"] == "completed"
    assert "care_plan" in result
    assert result["self_eval_passed"] is True
    assert len(result["care_plan"]["medication_schedule"]) >= 1