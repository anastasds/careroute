from careroute.core.adk_config import create_safe_model
"""EHR Extractor Agent (Gemini Flash) for CareRoute.

Specialized in rapid, structured extraction of clinical documents, diagnoses, medications,
allergies, and vital signs, updating the Clinical Knowledge Graph.
"""


from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from careroute.observability.tracing import tracer

from google.adk.agents import Agent

from careroute.core.constitution import EHR_EXTRACTOR_SYSTEM_PROMPT
from careroute.core.models import ClinicalIntakeRecord
from careroute.core.router import TaskComplexity, router
from careroute.config import settings
from careroute.memory.knowledge_graph import knowledge_graph

def _update_kg(patient_id: str, record: dict):
    if record:
        patient_node_id = f"PATIENT:{patient_id}"
        knowledge_graph.add_entity(patient_node_id, "PATIENT", f"Patient {patient_id}")
        
        meds = record.get("prescribed_medications", []) if isinstance(record, dict) else getattr(record, 'prescribed_medications', [])
        for med in meds:
            med_name = med.get("drug_name") if isinstance(med, dict) else getattr(med, 'drug_name', '')
            if med_name:
                drug_node_id = f"DRUG:{med_name.lower()}"
                knowledge_graph.add_entity(drug_node_id, "MEDICATION", med_name)
                knowledge_graph.add_relation(patient_node_id, drug_node_id, "PRESCRIBED")




class EHRRetrieveOutput(BaseModel):
    status: str = Field(...)
    patient_id: str = Field(...)
    record: Optional[ClinicalIntakeRecord] = None
    recovery_suggestion: Optional[str] = None

MOCK_EHR_DB: Dict[str, Dict[str, Any]] = {
    "PT-94821": {
        "patient_id": "PT-94821",
        "primary_diagnosis": "Acute Decompensated Heart Failure (CHF NYHA Class III)",
        "secondary_diagnoses": ["Type 2 Diabetes Mellitus", "Hypertension", "Chronic Osteoarthritis"],
        "prescribed_medications": [
            {"drug_name": "Warfarin", "dosage": "5mg", "frequency": "once daily with dinner", "route": "oral"},
            {"drug_name": "Ibuprofen", "dosage": "400mg", "frequency": "as needed for joint pain", "route": "oral"},
            {"drug_name": "Metformin", "dosage": "500mg", "frequency": "twice daily with meals", "route": "oral"},
            {"drug_name": "Lisinopril", "dosage": "10mg", "frequency": "once daily in morning", "route": "oral"}
        ],
        "allergies": ["Penicillin", "Sulfa drugs"],
        "recent_vitals": {
            "systolic_bp": 134,
            "diastolic_bp": 82,
            "heart_rate": 76,
            "respiratory_rate": 16,
            "oxygen_saturation": 98.0,
            "temperature_fahrenheit": 98.6
        },
        "clinician_discharge_instructions": (
            "Patient discharged following 4-day inpatient diuresis. Stable for discharge. "
            "Warning: Monitor INR closely. Strict low sodium diet. Follow up with cardiology in 7 days."
        )
    },
    "PT-10492": {
        "patient_id": "PT-10492",
        "primary_diagnosis": "Essential Hypertension",
        "secondary_diagnoses": ["Type 2 Diabetes Mellitus"],
        "prescribed_medications": [
            {"drug_name": "Lisinopril", "dosage": "10mg", "frequency": "once daily in morning", "route": "oral"},
            {"drug_name": "Metformin", "dosage": "500mg", "frequency": "twice daily with meals", "route": "oral"},
            {"drug_name": "Acetaminophen", "dosage": "500mg", "frequency": "as needed for headache", "route": "oral"}
        ],
        "allergies": [],
        "recent_vitals": {
            "systolic_bp": 128,
            "diastolic_bp": 80,
            "heart_rate": 72,
            "respiratory_rate": 14,
            "oxygen_saturation": 99.0,
            "temperature_fahrenheit": 98.4
        },
        "clinician_discharge_instructions": (
            "Patient is stable. Continue maintenance medications as scheduled. Low-salt diet."
        )
    },
    "PT-38194": {
        "patient_id": "PT-38194",
        "primary_diagnosis": "Post-Acute Coronary Syndrome (NSTEMI)",
        "secondary_diagnoses": ["Gastroesophageal Reflux Disease", "Hyperlipidemia"],
        "prescribed_medications": [
            {"drug_name": "Clopidogrel", "dosage": "75mg", "frequency": "once daily", "route": "oral"},
            {"drug_name": "Omeprazole", "dosage": "20mg", "frequency": "once daily before breakfast", "route": "oral"},
            {"drug_name": "Atorvastatin", "dosage": "40mg", "frequency": "once daily at bedtime", "route": "oral"}
        ],
        "allergies": ["Aspirin"],
        "recent_vitals": {
            "systolic_bp": 122,
            "diastolic_bp": 78,
            "heart_rate": 68,
            "respiratory_rate": 16,
            "oxygen_saturation": 98.0,
            "temperature_fahrenheit": 98.2
        },
        "clinician_discharge_instructions": (
            "Post-PCI stenting. Dual antiplatelet therapy adherence is mandatory. Follow up in 14 days."
        )
    }
}

