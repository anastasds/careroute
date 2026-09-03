"""Embedded clinical drug-drug interactions dataset for CareRoute."""

from typing import Any, Dict, List

RXNORM_INTERACTIONS_DATA: List[Dict[str, Any]] = [
    {
        "interaction_id": "DDI-001",
        "drug_a": "Warfarin",
        "drug_b": "Ibuprofen",
        "severity": "CRITICAL_CONTRAINDICATION",
        "mechanism": "NSAIDs inhibit platelet aggregation and cause gastric mucosal damage, synergistically increasing major gastrointestinal hemorrhage and bleeding risk when combined with oral anticoagulants.",
        "clinical_risk": "Severe, life-threatening internal or GI bleeding.",
        "recommended_action": "Avoid co-administration. Substitute Ibuprofen with Acetaminophen (Tylenol) for mild-to-moderate analgesia, limiting to max 2g/day with INR monitoring.",
        "alternative_therapies": ["Acetaminophen", "Topical Lidocaine", "Physical therapy"]
    },
    {
        "interaction_id": "DDI-002",
        "drug_a": "Warfarin",
        "drug_b": "Aspirin",
        "severity": "CRITICAL_CONTRAINDICATION",
        "mechanism": "Dual antiplatelet and anticoagulant effect dramatically elevates major bleeding risk unless specifically indicated under specialist cardiology supervision (e.g. post-PCI).",
        "clinical_risk": "Major intracranial and gastrointestinal hemorrhage.",
        "recommended_action": "Discontinue concurrent OTC Aspirin unless explicitly prescribed with gastric protection (PPI).",
        "alternative_therapies": ["Acetaminophen", "Consult Cardiologist"]
    },
    {
        "interaction_id": "DDI-003",
        "drug_a": "Metformin",
        "drug_b": "Iodinated Contrast",
        "severity": "CRITICAL_CONTRAINDICATION",
        "mechanism": "Intravascular iodinated contrast media can lead to acute renal impairment, precipitating toxic accumulation of Metformin and triggering fatal lactic acidosis.",
        "clinical_risk": "Metformin-associated lactic acidosis (MALA), metabolic shock.",
        "recommended_action": "Withhold Metformin 48 hours prior to and 48 hours after contrast imaging. Verify eGFR before resumption.",
        "alternative_therapies": ["Short-term sliding scale insulin during contrast procedure window"]
    },
    {
        "interaction_id": "DDI-004",
        "drug_a": "Lisinopril",
        "drug_b": "Spironolactone",
        "severity": "MAJOR_INTERACTION",
        "mechanism": "Simultaneous inhibition of the renin-angiotensin-aldosterone system by ACE inhibitors and potassium-sparing diuretics reduces renal potassium excretion.",
        "clinical_risk": "Severe, life-threatening hyperkalemia and cardiac dysrhythmias.",
        "recommended_action": "Monitor serum potassium and renal function (eGFR/Cr) within 1 week of co-initiation; adjust dosage if serum K+ > 5.0 mEq/L.",
        "alternative_therapies": ["Loop diuretics (e.g. Furosemide)", "Non-potassium sparing anti-hypertensives"]
    },
    {
        "interaction_id": "DDI-005",
        "drug_a": "Fluoxetine",
        "drug_b": "Phenelzine",
        "severity": "CRITICAL_CONTRAINDICATION",
        "mechanism": "Co-administration of SSRIs and MAO inhibitors causes massive accumulation of serotonin at the synaptic cleft.",
        "clinical_risk": "Serotonin Syndrome (hyperthermia, autonomic instability, neuromuscular rigidity, death).",
        "recommended_action": "Strictly contraindicated. Require at least a 5-week washout period after stopping Fluoxetine before starting an MAOI.",
        "alternative_therapies": ["Monotherapy optimization under psychiatrist supervision"]
    },
    {
        "interaction_id": "DDI-006",
        "drug_a": "Simvastatin",
        "drug_b": "Clarithromycin",
        "severity": "CRITICAL_CONTRAINDICATION",
        "mechanism": "Clarithromycin is a potent CYP3A4 inhibitor that increases plasma concentrations of Simvastatin by over 10-fold.",
        "clinical_risk": "Severe rhabdomyolysis, myoglobinuria, and acute kidney failure.",
        "recommended_action": "Temporarily suspend Simvastatin during the course of Clarithromycin, or substitute with Azithromycin (non-CYP3A4 inhibitor).",
        "alternative_therapies": ["Azithromycin", "Rosuvastatin / Pravastatin (at reduced dose)"]
    },
    {
        "interaction_id": "DDI-007",
        "drug_a": "Digoxin",
        "drug_b": "Amiodarone",
        "severity": "MAJOR_INTERACTION",
        "mechanism": "Amiodarone inhibits P-glycoprotein efflux pump, doubling serum Digoxin concentrations.",
        "clinical_risk": "Digoxin toxicity (lethal ventricular arrhythmias, heart block, visual disturbances).",
        "recommended_action": "Reduce Digoxin dose by 50% immediately upon initiating Amiodarone; monitor serum digoxin levels.",
        "alternative_therapies": ["Dose reduction of Digoxin", "Alternative rate control agents"]
    },
    {
        "interaction_id": "DDI-008",
        "drug_a": "Clopidogrel",
        "drug_b": "Omeprazole",
        "severity": "MAJOR_INTERACTION",
        "mechanism": "Omeprazole competitive inhibition of CYP2C19 prevents bioactivation of Clopidogrel prodrug into active antiplatelet metabolite.",
        "clinical_risk": "Reduced antiplatelet efficacy; increased risk of stent thrombosis and ischemic stroke.",
        "recommended_action": "Switch PPI from Omeprazole to Pantoprazole (minimal CYP2C19 inhibition) or H2-blocker (Famotidine).",
        "alternative_therapies": ["Pantoprazole", "Famotidine"]
    },
    {
        "interaction_id": "DDI-009",
        "drug_a": "Methotrexate",
        "drug_b": "Naproxen",
        "severity": "MAJOR_INTERACTION",
        "mechanism": "NSAIDs decrease renal clearance of Methotrexate by inhibiting renal prostaglandin synthesis and tubular secretion.",
        "clinical_risk": "Severe bone marrow suppression, leukopenia, and hepatotoxicity.",
        "recommended_action": "Avoid high-dose Methotrexate combination; use lowest effective NSAID dose under close hematologic monitoring.",
        "alternative_therapies": ["Acetaminophen", "Corticosteroid bridge under rheumatologist guidance"]
    },
    {
        "interaction_id": "DDI-010",
        "drug_a": "Ciprofloxacin",
        "drug_b": "Amiodarone",
        "severity": "CRITICAL_CONTRAINDICATION",
        "mechanism": "Additive prolongation of the cardiac ventricular repolarization (QT interval).",
        "clinical_risk": "Torsades de pointes, fatal ventricular fibrillation.",
        "recommended_action": "Avoid concurrent use. Use alternative class antibiotic (e.g. Amoxicillin-clavulanate or Doxycycline).",
        "alternative_therapies": ["Amoxicillin-clavulanate", "Doxycycline", "Ceftriaxone"]
    },
    {
        "interaction_id": "DDI-011",
        "drug_a": "Atorvastatin",
        "drug_b": "Grapefruit Juice",
        "severity": "MODERATE_INTERACTION",
        "mechanism": "Intestinal CYP3A4 inhibition increases systemic bioavailability of Atorvastatin.",
        "clinical_risk": "Increased risk of myopathy, muscle soreness, elevated liver transaminases.",
        "recommended_action": "Limit grapefruit / grapefruit juice intake to occasional small amounts or avoid completely.",
        "alternative_therapies": ["Switch to Rosuvastatin or Pravastatin if patient regularly consumes grapefruit"]
    },
    {
        "interaction_id": "DDI-012",
        "drug_a": "Metronidazole",
        "drug_b": "Alcohol",
        "severity": "MAJOR_INTERACTION",
        "mechanism": "Inhibition of aldehyde dehydrogenase results in accumulation of toxic acetaldehyde.",
        "clinical_risk": "Disulfiram-like reaction: severe nausea, vomiting, flushing, tachycardia, hypotension.",
        "recommended_action": "Strictly avoid all alcohol and alcohol-containing medications during treatment and for 48 hours following completion.",
        "alternative_therapies": ["Total alcohol abstinence"]
    }
]

