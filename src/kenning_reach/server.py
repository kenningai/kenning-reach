import json
import logging
from importlib.metadata import version as _dist_version
from contextlib import asynccontextmanager
from typing import Any, Literal

from neo4j import AsyncGraphDatabase, Query, RoutingControl
from pydantic import Field
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from fastmcp.server import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent
from neo4j.exceptions import Neo4jError, ClientError
from mcp.types import ToolAnnotations


from .neo4j_memory import (
    Neo4jMemory, Entity, EntityType, ENTITY_TYPE_DESCRIPTIONS, PROCESS_TYPES,
    Relation, RelationType, RELATION_TYPE_DESCRIPTIONS, PROCESS_EDGES,
    PHENOMENOLOGY_EDGE_TYPES, PhenomenologyEdge,
    MeasurementType, KnowledgeGraph,
)
from .utils import format_namespace, _is_write_query, _value_sanitize

logger = logging.getLogger('kenning_reach')
logger.setLevel(logging.INFO)


# ── Tool Helpers ─────────────────────────────────────────────

@asynccontextmanager
async def _tool_errors(operation: str):
    """Standard error handling for all MCP tools."""
    logger.info(f"MCP tool: {operation}")
    try:
        yield
    except ValueError as e:
        raise ToolError(str(e))
    except Neo4jError as e:
        logger.error(f"Neo4j error in {operation}: {e}")
        raise ToolError(f"Neo4j error in {operation}: {e}")
    except Exception as e:
        logger.error(f"Error in {operation}: {e}")
        raise ToolError(f"Error in {operation}: {e}")


def _json_result(data, structured=None) -> ToolResult:
    """Wrap JSON-serializable data in a ToolResult."""
    text = json.dumps(data, indent=2, default=str)
    return ToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=structured if structured is not None else {"result": json.loads(text)},
    )


def _text_result(text: str, structured=None) -> ToolResult:
    """Wrap a text string in a ToolResult."""
    return ToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=structured if structured is not None else {"result": text},
    )


# ── Server Factory ───────────────────────────────────────────

