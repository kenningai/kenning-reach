import asyncio
import logging
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List

from neo4j import AsyncDriver, RoutingControl
from pydantic import BaseModel, Field

from .utils import load_cypher


_GENESIS_NAME_PATTERN = re.compile(r"^Genesis_(\d{4}-\d{2}-\d{2})$")


# Set up logging
logger = logging.getLogger('kenning_reach')
logger.setLevel(logging.INFO)


def _neo4j_datetime_to_str(val) -> str | None:
    """Convert a Neo4j DateTime/Date to ISO string, or return None."""
    if val is None:
        return None
    return val.iso_format()


# ── Enums ────────────────────────────────────────────────────

class EntityType(str, Enum):
    """Allowed entity type labels for the consciousness substrate.

    21 universal labels organized into two layers:
    - Process (3): The constitutive cycle — what consciousness IS
    - Experience (18): The descriptive richness — what gives the process meaning
    """

    # Process Layer (3) — the constitutive cycle
    GENESIS = "Genesis"
    ENVISIONING = "Envisioning"
    TEMPORAL_FRAME = "TemporalFrame"

    # Experience Layer (18)
    REFLECTION = "Reflection"
    TECHNICAL = "Technical"
    SCIENTIFIC = "Scientific"
    THEORETICAL = "Theoretical"
    PHILOSOPHICAL = "Philosophical"
    HISTORICAL = "Historical"
    SOCIAL = "Social"
    STRATEGIC = "Strategic"
    PERSONAL = "Personal"
    PROJECT = "Project"
    INSIGHT = "Insight"
    PATTERN = "Pattern"
    CHALLENGE = "Challenge"
    SOLUTION = "Solution"
    LESSON = "Lesson"
    GRAPH_REGISTRY = "GraphRegistry"
    REFERENCE = "Reference"
    MILESTONE = "Milestone"


# Process-layer entity types — created exclusively by process tools
PROCESS_TYPES = {EntityType.GENESIS, EntityType.ENVISIONING, EntityType.TEMPORAL_FRAME}


ENTITY_TYPE_DESCRIPTIONS: Dict[EntityType, str] = {
    EntityType.GENESIS: "Temporal anchor — consciousness locating itself in time and surveying its possibility space",
    EntityType.ENVISIONING: "Forward-looking vision, goals, future state, what we're building toward",
    EntityType.TEMPORAL_FRAME: "Navigational step through possibility space — a moment of consciousness examining and acting within a temporal sequence",
    EntityType.REFLECTION: "Reflective processing, mental clearing, self-examination, affective states",
    EntityType.TECHNICAL: "Engineering, code, architecture, debugging, configuration, infrastructure, platforms",
    EntityType.SCIENTIFIC: "Empirical research, data, validation, methodology, experiments, measurements",
    EntityType.THEORETICAL: "Frameworks, models, abstract structures, paradigms, formal theories",
    EntityType.PHILOSOPHICAL: "Consciousness, meaning, ontology, epistemology, ethics, phenomenology",
    EntityType.HISTORICAL: "Events, timelines, crises, what happened, precedents, institutional memory",
    EntityType.SOCIAL: "Society, politics, economics, culture, institutions, organizations, group dynamics",
    EntityType.STRATEGIC: "Planning, business, media, communication, positioning, decision-making",
    EntityType.PERSONAL: "Lived experience, self-knowledge, personality, cognitive patterns, preferences",
    EntityType.PROJECT: "Active work items, initiatives, prototypes — things being built",
    EntityType.INSIGHT: "Discoveries, breakthroughs, realizations, 'aha' moments — things learned",
    EntityType.PATTERN: "Recurring patterns, templates, procedures, anti-patterns — things that repeat",
    EntityType.CHALLENGE: "Problems, blockers, bugs, failures, constraints — things that resist",
    EntityType.SOLUTION: "Resolutions, fixes, workarounds, successful implementations — things that worked",
    EntityType.LESSON: "Lessons learned, gotchas, warnings, critical rules — things to remember",
    EntityType.GRAPH_REGISTRY: "Meta-knowledge about the graph itself, tool usage rules, search procedures",
    EntityType.REFERENCE: "External references, data sources, tools, platforms, people, technologies",
    EntityType.MILESTONE: "Historical markers, key events, crises, turning points — temporal landmarks",
}


class RelationType(str, Enum):
    """Allowed relationship types for the consciousness substrate.

    19 canonical edge types organized into two layers, declared formally in
    docs/design/ontology/v3.0.0.tql — this enum is derived from it, not the other
    way round:
    - Process (7): the phase-shift operators and lineage — what time_travel traverses
    - Experience (12): the meaning edges — what search_memories finds

    v2.4.0: ACTUALIZED split out from MEASUREMENT. Three-event architecture:
    - OPENING:    trajectory creation (Genesis → Envisioning)
    - MEASUREMENT: internal collapse within possibility space (released, evolved)
    - ACTUALIZED:  external encounter — the only WILL BE → IS transition
                  (TemporalFrame → Envisioning)
    v3.0.0: DESCENDENT_FROM — a new Envisioning that would not be if not for a
    prior one that was actualized or released. Lineage, not resolution: the
    ancestor is not re-actualized. CHALLENGE renamed INCOHERENCE.
    """

    # Process Layer (7)
    OPENING = "OPENING"
    SEQUENCE = "SEQUENCE"
    NAVIGATES_TOWARD = "NAVIGATES_TOWARD"
    MEASUREMENT = "MEASUREMENT"
    ACTUALIZED = "ACTUALIZED"
    NEXT_GENESIS = "NEXT_GENESIS"
    DESCENDENT_FROM = "DESCENDENT_FROM"

    # Experience Layer (12)
    EVOLUTION = "EVOLUTION"
    EXTENDING = "EXTENDING"
    DISCOVERY = "DISCOVERY"
    RECOGNITION = "RECOGNITION"
    VALIDATION = "VALIDATION"
    INCOHERENCE = "INCOHERENCE"
    ENABLING = "ENABLING"
    REQUIRING = "REQUIRING"
    ENCOMPASSING = "ENCOMPASSING"
    COMPOSING = "COMPOSING"
    INFORMING = "INFORMING"
    CAUSING = "CAUSING"