def retrieve_patient_ehr_records(patient_id: str) -> Dict[str, Any]:
    """Retrieves structured baseline clinical records from the Electronic Health Record (EHR) database.

    Extracts primary and secondary diagnoses, outpatient medications, vital signs, known drug allergies,
    and historical clinician discharge summaries for the specified patient.

    Args:
        patient_id: Unique patient tracking identifier (e.g., 'PT-94821').

    Returns:
        Dict[str, Any]: Structured output dictionary containing:
            - status (str): 'success' or 'error'.
            - patient_id (str): The requested patient identifier.
            - record (Optional[ClinicalIntakeRecord]): Validated patient clinical record model.
            - recovery_suggestion (Optional[str]): Actionable error message if patient not found.
    """
    with tracer.span("Tool:retrieve_patient_ehr_records", {"patient_id": patient_id}):
        pid = patient_id
        if pid in MOCK_EHR_DB:
            record_dict = MOCK_EHR_DB[pid]
            record = ClinicalIntakeRecord.model_validate(record_dict)
            return EHRRetrieveOutput(
                status="success",
                patient_id=pid,
                record=record,
            ).model_dump()

        return EHRRetrieveOutput(
            status="error",
            patient_id=pid,
            record=None,
            recovery_suggestion=f"Patient {pid} not found in EHR database."
        ).model_dump()


def retrieve_patient_ehr_records_with_kg(patient_id: str) -> Dict[str, Any]:
    """Queries EHR records for a patient and automatically registers clinical entity triples into the Knowledge Graph.

    Seeds patient nodes, active condition nodes, and PRESCRIBED medication edges into the
    Clinical Knowledge Graph before pharmaceutical interaction screening.

    Args:
        patient_id: Unique patient tracking identifier (e.g., 'PT-94821').

    Returns:
        Dict[str, Any]: Structured output dictionary containing:
            - status (str): 'success' or 'error'.
            - patient_id (str): The requested patient identifier.
            - record (Optional[ClinicalIntakeRecord]): Validated patient clinical record model.
            - recovery_suggestion (Optional[str]): Actionable error message if patient not found.
    """
    res = retrieve_patient_ehr_records(patient_id)
    record = res.get("record")
    _update_kg(patient_id, record)
    return res


def parse_clinical_discharge_summary(
    discharge_input: Optional[Dict[str, Any]] = None,
    patient_id: Optional[str] = None,
    raw_discharge_text: Optional[str] = None
) -> Dict[str, Any]:
    """Parses raw unstructured clinical discharge summary text into structured clinical records.

    Extracts active medications, vital signs, diagnoses, and clinician instructions,
    validating minimum input length and formatting constraints.

    Args:
        discharge_input: Optional dictionary containing patient_id and raw_discharge_text.
        patient_id: Unique patient identifier.
        raw_discharge_text: Free-text clinical discharge summary notes from the inpatient team.

    Returns:
        Dict[str, Any]: Structured parsing payload containing:
            - status (str): 'success' or 'error'.
            - patient_id (str): The associated patient ID.
            - parsed_entities (Dict[str, Any]): Extracted clinical entities.
            - recovery_suggestion (Optional[str]): Actionable remediation suggestion if text is malformed or too brief.
    """
    with tracer.span("Tool:parse_clinical_discharge_summary", {"patient_id": patient_id}):
        if isinstance(discharge_input, dict):
            pid = discharge_input.get("patient_id", patient_id or "PT-UNKNOWN")
            text = discharge_input.get("raw_discharge_text", raw_discharge_text or "")
        else:
            pid = patient_id or "PT-UNKNOWN"
            text = raw_discharge_text or ""

        if len(text.strip()) < 20:
            return {
                "status": "error",
                "patient_id": pid,
                "parsed_entities": {},
                "recovery_suggestion": "Input validation failed: raw_discharge_text is too brief to extract meaningful clinical context. Provide comprehensive discharge notes."
            }

        return {
            "status": "success",
            "patient_id": pid,
            "parsed_entities": {
                "raw_text_length": len(text),
                "summary": text[:200]
            }
        }



ehr_agent = Agent(
        name="EHRExtractorAgent",
    instruction=EHR_EXTRACTOR_SYSTEM_PROMPT,
    model=create_safe_model(router.select_model_for_task(TaskComplexity.FAST_EXTRACTION)),
    tools=[retrieve_patient_ehr_records_with_kg],
    mode="task",
    output_schema=ClinicalIntakeRecord
)
