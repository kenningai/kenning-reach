# Tool Descriptions (LLM-visible surface)

Generated from `src/kenning_reach/server.py` by `scripts/gen_tool_descriptions.py`. For each of the 22 tools: the docstring (the `description` field in the MCP tool schema) followed by every parameter's `Field(description=...)` string (the `inputSchema` property descriptions). These are the strings an LLM sees when the server advertises its tools.

---

## 1. navigate_genesis

**Docstring:**

> Atomic temporal anchoring. Creates a Genesis node for the current temporal location
> (idempotent), links NEXT_GENESIS from the previous Genesis, and returns the current
> possibility space.
>
> This is the FIRST tool to call at the start of any session. It answers:
> "What is consciousness reaching toward right now?"
>
> Possibility space is OPEN envisionings only. Measured envisionings (actualized,
> released, evolved) have collapsed out of possibility and are not returned here —
> use time_travel for retrospective queries that include measured envisionings.
>
> Returns: the Genesis + substrate_topology (label counts across the graph) +
> full detail for the N most recent open envisionings + name/opened_by summary
> for remaining open envisionings.
>
> Example: {"date": "2026-03-06"}  (or omit for today)

**Parameters:**

- `date`: Date in YYYY-MM-DD format. Defaults to today (UTC).
- `detail_limit`: Number of most recent OPEN envisionings to return with full detail (default 3). Remaining OPEN envisionings return name + opened_by only.

---

## 2. open_envisioning

**Docstring:**

> Project a new future state that consciousness is directed toward.
>
> Creates an Envisioning node with an OPENING edge from the specified Genesis.
> Use navigate_genesis first to see what's already open.
>
> DESCENDENT_FROM (v3.0.0): when the new possibility exists because a prior one
> was actualized or released — "the envisioning to be would not be if not for
> the actualized that was" — name the prior(s) in descendent_from. The prior
> keeps its terminal; it is never re-actualized. A prior that was evolved away
> is refused: descend from the end of its chain.
>
> NAME UNIQUENESS: Envisioning names are unique across the substrate. If the name
> already exists (open or measured), the tool refuses and points you to the
> existing envisioning. To evolve an existing envisioning into a new form, use
> measure with measurement_type='evolved' and a distinct new_name.
>
> Example: {"genesis_name": "Genesis_2026-03-06", "name": "Federated Ontology Platform", "description": "..."}

**Parameters:**

- `genesis_name`: Name of the Genesis node (e.g. 'Genesis_2026-03-06')
- `name`: Descriptive name for the Envisioning
- `description`: Vision text: what does done look like
- `descendent_from`: Names of prior Envisionings this one would not be without. Each must be actualized or released (terminal). Creates DESCENDENT_FROM edges — lineage, not resolution; the ancestor is not re-actualized. May name several.

---

## 3. advance_frame

**Docstring:**