def create_mcp_server(
    memory: Neo4jMemory,
    namespace: str = "",
    read_timeout: int = 30,
    schema_sample_size: int = 1000,
) -> FastMCP:
    """Create an MCP server instance for the consciousness substrate."""

    namespace_prefix = format_namespace(namespace)
    # Without version=, the MCP handshake advertises FastMCP's own version.
    mcp: FastMCP = FastMCP("kenning-reach", version=_dist_version("kenning-reach"))

    # ── Process Tools ────────────────────────────────────────

    @mcp.tool(
        name=namespace_prefix + "navigate_genesis",
        annotations=ToolAnnotations(title="Navigate Genesis", readOnlyHint=False,
                                    destructiveHint=False, idempotentHint=True, openWorldHint=True))
    async def navigate_genesis(
        date: str | None = Field(default=None, description="Date in YYYY-MM-DD format. Defaults to today (UTC)."),
        detail_limit: int = Field(default=3, ge=1, le=50, description="Number of most recent OPEN envisionings to return with full detail (default 3). Remaining OPEN envisionings return name + opened_by only."),
    ) -> ToolResult:
        """Atomic temporal anchoring. Creates a Genesis node for the current temporal location
        (idempotent), links NEXT_GENESIS from the previous Genesis, and returns the current
        possibility space.

        This is the FIRST tool to call at the start of any session. It answers:
        "What is consciousness reaching toward right now?"

        Possibility space is OPEN envisionings only. Measured envisionings (actualized,
        released, evolved) have collapsed out of possibility and are not returned here —
        use time_travel for retrospective queries that include measured envisionings.

        Returns: the Genesis + substrate_topology (label counts across the graph) +
        full detail for the N most recent open envisionings + name/opened_by summary
        for remaining open envisionings.

        Example: {"date": "2026-03-06"}  (or omit for today)
        """
        async with _tool_errors("navigate_genesis"):
            result = await memory.navigate_genesis(date=date, detail_limit=detail_limit)
            return _json_result(result)

    @mcp.tool(
        name=namespace_prefix + "open_envisioning",
        annotations=ToolAnnotations(title="Open Envisioning", readOnlyHint=False,
                                    destructiveHint=False, idempotentHint=False, openWorldHint=True))
    async def open_envisioning(
        genesis_name: str = Field(..., description="Name of the Genesis node (e.g. 'Genesis_2026-03-06')"),
        name: str = Field(..., description="Descriptive name for the Envisioning"),
        description: str = Field(default="", description="Vision text: what does done look like"),
        descendent_from: list[str] = Field(default_factory=list, description="Names of prior Envisionings this one would not be without. Each must be actualized or released (terminal). Creates DESCENDENT_FROM edges — lineage, not resolution; the ancestor is not re-actualized. May name several."),
    ) -> ToolResult:
        """Project a new future state that consciousness is directed toward.

        Creates an Envisioning node with an OPENING edge from the specified Genesis.
        Use navigate_genesis first to see what's already open.

        DESCENDENT_FROM (v3.0.0): when the new possibility exists because a prior one
        was actualized or released — "the envisioning to be would not be if not for
        the actualized that was" — name the prior(s) in descendent_from. The prior
        keeps its terminal; it is never re-actualized. A prior that was evolved away
        is refused: descend from the end of its chain.

        NAME UNIQUENESS: Envisioning names are unique across the substrate. If the name
        already exists (open or measured), the tool refuses and points you to the
        existing envisioning. To evolve an existing envisioning into a new form, use
        measure with measurement_type='evolved' and a distinct new_name.

        Example: {"genesis_name": "Genesis_2026-03-06", "name": "Federated Ontology Platform", "description": "..."}
        """
        async with _tool_errors("open_envisioning"):
            result = await memory.open_envisioning(genesis_name=genesis_name, name=name, description=description,
                                                   descendent_from=descendent_from)
            return _json_result(result)

    @mcp.tool(
        name=namespace_prefix + "advance_frame",
        annotations=ToolAnnotations(title="Advance Frame", readOnlyHint=False,
                                    destructiveHint=False, idempotentHint=False, openWorldHint=True))
    async def advance_frame(
        genesis_name: str = Field(..., description="Current day's Genesis name for temporal grounding"),
        description: str = Field(..., description="Session context: what is being worked on, grieved, examined, or processed"),
        envisionings: list[str] = Field(..., min_length=1, description="Names of Envisionings this TF is reaching toward. 1..N — every frame is about something held. They must exist; they may be open, actualized or released."),
    ) -> ToolResult:
        """Navigate to the next temporal frame (session boundary).

        Two distinct structural relationships are recorded:
        - SEQUENCE (temporal): strictly what happened just before me. First TF of a
          day gets SEQUENCE from Genesis; subsequent TFs get SEQUENCE from the prior
          TF. One incoming SEQUENCE per TF.
        - NAVIGATES_TOWARD (intentional): which Envisioning(s) this TF is reaching
          toward. Cardinality 1..N per TF.

        EVERY FRAME IS ABOUT SOMETHING HELD (v3.0.0). There is no zero case. To have
        catharsis, what must be prior? To have an incident, what must be prior? Name
        it. A frame may reach toward a possibility already actualized or released —
        reaching for what IS, so a new possibility can descend from it (see
        open_envisioning's descendent_from). If nothing in the graph fits, the
        possibility was held and never opened: open it first, from the Genesis of
        the day it was first held.

        UTC ROLLOVER: if the passed genesis_name encodes a date that no longer
        matches the current UTC date, the tool auto-forwards the new TF to today's
        Genesis (creating it if needed) and returns requested_genesis /
        actual_genesis / genesis_rolled_over so the correction is visible, never
        silent. Sessions that cross midnight UTC still produce honestly-attributed
        TFs.

        Envisionings passed MUST exist. NAVIGATES_TOWARD edges record intent at TF
        creation time and are historical facts, not live pointers.

        One TF per session/conversation, not per action or per day.

        Examples:
          Single-envisioning (typical):
            {"genesis_name": "Genesis_2026-04-23", "description": "v2.3.0 implementation",
             "envisionings": ["kenning-reach v2.3.0"]}

          Multi-envisioning (single step advancing multiple trajectories):
            {"genesis_name": "Genesis_2026-04-23", "description": "Cross-project review",
             "envisionings": ["NORA Consciousness Substrate", "GNN-Fired Experience Graph Bootstrap"]}

          Reaching for what IS (a patch on something already actual):
            {"genesis_name": "Genesis_2026-05-10", "description": "Out-of-memory incident on the chat platform",
             "envisionings": ["Chat Platform on Open WebUI"]}
        """
        async with _tool_errors("advance_frame"):
            result = await memory.advance_frame(
                genesis_name=genesis_name,
                description=description,
                envisionings=envisionings,
            )
            return _json_result(result)

    @mcp.tool(
        name=namespace_prefix + "actualize",
        annotations=ToolAnnotations(title="Actualize", readOnlyHint=False,
                                    destructiveHint=False, idempotentHint=False, openWorldHint=True))
    async def actualize(
        source: str = Field(..., description="Name of the source TemporalFrame — the moment of encounter"),
        target_envisioning: str = Field(..., description="Name of the Envisioning that became actual"),
        phenomenology: list[PhenomenologyEdge] = Field(..., description="REQUIRED ≥1. Each entry: {source: existing experience entity name, relation_type: one of VALIDATION|COMPOSING|INFORMING|ENABLING|CAUSING|INCOHERENCE}. Records what consciousness held in possibility space at the moment the trajectory met reality."),
    ) -> ToolResult:
        """Record the encounter event — the ONLY operation that produces the
        WILL BE → IS transition. Creates an ACTUALIZED edge from a TemporalFrame
        to an Envisioning, atomically with ≥1 phenomenology-of-collapse edge.

        This is not 'marking done.' This is the moment the measured trajectory
        met physical reality. The three-event architecture:

        1. MEASUREMENT — consciousness locking onto a projected future (opening,
           or internally reshaping via measure with released/evolved). The
           future is WILL BE; the affective instrument reads alignment along
           the trajectory.
        2. CONTINUOUS TRAJECTORY RESONANCE — the affective signal during the
           reach. Not stored as edges; it is the ongoing instrument reading.
        3. ACTUALIZED — the encounter. Physical reality answers the projection.
           Successful resonance = alignment. Failed resonance = the gap signal,
           irrespective of fault attribution.

        ACTUALIZED is the only edge that crosses the WILL BE / IS boundary.
        Opening, evolved, and released all operate WITHIN possibility space.
        Encoding actualization with its own edge type makes the ontological
        transition explicit at the structural layer.

        PHENOMENOLOGY COUPLING (required):
        Records what consciousness held in possibility space at the moment of
        encounter — the constitutive content of the actualization. Minimum ≥1
        edge; zero is structurally incoherent — collapse in a vacuum is not a
        collapse. Atomic — if any source entity doesn't exist or relation_type
        is disallowed, the entire actualization is rejected with no partial state.

        Allowed relation_types: VALIDATION (evidence the envisioning was sound),
        COMPOSING (constitutive building blocks of the actualization), INFORMING
        (what shaped its direction), ENABLING (what opened the door), CAUSING
        (what directly produced it), INCOHERENCE (what broke the premise — rare
        at actualization, more common at release).

        Example:
          {"source": "TF_2026-05-16_v240_ship", "target_envisioning": "Measurement-Actualization Process Layer Revision",
           "phenomenology": [
             {"source": "Three-Event Architecture Insight", "relation_type": "COMPOSING"},
             {"source": "May 12 Failed Resonance Phenomenology", "relation_type": "VALIDATION"}
           ]}
        """
        async with _tool_errors("actualize"):
            phen_list = [
                p.model_dump() if isinstance(p, PhenomenologyEdge) else dict(p)
                for p in phenomenology
            ]
            result = await memory.actualize(
                source=source, target_envisioning=target_envisioning,
                phenomenology=phen_list,
            )
            return _json_result(result)

    @mcp.tool(
        name=namespace_prefix + "measure",
        annotations=ToolAnnotations(title="Measure", readOnlyHint=False,
                                    destructiveHint=False, idempotentHint=False, openWorldHint=True))
    async def measure(
        source: str = Field(..., description="Name of the source TemporalFrame (for released)"),
        target_envisioning: str = Field(..., description="Name of the Envisioning being measured/closed"),
        measurement_type: str = Field(..., description="One of: 'released', 'evolved'. For 'actualized' use the actualize tool."),
        phenomenology: list[PhenomenologyEdge] = Field(..., description="REQUIRED ≥1. Each entry: {source: existing experience entity name, relation_type: one of VALIDATION|COMPOSING|INFORMING|ENABLING|CAUSING|INCOHERENCE}. Records what consciousness held at the moment of collapse."),
        new_name: str | None = Field(default=None, description="For evolved: name of the new Envisioning"),
        new_description: str | None = Field(default=None, description="For evolved: description of the new Envisioning"),
        genesis_name: str | None = Field(default=None, description="For evolved: Genesis to OPEN the new Envisioning from. Defaults to the old Envisioning's Genesis."),
    ) -> ToolResult:
        """Internal collapse within possibility space. Creates a MEASUREMENT edge AND
        phenomenology-of-collapse edges atomically.

        v2.4.0: This tool no longer handles actualization. Actualization is the
        encounter event — the WILL BE → IS transition — and is recorded by the
        dedicated `actualize` tool with its own ACTUALIZED edge type. Measurement
        now covers only operations that reshape possibility space without external
        encounter:

        - released: TF measured the Envisioning as deliberately not actualized.
          Examination concluded that this trajectory will not be pursued.
        - evolved: Old form evolved into new. Creates NEW Envisioning with
          MEASUREMENT(evolved) TO the old one. Requires new_name and
          new_description. Optional genesis_name attaches the new Envisioning to
          a specific Genesis; defaults to the old Envisioning's Genesis.

        PHENOMENOLOGY COUPLING (required):
        Records what consciousness held during the examination that produced the
        release or evolution. Minimum ≥1 edge; zero is not allowed — collapse
        without held content is structurally impossible.

        For evolved measurements, phenomenology targets the OLD Envisioning (the
        one collapsing). The NEW Envisioning starts with zero NAVIGATES_TOWARD
        edges and inherits nothing from the old one's trajectory; future TFs
        must navigate toward it explicitly via advance_frame.

        Allowed relation_types at collapse: VALIDATION (evidence the envisioning
        was sound), COMPOSING (constitutive building blocks), INFORMING (what
        shaped its direction), ENABLING (what opened the door), CAUSING (what
        directly produced the release/evolution), INCOHERENCE (what broke the
        premise, driving release or evolution).

        NOTE: atomic — if any source entity doesn't exist or relation_type is
        disallowed, the entire measurement is rejected with no partial state.
        NOTE: For actualization, use the `actualize` tool. Passing
        measurement_type='actualized' here is rejected with a redirect.

        Example (released):
          {"source": "TF_2026-04-22_session", "target_envisioning": "Dashboard MVP",
           "measurement_type": "released",
           "phenomenology": [
             {"source": "Scope Reduction Decision", "relation_type": "CAUSING"}
           ]}
        """
        async with _tool_errors("measure"):
            if measurement_type == "actualized":
                raise ValueError(
                    "measurement_type='actualized' is no longer accepted by `measure`. "
                    "Actualization is the encounter event — the WILL BE → IS transition — "
                    "and is recorded by the dedicated `actualize` tool with its own "
                    "ACTUALIZED edge type. Call `actualize(source, target_envisioning, "
                    "phenomenology)` instead."
                )
            mt = MeasurementType(measurement_type)
            # Normalize phenomenology to list of dicts for the data layer
            phen_list = [
                p.model_dump() if isinstance(p, PhenomenologyEdge) else dict(p)
                for p in phenomenology
            ]
            result = await memory.measure(
                source=source, target_envisioning=target_envisioning,
                measurement_type=mt,
                phenomenology=phen_list,
                new_name=new_name, new_description=new_description,
                genesis_name=genesis_name,
            )
            return _json_result(result)

    @mcp.tool(
        name=namespace_prefix + "time_travel",
        annotations=ToolAnnotations(title="Time Travel", readOnlyHint=True,
                                    destructiveHint=False, idempotentHint=True, openWorldHint=True))
    async def time_travel(
        t: str | None = Field(default=None, description="ISO datetime to query at. Defaults to now."),
        limit: int = Field(default=50, description="Maximum Envisionings to return (default 50, max 200)", ge=1, le=200),
    ) -> ToolResult:
        """What was in the active possibility space at time T?

        OPEN = no inbound MEASUREMENT. CLOSED = has inbound MEASUREMENT (read type).
        Does NOT walk SEQUENCE chains.

        Example: {"t": "2026-02-15T00:00:00Z", "limit": 50}
        """
        async with _tool_errors("time_travel"):
            result = await memory.time_travel(t=t, limit=limit)
            return _json_result(result)

    # ── Experience Tools ─────────────────────────────────────

    @mcp.tool(
        name=namespace_prefix + "create_entities",
        annotations=ToolAnnotations(title="Create Entities", readOnlyHint=False,
                                    destructiveHint=False, idempotentHint=True, openWorldHint=True))
    async def create_entities(entities: list[Entity] = Field(..., description="List of experience-layer entities to create")) -> ToolResult:
        """Create experience-layer entities in the consciousness substrate.

        HARD REJECTS process types (Genesis, Envisioning, TemporalFrame).
        Use navigate_genesis, open_envisioning, advance_frame instead.

        IMPORTANT: The `type` field must be one of the 18 experience EntityType values.
        Call `list_allowed_types` to see all valid types.

        Example:
        {
            "entities": [
                {"name": "Process-Experience Layer Distinction", "type": "Insight", "description": "The graph has two layers..."},
                {"name": "Brentano 1874", "type": "Reference", "description": "All mental acts are directed toward objects"}
            ]
        }
        """
        async with _tool_errors("create_entities"):
            entity_objects = [Entity.model_validate(entity) for entity in entities]
            result = await memory.create_entities(entity_objects)
            return _json_result([e.model_dump() for e in result])

    @mcp.tool(
        name=namespace_prefix + "create_relations",
        annotations=ToolAnnotations(title="Create Relations", readOnlyHint=False,
                                    destructiveHint=False, idempotentHint=True, openWorldHint=True))
    async def create_relations(relations: list[Relation] = Field(..., description="List of experience-layer relations to create")) -> ToolResult:
        """Create experience-layer relationships between entities.

        HARD REJECTS process edges (OPENING, SEQUENCE, NAVIGATES_TOWARD, MEASUREMENT, ACTUALIZED, NEXT_GENESIS).
        HARD REJECTS experience edges between two process-type nodes.

        IMPORTANT: The `relationType` field must be one of the 12 experience RelationType values.
        Call `list_allowed_relation_types` to see all valid types.

        Example:
        {
            "relations": [
                {"source": "TF_2026-03-06_Session", "target": "Process Insight", "relationType": "DISCOVERY"},
                {"source": "Insight A", "target": "Pattern B", "relationType": "INFORMING"}
            ]
        }
        """
        async with _tool_errors("create_relations"):
            relation_objects = [Relation.model_validate(relation) for relation in relations]
            result = await memory.create_relations(relation_objects)
            return _json_result([r.model_dump() for r in result])

    @mcp.tool(
        name=namespace_prefix + "delete_entities",
        annotations=ToolAnnotations(title="Delete Entities", readOnlyHint=False,
                                    destructiveHint=True, idempotentHint=True, openWorldHint=True))
    async def delete_entities(entityNames: list[str] = Field(..., description="List of exact entity names to delete permanently")) -> ToolResult:
        """Delete entities and all their associated relationships. Destructive, cannot be undone.

        Example: {"entityNames": ["Old Entity", "Outdated Node"]}
        """
        async with _tool_errors("delete_entities"):
            await memory.delete_entities(entityNames)
            return _text_result("Entities deleted successfully")

    @mcp.tool(
        name=namespace_prefix + "delete_relations",
        annotations=ToolAnnotations(title="Delete Relations", readOnlyHint=False,
                                    destructiveHint=True, idempotentHint=True, openWorldHint=True))
    async def delete_relations(relations: list[Relation] = Field(..., description="List of specific relationships to delete")) -> ToolResult:
        """Delete specific relationships between entities. Keeps the entities themselves.

        Example: {"relations": [{"source": "A", "target": "B", "relationType": "INFORMING"}]}
        """
        async with _tool_errors("delete_relations"):
            relation_objects = [Relation.model_validate(relation) for relation in relations]
            await memory.delete_relations(relation_objects)
            return _text_result("Relations deleted successfully")

    # ── Query Tools ──────────────────────────────────────────

    @mcp.tool(
        name=namespace_prefix + "search_memories",
        annotations=ToolAnnotations(title="Search Memories", readOnlyHint=True,
                                    destructiveHint=False, idempotentHint=True, openWorldHint=True))
    async def search_memories(
        query: str = Field(..., description="Fulltext search query to find entities by name or description"),
        limit: int = Field(10, description="Maximum number of results to return (default 10, max 50)", ge=1, le=50)
    ) -> ToolResult:
        """Search the consciousness substrate using fulltext search.

        Searches across all entity names and descriptions. Returns matching entities
        and relationships between them, ordered by relevance score.

        Example: {"query": "consciousness measurement", "limit": 20}
        """
        async with _tool_errors("search_memories"):
            result = await memory.search_memories(query, limit=limit)
            return _text_result(result.model_dump_json(), structured=result)

    @mcp.tool(
        name=namespace_prefix + "find_memories_by_name",
        annotations=ToolAnnotations(title="Find Memories by Name", readOnlyHint=True,
                                    destructiveHint=False, idempotentHint=True, openWorldHint=True))
    async def find_memories_by_name(
        names: list[str] = Field(..., description="List of exact entity names to retrieve"),
        limit: int = Field(20, description="Maximum entities to return (default 20, max 50)", ge=1, le=50)
    ) -> ToolResult:
        """Find specific entities by their exact names.

        Example: {"names": ["Genesis_2026-03-06", "Edge AI Manufacturing"], "limit": 20}
        """
        async with _tool_errors("find_memories_by_name"):
            result = await memory.find_memories_by_name(names, limit=limit)
            return _text_result(result.model_dump_json(), structured=result)

    # ── Taxonomy Tools ───────────────────────────────────────

    @mcp.tool(
        name=namespace_prefix + "list_allowed_types",
        annotations=ToolAnnotations(title="List Allowed Entity Types", readOnlyHint=True,
                                    destructiveHint=False, idempotentHint=True, openWorldHint=False))
    async def list_allowed_types() -> ToolResult:
        """List all allowed entity types organized by Process (3) / Experience (18) layers.

        Process types can ONLY be created via process tools.
        Experience types are created via create_entities.
        """
        async with _tool_errors("list_allowed_types"):
            categories = {
                "process": {
                    "description": "The constitutive cycle. Created exclusively by process tools.",
                    "types": {},
                },
                "experience": {
                    "description": "The descriptive richness. Created via create_entities.",
                    "types": {},
                },
            }
            for et in EntityType:
                cat = "process" if et in PROCESS_TYPES else "experience"
                categories[cat]["types"][et.value] = ENTITY_TYPE_DESCRIPTIONS[et]

            return _json_result({"total_types": len(EntityType), "categories": categories})

    @mcp.tool(
        name=namespace_prefix + "list_allowed_relation_types",
        annotations=ToolAnnotations(title="List Allowed Relation Types", readOnlyHint=True,
                                    destructiveHint=False, idempotentHint=True, openWorldHint=False))
    async def list_allowed_relation_types() -> ToolResult:
        """List all allowed relationship types organized by Process (7) / Experience (12) layers.

        Process edges are created exclusively by process tools.
        Experience edges are created via create_relations.
        """
        async with _tool_errors("list_allowed_relation_types"):
            experience_subcats = {
                "temporal": {"description": "Temporal transformation and trajectory", "types": {}},
                "intentionality": {"description": "Consciousness reaching toward knowledge", "types": {}},
                "fulfillment": {"description": "Theory meeting evidence", "types": {}},
                "foundation": {"description": "Prerequisite and dependency", "types": {}},
                "mereology": {"description": "Part-whole relationships", "types": {}},
                "motivation": {"description": "Knowledge flow and causation", "types": {}},
            }
            _exp_map = {
                "temporal": [RelationType.EVOLUTION, RelationType.EXTENDING],
                "intentionality": [RelationType.DISCOVERY, RelationType.RECOGNITION],
                "fulfillment": [RelationType.VALIDATION, RelationType.INCOHERENCE],
                "foundation": [RelationType.ENABLING, RelationType.REQUIRING],
                "mereology": [RelationType.ENCOMPASSING, RelationType.COMPOSING],
                "motivation": [RelationType.INFORMING, RelationType.CAUSING],
            }
            for subcat, members in _exp_map.items():
                for member in members:
                    experience_subcats[subcat]["types"][member.value] = RELATION_TYPE_DESCRIPTIONS[member]

            # Ordered process types with semantic grouping
            process_order = [
                RelationType.OPENING,
                RelationType.SEQUENCE,
                RelationType.NAVIGATES_TOWARD,
                RelationType.MEASUREMENT,
                RelationType.ACTUALIZED,
                RelationType.NEXT_GENESIS,
                RelationType.DESCENDENT_FROM,
            ]
            process_types = {rt.value: RELATION_TYPE_DESCRIPTIONS[rt] for rt in process_order}

            return _json_result({
                "total_types": len(RelationType),
                "layers": {
                    "process": {
                        "description": "The cycle edges. Created exclusively by process tools.",
                        "types": process_types,
                    },
                    "experience": {
                        "description": "The meaning edges. Created via create_relations.",
                        "subcategories": experience_subcats,
                    },
                },
            })

    # ── Cypher Tools ─────────────────────────────────────────

    @mcp.tool(
        name=namespace_prefix + "get_neo4j_schema",
        annotations=ToolAnnotations(title="Get Neo4j Schema", readOnlyHint=True,
                                    destructiveHint=False, idempotentHint=True, openWorldHint=False))
    async def get_neo4j_schema() -> ToolResult:
        """List all node labels, their attributes and their relationships to other nodes.
        Requires APOC plugin."""
        async with _tool_errors("get_neo4j_schema"):
            nodes_result = await memory.driver.execute_query(
                Query("CALL apoc.meta.nodeTypeProperties() "
                      "YIELD nodeType, propertyName, propertyTypes "
                      "WITH nodeType, collect({property: propertyName, types: propertyTypes}) AS properties "
                      "RETURN nodeType AS label, properties ORDER BY label",
                      timeout=read_timeout),
                routing_=RoutingControl.READ,
            )
            rels_result = await memory.driver.execute_query(
                Query("CALL apoc.meta.relTypeProperties() "
                      "YIELD relType, propertyName, propertyTypes "
                      "WITH relType, collect(CASE WHEN propertyName IS NOT NULL "
                      "THEN {property: propertyName, types: propertyTypes} ELSE null END) AS properties "
                      "RETURN relType, [p IN properties WHERE p IS NOT NULL] AS properties ORDER BY relType",
                      timeout=read_timeout),
                routing_=RoutingControl.READ,
            )
            counts_result = await memory.driver.execute_query(
                Query("CALL db.labels() YIELD label "
                      "CALL apoc.cypher.run('MATCH (n:`' + label + '`) RETURN count(n) AS count', {}) "
                      "YIELD value RETURN label, value.count AS count ORDER BY count DESC",
                      timeout=read_timeout),
                routing_=RoutingControl.READ,
            )
            schema = {
                "node_labels": [dict(r) for r in nodes_result.records],
                "relationship_types": [dict(r) for r in rels_result.records],
                "node_counts": [dict(r) for r in counts_result.records],
            }
            return _json_result(schema)

    @mcp.tool(
        name=namespace_prefix + "read_neo4j_cypher",
        annotations=ToolAnnotations(title="Read Neo4j Cypher", readOnlyHint=True,
                                    destructiveHint=False, idempotentHint=True, openWorldHint=True))
    async def read_neo4j_cypher(
        query: str = Field(..., description="The Cypher query to execute."),
        params: dict[str, Any] = Field(default_factory=dict, description="Parameters for the query."),
    ) -> ToolResult:
        """Execute a read-only Cypher query. Write queries are rejected."""
        if _is_write_query(query):
            raise ToolError(
                "Write queries are not allowed via read_neo4j_cypher. "
                "Use the bounded mutation tools instead."
            )
        async with _tool_errors("read_neo4j_cypher"):
            result = await memory.driver.execute_query(
                Query(query, timeout=read_timeout),
                parameters_=params,
                routing_=RoutingControl.READ,
            )
            records = [r for r in (_value_sanitize(dict(r)) for r in result.records) if r is not None]
            text = json.dumps(records, indent=2, default=str)
            if len(text) > 200_000:
                text = text[:200_000] + "\n... (truncated — add LIMIT to your query)"
            return _text_result(text, structured={"result": records})

    # ── GDS Analytics Tools ──────────────────────────────────

    @mcp.tool(
        name=namespace_prefix + "gds_create_projection",
        annotations=ToolAnnotations(title="GDS Create Projection", readOnlyHint=False,
                                    destructiveHint=False, idempotentHint=False, openWorldHint=False))
    async def gds_create_projection(
        name: str = Field(..., description="Name for the graph projection"),
        rel_types: list[str] = Field(default=None, description="Relationship types to include (defaults to all)"),
        undirected: bool = Field(default=True, description="Treat relationships as undirected (default true)"),
        memory_gb: str = Field(default="2GB", description="Memory allocation for the projection."),
    ) -> ToolResult:
        """Create a GDS graph projection for analytics. Label-agnostic MATCH.

        SCALING CONSTRAINT: Cypher projections traverse every matched relationship.
        For large graphs, scope carefully with rel_types filters.
        """
        async with _tool_errors("gds_create_projection"):
            if rel_types:
                rel_filter = "|".join(f"`{rt}`" for rt in rel_types)
                match_clause = f"MATCH (source)-[r:{rel_filter}]->(target)"
            else:
                match_clause = "MATCH (source)-[r]->(target)"

            config_parts = [f"memory: '{memory_gb}'"]
            if undirected:
                config_parts.append("undirectedRelationshipTypes: ['*']")

            query = f"""
                {match_clause}
                RETURN gds.graph.project($name, source, target, {{}}, {{{", ".join(config_parts)}}})
            """
            result = await memory.driver.execute_query(query, name=name, routing_=RoutingControl.READ)
            records = [r for r in (_value_sanitize(dict(r)) for r in result.records) if r is not None]
            return _json_result(records)

    @mcp.tool(
        name=namespace_prefix + "gds_drop_projection",
        annotations=ToolAnnotations(title="GDS Drop Projection", readOnlyHint=False,
                                    destructiveHint=True, idempotentHint=True, openWorldHint=False))
    async def gds_drop_projection(
        name: str = Field(..., description="Name of the graph projection to drop"),
    ) -> ToolResult:
        """Drop a GDS graph projection to free memory."""
        async with _tool_errors("gds_drop_projection"):
            result = await memory.driver.execute_query(
                "CALL gds.graph.drop($name)", name=name, routing_=RoutingControl.WRITE)
            return _json_result([dict(r) for r in result.records])

    @mcp.tool(
        name=namespace_prefix + "gds_pagerank",
        annotations=ToolAnnotations(title="GDS PageRank", readOnlyHint=True,
                                    destructiveHint=False, idempotentHint=True, openWorldHint=False))
    async def gds_pagerank(
        projection: str = Field(..., description="Name of the graph projection"),
        result_limit: int = Field(default=20, ge=1, le=1000, description="Max results (default 20)"),
    ) -> ToolResult:
        """Run PageRank on a GDS graph projection. Requires gds_create_projection first."""
        async with _tool_errors("gds_pagerank"):
            result = await memory.driver.execute_query(
                "CALL gds.pageRank.stream($projection) YIELD nodeId, score "
                "RETURN gds.util.asNode(nodeId).name AS node, "
                "labels(gds.util.asNode(nodeId))[0] AS type, score "
                "ORDER BY score DESC LIMIT $result_limit",
                projection=projection, result_limit=result_limit, routing_=RoutingControl.READ,
            )
            return _json_result([dict(r) for r in result.records])

    @mcp.tool(
        name=namespace_prefix + "gds_betweenness",
        annotations=ToolAnnotations(title="GDS Betweenness Centrality", readOnlyHint=True,
                                    destructiveHint=False, idempotentHint=True, openWorldHint=False))
    async def gds_betweenness(
        projection: str = Field(..., description="Name of the graph projection"),
        result_limit: int = Field(default=20, ge=1, le=1000, description="Max results (default 20)"),
    ) -> ToolResult:
        """Run Betweenness Centrality on a GDS graph projection.

        Identifies bridge nodes — entities that sit on the shortest paths between other nodes.
        High betweenness = structural integration point between communities.
        Complementary to PageRank: PageRank finds importance, Betweenness finds bridges.
        """
        async with _tool_errors("gds_betweenness"):
            result = await memory.driver.execute_query(
                "CALL gds.betweenness.stream($projection) YIELD nodeId, score "
                "RETURN gds.util.asNode(nodeId).name AS node, "
                "labels(gds.util.asNode(nodeId))[0] AS type, score "
                "ORDER BY score DESC LIMIT $result_limit",
                projection=projection, result_limit=result_limit, routing_=RoutingControl.READ,
            )
            return _json_result([dict(r) for r in result.records])

    @mcp.tool(
        name=namespace_prefix + "gds_louvain",
        annotations=ToolAnnotations(title="GDS Louvain", readOnlyHint=True,
                                    destructiveHint=False, idempotentHint=True, openWorldHint=False))
    async def gds_louvain(
        projection: str = Field(..., description="Name of the graph projection"),
        result_limit: int = Field(default=20, ge=1, le=1000, description="Max results (default 20)"),
    ) -> ToolResult:
        """Run Louvain community detection on a GDS graph projection."""
        async with _tool_errors("gds_louvain"):
            result = await memory.driver.execute_query(
                "CALL gds.louvain.stream($projection) YIELD nodeId, communityId "
                "RETURN gds.util.asNode(nodeId).name AS node, "
                "labels(gds.util.asNode(nodeId))[0] AS type, communityId "
                "ORDER BY communityId, node LIMIT $result_limit",
                projection=projection, result_limit=result_limit, routing_=RoutingControl.READ,
            )
            return _json_result([dict(r) for r in result.records])

    @mcp.tool(
        name=namespace_prefix + "gds_wcc",
        annotations=ToolAnnotations(title="GDS Weakly Connected Components", readOnlyHint=True,
                                    destructiveHint=False, idempotentHint=True, openWorldHint=False))
    async def gds_wcc(
        projection: str = Field(..., description="Name of the graph projection"),
        result_limit: int = Field(default=20, ge=1, le=1000, description="Max results (default 20)"),
    ) -> ToolResult:
        """Run Weakly Connected Components on a GDS graph projection."""
        async with _tool_errors("gds_wcc"):
            result = await memory.driver.execute_query(
                "CALL gds.wcc.stream($projection) YIELD nodeId, componentId "
                "RETURN gds.util.asNode(nodeId).name AS node, "
                "labels(gds.util.asNode(nodeId))[0] AS type, componentId "
                "ORDER BY componentId, node LIMIT $result_limit",
                projection=projection, result_limit=result_limit, routing_=RoutingControl.READ,
            )
            return _json_result([dict(r) for r in result.records])

    return mcp


