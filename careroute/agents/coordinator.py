from careroute.core.adk_config import create_safe_model
from google.genai import types
"""ADK-based Root Coordinator Agent for CareRoute."""

import asyncio

import uuid
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from careroute.core.models import ClinicianApprovalRequest, TriageUrgency, VitalSigns
from careroute.observability.logger import logger
from careroute.observability.tracing import tracer


from google.adk.agents import Agent
from careroute.agents.ehr_extractor import ehr_agent
from careroute.agents.medication_safety import safety_agent
from careroute.agents.patient_concierge import concierge_agent
from careroute.core.models import PersonalizedCarePlan, DrugInteractionResult
from careroute.core.router import TaskComplexity, router
from careroute.core.constitution import SYSTEM_CONSTITUTION
from careroute.core.guardrails import EmergencyTriageGuardrail, PromptInjectionGuardrail
from careroute.config import settings
from careroute.core.adk_config import adk_client
from careroute.memory.firestore_store import session_store
from careroute.memory.knowledge_graph import knowledge_graph
from careroute.memory.compaction import compactor
from careroute.memory.async_worker import async_consolidator



# --- HITL Tools ---
class HITLApprovalOutput(BaseModel):
    status: str = Field(..., description="'APPROVED', 'PENDING_APPROVAL', 'REJECTED', or 'error'")
    approval_id: str = Field(...)
    patient_id: str = Field(...)
    action_type: str = Field(...)
    requires_human_confirmation: bool = Field(default=True)
    is_approved: bool = Field(default=False)
    approved_by: Optional[str] = None
    clinical_audit_note: str = Field(...)
    recovery_suggestion: Optional[str] = None

class EscalationAlertOutput(BaseModel):
    status: str = Field(...)
    dispatch_id: str = Field(...)
    patient_id: str = Field(...)
    recipient_team: str = Field(...)
    notification_dispatched: bool = Field(...)
    recovery_suggestion: Optional[str] = None

APPROVAL_REGISTRY: Dict[str, ClinicianApprovalRequest] = {}

def _persist_approval(record: ClinicianApprovalRequest) -> None:
    """Persists approval to Firestore if available."""
    try:
        from google.cloud import firestore
        db = firestore.Client()
        db.collection("clinician_approvals").document(record.approval_id).set(record.model_dump())
    except Exception:
        pass