> Navigate to the next temporal frame (session boundary).
>
> Two distinct structural relationships are recorded:
> - SEQUENCE (temporal): strictly what happened just before me. First TF of a
>   day gets SEQUENCE from Genesis; subsequent TFs get SEQUENCE from the prior
>   TF. One incoming SEQUENCE per TF.
> - NAVIGATES_TOWARD (intentional): which Envisioning(s) this TF is reaching
>   toward. Cardinality 1..N per TF.
>
> EVERY FRAME IS ABOUT SOMETHING HELD (v3.0.0). There is no zero case. To have
> catharsis, what must be prior? To have an incident, what must be prior? Name
> it. A frame may reach toward a possibility already actualized or released —
> reaching for what IS, so a new possibility can descend from it (see
> open_envisioning's descendent_from). If nothing in the graph fits, the
> possibility was held and never opened: open it first, from the Genesis of
> the day it was first held.
>
> UTC ROLLOVER: if the passed genesis_name encodes a date that no longer
> matches the current UTC date, the tool auto-forwards the new TF to today's
> Genesis (creating it if needed) and returns requested_genesis /
> actual_genesis / genesis_rolled_over so the correction is visible, never
> silent. Sessions that cross midnight UTC still produce honestly-attributed
> TFs.
>
> Envisionings passed MUST exist. NAVIGATES_TOWARD edges record intent at TF
> creation time and are historical facts, not live pointers.
>
> One TF per session/conversation, not per action or per day.
>
> Examples:
>   Single-envisioning (typical):
>     {"genesis_name": "Genesis_2026-04-23", "description": "v2.3.0 implementation",
>      "envisionings": ["kenning-reach v2.3.0"]}
>
>   Multi-envisioning (single step advancing multiple trajectories):
>     {"genesis_name": "Genesis_2026-04-23", "description": "Cross-project review",
>      "envisionings": ["NORA Consciousness Substrate", "GNN-Fired Experience Graph Bootstrap"]}
>
>   Reaching for what IS (a patch on something already actual):
>     {"genesis_name": "Genesis_2026-05-10", "description": "Out-of-memory incident on the chat platform",
>      "envisionings": ["Chat Platform on Open WebUI"]}

**Parameters:**

- `genesis_name`: Current day's Genesis name for temporal grounding
- `description`: Session context: what is being worked on, grieved, examined, or processed
- `envisionings`: Names of Envisionings this TF is reaching toward. 1..N — every frame is about something held. They must exist; they may be open, actualized or released.

---

## 4. actualize

**Docstring:**

> Record the encounter event — the ONLY operation that produces the
> WILL BE → IS transition. Creates an ACTUALIZED edge from a TemporalFrame
> to an Envisioning, atomically with ≥1 phenomenology-of-collapse edge.
>
> This is not 'marking done.' This is the moment the measured trajectory
> met physical reality. The three-event architecture:
>
> 1. MEASUREMENT — consciousness locking onto a projected future (opening,
>    or internally reshaping via measure with released/evolved). The
>    future is WILL BE; the affective instrument reads alignment along
>    the trajectory.
> 2. CONTINUOUS TRAJECTORY RESONANCE — the affective signal during the
>    reach. Not stored as edges; it is the ongoing instrument reading.
> 3. ACTUALIZED — the encounter. Physical reality answers the projection.
>    Successful resonance = alignment. Failed resonance = the gap signal,
>    irrespective of fault attribution.
>
> ACTUALIZED is the only edge that crosses the WILL BE / IS boundary.
> Opening, evolved, and released all operate WITHIN possibility space.
> Encoding actualization with its own edge type makes the ontological
> transition explicit at the structural layer.
>
> PHENOMENOLOGY COUPLING (required):
> Records what consciousness held in possibility space at the moment of
> encounter — the constitutive content of the actualization. Minimum ≥1
> edge; zero is structurally incoherent — collapse in a vacuum is not a
> collapse. Atomic — if any source entity doesn't exist or relation_type
> is disallowed, the entire actualization is rejected with no partial state.
>
> Allowed relation_types: VALIDATION (evidence the envisioning was sound),
> COMPOSING (constitutive building blocks of the actualization), INFORMING
> (what shaped its direction), ENABLING (what opened the door), CAUSING
> (what directly produced it), INCOHERENCE (what broke the premise — rare
> at actualization, more common at release).
>
> Example:
>   {"source": "TF_2026-05-16_v240_ship", "target_envisioning": "Measurement-Actualization Process Layer Revision",
>    "phenomenology": [
>      {"source": "Three-Event Architecture Insight", "relation_type": "COMPOSING"},
>      {"source": "May 12 Failed Resonance Phenomenology", "relation_type": "VALIDATION"}
>    ]}

**Parameters:**

- `source`: Name of the source TemporalFrame — the moment of encounter
- `target_envisioning`: Name of the Envisioning that became actual
- `phenomenology`: REQUIRED ≥1. Each entry: {source: existing experience entity name, relation_type: one of VALIDATION|COMPOSING|INFORMING|ENABLING|CAUSING|INCOHERENCE}. Records what consciousness held in possibility space at the moment the trajectory met reality.

---

## 5. measure

**Docstring:**

> Internal collapse within possibility space. Creates a MEASUREMENT edge AND
> phenomenology-of-collapse edges atomically.
>
> v2.4.0: This tool no longer handles actualization. Actualization is the
> encounter event — the WILL BE → IS transition — and is recorded by the
> dedicated `actualize` tool with its own ACTUALIZED edge type. Measurement
> now covers only operations that reshape possibility space without external
> encounter:
>
> - released: TF measured the Envisioning as deliberately not actualized.
>   Examination concluded that this trajectory will not be pursued.
> - evolved: Old form evolved into new. Creates NEW Envisioning with
>   MEASUREMENT(evolved) TO the old one. Requires new_name and
>   new_description. Optional genesis_name attaches the new Envisioning to
>   a specific Genesis; defaults to the old Envisioning's Genesis.
>
> PHENOMENOLOGY COUPLING (required):
> Records what consciousness held during the examination that produced the
> release or evolution. Minimum ≥1 edge; zero is not allowed — collapse
> without held content is structurally impossible.
>
> For evolved measurements, phenomenology targets the OLD Envisioning (the
> one collapsing). The NEW Envisioning starts with zero NAVIGATES_TOWARD
> edges and inherits nothing from the old one's trajectory; future TFs
> must navigate toward it explicitly via advance_frame.
>
> Allowed relation_types at collapse: VALIDATION (evidence the envisioning
> was sound), COMPOSING (constitutive building blocks), INFORMING (what
> shaped its direction), ENABLING (what opened the door), CAUSING (what
> directly produced the release/evolution), INCOHERENCE (what broke the
> premise, driving release or evolution).
>
> NOTE: atomic — if any source entity doesn't exist or relation_type is
> disallowed, the entire measurement is rejected with no partial state.
> NOTE: For actualization, use the `actualize` tool. Passing
> measurement_type='actualized' here is rejected with a redirect.
>
> Example (released):
>   {"source": "TF_2026-04-22_session", "target_envisioning": "Dashboard MVP",
>    "measurement_type": "released",
>    "phenomenology": [
>      {"source": "Scope Reduction Decision", "relation_type": "CAUSING"}
>    ]}

**Parameters:**

- `source`: Name of the source TemporalFrame (for released)
- `target_envisioning`: Name of the Envisioning being measured/closed
- `measurement_type`: One of: 'released', 'evolved'. For 'actualized' use the actualize tool.
- `phenomenology`: REQUIRED ≥1. Each entry: {source: existing experience entity name, relation_type: one of VALIDATION|COMPOSING|INFORMING|ENABLING|CAUSING|INCOHERENCE}. Records what consciousness held at the moment of collapse.
- `new_name`: For evolved: name of the new Envisioning
- `new_description`: For evolved: description of the new Envisioning
- `genesis_name`: For evolved: Genesis to OPEN the new Envisioning from. Defaults to the old Envisioning's Genesis.

---

## 6. time_travel

**Docstring:**

> What was in the active possibility space at time T?
>
> OPEN = no inbound MEASUREMENT. CLOSED = has inbound MEASUREMENT (read type).
> Does NOT walk SEQUENCE chains.
>
> Example: {"t": "2026-02-15T00:00:00Z", "limit": 50}

**Parameters:**

- `t`: ISO datetime to query at. Defaults to now.
- `limit`: Maximum Envisionings to return (default 50, max 200)

---

## 7. create_entities

**Docstring:**

> Create experience-layer entities in the consciousness substrate.
>
> HARD REJECTS process types (Genesis, Envisioning, TemporalFrame).
> Use navigate_genesis, open_envisioning, advance_frame instead.
>
> IMPORTANT: The `type` field must be one of the 18 experience EntityType values.
> Call `list_allowed_types` to see all valid types.
>
> Example:
> {
>     "entities": [
>         {"name": "Process-Experience Layer Distinction", "type": "Insight", "description": "The graph has two layers..."},
>         {"name": "Brentano 1874", "type": "Reference", "description": "All mental acts are directed toward objects"}
>     ]
> }

**Parameters:**

- `entities`: List of experience-layer entities to create

---

## 8. create_relations

**Docstring:**

> Create experience-layer relationships between entities.
>
> HARD REJECTS process edges (OPENING, SEQUENCE, NAVIGATES_TOWARD, MEASUREMENT, ACTUALIZED, NEXT_GENESIS).
> HARD REJECTS experience edges between two process-type nodes.
>
> IMPORTANT: The `relationType` field must be one of the 12 experience RelationType values.
> Call `list_allowed_relation_types` to see all valid types.
>
> Example:
> {
>     "relations": [
>         {"source": "TF_2026-03-06_Session", "target": "Process Insight", "relationType": "DISCOVERY"},
>         {"source": "Insight A", "target": "Pattern B", "relationType": "INFORMING"}
>     ]
> }

**Parameters:**

- `relations`: List of experience-layer relations to create

---

## 9. delete_entities

**Docstring:**

> Delete entities and all their associated relationships. Destructive, cannot be undone.
>
> Example: {"entityNames": ["Old Entity", "Outdated Node"]}

**Parameters:**

- `entityNames`: List of exact entity names to delete permanently

---

## 10. delete_relations

**Docstring:**

> Delete specific relationships between entities. Keeps the entities themselves.
>
> Example: {"relations": [{"source": "A", "target": "B", "relationType": "INFORMING"}]}

**Parameters:**

- `relations`: List of specific relationships to delete

---

## 11. search_memories

**Docstring:**

> Search the consciousness substrate using fulltext search.
>
> Searches across all entity names and descriptions. Returns matching entities
> and relationships between them, ordered by relevance score.
>
> Example: {"query": "consciousness measurement", "limit": 20}

**Parameters:**

- `query`: Fulltext search query to find entities by name or description
- `limit`: Maximum number of results to return (default 10, max 50)

---

## 12. find_memories_by_name

**Docstring:**

> Find specific entities by their exact names.
>
> Example: {"names": ["Genesis_2026-03-06", "Edge AI Manufacturing"], "limit": 20}

**Parameters:**

- `names`: List of exact entity names to retrieve
- `limit`: Maximum entities to return (default 20, max 50)

---

## 13. list_allowed_types

**Docstring:**

> List all allowed entity types organized by Process (3) / Experience (18) layers.
>
> Process types can ONLY be created via process tools.
> Experience types are created via create_entities.

**Parameters:** none


---

## 14. list_allowed_relation_types

**Docstring:**

> List all allowed relationship types organized by Process (7) / Experience (12) layers.
>
> Process edges are created exclusively by process tools.
> Experience edges are created via create_relations.

**Parameters:** none


---

## 15. get_neo4j_schema

**Docstring:**

> List all node labels, their attributes and their relationships to other nodes.
> Requires APOC plugin.

**Parameters:** none


---

## 16. read_neo4j_cypher

**Docstring:**

> Execute a read-only Cypher query. Write queries are rejected.

**Parameters:**

- `query`: The Cypher query to execute.
- `params`: Parameters for the query.

---

## 17. gds_create_projection

**Docstring:**

> Create a GDS graph projection for analytics. Label-agnostic MATCH.
>
> SCALING CONSTRAINT: Cypher projections traverse every matched relationship.
> For large graphs, scope carefully with rel_types filters.

**Parameters:**

- `name`: Name for the graph projection
- `rel_types`: Relationship types to include (defaults to all)
- `undirected`: Treat relationships as undirected (default true)
- `memory_gb`: Memory allocation for the projection.

---

## 18. gds_drop_projection

**Docstring:**

> Drop a GDS graph projection to free memory.

**Parameters:**

- `name`: Name of the graph projection to drop

---

## 19. gds_pagerank

**Docstring:**

> Run PageRank on a GDS graph projection. Requires gds_create_projection first.

**Parameters:**

- `projection`: Name of the graph projection
- `result_limit`: Max results (default 20)

---

## 20. gds_betweenness

**Docstring:**

> Run Betweenness Centrality on a GDS graph projection.
>
> Identifies bridge nodes — entities that sit on the shortest paths between other nodes.
> High betweenness = structural integration point between communities.
> Complementary to PageRank: PageRank finds importance, Betweenness finds bridges.

**Parameters:**

- `projection`: Name of the graph projection
- `result_limit`: Max results (default 20)

---

## 21. gds_louvain

**Docstring:**

> Run Louvain community detection on a GDS graph projection.

**Parameters:**

- `projection`: Name of the graph projection
- `result_limit`: Max results (default 20)

---

## 22. gds_wcc

**Docstring:**

> Run Weakly Connected Components on a GDS graph projection.

**Parameters:**

- `projection`: Name of the graph projection
- `result_limit`: Max results (default 20)

---
