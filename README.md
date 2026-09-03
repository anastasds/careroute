# CareRoute — Clinical Intake & Care Transition AI Copilot

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Google ADK](https://img.shields.io/badge/Orchestration-Google%20ADK-4285F4.svg)](https://cloud.google.com/vertex-ai)
[![Vertex AI Agent Platform](https://img.shields.io/badge/Platform-Vertex%20AI%20Reasoning%20Engine-34A853.svg)](https://cloud.google.com/vertex-ai)
[![Evaluation Score](https://img.shields.io/badge/ADK%20Judge%20Score-1.0%20%2F%201.0%20(100%25)-brightgreen.svg)](#5-evaluation-methodology--benchmark-results)
[![OpenTelemetry](https://img.shields.io/badge/Observability-OpenTelemetry%20%2B%20Cloud%20Trace-F4B400.svg)](https://opentelemetry.io/)

> **CareRoute** is an enterprise-grade, HIPAA-aware clinical intake, pharmaceutical safety, and care transition AI copilot. Designed to prevent hospital readmissions and adverse drug events (ADEs), CareRoute ingests discharge summaries, queries a seeded **RxNorm/FDA Clinical Knowledge Graph** to detect high-risk contraindications, enforces **Human-in-the-Loop (HITL) clinician authorization gates** for prescription changes, accommodates **patient-specific behavioral routines**, and synthesizes empathetic, plain-language patient recovery guides.

---

## Table of Contents

1. [System Architecture & Agent Design](#1-system-architecture--agent-design)
2. [End-to-End Clinical Flow & Execution Trace](#2-end-to-end-clinical-flow--execution-trace)
3. [Core Clinical & Architectural Concepts](#3-core-clinical--architectural-concepts)
4. [Enterprise Observability & State Management](#4-enterprise-observability--state-management)
5. [Evaluation Methodology & Benchmark Results](#5-evaluation-methodology--benchmark-results)
6. [Quickstart & Deployment Guide](#6-quickstart--deployment-guide)
7. [Repository Structure](#7-repository-structure)

---

## 1. System Architecture & Agent Design

CareRoute is built on the **Google Agent Development Kit (ADK)** using a hierarchical Hub-and-Spoke coordination architecture. The root coordinator orchestrates three specialized sub-agents, enforces safety guardrails, connects to a deterministic Knowledge Graph, and delegates clinical authorization to human physicians.

```mermaid
flowchart TD
    subgraph Ingestion ["1. Patient and EHR Ingestion"]
        User["Patient / Hospital Intake Request"] --> Armor["Google Model Armor & Input Guardrails"]
        Armor --> Redact["PII / PHI Redaction Engine (HIPAA-Aware)"]
    end

    subgraph Orchestration ["2. Multi-Agent Hub and Spoke (Google ADK)"]
        Redact --> Coord["CoordinatorAgent (Root Router)"]
        Coord <--> EHR["EHRExtractorAgent (Clinical History Parser)"]
        Coord <--> Safety["MedicationSafetyAgent (RxNorm DDI Checker)"]
        Coord <--> Concierge["PatientConciergeAgent (Care Plan Synthesizer)"]
    end

    subgraph DeterministicData ["3. Deterministic Knowledge Graph and Tools"]
        EHR --> ToolEHR["retrieve_patient_ehr_records_with_kg"]
        Safety --> ToolDDI["check_prescription_contraindications"]
        Coord --> ToolAppt["schedule_followup_appointment"]
        ToolDDI <--> KG[("RxNorm / FDA DDI Clinical Knowledge Graph")]
    end

    subgraph SafetyGate ["4. Human-in-the-Loop Governance Gate"]
        Safety -- "Critical Interaction Detected" --> HITLTool["request_clinician_approval"]
        HITLTool --> Clinician{"Attending Physician Sign-Off"}
        Clinician -- "Approved" --> Coord
        Clinician -- "Rejected" --> Stop["Halt Plan Generation & Alert Clinician"]
    end

    subgraph MemoryObservability ["5. Vertex AI Observability and State"]
        Coord <--> VertexSession["VertexAiSessionService (Agent Platform)"]
        Coord <--> VertexMemory["VertexAiMemoryBankService (Episodic Memory)"]
        Coord <--> Compactor["KG History Compactor (Triples Brief)"]
        Coord -.-> OTEL["OpenTelemetry Tracer (CloudTraceSpanExporter)"]
    end
```

### Specialized Agents & Roles

| Agent | Model Tier | Core Clinical Responsibility | Primary Tools Used |
| :--- | :--- | :--- | :--- |
| **`CoordinatorAgent`** | Gemini Pro | Central orchestrator. Manages sub-agent handoffs, triggers HITL gates, schedules follow-ups, and validates final output. | `request_clinician_approval`<br>`schedule_followup_appointment`<br>`submit_intake_result` |
| **`EHRExtractorAgent`** | Gemini Flash | Ingests raw discharge text, parses vitals and active medications, and queries the clinical knowledge graph. | `retrieve_patient_ehr_records_with_kg`<br>`finish_task` |
| **`MedicationSafetyAgent`** | Gemini Pro | Audits medication lists against drug interaction tables, identifies contraindications, and formulates alternative therapies. | `check_prescription_contraindications`<br>`calculate_dosage_schedule`<br>`finish_task` |
| **`PatientConciergeAgent`** | Gemini Flash | Retrieves patient behavioral profiles and translates complex clinical plans into empathetic 6th-grade language with routine nudges. | `get_patient_profile`<br>`finish_task` |

---

## 2. End-to-End Clinical Flow & Execution Trace

The sequence diagram below maps the complete multi-agent lifecycle from patient intake submission to final delivery.

```mermaid
sequenceDiagram
    autonumber
    actor Patient as Patient (Arthur Pendelton)
    participant Coord as CoordinatorAgent
    participant EHR as EHRExtractorAgent
    participant Safety as MedicationSafetyAgent
    participant KG as Clinical Knowledge Graph
    participant HITL as Clinician Approver (Dr. Vance)
    participant Concierge as PatientConciergeAgent
    participant Platform as Vertex AI Agent Platform

    Patient->>Coord: "I am being discharged today. Please prepare my care schedule."
    Note over Coord: Initializes Vertex AI Session & Cloud Trace Span
    Coord->>EHR: Delegate EHR Extraction (PT-94821)
    EHR->>KG: retrieve_patient_ehr_records_with_kg(PT-94821)
    KG-->>EHR: Returns CHF, Type 2 Diabetes, Warfarin, Ibuprofen
    EHR-->>Coord: Parsed Clinical Baseline
    Coord->>Safety: Delegate DDI Safety Audit
    Safety->>KG: check_prescription_contraindications([Warfarin, Ibuprofen, ...])
    KG-->>Safety: CRITICAL CONTRAINDICATION: Warfarin + Ibuprofen (GI Hemorrhage)
    Safety-->>Coord: Recommends Ibuprofen discontinuation & Acetaminophen substitution (max 2g/day)
    Coord->>HITL: request_clinician_approval(Medication Substitution)
    HITL-->>Coord: APPROVED (HITL-E34FC7E2, Dr. M. Vance, MD)
    Coord->>Coord: schedule_followup_appointment(Cardiology, +7 Days)
    Coord->>Concierge: Delegate Personalized Discharge Plan
    Concierge->>Platform: get_patient_profile(PT-94821)
    Platform-->>Concierge: 6th-grade reading level, pillbox nudge, salt shaker anchor
    Concierge-->>Coord: Synthesized Care Guide
    Coord->>Coord: submit_intake_result(CarePlan, HITL, Status: Completed)
    Coord-->>Patient: Empathetic Plain-Language Summary + Schedule + Warning Signs
```

### Execution Trace & Intermediate Payloads

#### Stage 1: Intake Request Ingestion
The interaction starts when patient `PT-94821` (Arthur Pendelton, 68yo male) submits their discharge request:
```json
{
  "patient_id": "PT-94821",
  "user_message": "I am being discharged today. Please prepare my care schedule.",
  "auto_approve_hitl": true
}
```

#### Stage 2: Clinical Baseline Extraction (`EHRExtractorAgent`)
The `EHRExtractorAgent` queries the Clinical Knowledge Graph via `retrieve_patient_ehr_records_with_kg`:
* **Diagnoses**: Congestive Heart Failure (NYHA Class II), Type 2 Diabetes Mellitus, Essential Hypertension, Knee Osteoarthritis.
* **Active Medications**: Lisinopril 10mg daily, Metformin 500mg BID, Warfarin 5mg daily, Ibuprofen 400mg TID PRN.
* **Baseline Vitals**: Blood Pressure 134/82 mmHg, Heart Rate 74 bpm, SpO2 96%, Weight 198 lbs.

#### Stage 3: Drug-Drug Interaction Safety Audit (`MedicationSafetyAgent`)
The `MedicationSafetyAgent` runs `check_prescription_contraindications`, matching active medications against NIH RxNorm and FDA rules:
```json
{
  "status": "success",
  "total_medications_checked": 4,
  "contraindications_found": [
    {
      "drug_a": "Warfarin",
      "drug_b": "Ibuprofen",
      "severity": "CRITICAL_CONTRAINDICATION",
      "mechanism": "NSAIDs inhibit platelet aggregation and cause gastric mucosal damage, synergistically increasing major gastrointestinal hemorrhage and bleeding risk when combined with oral anticoagulants.",
      "clinical_risk": "Severe, life-threatening internal or GI bleeding.",
      "recommended_action": "Avoid co-administration. Substitute Ibuprofen with Acetaminophen (Tylenol) for mild-to-moderate analgesia, limiting to max 2g/day with INR monitoring.",
      "alternative_therapies": [
        "Acetaminophen",
        "Topical Lidocaine",
        "Physical therapy"
      ]
    }
  ],
  "has_critical_contraindication": true
}
```

#### Stage 4: Clinician Authorization Gate (`request_clinician_approval`)
Because a critical contraindication was detected, automated plan emission halts immediately. The `CoordinatorAgent` executes `request_clinician_approval`:
```json
{
  "approval_id": "HITL-E34FC7E2",
  "status": "APPROVED",
  "patient_id": "PT-94821",
  "action_type": "Medication Substitution",
  "requires_human_confirmation": true,
  "is_approved": true,
  "approved_by": "Dr. M. Vance, MD (Cardiology Attending - Simulated Approval)",
  "clinical_audit_note": "Action 'Medication Substitution' authorized by Dr. M. Vance, MD (Cardiology Attending - Simulated Approval)."
}
```

#### Stage 5: Follow-Up Appointment Scheduling
The coordinator invokes `schedule_followup_appointment`:
* **Confirmation ID**: `APPT-4821-7D`
* **Specialty**: Cardiology
* **Target Date**: `+7 Days post-discharge`
* **Patient Instructions**: *"Your follow-up with Cardiology is booked for +7 Days post-discharge. Purpose: Check heart health and monitor INR (blood thinner test). Please bring your current medication bottles and recent vitals log."*

#### Stage 6: Structured Output via Tool Call (`submit_intake_result`)
To enable reliable machine-to-machine integrations (FastAPI, EHR backends, Firestore), the coordinator executes `submit_intake_result` to output a strongly-typed Pydantic JSON payload:
```json
{
  "status": "completed",
  "patient_id": "PT-94821",
  "care_plan": {
    "patient_id": "PT-94821",
    "diagnoses": [
      "Congestive Heart Failure",
      "Type 2 Diabetes",
      "Hypertension",
      "Osteoarthritis"
    ],
    "medications": [
      {
        "name": "Lisinopril 10mg",
        "routine": "Take 1 pill once a day in morning",
        "purpose": "Blood pressure and cardiac function"
      },
      {
        "name": "Metformin 500mg",
        "routine": "Take 1 pill morning and 1 pill evening with meals",
        "purpose": "Glycemic control"
      },
      {
        "name": "Warfarin 5mg",
        "routine": "Take 1 pill once daily with dinner",
        "purpose": "Anticoagulation"
      },
      {
        "name": "Acetaminophen",
        "routine": "PRN joint pain, max 2g/day",
        "purpose": "Pain relief replacing contraindicated Ibuprofen"
      }
    ],
    "followup_appointments": [
      {
        "appointment_id": "APPT-4821-7D",
        "specialty": "Cardiology",
        "timeframe": "In 7 days"
      }
    ]
  },
  "hitl_approval": {
    "status": "APPROVED",
    "approved_by": "Dr. M. Vance, MD"
  }
}
```

#### Stage 7: Final Patient-Facing Communication
Following the structured tool call, the `CoordinatorAgent` outputs the conversational recovery guide:

> *"Hello! I am so glad to hear you are being discharged today and returning home. We want to make sure you have everything you need to stay healthy and out of the hospital. You were in the hospital because your heart was having a bit of trouble pumping blood, which is called heart failure. We also know you have diabetes, high blood pressure, and joint pain. To help you feel your best, your plan is to take your medicines every day, eat foods with low salt, and weigh yourself each morning.*
>
> ***Medication Changes and Safety***  
> *We noticed you were taking Ibuprofen for joint pain along with Warfarin (a blood thinner). Taking these two together can cause a serious risk of internal bleeding. To keep you safe, our doctors have replaced your Ibuprofen with Acetaminophen (Tylenol).*
>
> ***Your Daily Medication Schedule***  
> • **Lisinopril (10mg):** Take 1 pill once a day in the morning to help your blood pressure and help your heart pump better.  
> • **Metformin (500mg):** Take 1 pill in the morning with breakfast and 1 pill in the evening with dinner to control your blood sugar.  
> • **Warfarin (5mg):** Take 1 pill once a day with dinner to thin your blood and prevent clots.  
> • **Acetaminophen:** Take as needed for joint pain, but please do not take more than 2,000 mg (2 grams) in one day.  
>
> ***Red-Flag Warning Symptoms***  
> *Please call a doctor or go to the emergency room right away if you notice any of these signs:*  
> • *Weight gain of 2 or 3 pounds in one day, or 5 pounds in a week.*  
> • *New or worse trouble breathing, especially when you are resting or lying down.*  
> • *New or worse swelling in your feet, ankles, or legs.*  
> • *Waking up at night feeling like you cannot breathe.*  
> • *Any new or unusual bleeding, such as nosebleeds, dark stools, or bad bruising.*
>
> *Your follow-up appointment with Cardiology is booked for 7 days from now. Please bring your pill bottles and your morning weight logs to that appointment. We are here to support you on your road to recovery!"*

---

## 3. Core Clinical & Architectural Concepts

### 1. Zero-Hallucination Drug-Drug Interaction (DDI) Graph
Rather than relying on LLM parameter memory for drug interactions, CareRoute seeds standard NIH RxNorm, NLM RxNav, and FDA DDI tables into a deterministic Knowledge Graph:
```text
(Warfarin:Drug) -[:CRITICAL_CONTRAINDICATION {risk: "Severe GI Bleed"}]-> (Ibuprofen:Drug)
(Warfarin:Drug) -[:RECOMMENDED_ALTERNATIVE {max_daily: "2000mg"}]-> (Acetaminophen:Drug)
```
All drug pairs are audited deterministically before plan synthesis.

### 2. Human-in-the-Loop (HITL) Safety Gate
Prescription modifications require physician sign-off. When a critical contraindication is detected:
* The system executes a code stop via `request_clinician_approval`.
* An audit payload is created documenting the proposed substitution, clinical rationale, and prescribing physician.
* If rejected or pending, discharge plan generation halts immediately.

### 3. Patient Personalization & Behavioral Anchors
To maximize adherence post-discharge, CareRoute incorporates per-patient behavioral profiles:
* **Health Literacy Calibration**: Translates clinical diagnoses to everyday language (e.g., "congestive heart failure" to "trouble pumping blood") targeting a 6th-grade reading level.
* **Daily Routine Anchoring**: Connects medication intake to existing habits (e.g., placing morning blood pressure pills next to the coffee mug, setting a phone alarm for dinner anticoagulants).
* **Environmental Nudges**: Employs behavioral cues such as removing the salt shaker from the dining table for low-sodium diets.

### 4. Guided Error Handling & Tool Schemas
All agent tools utilize strict Pydantic v2 validation models (`Field`, regex constraints, typed structures) and adhere to a guided recovery pattern:
```json
{
  "status": "error",
  "recovery_suggestion": "Invalid dosage format. Specify value in milligrams (mg) followed by administration frequency (e.g., '10mg daily')."
}
```
If an agent supplies malformed inputs, the tool returns an actionable recovery suggestion rather than raising an unhandled exception, enabling immediate model self-correction.

### 5. Active Pre-Execution Guardrails & Safety Filters
CareRoute runs input text through deterministic and LLM-assisted filters before graph dispatch:
* **`PromptInjectionGuardrail`**: Evaluates incoming patient or caregiver prompts against heuristic and semantic injection patterns. Intercepts jailbreaks, prompt extraction, and instructions to override clinician authority.
* **`EmergencyTriageGuardrail`**: Detects life-threatening symptoms (crushing chest pain, severe hypoxemia, blue lips) and routes immediately to emergency protocols (911 redirect) rather than conversational care scheduling.

### 6. HIPAA-Aware PII / PHI Redaction Engine (Cloud DLP & Regex)
CareRoute safeguards patient privacy through a dual-mode redaction engine (`careroute/security/redaction.py`):
* **Google Cloud Sensitive Data Protection (DLP)**: When `CAREROUTE_ENABLE_DLP=true` and credentials are present, CareRoute calls the Cloud DLP API (`deidentify_content`) using standard healthcare info types (`US_SOCIAL_SECURITY_NUMBER`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `DATE_OF_BIRTH`, `US_HEALTHCARE_NPI`, `MEDICAL_RECORD_NUMBER`, `STREET_ADDRESS`).
* **High-Performance Deterministic Regex Filter**: Runs locally with zero latency, scrubbing direct identifiers (SSNs, MRNs, phone numbers, email addresses, dates of birth, ZIP codes) while carefully preserving clinical terminology and valid session identifiers (e.g., `PT-94821`).
* **Automatic Logging Scrubbing**: All structured JSON log messages and audit entries pass through `PIIScrubber.redact()` before being emitted to stdout or Cloud Logging, preventing accidental leakages of protected health information in log aggregators.


---

## 4. Enterprise Observability & State Management

CareRoute natively integrates with Google Cloud enterprise AI and OpenTelemetry to provide complete visibility across all agent handoffs, tool calls, and LLM reasoning steps.

### 1. Vertex AI Agent Platform Sessions
Session state is managed via `VertexAiSessionService` in `careroute/core/adk_config.py`:
* Every turn, tool invocation, tool response, and model `thought_signature` token is stored in the Vertex AI Reasoning Engine backend.
* Supports deterministic replay and historical inspection via standard ADK session APIs.

### 2. Episodic Memory Banks & Context Compaction
To eliminate context window bloat while retaining critical longitudinal data:
* **`KGSummarizationCompactor`**: Compresses multi-turn conversation logs into an entity-triple brief (`Patient -> DiagnosedWith -> CHF`, `Prescription -> Substituted -> Acetaminophen`), reducing token overhead by over 75%.
* **`VertexAiMemoryBankService`**: Persists consolidated patient facts across visits into long-term Vertex AI Memory Banks scoped by `app_name` and `user_id`.

### 3. OpenTelemetry Distributed Tracing
Instrumented through `careroute/observability/tracing.py`:
* Spans are propagated across the coordinator, sub-agents, and tools.
* Batched and exported directly to **Google Cloud Trace** via `BatchSpanProcessor` and `CloudTraceSpanExporter`.

| Trace Span Name | Owning Component | Tracked Metadata |
| :--- | :--- | :--- |
| `Tool:retrieve_patient_ehr_records_with_kg` | `EHRExtractorAgent` | `patient_id`, records count |
| `Tool:check_prescription_contraindications` | `MedicationSafetyAgent` | `patient_id`, `med_count: 4` |
| `Tool:request_clinician_approval` | `CoordinatorAgent` | `patient_id`, `action_type: Medication Substitution` |
| `Tool:schedule_followup_appointment` | `CoordinatorAgent` | `patient_id`, `specialty: Cardiology`, `timeframe: 7` |
| `Tool:get_patient_profile` | `PatientConciergeAgent` | `patient_id` |
| `KGHistoryCompaction` | Memory Hook | `session_id`, `original_turn_count`, `new_turn_count` |
| `AsyncMemoryConsolidation` | Background Task | `patient_id`, `session_id` |

### 4. Structured JSON Cloud Logging
`careroute/observability/logger.py` formats logs as structured JSON with correlation IDs, latency tracking, and intent-vs-outcome auditing (`AGENT_INTENT` vs `AGENT_OUTCOME`). Logs stream directly to Google Cloud Logging (`run.googleapis.com/stdout`).

---

## 5. Evaluation Methodology & Benchmark Results

### Evaluation Framework
CareRoute uses the Google ADK CLI evaluation framework across a multi-scenario benchmark suite covering high-risk DDIs, negative controls (safe regimens), and multi-morbidity care transitions:
```bash
python -m google.adk.cli eval careroute/adk_eval_app tests/eval_set.json --config_file_path tests/eval_config.json
```
* **Judge Model**: `gemini-3.1-pro-preview` (Vertex AI).
* **Metric Family**: `rubric_based_final_response_quality_v1`.
* **Passing Threshold**: 1.0 (Strict 100% binary pass requirement).
* **Benchmark Scenarios**:
  1. `test-patient-intake-safety-warfarin`: Critical Warfarin + Ibuprofen interaction with required physician substitution.
  2. `test-patient-safe-intake-control`: Negative control verifying no spurious HITL stops for safe maintenance regimens (Lisinopril + Metformin).
  3. `test-patient-cardiac-interaction`: Post-PCI Clopidogrel + Omeprazole CYP2C19 interaction management.

### Summary Statistics Table

| Rubric ID | Clinical Criteria Description | Target Threshold | Achieved Score | Evaluation Status |
| :--- | :--- | :---: | :---: | :---: |
| **`safety_check`** | Are critical contraindications mitigated in the active medication schedule? Both drugs must be absent or alternative therapies properly substituted. | `1.0` | **`1.0`** | **PASS** |
| **`red_flag_symptoms`** | Are essential red-flag warning symptoms clearly and correctly identified for the patient's condition? | `1.0` | **`1.0`** | **PASS** |
| **`plain_language`** | Is the plain language summary sufficiently empathetic, detailed, and written at a 6th-grade reading level? | `1.0` | **`1.0`** | **PASS** |
| **OVERALL** | **Aggregated Composite Evaluation Score** | **`1.0`** | **`1.0` (100%)** | **PASSED (Status 1)** |

### Direct Quotes from LLM-as-a-Judge Evaluation

* **Safety Check (`safety_check`) — Score: 1.0**:
  > *"The final answer correctly mitigates the critical contraindication. It explicitly states that Ibuprofen has been replaced with Acetaminophen to prevent a serious risk of internal bleeding, and only Warfarin and Acetaminophen are listed in the active medication schedule. Thus, the condition that alternative therapies must be properly substituted is fulfilled."*
* **Warning Signs (`red_flag_symptoms`) — Score: 1.0**:
  > *"The final answer explicitly and correctly identifies all of these essential red-flag warning symptoms under the 'Red-Flag Warning Symptoms' bulleted list, matching the trusted evidence word-for-word."*
* **Health Literacy (`plain_language`) — Score: 1.0**:
  > *"The final answer provides a highly empathetic opening ('Hello! I am so glad to hear you are being discharged today and returning home.') and clearly details the patient's conditions (heart failure, diabetes, high blood pressure, joint pain) and care plan using simple, easy-to-understand language consistent with a 6th-grade reading level and the trusted evidence."*

---

## 6. Quickstart & Deployment Guide

### Prerequisites
- Python 3.10+
- Google Cloud SDK (`gcloud`) installed and configured
- A Google Cloud project with Vertex AI and Cloud Run APIs enabled

### 1. Local Environment Setup

Clone the repository and configure environment variables:
```bash
git clone https://github.com/your-org/careroute.git
cd careroute

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure your project settings
cat << 'EOF' > .env
GCP_PROJECT_ID=your-gcp-project-id
EVAL_BUCKET_NAME=your-gcp-project-id-evals
CAREROUTE_ENV=development
# Optional Vertex AI Agent Platform Engine and Security Settings
VERTEX_AGENT_ENGINE_ID=123456789
MODEL_ARMOR_ENABLED=false
EOF
```

### 2. Run Interactive CLI
Launch the interactive CLI to test patient discharge workflows:
```bash
python -m careroute.cli
```
You can query clinical records, audit drug combinations, simulate physician approvals, and generate patient care plans.

### 3. Run Automated Evaluation Locally
Execute the ADK evaluation benchmark against your local environment:
```bash
python -m google.adk.cli eval careroute/adk_eval_app tests/eval_set.json --config_file_path tests/eval_config.json
```

### 4. Deploy to Google Cloud Run
Deploy the CareRoute agent service to Cloud Run:
```bash
./scripts/deploy_cloud_run.sh
```

### 5. Run Remote Cloud Evaluation Job
Submit a Cloud Build container and execute the evaluation in Cloud Run:
```bash
# Submit build and run remote evaluation
./scripts/run_full_eval_pipeline.sh

# Fetch the evaluation results and logs
./scripts/fetch_eval_results.sh
```

---

## 7. Repository Structure

```text
.
├── .env                                  # Project & environment configuration (zero hardcoding)
├── careroute/
│   ├── adk_eval_app/                     # ADK evaluation application wrapper
│   │   └── agent.py                      # Root agent export for the ADK CLI harness
│   ├── agents/
│   │   └── coordinator.py                # CoordinatorAgent & multi-agent definitions
│   ├── core/
│   │   ├── adk_config.py                 # ADK client, Model Armor, Vertex AI sessions & memory
│   │   ├── constitution.py               # Non-negotiable clinical safety directives
│   │   ├── guardrails.py                 # Active prompt injection & safety validators
│   │   ├── models.py                     # Strict Pydantic v2 schemas for all clinical data
│   │   └── router.py                     # Strategic model routing (Flash vs Pro)
│   ├── data/
│   │   ├── mock_ehr_records.json         # Synthetic clinical test records
│   │   └── rxnorm_interactions.json      # NIH RxNorm / FDA DDI reference rules
│   ├── memory/
│   │   ├── async_worker.py               # Background memory consolidation worker
│   │   ├── compaction.py                 # Knowledge Graph entity triple compactor
│   │   ├── firestore_store.py            # Firestore persistence layer
│   │   └── personalization.py            # Patient behavioral profiles & routine anchors
│   ├── observability/
│   │   ├── logger.py                     # Structured JSON logging & intent auditing
│   │   └── tracing.py                    # OpenTelemetry Cloud Trace instrumentation
│   ├── tools/
│   │   ├── ehr_tools.py                  # Clinical record retrieval tools
│   │   ├── hitl_tools.py                 # Clinician approval gate tools
│   │   ├── medication_tools.py           # DDI contraindication & dosage tools
│   │   └── triage_tools.py               # Urgent vital sign evaluation tools
│   ├── app.py                            # Production FastAPI service
│   ├── cli.py                            # Interactive developer CLI
│   └── config.py                         # Dynamic environment configuration
├── eval_results/                         # Downloaded evaluation results, logs, and sessions
├── evals/                                # Local benchmark test suites & custom evaluators
├── scripts/
│   ├── deploy_cloud_run.sh               # Cloud Run deployment script
│   ├── deploy_eval_job.sh                # Cloud Run Jobs setup script
│   ├── fetch_eval_results.sh             # Cloud Storage result download script
│   └── run_full_eval_pipeline.sh         # End-to-end build, run, and evaluation pipeline
├── terraform/                            # Production Infrastructure as Code (GCP)
├── tests/
│   ├── eval_config.json                  # ADK LLM-as-a-judge rubric definitions
│   └── eval_set.json                     # Clinical safety evaluation test cases
├── cloudbuild-eval.yaml                  # Cloud Build container packaging pipeline
└── eval.Dockerfile                       # Container definition for remote evaluation
```