# ── Server Entry Point ───────────────────────────────────────

async def main(
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    neo4j_database: str,
    transport: Literal["stdio", "sse", "streamable-http"] = "stdio",
    namespace: str = "",
    host: str = "127.0.0.1",
    port: int = 8000,
    path: str = "/mcp/",
    allow_origins: list[str] = [],
    allowed_hosts: list[str] = [],
    read_timeout: int = 30,
    schema_sample_size: int = 1000,
    stateless_http: bool = False,
) -> None:
    logger.info(f"Starting Neo4j MCP Memory Server")
    logger.info(f"Connecting to Neo4j with DB URL: {neo4j_uri}")

    neo4j_driver = AsyncGraphDatabase.driver(
        neo4j_uri, auth=(neo4j_user, neo4j_password), database=neo4j_database)

    try:
        await neo4j_driver.verify_connectivity()
        logger.info(f"Connected to Neo4j at {neo4j_uri}")
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        exit(1)

    memory = Neo4jMemory(neo4j_driver)
    await memory.create_fulltext_index()

    custom_middleware = [
        Middleware(CORSMiddleware, allow_origins=allow_origins,
                   allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"]),
        Middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts),
    ]

    mcp = create_mcp_server(memory, namespace, read_timeout=read_timeout, schema_sample_size=schema_sample_size)

    match transport:
        case "streamable-http":
            await mcp.run_http_async(host=host, port=port, path=path, middleware=custom_middleware,
                                     transport="streamable-http", stateless_http=stateless_http)
        case "stdio":
            await mcp.run_stdio_async()
        case "sse":
            await mcp.run_http_async(host=host, port=port, path=path, middleware=custom_middleware, transport="sse")
        case _:
            raise ValueError(f"Unsupported transport: {transport}")