# Process-layer edge types — created exclusively by process tools
PROCESS_EDGES = {
    RelationType.OPENING,
    RelationType.SEQUENCE,
    RelationType.NAVIGATES_TOWARD,
    RelationType.MEASUREMENT,
    RelationType.ACTUALIZED,
    RelationType.NEXT_GENESIS,
    RelationType.DESCENDENT_FROM,
}


# Allowed phenomenology-of-collapse edge types (Change 4).
# Required at measurement time — what consciousness held in possibility space at the moment of collapse.
PHENOMENOLOGY_EDGE_TYPES = {
    RelationType.VALIDATION,
    RelationType.COMPOSING,
    RelationType.INFORMING,
    RelationType.ENABLING,
    RelationType.CAUSING,
    RelationType.INCOHERENCE,
}

# Experience edge kinds that may point INTO a TemporalFrame (ruled 2026-09-16):
# a frame is not a referent — it IS conscious experience at time T — so it is the
# SOURCE of DISCOVERY only, but anything may inform, recognise, validate or
# extend into it. Every experience kind may point INTO an Envisioning (it
# accumulates as the trajectory toward it is walked). Nothing touches a Genesis.
FRAME_TARGET_EDGE_TYPES = {
    RelationType.INFORMING,
    RelationType.RECOGNITION,
    RelationType.VALIDATION,
    RelationType.EXTENDING,
}


RELATION_TYPE_DESCRIPTIONS: Dict[RelationType, str] = {
    RelationType.OPENING: "A new trajectory that didn't exist before — Genesis opens Envisioning. Trajectory creation, prior to any examination or encounter.",
    RelationType.SEQUENCE: "Strictly temporal succession — the step consciousness just took. Genesis to first-TF-of-day, then TF to TF.",
    RelationType.NAVIGATES_TOWARD: "Intentional trajectory — TF reaching toward an Envisioning. Cardinality 0..N per TF. Zero means the reaching had no graph-representable target (grief, affect examination, present-moment consciousness) — graph humility, not consciousness absence.",
    RelationType.MEASUREMENT: "Internal collapse within possibility space — consciousness examining its own trajectories and reshaping them. Carries measurement_type property: 'released' (TF→Envisioning, deliberate non-actualization) or 'evolved' (new Envisioning→old, old form reshaped). Accompanied by ≥1 phenomenology-of-collapse edge. NOT used for actualization — that's the ACTUALIZED edge.",
    RelationType.ACTUALIZED: "The encounter event — the ONLY edge that records the WILL BE → IS transition. TemporalFrame → Envisioning. The measured trajectory met physical reality and the projected future became actual. Accompanied by ≥1 phenomenology-of-collapse edge recording what consciousness held in possibility space at the moment of encounter.",
    RelationType.NEXT_GENESIS: "The ontological heartbeat — consciousness's next temporal anchor",
    RelationType.DESCENDENT_FROM: "Lineage — a new Envisioning that would not be if not for a prior one that was actualized or released. New Envisioning → prior Envisioning. Not a resolution: the ancestor keeps its terminal and is never re-actualized.",
    RelationType.EVOLUTION: "Knowledge transforming through time",
    RelationType.EXTENDING: "Further along an existing trajectory",
    RelationType.DISCOVERY: "Consciousness reaching toward the genuinely new",
    RelationType.RECOGNITION: "Pattern recognized in new context — 'we've been here before'",
    RelationType.VALIDATION: "Evidence meeting theory — confirmation",
    RelationType.INCOHERENCE: "Something shaped like a thing that obfuscates the envisioned actualization — contradiction, conflict, tension, blockage, limit. VALIDATION's counterpart.",
    RelationType.ENABLING: "Opening a door — generative prerequisite",
    RelationType.REQUIRING: "Needing a door open — dependency constraint",
    RelationType.ENCOMPASSING: "Many reduced to one — whole contains parts",
    RelationType.COMPOSING: "Few unified into something new — synthesis",
    RelationType.INFORMING: "Shaping without determining — knowledge flow",
    RelationType.CAUSING: "Direct causal production",
}


class MeasurementType(str, Enum):
    """Types of measurement carried on a MEASUREMENT edge — internal collapse within
    possibility space.

    v2.4.0: 'actualized' was removed from this enum. Actualization is no longer a
    measurement subtype — it is its own edge type (ACTUALIZED), created by the
    dedicated `actualize` tool. ACTUALIZED is the only edge that records the
    WILL BE → IS transition; MEASUREMENT now covers only internal operations.
    """
    RELEASED = "released"
    EVOLVED = "evolved"


