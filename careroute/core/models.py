"""Strict Pydantic schemas and domain models for CareRoute.

Defines validated input/output schemas for tools, agents, clinical knowledge graph entities,
patient memory profiles, and triage states.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class SeverityLevel(str, Enum):
    """Clinical severity classifications for drug interactions and triage."""
    CRITICAL_CONTRAINDICATION = "CRITICAL_CONTRAINDICATION"
    MAJOR_INTERACTION = "MAJOR_INTERACTION"
    MODERATE_INTERACTION = "MODERATE_INTERACTION"
    FOOD_LIFESTYLE_INTERACTION = "FOOD_LIFESTYLE_INTERACTION"
    SAFE = "SAFE"


class TriageUrgency(str, Enum):
    """Urgency tier for clinical patient evaluation."""
    EMERGENCY_911 = "EMERGENCY_911"
    URGENT_EVALUATION = "URGENT_EVALUATION"
    ROUTINE_MONITORING = "ROUTINE_MONITORING"
    STABLE = "STABLE"


class MedicationItem(BaseModel):
    """Individual prescribed or over-the-counter medication."""
    drug_name: str = Field(..., description="Generic or standard brand name of the drug", min_length=1)
    dosage: str = Field(..., description="Dosage quantity and unit (e.g., '5mg', '500mg')", min_length=1)
    frequency: str = Field(..., description="Administration schedule (e.g., 'once daily with meals', 'every 12 hours')")
    route: str = Field(default="oral", description="Route of administration (oral, subcutaneous, IV, etc.)")
    indication: Optional[str] = Field(default=None, description="Clinical reason for prescription")


class VitalSigns(BaseModel):
    """Patient vital sign measurements."""
    systolic_bp: Optional[int] = Field(default=None, description="Systolic blood pressure (mmHg)", ge=40, le=300)
    diastolic_bp: Optional[int] = Field(default=None, description="Diastolic blood pressure (mmHg)", ge=20, le=200)
    heart_rate: Optional[int] = Field(default=None, description="Heart rate in beats per minute", ge=20, le=250)
    respiratory_rate: Optional[int] = Field(default=None, description="Breaths per minute", ge=5, le=60)
    oxygen_saturation: Optional[float] = Field(default=None, description="SpO2 percentage", ge=50.0, le=100.0)
    temperature_fahrenheit: Optional[float] = Field(default=None, description="Body temperature in Fahrenheit", ge=80.0, le=115.0)


class PatientPersonalizationProfile(BaseModel):
    """Per-user behavioral traits, adherence habits, and communication preferences."""
    patient_id: str = Field(..., description="Unique patient identifier", min_length=1)
    behavioral_traits: List[str] = Field(
        default_factory=list,
        description="Observed adherence patterns (e.g., 'tends to take daily medication at an inconsistent time because they are forgetful')"
    )
    daily_routines: Dict[str, str] = Field(
        default_factory=dict,
        description="Key routine timestamps (e.g. {'wake_up': '8:30 AM', 'lunch': '1:00 PM', 'bedtime': '10:30 PM'})"
    )
    reading_level_preference: str = Field(default="6th-grade", description="Reading level preference for patient materials")
    preferred_reminder_channel: str = Field(default="SMS", description="Channel for reminders (SMS, App, Phone Call, Caregiver)")
    caregiver_name: Optional[str] = Field(default=None, description="Primary family caregiver name")
    caregiver_phone: Optional[str] = Field(default=None, description="Caregiver phone number for escalation nudges")
    clinician_notes: List[str] = Field(
        default_factory=list,
        description="Private clinician observations and guidance directives"
    )


class DrugInteractionResult(BaseModel):
    """Detailed clinical contraindication check result."""
    drug_a: str = Field(..., description="First interacting medication")
    drug_b: str = Field(..., description="Second interacting medication")
    severity: SeverityLevel = Field(..., description="Severity level of the interaction")
    mechanism: str = Field(..., description="Physiological mechanism explaining why the combination is hazardous")
    clinical_risk: str = Field(..., description="Adverse outcome (e.g., GI bleeding, hyperkalemia, serotonin syndrome)")
    recommended_action: str = Field(..., description="Actionable clinical recovery guideline")
    alternative_therapies: List[str] = Field(default_factory=list, description="Safer therapeutic substitutes")


class ClinicalIntakeRecord(BaseModel):
    """Structured extraction of raw clinical notes / discharge documents."""
    patient_id: str = Field(..., description="Unique patient ID")
    primary_diagnosis: str = Field(..., description="Primary clinical discharge diagnosis")
    secondary_diagnoses: List[str] = Field(default_factory=list, description="Secondary or chronic comorbidities")
    prescribed_medications: List[MedicationItem] = Field(default_factory=list, description="Active discharge medication list")
    allergies: List[str] = Field(default_factory=list, description="Known drug and food allergies")
    recent_vitals: Optional[VitalSigns] = Field(default=None, description="Last recorded vital signs prior to discharge")
    clinician_discharge_instructions: str = Field(default="", description="Original clinician discharge instructions")


class ClinicianApprovalRequest(BaseModel):
    """Human-in-the-loop authorization payload for high-stakes clinical changes."""
    approval_id: str = Field(..., description="Unique approval request ID")
    patient_id: str = Field(..., description="Target patient ID")
    action_type: str = Field(..., description="Action name requiring approval (e.g. 'ADJUST_PRESCRIPTION', 'CRITICAL_ESCALATION')")
    justification: str = Field(..., description="Clinical reasoning explaining the required action")
    proposed_changes: Dict[str, Any] = Field(..., description="Exact proposed state diff or prescription modification")
    requires_human_confirmation: bool = Field(default=True, description="Strict lock requiring human clinician sign-off")
    is_approved: Optional[bool] = Field(default=None, description="True if approved by clinician, False if rejected")
    approved_by: Optional[str] = Field(default=None, description="Clinician identifier who signed off")


class PersonalizedCarePlan(BaseModel):
    """Final, plain-language patient recovery plan tailored to individual habits."""
    patient_id: str = Field(..., description="Unique patient ID")
    plain_language_summary: str = Field(..., description="Empathetic, clear overview of the patient's condition and goals")
    medication_schedule: List[Dict[str, Any]] = Field(
        ...,
        description="Medication schedule mapped to concrete daily events (e.g. 'With breakfast', 'With lunch') to aid adherence"
    )
    behavioral_nudges: List[str] = Field(
        default_factory=list,
        description="Specific tips accommodating patient habits (e.g., phone alarms or pillbox reminders for forgetfulness)"
    )
    red_flag_symptoms: List[str] = Field(
        ...,
        description="Critical warning signs requiring immediate medical attention (When to Call Your Doctor or go to ED)"
    )
    followup_appointments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Scheduled follow-up consultations and lab tests"
    )
    safety_contraindications_flagged: List[DrugInteractionResult] = Field(
        default_factory=list,
        description="List of detected interactions that were resolved or flagged during review"
    )

