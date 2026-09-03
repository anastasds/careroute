"""Clinical Knowledge Graph with Pharmaceutical Contraindication Seeding for CareRoute.

Builds and traverses an in-memory & persistent entity-relation graph mapping:
- Patients -> Behaviors (e.g. EXHIBITS_BEHAVIOR: forgetfulness, erratic morning routine)
- Patients -> Medications (PRESCRIBED)
- Medications -> Medications (CONTRAINDICATED_WITH, INTERACTS_WITH)
- Medications -> Allergies (CONTRAINDICATED_FOR_ALLERGY)

Supports live querying against Google Cloud Firestore collection 'careroute_contraindications'.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field
from careroute.config import settings
from careroute.core.models import DrugInteractionResult, SeverityLevel
from careroute.data.rxnorm_data import RXNORM_INTERACTIONS_DATA
from careroute.observability.logger import logger


class GraphEntity(BaseModel):
    """An entity node in the Clinical Knowledge Graph."""
    entity_id: str = Field(..., description="Unique entity identifier (e.g. 'DRUG:Warfarin', 'PATIENT:PT-123')")
    entity_type: str = Field(..., description="Type of entity: PATIENT, CONDITION, MEDICATION, ALLERGY, BEHAVIOR")
    label: str = Field(..., description="Human readable label")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Metadata and clinical attributes")


class GraphRelation(BaseModel):
    """A directed edge between two entities in the Clinical Knowledge Graph."""
    source_id: str = Field(..., description="Source entity ID")
    target_id: str = Field(..., description="Target entity ID")
    relation_type: str = Field(..., description="Relation type (e.g., 'CONTRAINDICATED_WITH', 'PRESCRIBED', 'EXHIBITS_BEHAVIOR')")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Clinical severity, mechanism, etc.")


class ClinicalKnowledgeGraph:
    """Clinical knowledge graph seeded from RxNorm and persistent Google Cloud Firestore."""

    def __init__(self, seed_file_path: Optional[str] = None):
        self.nodes: Dict[str, GraphEntity] = {}
        self.edges: List[GraphRelation] = []
        self._firestore_client = None
        self._seed_rxnorm_database(seed_file_path)
        self._init_firestore()

    def _init_firestore(self) -> None:
        """Connects to Google Cloud Firestore if configured."""
        if settings.gcp_project_id:
            try:
                from google.cloud import firestore
                self._firestore_client = firestore.Client(
                    project=settings.gcp_project_id,
                    database=settings.firestore_db
                )
            except Exception:
                pass

    def _seed_rxnorm_database(self, seed_file_path: Optional[str] = None) -> None:
        """Seeds the graph with standard RxNorm and FDA drug-drug contraindications."""
        interactions = RXNORM_INTERACTIONS_DATA

        if seed_file_path and os.path.exists(seed_file_path):
            try:
                with open(seed_file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                interactions = data.get("interactions", RXNORM_INTERACTIONS_DATA)
            except Exception:
                pass

        for item in interactions:
            drug_a = item["drug_a"].strip()
            drug_b = item["drug_b"].strip()
            severity = item.get("severity", SeverityLevel.MAJOR_INTERACTION)
            mechanism = item.get("mechanism", "")
            clinical_risk = item.get("clinical_risk", "")
            recommended_action = item.get("recommended_action", "")
            alternatives = item.get("alternative_therapies", [])

            id_a = f"DRUG:{drug_a.lower()}"
            id_b = f"DRUG:{drug_b.lower()}"

            self.add_entity(id_a, "MEDICATION", drug_a)
            self.add_entity(id_b, "MEDICATION", drug_b)

            # Bi-directional contraindication edge
            self.add_relation(
                source_id=id_a,
                target_id=id_b,
                relation_type="CONTRAINDICATED_WITH",
                properties={
                    "severity": severity,
                    "mechanism": mechanism,
                    "clinical_risk": clinical_risk,
                    "recommended_action": recommended_action,
                    "alternative_therapies": alternatives,
                }
            )
            self.add_relation(
                source_id=id_b,
                target_id=id_a,
                relation_type="CONTRAINDICATED_WITH",
                properties={
                    "severity": severity,
                    "mechanism": mechanism,
                    "clinical_risk": clinical_risk,
                    "recommended_action": recommended_action,
                    "alternative_therapies": alternatives,
                }
            )

        logger.info(f"Successfully seeded Clinical Knowledge Graph with {len(interactions)} RxNorm DDI rules.")

    def add_entity(self, entity_id: str, entity_type: str, label: str, properties: Optional[Dict[str, Any]] = None) -> GraphEntity:
        """Adds or updates a node in the graph."""
        if entity_id not in self.nodes:
            self.nodes[entity_id] = GraphEntity(
                entity_id=entity_id,
                entity_type=entity_type,
                label=label,
                properties=properties or {}
            )
        else:
            if properties:
                self.nodes[entity_id].properties.update(properties)
        return self.nodes[entity_id]

    def add_relation(self, source_id: str, target_id: str, relation_type: str, properties: Optional[Dict[str, Any]] = None) -> GraphRelation:
        """Adds a directed relation edge between two entities."""
        if source_id not in self.nodes:
            self.add_entity(source_id, "UNKNOWN", source_id)
        if target_id not in self.nodes:
            self.add_entity(target_id, "UNKNOWN", target_id)

        for edge in self.edges:
            if edge.source_id == source_id and edge.target_id == target_id and edge.relation_type == relation_type:
                if properties:
                    edge.properties.update(properties)
                return edge

        relation = GraphRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            properties=properties or {}
        )
        self.edges.append(relation)
        return relation

    def find_contraindications(self, active_drugs: List[str]) -> List[DrugInteractionResult]:
        """Queries both in-memory graph and persistent Firestore collection for contraindications."""
        results: List[DrugInteractionResult] = []
        normalized_drugs = [d.strip().lower() for d in active_drugs if d.strip()]
        seen_pairs: Set[Tuple[str, str]] = set()

        for i, drug_a in enumerate(normalized_drugs):
            id_a = f"DRUG:{drug_a}"
            for drug_b in normalized_drugs[i+1:]:
                id_b = f"DRUG:{drug_b}"
                pair_key = tuple(sorted([drug_a, drug_b]))
                if pair_key in seen_pairs:
                    continue

                # 1. Check in-memory seeded graph
                found_in_graph = False
                for edge in self.edges:
                    if edge.source_id == id_a and edge.target_id == id_b and edge.relation_type == "CONTRAINDICATED_WITH":
                        seen_pairs.add(pair_key)
                        found_in_graph = True
                        props = edge.properties
                        results.append(
                            DrugInteractionResult(
                                drug_a=self.nodes.get(id_a, GraphEntity(entity_id="", entity_type="", label=drug_a)).label,
                                drug_b=self.nodes.get(id_b, GraphEntity(entity_id="", entity_type="", label=drug_b)).label,
                                severity=SeverityLevel(props.get("severity", SeverityLevel.MAJOR_INTERACTION)),
                                mechanism=props.get("mechanism", "Pharmacokinetic / Pharmacodynamic clash"),
                                clinical_risk=props.get("clinical_risk", "Adverse clinical effect"),
                                recommended_action=props.get("recommended_action", "Clinical review required"),
                                alternative_therapies=props.get("alternative_therapies", [])
                            )
                        )
                        break

                # 2. Check Firestore collection if not found in memory
                if not found_in_graph and self._firestore_client:
                    try:
                        doc_id = f"{drug_a}_{drug_b}"
                        doc = self._firestore_client.collection("careroute_contraindications").document(doc_id).get()
                        if doc.exists:
                            seen_pairs.add(pair_key)
                            data = doc.to_dict()
                            results.append(
                                DrugInteractionResult(
                                    drug_a=data.get("drug_a", drug_a),
                                    drug_b=data.get("drug_b", drug_b),
                                    severity=SeverityLevel(data.get("severity", SeverityLevel.MAJOR_INTERACTION)),
                                    mechanism=data.get("mechanism", ""),
                                    clinical_risk=data.get("clinical_risk", ""),
                                    recommended_action=data.get("recommended_action", ""),
                                    alternative_therapies=data.get("alternative_therapies", [])
                                )
                            )
                    except Exception:
                        pass

        return results

    def get_patient_graph_summary(self, patient_id: str) -> Dict[str, Any]:
        """Returns all connected entities and relations for a given patient."""
        patient_node_id = f"PATIENT:{patient_id}"
        connected_edges = [
            e for e in self.edges if e.source_id == patient_node_id or e.target_id == patient_node_id
        ]
        connected_node_ids = set()
        for e in connected_edges:
            connected_node_ids.add(e.source_id)
            connected_node_ids.add(e.target_id)

        return {
            "patient_id": patient_id,
            "entities": [self.nodes[nid].model_dump() for nid in connected_node_ids if nid in self.nodes],
            "relations": [e.model_dump() for e in connected_edges],
        }


# Singleton knowledge graph instance
knowledge_graph = ClinicalKnowledgeGraph()