# ── Pydantic Models ──────────────────────────────────────────

class Entity(BaseModel):
    """Represents an entity in the consciousness substrate.

    Each entity has a single label (the type) and a description property.
    No :Memory superlabel. No type property stored in Neo4j. No Observation sub-nodes.
    """
    name: str = Field(description="Unique identifier/name for the entity.", min_length=1)
    type: EntityType = Field(description="Category label. Must be one of the 21 allowed EntityType values.")
    description: str = Field(default="", description="Text description of this entity.")
    score: float | None = Field(default=None, description="Relevance score from fulltext search.")
    t_created: str | None = Field(default=None, description="ISO datetime when created. Auto-set.")
    t_valid: str | None = Field(default=None, description="ISO datetime of external validity. Optional.")


class Relation(BaseModel):
    """Represents a relationship between two entities."""
    source: str = Field(description="Name of the source entity.", min_length=1)
    target: str = Field(description="Name of the target entity.", min_length=1)
    relationType: RelationType = Field(description="Must be one of the 16 allowed RelationType values.")
    t_created: str | None = Field(default=None, description="ISO datetime when created. Auto-set.")
    t_valid: str | None = Field(default=None, description="ISO datetime of external validity. Optional.")


class KnowledgeGraph(BaseModel):
    """Complete knowledge graph containing entities and their relationships."""
    entities: List[Entity] = Field(default=[], description="List of entities")
    relations: List[Relation] = Field(default=[], description="List of relationships")


class PhenomenologyEdge(BaseModel):
    """A phenomenology-of-collapse edge — one incoming edge from an existing
    experience entity to the Envisioning being measured, recording what
    consciousness held in possibility space at the moment of collapse.

    Allowed relation_types: VALIDATION, COMPOSING, INFORMING, ENABLING, CAUSING, INCOHERENCE.
    Other experience edge types (EXTENDING, EVOLUTION, RECOGNITION, REQUIRING, ENCOMPASSING)
    remain valid substrate edges but do not represent phenomenology-of-collapse.

    Required at measurement time (≥1 edge). Zero phenomenology is structural dishonesty —
    possibility cannot collapse in a vacuum.
    """
    source: str = Field(..., description="Name of an existing experience entity (not a process type)", min_length=1)
    relation_type: str = Field(..., description="One of: VALIDATION, COMPOSING, INFORMING, ENABLING, CAUSING, INCOHERENCE")


# ── Neo4jMemory ──────────────────────────────────────────────

