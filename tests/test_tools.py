"""Unit tests for CareRoute tool design, strict schemas, docstrings, and guided error handling."""

import pytest
from careroute.agents.ehr_extractor import parse_clinical_discharge_summary, retrieve_patient_ehr_records
from careroute.agents.medication_safety import calculate_dosage_schedule, check_prescription_contraindications
from careroute.agents.coordinator import evaluate_vital_signs_urgency, schedule_followup_appointment, request_clinician_approval


def test_tool_docstrings_presence():
    """Validates that all tools contain comprehensive human-readable docstrings and parameter docs."""
    tools = [
        check_prescription_contraindications,
        calculate_dosage_schedule,
        retrieve_patient_ehr_records,
        parse_clinical_discharge_summary,
        evaluate_vital_signs_urgency,
        schedule_followup_appointment,
        request_clinician_approval,
    ]
    for tool in tools:
        assert tool.__doc__ is not None
        assert len(tool.__doc__.strip()) > 50
        assert "Args:" in tool.__doc__
        assert "Returns:" in tool.__doc__


def test_tool_guided_error_handling_invalid_input():
    """Validates that tools do NOT crash on malformed input, but return descriptive recovery suggestions."""
    # 1. Medication check with invalid empty input
    res = check_prescription_contraindications({"medications": []})
    assert res["status"] == "error"
    assert "recovery_suggestion" in res
    assert "Input validation failed" in res["recovery_suggestion"]

    # 2. Vitals check with out-of-range / invalid types
    vitals_res = evaluate_vital_signs_urgency({"vitals": {"systolic_bp": 999}})
    assert vitals_res["status"] == "error"
    assert "recovery_suggestion" in vitals_res

    # 3. Discharge parse with too short text
    parse_res = parse_clinical_discharge_summary({"patient_id": "PT-1", "raw_discharge_text": "short"})
    assert parse_res["status"] == "error"
    assert "recovery_suggestion" in parse_res


def test_calculate_dosage_schedule_personalization():
    """Validates routine-anchored dosage scheduling."""
    res = calculate_dosage_schedule({
        "drug_name": "Warfarin",
        "dosage": "5mg",
        "frequency": "once daily in evening",
        "routine_anchors": {"dinner": "7:30 PM", "breakfast": "8:30 AM"}
    })
    assert res["status"] == "success"
    assert "7:30 PM" in res["scheduled_time"]
    assert "dinner" in res["food_instruction"].lower()