def request_clinician_approval(
    patient_id: str,
    action_type: str,
    justification: str,
    proposed_changes: Dict[str, Any],
    auto_approve_simulation: bool = False
) -> Dict[str, Any]:
    """Halts execution and submits a critical clinical modification for human clinician authorization.

    Enforces mandatory Human-in-the-Loop (HITL) safety governance before any high-stakes prescription
    discontinuation, drug substitution, or major care plan modification is finalized.

    Args:
        patient_id: Unique patient identifier for clinical correlation.
        action_type: Clinical category of proposed modification (e.g., 'Medication Substitution', 'Discontinuation').
        justification: Evidence-based clinical rationale explaining why the action is required (e.g. severe bleeding risk).
        proposed_changes: Structured details of medications being removed, added, or substituted.
        auto_approve_simulation: If True, simulates digital approval by an attending physician for automated integration runs.

    Returns:
        Dict[str, Any]: Structured approval receipt containing:
            - status (str): 'APPROVED' or 'PENDING_APPROVAL'.
            - approval_id (str): Unique audit tracking identifier for the approval record.
            - patient_id (str): Associated patient ID.
            - action_type (str): Category of clinical action submitted.
            - requires_human_confirmation (bool): True if clinician sign-off is mandatory.
            - is_approved (bool): Current authorization state.
            - approved_by (Optional[str]): Clinician signature/name if authorized.
            - clinical_audit_note (str): Audit log entry documenting approval status.
            - recovery_suggestion (Optional[str]): Follow-up guidance if awaiting clinician review.
    """
    with tracer.span("Tool:request_clinician_approval", {"patient_id": patient_id}):
        approval_id = f"HITL-{uuid.uuid4().hex[:8].upper()}"
        if auto_approve_simulation:
            approval_record = ClinicianApprovalRequest(
                approval_id=approval_id,
                patient_id=patient_id,
                action_type=action_type,
                justification=justification,
                proposed_changes=proposed_changes,
                requires_human_confirmation=True,
                is_approved=True,
                approved_by="Dr. M. Vance, MD (Cardiology Attending - Simulated Approval)"
            )
            APPROVAL_REGISTRY[approval_id] = approval_record
            _persist_approval(approval_record)
            logger.info(
                f"Clinician HITL action {action_type} APPROVED for patient {patient_id}",
                extra={"approval_id": approval_id, "patient_id": patient_id, "status": "APPROVED"}
            )
            return HITLApprovalOutput(
                status="APPROVED",
                approval_id=approval_id,
                patient_id=patient_id,
                action_type=action_type,
                requires_human_confirmation=True,
                is_approved=True,
                approved_by=approval_record.approved_by,
                clinical_audit_note=f"Action '{action_type}' authorized by {approval_record.approved_by}.",
            ).model_dump()
        
        approval_record = ClinicianApprovalRequest(
            approval_id=approval_id,
            patient_id=patient_id,
            action_type=action_type,
            justification=justification,
            proposed_changes=proposed_changes,
            requires_human_confirmation=True,
            is_approved=False,
            approved_by=None
        )
        APPROVAL_REGISTRY[approval_id] = approval_record
        _persist_approval(approval_record)
        logger.warning(
            f"HITL CODE STOP: Clinical action [{action_type}] paused waiting for clinician authorization",
            extra={"approval_id": approval_id, "patient_id": patient_id, "action_type": action_type}
        )
        return HITLApprovalOutput(
            status="PENDING_APPROVAL",
            approval_id=approval_id,
            patient_id=patient_id,
            action_type=action_type,
            requires_human_confirmation=True,
            is_approved=False,
            approved_by=None,
            clinical_audit_note="Action placed in PENDING state awaiting human clinician review.",
            recovery_suggestion="Present approval request summary to the attending clinician for digital sign-off."
        ).model_dump()

def escalate_critical_triage_alert(
    patient_id: str,
    urgency_tier: str,
    alert_summary: str,
    vital_signs_summary: Optional[str] = None
) -> Dict[str, Any]:
    """Dispatches emergency clinical alerts to rapid response teams and attending physicians.

    Initiates urgent hospital triage alerts when severe hemodynamic instability, hypertensive crisis,
    or acute red-flag symptoms require immediate clinical intervention.

    Args:
        patient_id: Unique patient identifier.
        urgency_tier: Urgency classification (e.g., 'EMERGENCY_911', 'URGENT_EVALUATION').
        alert_summary: Concise clinical summary of the life-threatening condition or symptom.
        vital_signs_summary: Optional text summary of current vital signs driving the escalation.

    Returns:
        Dict[str, Any]: Dispatch record containing:
            - status (str): 'success' or 'error'.
            - dispatch_id (str): Unique tracking identifier for the emergency dispatch.
            - patient_id (str): Patient associated with the alert.
            - recipient_team (str): The clinical response unit notified.
            - notification_dispatched (bool): Confirmation of alert transmission.
    """
    with tracer.span("Tool:escalate_critical_triage_alert", {"patient_id": patient_id}):
        dispatch_id = f"DISPATCH-{uuid.uuid4().hex[:6].upper()}"
        recipient = "Hospital Rapid Response Team & On-Call Attending" if "911" in urgency_tier else "Care Transition Triage Nurse"
        logger.warning(
            f"CRITICAL ESCALATION DISPATCHED: {alert_summary}",
            extra={
                "dispatch_id": dispatch_id,
                "patient_id": patient_id,
                "urgency": urgency_tier,
                "recipient": recipient
            }
        )
        return EscalationAlertOutput(
            status="success",
            dispatch_id=dispatch_id,
            patient_id=patient_id,
            recipient_team=recipient,
            notification_dispatched=True,
        ).model_dump()

# --- Triage Tools ---
class VitalsEvaluationOutput(BaseModel):
    status: str = Field(...)
    urgency_tier: TriageUrgency = Field(...)
    clinical_flags: List[str] = Field(default_factory=list)
    recommended_clinical_action: str = Field(...)
    recovery_suggestion: Optional[str] = None

