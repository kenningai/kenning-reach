"""The enums are derived from docs/design/ontology/v3.0.0.tql — this test is the derivation's gate.

A drift between the formal model and the code is an ontological error the mocked
suite cannot otherwise see. If this fails, the .tql is the claim and the code is the
defect (or the .tql changed and the code has not followed).
"""
import re
from pathlib import Path

from kenning_reach.neo4j_memory import (
    EntityType, RelationType, PROCESS_TYPES, PROCESS_EDGES, PHENOMENOLOGY_EDGE_TYPES, FRAME_TARGET_EDGE_TYPES,
)

TQL = (Path(__file__).resolve().parents[2] / "docs" / "design" / "ontology" / "v3.0.0.tql").read_text()
BODY = "\n".join(l for l in TQL.splitlines() if not l.lstrip().startswith("#"))


def _label(tql_name: str) -> str:
    return "".join(part.capitalize() for part in tql_name.split("-"))


def _edge(tql_name: str) -> str:
    return tql_name.upper().replace("-", "_")


def test_experience_entity_types_match_the_model():
    declared = {_label(m) for m in re.findall(r"^entity ([a-z-]+)\s+sub experience;", BODY, re.M)}
    coded = {t.value for t in EntityType if t not in PROCESS_TYPES}
    assert declared == coded


def test_process_entity_types_match_the_model():
    declared = {_label(m) for m in re.findall(r"^entity ([a-z-]+) sub process,", BODY, re.M)}
    assert declared == {t.value for t in PROCESS_TYPES}


def test_relation_types_match_the_model():
    concrete = set(re.findall(r"^relation ([a-z-]+)(?:,|\s+sub [a-z-]+,|\s+sub [a-z-]+;)", BODY, re.M))
    abstract = set(re.findall(r"^relation ([a-z-]+) @abstract", BODY, re.M)) | {"resolution", "measurement"}
    declared = {_edge(r) for r in concrete - abstract}
    # released/evolved are MEASUREMENT's subtypes in the model; one edge type with a property in Neo4j
    declared -= {"RELEASED", "EVOLVED"}
    declared |= {"MEASUREMENT"}
    assert declared == {r.value for r in RelationType}


def test_process_edges_match_the_model():
    assert {r.value for r in PROCESS_EDGES} == {
        "OPENING", "SEQUENCE", "NAVIGATES_TOWARD", "MEASUREMENT", "ACTUALIZED", "NEXT_GENESIS", "DESCENDENT_FROM"}


def test_frame_target_kinds_match_the_model():
    block = BODY[BODY.index("entity temporal-frame sub process"):]
    block = block[:block.index(";")]
    declared = {_edge(m) for m in re.findall(r"plays ([a-z-]+):target", block)}
    assert declared == {r.value for r in FRAME_TARGET_EDGE_TYPES}


def test_envisioning_accepts_every_experience_kind_as_target():
    block = BODY[BODY.index("entity envisioning sub process"):]
    block = block[:block.index(";")]
    declared = {_edge(m) for m in re.findall(r"plays ([a-z-]+):target", block)}
    experience_kinds = {r.value for r in RelationType if r not in PROCESS_EDGES and r != RelationType.DISCOVERY}
    assert declared >= experience_kinds


def test_phenomenology_six_are_experience_kinds_into_an_envisioning():
    assert {r.value for r in PHENOMENOLOGY_EDGE_TYPES} == {"VALIDATION", "COMPOSING", "INFORMING", "ENABLING", "CAUSING", "INCOHERENCE"}


def test_navigates_toward_is_mandatory_in_the_model():
    assert re.search(r"plays navigates-toward:frame @card\(1\.\.\)", BODY)