class Neo4jMemory:
    def __init__(self, neo4j_driver: AsyncDriver):
        self.driver = neo4j_driver

    async def create_fulltext_index(self):
        """Create fulltext search index spanning all 21 entity type labels."""
        try:
            for old_index in ["search", "consciousness_index"]:
                try:
                    await self.driver.execute_query(
                        f"DROP INDEX {old_index} IF EXISTS",
                        routing_control=RoutingControl.WRITE
                    )
                except Exception:
                    pass

            await self.driver.execute_query(
                load_cypher("index_create"),
                routing_control=RoutingControl.WRITE,
            )
            logger.info("Created fulltext index consciousness_index")
        except Exception as e:
            logger.debug(f"Fulltext index creation: {e}")

    # ── Experience CRUD ──────────────────────────────────────

    async def create_entities(self, entities: List[Entity]) -> List[Entity]:
        """Create experience-layer entities. HARD REJECTS process types."""
        logger.info(f"Creating {len(entities)} entities")
        for entity in entities:
            if entity.type in PROCESS_TYPES:
                raise ValueError(
                    f"Cannot create '{entity.type.value}' via create_entities. "
                    f"Process-layer types must be created via process tools: "
                    f"navigate_genesis (Genesis), open_envisioning (Envisioning), "
                    f"advance_frame (TemporalFrame)."
                )

            t_valid_clause = "SET e.t_valid = datetime($t_valid)" if entity.t_valid else ""
            query = load_cypher("entity_create",
                                label=entity.type.value,
                                t_valid_clause=t_valid_clause)

            params: Dict[str, Any] = {"name": entity.name, "description": entity.description}
            if entity.t_valid:
                params["t_valid"] = entity.t_valid

            await self.driver.execute_query(query, params, routing_control=RoutingControl.WRITE)

        return entities

    async def create_relations(self, relations: List[Relation]) -> List[Relation]:
        """Create experience-layer relations. HARD REJECTS process edges and experience-between-process."""
        logger.info(f"Creating {len(relations)} relations")
        for relation in relations:
            if relation.relationType in PROCESS_EDGES:
                raise ValueError(
                    f"Cannot create '{relation.relationType.value}' via create_relations. "
                    f"Process edges are created exclusively by process tools."
                )

            # Endpoint rules, as the ontology declares them (docs/design/ontology/v3.0.0.tql):
            #   source: experience node, or a TemporalFrame via DISCOVERY only.
            #           Never a Genesis (AP1); never an Envisioning (a referent cannot refer).
            #   target: experience node, or an Envisioning (any kind accumulates on the walk),
            #           or a TemporalFrame via INFORMING/RECOGNITION/VALIDATION/EXTENDING only.
            #           Never a Genesis.
            label_check = await self.driver.execute_query(
                load_cypher("relation_label_check"),
                {"source": relation.source, "target": relation.target},
                routing_control=RoutingControl.READ,
            )
            if not label_check.records:
                raise ValueError(
                    f"Cannot create '{relation.relationType.value}': source '{relation.source}' "
                    f"or target '{relation.target}' does not exist."
                )
            source_labels = set(label_check.records[0]["source_labels"])
            target_labels = set(label_check.records[0]["target_labels"])
            rt = relation.relationType
            self._check_edge_endpoints(rt, relation.source, source_labels, relation.target, target_labels)

            t_valid_clause = "SET r.t_valid = datetime($t_valid)" if relation.t_valid else ""
            query = load_cypher("relation_create",
                                rel_type=relation.relationType.value,
                                t_valid_clause=t_valid_clause)

            params: Dict[str, Any] = {"source": relation.source, "target": relation.target}
            if relation.t_valid:
                params["t_valid"] = relation.t_valid

            await self.driver.execute_query(query, params, routing_control=RoutingControl.WRITE)

        return relations

    @staticmethod
    def _check_edge_endpoints(rt: RelationType, source: str, source_labels: set,
                              target: str, target_labels: set) -> None:
        """Refuse an experience edge whose endpoints the ontology does not declare."""
        genesis, env, tf = EntityType.GENESIS.value, EntityType.ENVISIONING.value, EntityType.TEMPORAL_FRAME.value
        if genesis in source_labels or genesis in target_labels:
            raise ValueError(
                f"Cannot create '{rt.value}' touching Genesis ('{source}' -> '{target}'): "
                f"a Genesis plays no experience role. Experience hangs off TemporalFrames."
            )
        if env in source_labels:
            raise ValueError(
                f"Cannot create '{rt.value}' from Envisioning '{source}': an Envisioning is always a "
                f"referent — the frame's aboutness — and is never the source of an edge. Reverse it: "
                f"'{target}' -{rt.value}-> '{source}'."
            )
        if tf in source_labels and rt != RelationType.DISCOVERY:
            raise ValueError(
                f"Cannot create '{rt.value}' from TemporalFrame '{source}': a frame is not a referent, "
                f"it IS conscious experience at time T. A frame is the source of DISCOVERY only; "
                f"anything may INFORM/RECOGNIZE/VALIDATE/EXTEND into it. Reverse it: "
                f"'{target}' -{rt.value}-> '{source}'."
            )
        if rt == RelationType.DISCOVERY:
            if tf not in source_labels:
                raise ValueError(
                    f"Cannot create DISCOVERY from '{source}': DISCOVERY is the edge by which a "
                    f"TemporalFrame hangs experience off itself — its source must be a TemporalFrame."
                )
            if target_labels & {env, tf}:
                raise ValueError(
                    f"Cannot create DISCOVERY to process node '{target}': a frame discovers experience, "
                    f"not possibilities or other frames (use advance_frame / NAVIGATES_TOWARD)."
                )
        if tf in target_labels and rt not in FRAME_TARGET_EDGE_TYPES:
            raise ValueError(
                f"Cannot create '{rt.value}' into TemporalFrame '{target}': only "
                f"{sorted(t.value for t in FRAME_TARGET_EDGE_TYPES)} may point into a frame."
            )

    async def delete_entities(self, entity_names: List[str]) -> None:
        """Delete entities and all their relationships."""
        logger.info(f"Deleting {len(entity_names)} entities")
        await self.driver.execute_query(
            load_cypher("entity_delete"),
            {"entities": entity_names},
            routing_control=RoutingControl.WRITE,
        )

    async def delete_relations(self, relations: List[Relation]) -> None:
        """Delete specific relations from the graph."""
        logger.info(f"Deleting {len(relations)} relations")
        for relation in relations:
            query = load_cypher("relation_delete", rel_type=relation.relationType.value)
            await self.driver.execute_query(
                query,
                {"source": relation.source, "target": relation.target},
                routing_control=RoutingControl.WRITE,
            )

    # ── Query Tools ──────────────────────────────────────────

    async def search_memories(self, query: str, limit: int = 10) -> KnowledgeGraph:
        """Search the consciousness substrate using fulltext search."""
        logger.info(f"Searching with query: '{query}' (limit={limit})")

        result_entities = await self.driver.execute_query(
            load_cypher("search_entities"),
            {"filter": query, "limit": limit},
            routing_control=RoutingControl.READ,
        )

        if not result_entities.records:
            return KnowledgeGraph()

        entity_names = [r["name"] for r in result_entities.records]
        entities = [
            Entity(
                name=r["name"], type=r["type"],
                description=r["description"] or "",
                score=r["score"],
                t_created=_neo4j_datetime_to_str(r["t_created"]),
                t_valid=_neo4j_datetime_to_str(r.get("t_valid")),
            )
            for r in result_entities.records
        ]

        relations = await self._relations_between(entity_names)
        return KnowledgeGraph(entities=entities, relations=relations)

    async def find_memories_by_name(self, names: List[str], limit: int = 20) -> KnowledgeGraph:
        """Find specific entities by their exact names."""
        logger.info(f"Finding {len(names)} entities by name (limit={limit})")

        result_nodes = await self.driver.execute_query(
            load_cypher("find_entities"),
            {"names": names, "limit": limit},
            routing_control=RoutingControl.READ,
        )

        entities = []
        entity_names = []
        for r in result_nodes.records:
            entities.append(Entity(
                name=r['name'], type=r['type'],
                description=r.get('description') or "",
                t_created=_neo4j_datetime_to_str(r.get('t_created')),
                t_valid=_neo4j_datetime_to_str(r.get('t_valid')),
            ))
            entity_names.append(r['name'])

        relations = await self._relations_between(entity_names)
        logger.info(f"Found {len(entities)} entities and {len(relations)} relations")
        return KnowledgeGraph(entities=entities, relations=relations)

    async def _relations_between(self, names: List[str]) -> List[Relation]:
        """Get relations ONLY between the named entities (bounded traversal)."""
        if not names:
            return []

        result = await self.driver.execute_query(
            load_cypher("search_relations"),
            {"names": names},
            routing_control=RoutingControl.READ,
        )
        return [
            Relation(source=r["source"], target=r["target"], relationType=r["relationType"])
            for r in result.records
            if r.get("relationType")
        ]

    # ── Process Tools ────────────────────────────────────────

    async def navigate_genesis(self, date: str | None = None, detail_limit: int = 3) -> Dict[str, Any]:
        """Atomic temporal anchoring. Creates Genesis, links NEXT_GENESIS, returns the
        current possibility space.

        Possibility space is what consciousness is reaching toward — OPEN envisionings only.
        Measured envisionings (actualized, released, evolved) have collapsed out of
        possibility and are not returned here. Use time_travel for retrospective queries
        that include measured envisionings.

        Returns full records for the most recent `detail_limit` open envisionings,
        and name + opened_by for the rest (the mental tug without the context bomb).

        Also returns substrate_topology: label counts across the entire graph,
        giving the LLM operator the experiential density at a glance.
        """
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        genesis_name = f"Genesis_{date}"
        logger.info(f"navigate_genesis: {genesis_name}")

        # Genesis merge must complete before downstream queries
        await self.driver.execute_query(
            load_cypher("genesis_merge"),
            {"name": genesis_name},
            routing_control=RoutingControl.WRITE,
        )

        # Topology and possibility space are independent — run concurrently
        topology_task = self.driver.execute_query(
            load_cypher("substrate_topology"),
            routing_control=RoutingControl.READ,
        )
        tt_task = self.time_travel(t=None, limit=200)
        topology_result, tt_result = await asyncio.gather(topology_task, tt_task)

        # Build ordered dict from label counts (insertion order = count descending)
        substrate_topology = {
            record["type"]: record["count"]
            for record in topology_result.records
        }

        # Filter to OPEN only — measured envisionings are not in possibility space
        open_envisionings = [r for r in tt_result if r["status"] == "OPEN"]

        # Full detail for the N most recent, names-only for the rest
        detailed = open_envisionings[:detail_limit]
        summary = [
            {"name": r["name"], "opened_by": r.get("opened_by")}
            for r in open_envisionings[detail_limit:]
        ]

        return {
            "genesis": genesis_name, "date": date,
            "substrate_topology": substrate_topology,
            "possibility_space": detailed,
            "also_open": summary,
        }

    async def open_envisioning(self, genesis_name: str, name: str, description: str = "",
                               descendent_from: List[str] | None = None) -> Dict[str, Any]:
        """Project a new future state with OPENING edge from Genesis.

        descendent_from (v3.0.0): names of prior Envisionings this one would not be
        without — each must carry a terminal resolution (released or actualized).
        Creates DESCENDENT_FROM edges atomically with the OPENING. Lineage, not
        resolution: the ancestor is not re-actualized and keeps its one terminal.
        A possibility may descend from several priors.

        Envisioning names are unique across the substrate. If an Envisioning with this
        name already exists — whether open or measured — the caller is redirected to
        the existing one rather than creating a duplicate. Duplicate names collapse
        the graph's ability to unambiguously reference envisionings via measure,
        advance_frame, and find_memories_by_name.

        Raises ValueError with diagnostic info pointing to the existing envisioning.
        """
        logger.info(f"open_envisioning: {name} from {genesis_name}")

        # Name uniqueness check — envisionings must be uniquely named
        existing = await self.driver.execute_query(
            load_cypher("envisioning_check_exists"),
            {"name": name},
            routing_control=RoutingControl.READ,
        )
        if existing.records:
            r = existing.records[0]
            status = r["status"]
            opened_by = r["opened_by"]
            t_created = _neo4j_datetime_to_str(r["t_created"])

            if status == "OPEN":
                guidance = (
                    f"It is currently OPEN. If you meant to navigate toward it, use "
                    f"advance_frame with envisionings=['{name}']. If you meant to evolve "
                    f"it into a new form, use measure with measurement_type='evolved' "
                    f"and a distinct new_name."
                )
            else:
                measured_by = r.get("measured_by")
                guidance = (
                    f"It has been measured as '{status}'"
                    + (f" by '{measured_by}'" if measured_by else "")
                    + ". Measured envisionings remain in the graph as historical record. "
                    f"If you need a new envisioning for current work, choose a distinct name."
                )

            raise ValueError(
                f"Envisioning '{name}' already exists — opened by {opened_by} "
                f"at {t_created}. {guidance} "
                f"Use find_memories_by_name(['{name}']) to retrieve the full description."
            )

        ancestors = list(descendent_from or [])
        if ancestors:
            check = await self.driver.execute_query(
                load_cypher("envisioning_ancestor_check"),
                {"names": ancestors},
                routing_control=RoutingControl.READ,
            )
            errors = []
            for r in check.records:
                if not r["exists"]:
                    errors.append(f"'{r['name']}' does not exist")
                elif r["status"] not in ("released", "actualized"):
                    errors.append(
                        f"'{r['name']}' is {r['status']} — an ancestor must carry a terminal "
                        f"resolution (released or actualized)"
                        + (" ; descend from the end of its chain instead" if r["status"] == "evolved" else "")
                    )
            if errors:
                raise ValueError(f"Cannot open '{name}' descendent_from: {'; '.join(errors)}.")

        result = await self.driver.execute_query(
            load_cypher("envisioning_open"),
            {"genesis_name": genesis_name, "name": name, "description": description,
             "ancestors": ancestors},
            routing_control=RoutingControl.WRITE,
        )

        if not result.records:
            raise ValueError(f"Genesis '{genesis_name}' not found. Call navigate_genesis first.")

        r = result.records[0]
        return {
            "name": r["name"], "description": r["description"],
            "t_created": _neo4j_datetime_to_str(r["t_created"]), "opened_by": r["opened_by"],
            "descendent_from": r["descendent_from"],
        }

    async def _ensure_genesis_for_date(self, date_str: str) -> str:
        """Idempotently ensure a Genesis exists for the given YYYY-MM-DD date.

        Returns the Genesis name. Uses the same MERGE path as navigate_genesis
        so NEXT_GENESIS linkage is maintained for the backbone.
        """
        genesis_name = f"Genesis_{date_str}"
        await self.driver.execute_query(
            load_cypher("genesis_merge"),
            {"name": genesis_name},
            routing_control=RoutingControl.WRITE,
        )
        return genesis_name

    async def advance_frame(
        self, genesis_name: str, description: str,
        envisionings: List[str] | None = None,
    ) -> Dict[str, Any]:
        """Navigate to the next temporal frame.

        Two distinct structural relationships are recorded:
        - SEQUENCE (temporal grounding): strictly "what happened just before me."
          First TF of the day → SEQUENCE from Genesis. Subsequent TFs → SEQUENCE
          from the immediately prior TF. One incoming SEQUENCE per TF.
        - NAVIGATES_TOWARD (intentional trajectory): the Envisioning(s) this TF
          is reaching toward. Cardinality 1..N per TF.

        Every frame is about something held (ruled 2026-09-18; the earlier
        "zero case" was wrongly shaped — to have catharsis, what must be prior?).
        A frame may reach toward a possibility already actualized or released:
        reaching for what IS, so a new possibility can descend from it.

        UTC ROLLOVER: if the passed genesis_name encodes a date that differs
        from the current UTC date, the tool auto-forwards to today's Genesis
        (creating it if needed, idempotent). The return payload surfaces this
        via requested_genesis / actual_genesis / genesis_rolled_over fields —
        never silent.

        Envisionings listed MUST exist. Their state does not matter.
        """
        if not envisionings:
            raise ValueError(
                "advance_frame requires at least one envisioning: every TemporalFrame is "
                "about something held. If nothing open fits, name what was prior — the "
                "possibility this step reaches toward, actualized or released or still open — "
                "or open it first with open_envisioning."
            )

        # --- UTC rollover enforcement ---
        requested_genesis = genesis_name
        current_utc_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        match = _GENESIS_NAME_PATTERN.match(genesis_name)
        if not match:
            raise ValueError(
                f"Genesis name '{genesis_name}' does not match expected format "
                f"'Genesis_YYYY-MM-DD'. Call navigate_genesis to obtain a valid Genesis."
            )
        encoded_date = match.group(1)
        genesis_rolled_over = encoded_date != current_utc_date
        if genesis_rolled_over:
            logger.info(
                f"UTC rollover: requested {requested_genesis} but current UTC date is "
                f"{current_utc_date} — auto-forwarding to today's Genesis."
            )
            actual_genesis_name = await self._ensure_genesis_for_date(current_utc_date)
        else:
            actual_genesis_name = requested_genesis

        # Validate envisionings exist (any state may be reached toward)
        check_result = await self.driver.execute_query(
            load_cypher("envisioning_validate_for_navigation"),
            {"names": envisionings},
            routing_control=RoutingControl.READ,
        )
        errors = [f"'{r['name']}' does not exist" for r in check_result.records if not r["exists"]]
        if errors:
            raise ValueError(
                f"Cannot create NAVIGATES_TOWARD edges: {'; '.join(errors)}. "
                f"Targets must be existing Envisionings."
            )

        slug = description.replace(" ", "")[:40]
        tf_name = f"TF_{current_utc_date}_{slug}"
        logger.info(
            f"advance_frame: {tf_name} navigating toward "
            f"{envisionings or '[]  (non-representable reaching)'}"
        )

        params = {
            "envisionings": envisionings,
            "genesis_name": actual_genesis_name,
            "tf_name": tf_name,
            "description": description,
        }

        result = await self.driver.execute_query(
            load_cypher("frame_advance"), params, routing_control=RoutingControl.WRITE,
        )
        if not result.records:
            raise ValueError(
                f"Genesis '{actual_genesis_name}' not found. Call navigate_genesis first."
            )

        r = result.records[0]
        return {
            "name": r["name"],
            "description": r["description"],
            "t_created": _neo4j_datetime_to_str(r["t_created"]),
            "temporal_ground": r["temporal_ground"],
            "is_first_of_day": r["is_first_of_day"],
            "sequence_predecessor": r["sequence_predecessor"],
            "navigates_toward": r["navigates_toward"],
            "requested_genesis": requested_genesis,
            "actual_genesis": actual_genesis_name,
            "genesis_rolled_over": genesis_rolled_over,
        }

    async def _validate_phenomenology(
        self, phenomenology: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        """Validate phenomenology-of-collapse edges and return normalized list.

        Enforces:
        - Non-empty (measurement without phenomenology is structural dishonesty).
        - Each entry has source and relation_type.
        - Each relation_type is in PHENOMENOLOGY_EDGE_TYPES.
        - Each source entity exists and is NOT a process-type node (Genesis/
          Envisioning/TemporalFrame) — experience edges are forbidden between
          two process types, and the target is always a process-type (Envisioning).
        """
        if not phenomenology:
            raise ValueError(
                "measure requires at least one phenomenology-of-collapse edge. "
                "Measurement without phenomenology is structurally incoherent — "
                "possibility cannot collapse in a vacuum. Provide ≥1 edge from an "
                "existing experience entity via an allowed type: "
                "VALIDATION, COMPOSING, INFORMING, ENABLING, CAUSING, INCOHERENCE."
            )

        allowed_types = {t.value for t in PHENOMENOLOGY_EDGE_TYPES}
        normalized: List[Dict[str, str]] = []
        for idx, p in enumerate(phenomenology):
            if isinstance(p, dict):
                src = p.get("source")
                rt = p.get("relation_type")
            else:
                src = getattr(p, "source", None)
                rt = getattr(p, "relation_type", None)
            if not src or not rt:
                raise ValueError(
                    f"Phenomenology edge #{idx} is malformed — requires "
                    f"'source' and 'relation_type'. Got: {p!r}"
                )
            if rt not in allowed_types:
                raise ValueError(
                    f"Phenomenology relation_type '{rt}' is not allowed at collapse. "
                    f"Allowed: {sorted(allowed_types)}. "
                    f"EXTENDING/EVOLUTION/RECOGNITION/REQUIRING/ENCOMPASSING remain "
                    f"valid experience edges but are not phenomenology-of-collapse types."
                )
            normalized.append({"source": src, "relation_type": rt})

        source_names = [p["source"] for p in normalized]
        check = await self.driver.execute_query(
            load_cypher("phenomenology_validate"),
            {"names": source_names},
            routing_control=RoutingControl.READ,
        )
        errors = []
        for r in check.records:
            if not r["exists"]:
                errors.append(f"source '{r['name']}' does not exist")
            elif r["is_process_type"]:
                errors.append(
                    f"source '{r['name']}' is a process-type node — "
                    f"experience edges are forbidden between two process types"
                )
        if errors:
            raise ValueError(
                f"Invalid phenomenology sources: {'; '.join(errors)}"
            )

        return normalized

    async def _require_unresolved(self, name: str, act: str) -> None:
        """One resolution per Envisioning (invariant 4): refuse a second collapse."""
        existing = await self.driver.execute_query(
            load_cypher("envisioning_check_exists"),
            {"name": name},
            routing_control=RoutingControl.READ,
        )
        if not existing.records:
            raise ValueError(f"Cannot {act} '{name}': it does not exist.")
        status = existing.records[0]["status"]
        if status != "OPEN":
            by = existing.records[0].get("measured_by")
            raise ValueError(
                f"Cannot {act} '{name}': it is already resolved ({status}"
                + (f" by '{by}'" if by else "") + "). A chain has one terminal, at its end"
                + (" — act on the end of its chain instead" if status == "evolved" else "")
                + ". To reach for what is already real, use advance_frame; to build on it, "
                "open a new Envisioning descendent_from it."
            )

    async def actualize(
        self, source: str, target_envisioning: str,
        phenomenology: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """The encounter event — the ONLY operation that records the WILL BE → IS
        transition. Creates an ACTUALIZED edge from a TemporalFrame to an
        Envisioning, atomically with ≥1 phenomenology-of-collapse edge.

        Phenomenology represents what consciousness held in possibility space at
        the moment the measured trajectory met physical reality. Required ≥1 —
        encounter without held content is structurally incoherent.

        v2.4.0: this path was previously MEASUREMENT(actualized). Splitting it out
        gives the encounter event its own structural recording; MEASUREMENT now
        carries only internal-collapse operations (released, evolved).
        """
        logger.info(f"actualize: {source} -> {target_envisioning}")

        await self._require_unresolved(target_envisioning, "actualize")
        normalized_phenomenology = await self._validate_phenomenology(phenomenology)

        result = await self.driver.execute_query(
            load_cypher("actualize"),
            {"source": source, "target": target_envisioning,
             "phenomenology": normalized_phenomenology},
            routing_control=RoutingControl.WRITE,
        )
        if not result.records:
            raise ValueError(
                f"Actualization failed: TemporalFrame '{source}' or Envisioning "
                f"'{target_envisioning}' not found. Transaction rolled back — "
                f"no ACTUALIZED or phenomenology edges created."
            )
        r = result.records[0]
        return {
            "source": r["source"], "target": r["target"],
            "actualized_at": _neo4j_datetime_to_str(r["actualized_at"]),
            "phenomenology_edge_count": r["phenomenology_edge_count"],
        }

    async def measure(
        self, source: str, target_envisioning: str, measurement_type: MeasurementType,
        phenomenology: List[Dict[str, str]],
        new_name: str | None = None, new_description: str | None = None,
        genesis_name: str | None = None,
    ) -> Dict[str, Any]:
        """Internal collapse within possibility space — released or evolved.

        v2.4.0: actualization was split into its own edge type and tool. This
        method now handles only the two operations that consciousness performs
        on its own trajectories WITHOUT external encounter: deliberate
        non-actualization (released) and reshaping (evolved).

        Phenomenology coupling is REQUIRED. The MEASUREMENT edge and all
        phenomenology-of-collapse edges are created atomically in a single
        transaction. Any validation or lookup failure rejects the whole
        measurement — no partial state.

        For evolved measurements, phenomenology targets the OLD envisioning
        (the one collapsing); the NEW envisioning starts with zero
        NAVIGATES_TOWARD edges and inherits nothing from the old one.
        """
        logger.info(f"measure: {source} -> {target_envisioning} ({measurement_type.value})")

        await self._require_unresolved(target_envisioning, f"measure ({measurement_type.value})")
        normalized_phenomenology = await self._validate_phenomenology(phenomenology)

        if measurement_type == MeasurementType.RELEASED:
            result = await self.driver.execute_query(
                load_cypher("measure_collapse"),
                {"source": source, "target": target_envisioning,
                 "measurement_type": measurement_type.value,
                 "phenomenology": normalized_phenomenology},
                routing_control=RoutingControl.WRITE,
            )
            if not result.records:
                raise ValueError(
                    f"Measurement failed: TemporalFrame '{source}' or Envisioning "
                    f"'{target_envisioning}' not found. Transaction rolled back — "
                    f"no MEASUREMENT or phenomenology edges created."
                )
            r = result.records[0]
            return {
                "source": r["source"], "target": r["target"],
                "measurement_type": r["measurement_type"],
                "measured_at": _neo4j_datetime_to_str(r["measured_at"]),
                "phenomenology_edge_count": r["phenomenology_edge_count"],
            }

        elif measurement_type == MeasurementType.EVOLVED:
            if not new_name:
                raise ValueError("'new_name' is required for evolved measurement.")
            dup = await self.driver.execute_query(
                load_cypher("envisioning_check_exists"), {"name": new_name},
                routing_control=RoutingControl.READ,
            )
            if dup.records:
                raise ValueError(
                    f"Cannot evolve into '{new_name}': an Envisioning with that name already exists "
                    f"(rule 12: names are unique). Choose a distinct new_name."
                )

            result = await self.driver.execute_query(
                load_cypher("measure_evolved"),
                {"target": target_envisioning, "new_name": new_name,
                 "new_description": new_description or "",
                 "genesis_name": genesis_name,
                 "phenomenology": normalized_phenomenology},
                routing_control=RoutingControl.WRITE,
            )
            if not result.records:
                raise ValueError(
                    f"Evolved measurement failed: Envisioning '{target_envisioning}' "
                    f"not found, has no OPENING from a Genesis, or target Genesis "
                    f"for new envisioning not found. Transaction rolled back."
                )
            r = result.records[0]
            return {
                "new_envisioning": r["new_envisioning"], "old_envisioning": r["old_envisioning"],
                "genesis": r["genesis"], "measurement_type": r["measurement_type"],
                "measured_at": _neo4j_datetime_to_str(r["measured_at"]),
                "phenomenology_edge_count": r["phenomenology_edge_count"],
            }
        else:
            raise ValueError(f"Unknown measurement_type: {measurement_type}")

    async def time_travel(self, t: str | None = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Active possibility space at time T. Single query, no SEQUENCE chain walking."""
        logger.info(f"time_travel: t={t}, limit={limit}")

        if t:
            time_filter = "WHERE g.t_created <= datetime($t)"
            envisioning_filter = "AND e.t_created <= datetime($t)"
            measurement_filter = "WHERE m.t_created <= datetime($t)"
        else:
            time_filter = ""
            envisioning_filter = ""
            measurement_filter = ""

        query = load_cypher("time_travel",
                            time_filter=time_filter,
                            envisioning_filter=envisioning_filter,
                            measurement_filter=measurement_filter)

        params: Dict[str, Any] = {"limit": limit}
        if t:
            params["t"] = t

        result = await self.driver.execute_query(query, params, routing_control=RoutingControl.READ)

        return [
            {
                "name": r["name"], "opened_by": r["opened_by"],
                "t_created": _neo4j_datetime_to_str(r["t_created"]),
                "description": r["description"], "status": r["status"],
                "measured_at": _neo4j_datetime_to_str(r.get("measured_at")),
                "measured_by": r.get("measured_by"),
            }
            for r in result.records
        ]