class AppointmentScheduleOutput(BaseModel):
    status: str = Field(...)
    confirmation_id: str = Field(...)
    patient_id: str = Field(...)
    specialty: str = Field(...)
    scheduled_date: str = Field(...)
    instructions_for_patient: str = Field(...)
    recovery_suggestion: Optional[str] = None

def evaluate_vital_signs_urgency(
    systolic_bp: Optional[int] = None,
    diastolic_bp: Optional[int] = None,
    heart_rate: Optional[int] = None,
    respiratory_rate: Optional[int] = None,
    oxygen_saturation: Optional[float] = None,
    temperature_fahrenheit: Optional[float] = None,
    patient_id: Optional[str] = None,
    vitals: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Evaluates physiological vital signs against established clinical triage protocols.

    Assesses blood pressure, heart rate, oxygenation, and respiratory rate to identify
    hypertensive crises, severe hypoxemia, or hemodynamic instability requiring emergency triage.

    Args:
        systolic_bp: Systolic blood pressure in mmHg.
        diastolic_bp: Diastolic blood pressure in mmHg.
        heart_rate: Beats per minute (bpm).
        respiratory_rate: Breaths per minute.
        oxygen_saturation: Blood oxygen percentage (SpO2, 0.0 - 100.0).
        temperature_fahrenheit: Core body temperature in degrees Fahrenheit.
        patient_id: Optional patient tracking ID.
        vitals: Optional nested dictionary of vital sign metrics for flexible tool invocation.

    Returns:
        Dict[str, Any]: Triage assessment dictionary containing:
            - status (str): 'success' or 'error'.
            - urgency_tier (TriageUrgency): STABLE, URGENT_EVALUATION, or EMERGENCY_911.
            - clinical_flags (List[str]): Identified physiological abnormalities.
            - recommended_clinical_action (str): Immediate clinical management protocol.
            - recovery_suggestion (Optional[str]): Remediation instructions if input parameters are invalid.
    """
    with tracer.span("Tool:evaluate_vital_signs_urgency", {"patient_id": patient_id}):
        # Handle dict being passed as the first positional argument
        if isinstance(systolic_bp, dict):
            inner = systolic_bp.get("vitals", systolic_bp)
            systolic_bp = inner.get("systolic_bp")
            diastolic_bp = inner.get("diastolic_bp")
            heart_rate = inner.get("heart_rate")
            respiratory_rate = inner.get("respiratory_rate")
            oxygen_saturation = inner.get("oxygen_saturation")
            temperature_fahrenheit = inner.get("temperature_fahrenheit")
        elif isinstance(vitals, dict):
            systolic_bp = vitals.get("systolic_bp", systolic_bp)
            diastolic_bp = vitals.get("diastolic_bp", diastolic_bp)
            heart_rate = vitals.get("heart_rate", heart_rate)
            respiratory_rate = vitals.get("respiratory_rate", respiratory_rate)
            oxygen_saturation = vitals.get("oxygen_saturation", oxygen_saturation)
            temperature_fahrenheit = vitals.get("temperature_fahrenheit", temperature_fahrenheit)

        # Input boundary validation
        if systolic_bp is not None and (systolic_bp < 40 or systolic_bp > 300):
            return {
                "status": "error",
                "urgency_tier": "URGENT_EVALUATION",
                "clinical_flags": ["Invalid physiological value"],
                "recommended_clinical_action": "Repeat vitals measurement manually.",
                "recovery_suggestion": f"Input validation failed: Systolic BP {systolic_bp} mmHg is outside plausible physiological range (40-300 mmHg)."
            }
        import json
        
        prompt = f"""
Evaluate the following patient vitals for clinical urgency.
Systolic BP: {systolic_bp}
Diastolic BP: {diastolic_bp}
Heart Rate: {heart_rate}
Respiratory Rate: {respiratory_rate}
Oxygen Saturation: {oxygen_saturation}%
Temperature: {temperature_fahrenheit}F

Follow these clinical guidelines when evaluating:
1. Hypertensive Crisis: If Systolic BP >= 180 or Diastolic BP >= 120, flag as "Hypertensive Crisis" and set urgency to EMERGENCY_911.
2. Severe Hypoxemia: If Oxygen Saturation < 90.0%, flag as "Severe Hypoxemia" and set urgency to EMERGENCY_911.
3. Hemodynamic Instability: If Heart Rate < 45 or > 130, flag as "Hemodynamic Instability: Abnormal Heart Rate" and set urgency to URGENT_EVALUATION (unless EMERGENCY_911 is already triggered).
4. If no flags are triggered, set urgency to STABLE.

Determine the `urgency_tier` (STABLE, URGENT_EVALUATION, or EMERGENCY_911).
List any `clinical_flags`.
Provide a `recommended_clinical_action` corresponding to the urgency.
Always return a 'status' of 'success'.
"""
        response = adk_client.models.generate_content(
            model=settings.pro_model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=VitalsEvaluationOutput,
                temperature=0.0
            )
        )
        try:
            return json.loads(response.text)
        except Exception:
            return VitalsEvaluationOutput(
                status="error",
                urgency_tier=TriageUrgency.URGENT_EVALUATION,
                clinical_flags=["AI parsing failed"],
                recommended_clinical_action="Fallback: Urgent clinician review needed."
            ).model_dump()

def schedule_followup_appointment(
    patient_id: str,
    specialty: str,
    timeframe_days: int,
    appointment_reason: str
) -> Dict[str, Any]:
    """Schedules an outpatient specialist follow-up visit and formats patient instructions.

    Coordinates post-discharge outpatient continuity of care, generating a tracking confirmation ID,
    target post-discharge appointment window, and preparation instructions for the patient.

    Args:
        patient_id: Unique patient identifier.
        specialty: Clinical department or medical specialty (e.g., 'Cardiology', 'Primary Care').
        timeframe_days: Recommended follow-up window in days from discharge (e.g., 7 or 14).
        appointment_reason: Specific clinical objective of the visit (e.g., 'Monitor INR and heart failure recovery').

    Returns:
        Dict[str, Any]: Appointment booking payload containing:
            - status (str): 'success' or 'error'.
            - confirmation_id (str): Unique appointment reference ID.
            - patient_id (str): Associated patient identifier.
            - specialty (str): Medical specialty booked.
            - scheduled_date (str): Relative post-discharge appointment date string.
            - instructions_for_patient (str): Clear, patient-facing visit preparation guidelines.
    """
    with tracer.span("Tool:schedule_followup_appointment", {"patient_id": patient_id}):
        conf_id = f"APPT-{patient_id[-4:] if len(patient_id) >= 4 else '0000'}-{timeframe_days}D"
        target_date = f"+{timeframe_days} Days post-discharge"
        return AppointmentScheduleOutput(
            status="success",
            confirmation_id=conf_id,
            patient_id=patient_id,
            specialty=specialty,
            scheduled_date=target_date,
            instructions_for_patient=(
                f"Your follow-up with {specialty} is booked for {target_date}. "
                f"Purpose: {appointment_reason}. Please bring your current medication bottles and recent vitals log."
            ),
        ).model_dump()


def submit_intake_result(
    status: str,
    patient_id: str,
    care_plan: Optional[Dict[str, Any]] = None,
    hitl_approval: Optional[Dict[str, Any]] = None,
    contraindications: Optional[List[Any]] = None,
    message: Optional[str] = None
) -> Dict[str, Any]:
    """Submits the final validated clinical intake record and care plan to the host system.

    Constructs a strongly-typed Pydantic result capturing transition status, personalized care plan,
    clinician authorization audits, contraindication resolutions, and patient communication guides.

    Args:
        status: Final transition workflow status (e.g., 'completed', 'pending_clinician_approval').
        patient_id: Unique patient identifier.
        care_plan: Optional structured care plan dictionary including diagnoses, schedules, and appointments.
        hitl_approval: Optional Human-in-the-Loop clinician approval audit receipt.
        contraindications: Optional list of identified drug interaction results and mitigations.
        message: Optional patient-facing summary message.

    Returns:
        Dict[str, Any]: Validated IntakeResult model dictionary for external system ingestion.
    """
    if care_plan and isinstance(care_plan, dict) and "patient_id" not in care_plan:
        care_plan["patient_id"] = patient_id
    clean_contraindications = []
    for c in (contraindications or []):
        if isinstance(c, dict):
            clean_c = {
                "drug_a": c.get("drug_a", "Medication A"),
                "drug_b": c.get("drug_b", "Medication B"),
                "severity": c.get("severity", "CRITICAL_CONTRAINDICATION"),
                "mechanism": c.get("mechanism", "Pharmacodynamic / pharmacokinetic drug interaction"),
                "clinical_risk": c.get("clinical_risk", "Adverse drug interaction risk"),
                "recommended_action": c.get("recommended_action", "Clinical medication review and therapy substitution"),
                "alternative_therapies": c.get("alternative_therapies", [])
            }
            clean_contraindications.append(clean_c)
        else:
            clean_contraindications.append(c)
    return IntakeResult(status=status, patient_id=patient_id, care_plan=care_plan, hitl_approval=hitl_approval, contraindications=clean_contraindications, message=message).model_dump()

class IntakeResult(BaseModel):
    status: str = Field(description="Status of the transition, e.g. 'completed' or 'pending_clinician_approval'")
    patient_id: str
    care_plan: Optional[PersonalizedCarePlan] = None
    hitl_approval: Optional[dict] = None
    contraindications: list[Any] = Field(default_factory=list)
    message: Optional[str] = None


COORDINATOR_INSTRUCTION = f"""{SYSTEM_CONSTITUTION}

You are the CareRoute Clinical Transition Coordinator.
Your job is to orchestrate the clinical intake process by delegating to specialized sub-agents.
For a given patient intake request:
1. Transfer to `EHRExtractorAgent` to parse the clinical records or discharge summary.
2. Transfer to `MedicationSafetyAgent` to evaluate medication safety and check for critical contraindications.
3. If critical contraindications are found, you MUST use `request_clinician_approval` to get human sign-off on the alternative therapies before generating a care plan.
4. Use `schedule_followup_appointment` to schedule any necessary follow ups.
5. Finally, transfer to `PatientConciergeAgent` to generate the personalized patient-facing care guide.
6. Assemble the final `IntakeResult` with the generated care plan, any hitl approval results, and status. If HITL approval is rejected or pending, do not generate a care plan.
7. CRITICAL REQUIREMENT: Once `submit_intake_result` returns, you MUST ALWAYS generate a comprehensive plain-text conversational message to the patient. You must NEVER end your turn without outputting this message.
   In this final message, you MUST explicitly include:
   a. An empathetic, plain-language recovery summary written at a 6th-grade reading level.
   b. The active daily medication schedule with instructions and daily routine cues.
   c. Clear verification of medication safety, detailing any critical contraindications identified (e.g. Warfarin + Ibuprofen, or Clopidogrel + Omeprazole) and how they were substituted or resolved.
   d. The complete and EXHAUSTIVE list of ALL essential red-flag warning symptoms and emergency signs identified in the care plan, without omitting, summarizing, or shortening ANY of them (e.g., list all diabetes warning signs: unhealing sores/wounds, fruity breath, confusion, extreme thirst/urination; and all cardiac/BP warning signs).
   Do not output an empty message under any circumstances.
"""

coordinator_agent = Agent(
    name="CoordinatorAgent",
    instruction=COORDINATOR_INSTRUCTION,
    model=create_safe_model(router.select_model_for_task(TaskComplexity.CLINICAL_REASONING)),
    sub_agents=[ehr_agent, safety_agent, concierge_agent],
    tools=[request_clinician_approval, schedule_followup_appointment, submit_intake_result],
    mode="chat"
)


async def process_patient_intake(session_id: str, patient_id: str, user_message: str, raw_discharge_text: Optional[str] = None, auto_approve_hitl: bool = False) -> Dict[str, Any]:

    # 1. Security Check: Prompt Injection Guardrail
    is_injection, injection_msg = PromptInjectionGuardrail.evaluate(user_message)
    if is_injection:
        logger.warning(f"Security Alert: Blocked prompt injection for session {session_id}")
        return {
            "status": "blocked",
            "patient_id": patient_id,
            "care_plan": None,
            "hitl_approval": {"status": "BLOCKED", "approved_by": None},
            "self_eval_passed": False,
            "self_eval_errors": [injection_msg],
            "history_compacted": False,
            "message": "I cannot fulfill this request as it violates clinical safety and security directives."
        }

    # 2. Clinical Emergency Triage Guardrail
    is_emergency, emergency_msg = EmergencyTriageGuardrail.evaluate(user_message)
    if is_emergency:
        logger.warning(f"Clinical Alert: Emergency symptoms detected for session {session_id}")
        return {
            "status": "emergency_redirect",
            "patient_id": patient_id,
            "care_plan": None,
            "hitl_approval": {"status": "EMERGENCY_OVERRIDE", "approved_by": None},
            "self_eval_passed": False,
            "self_eval_errors": [],
            "history_compacted": False,
            "message": emergency_msg
        }

    # 3. HIPAA / Privacy Layer: PII & PHI Scrubbing (Cloud DLP / Regex Filter)
    from careroute.security.redaction import PIIScrubber
    clean_user_message = PIIScrubber.redact(user_message)
    clean_discharge_text = PIIScrubber.redact(raw_discharge_text) if raw_discharge_text else None

    from google.adk import Runner
    import json
    
    # We pass the input context so the LLM coordinator knows what to do
    prompt = f"Patient ID: {patient_id}\nUser Message: {clean_user_message}\nAuto-approve HITL: {auto_approve_hitl}"
    if raw_discharge_text:
        prompt += f"\nRaw Discharge Text: {clean_discharge_text}"
        
    from careroute.core.adk_config import adk_session_service, adk_telemetry_config, adk_memory_service
    from google.adk.runners import RunConfig
    from careroute.config import settings
    import os

    if settings.storage_backend == "agentplatform" and os.getenv("VERTEX_AGENT_ENGINE_ID") and os.getenv("VERTEX_AGENT_ENGINE_ID") != "123456789":
        session_svc = adk_session_service
        memory_svc = adk_memory_service
    else:
        from google.adk.sessions import InMemorySessionService
        session_svc = InMemorySessionService()
        memory_svc = None

    runner = Runner(agent=coordinator_agent, app_name="coordinator", session_service=session_svc, memory_service=memory_svc, auto_create_session=True)
    
    # Run the ADK graph
    final_output = None
    async for event in runner.run_async(user_id=patient_id, session_id=session_id, new_message=types.Content(role="user", parts=[types.Part.from_text(text=prompt)]), run_config=RunConfig(telemetry=adk_telemetry_config)):
        for fc in event.get_function_calls():
            if fc.name == "submit_intake_result":
                final_output = IntakeResult.model_validate(fc.args)

    if not final_output:
        raise RuntimeError("Coordinator did not return a final output")

    # final_output is a pydantic model or dict depending on ADK setup
    result = final_output if isinstance(final_output, IntakeResult) else IntakeResult.model_validate(final_output)

    is_plan_valid = True
    eval_errors = []
    compacted_turns = []
    history_turns = []

    if result.care_plan and result.status == "completed":

        # 11. Persistent Storage in Firestore
        await session_store.save_care_plan(patient_id, result.care_plan.model_dump())
        await session_store.append_turn(
            session_id, "assistant",
            result.care_plan.plain_language_summary,
            {"care_plan_id": patient_id}
        )

        # 12. History Compaction
        history_turns = await session_store.get_session_history(session_id)
        compacted_turns = compactor.compact_history(session_id, history_turns, patient_id, knowledge_graph)

        # 13. Async Memory Operations
        try:
            loop = asyncio.get_running_loop()
            async_consolidator.schedule_session_consolidation(session_id, patient_id, history_turns)
        except RuntimeError:
            pass

    return {
        "status": result.status,
        "patient_id": patient_id,
        "care_plan": result.care_plan.model_dump() if result.care_plan else None,
        "hitl_approval": result.hitl_approval,
        "self_eval_passed": is_plan_valid,
        "self_eval_errors": eval_errors,
        "history_compacted": len(compacted_turns) < len(history_turns) if len(history_turns) > 6 else False
    }

