"""FastAPI REST Service for CareRoute Clinical AI Agent.

Exposes RESTful endpoints for patient intake, Knowledge Graph querying, and
Human-in-the-Loop clinician authorization webhooks.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from careroute.agents.coordinator import process_patient_intake
from careroute.core.models import PersonalizedCarePlan
from careroute.memory.firestore_store import session_store
from careroute.memory.knowledge_graph import knowledge_graph
from careroute.memory.personalization import personalization_memory
from careroute.agents.coordinator import APPROVAL_REGISTRY

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(
    title="CareRoute Clinical Copilot API",
    description="AgentOps compliant Clinical Intake, Medication Safety & Care Transition Service",
    version="0.1.0",
    lifespan=lifespan
)


class IntakeRequest(BaseModel):
    session_id: str = Field(..., description="Unique conversational session ID")
    patient_id: str = Field(..., description="Patient ID")
    user_message: str = Field(..., description="Patient or clinician query text")
    raw_discharge_text: Optional[str] = Field(default=None, description="Unstructured clinical notes")
    auto_approve_hitl: bool = Field(default=False, description="Simulate clinician approval for automated testing")


class ClinicianSignoffRequest(BaseModel):
    clinician_id: str = Field(..., description="Name or NPI of authorizing clinician")
    decision: str = Field(..., description="'APPROVE' or 'REJECT'")
    clinical_notes: Optional[str] = Field(default=None)


@app.get("/health", tags=["System"])
def health_check():
    """Returns system status, model routing health, and telemetry state."""
    return {
        "status": "healthy",
        "service": "careroute-agent",
        "models": {
            "pro_reasoning_model": "MedicationSafetyAgent",
            "flash_extraction_model": "EHRExtractorAgent",
        },
        "knowledge_graph_nodes": len(knowledge_graph.nodes),
        "knowledge_graph_edges": len(knowledge_graph.edges),
    }


@app.post("/api/v1/intake", tags=["Clinical Transition"])
async def process_intake(req: IntakeRequest):
    """Processes patient clinical intake, runs multi-agent contraindication checks, and builds care plan."""
    result = await process_patient_intake(
        session_id=req.session_id,
        patient_id=req.patient_id,
        user_message=req.user_message,
        raw_discharge_text=req.raw_discharge_text,
        auto_approve_hitl=req.auto_approve_hitl,
    )
    return result


@app.post("/api/v1/approvals/{approval_id}/sign", tags=["Human-in-the-Loop"])
def sign_clinician_approval(approval_id: str, req: ClinicianSignoffRequest):
    """Authorizes or rejects a pending Human-in-the-Loop clinical modification."""
    if approval_id not in APPROVAL_REGISTRY:
        try:
            from google.cloud import firestore
            db = firestore.Client()
            doc = db.collection("clinician_approvals").document(approval_id).get()
            if doc.exists:
                from careroute.core.models import ClinicianApprovalRequest
                APPROVAL_REGISTRY[approval_id] = ClinicianApprovalRequest.model_validate(doc.to_dict())
        except Exception:
            pass

    if approval_id not in APPROVAL_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request '{approval_id}' not found."
        )

    record = APPROVAL_REGISTRY[approval_id]
    if req.decision.upper() == "APPROVE":
        record.is_approved = True
        record.approved_by = req.clinician_id
        return {
            "status": "APPROVED",
            "approval_id": approval_id,
            "authorized_by": req.clinician_id,
            "message": f"Action '{record.action_type}' for patient {record.patient_id} successfully authorized."
        }
    else:
        record.is_approved = False
        record.approved_by = f"{req.clinician_id} (REJECTED)"
        return {
            "status": "REJECTED",
            "approval_id": approval_id,
            "authorized_by": req.clinician_id,
            "message": f"Action '{record.action_type}' for patient {record.patient_id} rejected."
        }


@app.get("/api/v1/patients/{patient_id}/care-plan", tags=["Patient Records"])
async def get_patient_care_plan(patient_id: str):
    """Fetches stored care plan from Firestore persistent store."""
    plan = await session_store.get_care_plan(patient_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"No active care plan found for patient {patient_id}.")
    return plan


@app.get("/api/v1/patients/{patient_id}/knowledge-graph", tags=["Knowledge Graph"])
def get_patient_knowledge_graph(patient_id: str):
    """Returns connected Knowledge Graph entities and relations for a patient."""
    return knowledge_graph.get_patient_graph_summary(patient_id)
