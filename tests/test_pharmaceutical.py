"""Unit tests for RxNorm Pharmaceutical Database and Knowledge Graph Contraindication Seeding."""

import pytest
from careroute.core.models import SeverityLevel
from careroute.memory.knowledge_graph import ClinicalKnowledgeGraph, knowledge_graph


def test_rxnorm_seeding_nodes_and_edges():
    """Validates that RxNorm clinical interactions were seeded properly into the Knowledge Graph."""
    assert len(knowledge_graph.nodes) >= 10
    assert len(knowledge_graph.edges) >= 10

    # Ensure Warfarin and Ibuprofen nodes exist
    assert "DRUG:warfarin" in knowledge_graph.nodes
    assert "DRUG:ibuprofen" in knowledge_graph.nodes


def test_critical_contraindication_warfarin_ibuprofen():
    """Validates that Warfarin + Ibuprofen triggers a CRITICAL_CONTRAINDICATION with mechanism."""
    interactions = knowledge_graph.find_contraindications(["Warfarin", "Ibuprofen", "Metformin"])
    assert len(interactions) >= 1

    crit = [i for i in interactions if i.severity == SeverityLevel.CRITICAL_CONTRAINDICATION]
    assert len(crit) == 1
    assert "bleeding" in crit[0].clinical_risk.lower() or "hemorrhage" in crit[0].clinical_risk.lower()
    assert "Acetaminophen" in crit[0].alternative_therapies


def test_major_interaction_lisinopril_spironolactone():
    """Validates detection of Lisinopril + Spironolactone hyperkalemia interaction."""
    interactions = knowledge_graph.find_contraindications(["Lisinopril", "Spironolactone"])
    assert len(interactions) == 1
    assert interactions[0].severity == SeverityLevel.MAJOR_INTERACTION
    assert "hyperkalemia" in interactions[0].clinical_risk.lower()


def test_safe_regimen_no_contraindications():
    """Validates that safe, non-interacting medications return an empty contraindication list."""
    interactions = knowledge_graph.find_contraindications(["Acetaminophen", "Amoxicillin", "Loratadine"])
    assert len(interactions) == 0

