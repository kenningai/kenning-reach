import pytest
from unittest.mock import Mock, AsyncMock
from pydantic import ValidationError

from kenning_reach.server import format_namespace, create_mcp_server
from kenning_reach.neo4j_memory import (
    Neo4jMemory, KnowledgeGraph, Entity, EntityType, PROCESS_TYPES,
    Relation, RelationType, PROCESS_EDGES, MeasurementType,
    PHENOMENOLOGY_EDGE_TYPES, PhenomenologyEdge,
    _GENESIS_NAME_PATTERN,
)


async def tool_map(server):
    """The server's tools keyed by name. FastMCP 3 lists them as a sequence."""
    return {tool.name: tool for tool in await server.list_tools()}


class TestFormatNamespace:
    """Test the format_namespace function behavior."""

    def testformat_namespace_empty_string(self):
        """Test format_namespace with empty string returns empty string."""
        assert format_namespace("") == ""

    def testformat_namespace_no_hyphen(self):
        """Test format_namespace adds hyphen when not present."""
        assert format_namespace("myapp") == "myapp-"

    def testformat_namespace_with_hyphen(self):
        """Test format_namespace returns string as-is when hyphen already present."""
        assert format_namespace("myapp-") == "myapp-"

    def testformat_namespace_complex_name(self):
        """Test format_namespace with complex namespace names."""
        assert format_namespace("company.product") == "company.product-"
        assert format_namespace("app_v2") == "app_v2-"


class TestNamespacing:
    """Test namespacing functionality."""

    @pytest.fixture
    def mock_memory(self):
        """Create a mock Neo4jMemory for testing."""
        memory = Mock(spec=Neo4jMemory)
        knowledge_graph = KnowledgeGraph(entities=[], relations=[])
        memory.create_entities = AsyncMock(return_value=[])
        memory.create_relations = AsyncMock(return_value=[])
        memory.delete_entities = AsyncMock(return_value=None)
        memory.delete_relations = AsyncMock(return_value=None)
        memory.search_memories = AsyncMock(return_value=knowledge_graph)
        memory.find_memories_by_name = AsyncMock(return_value=knowledge_graph)
        memory.navigate_genesis = AsyncMock(return_value={"genesis": "Genesis_2026-03-06", "date": "2026-03-06", "possibility_space": []})
        memory.open_envisioning = AsyncMock(return_value={"name": "Test", "description": "", "t_created": None, "opened_by": "Genesis_2026-03-06"})
        memory.advance_frame = AsyncMock(return_value={"name": "TF_2026-03-06_Test", "description": "Test", "t_created": None, "temporal_ground": "Genesis_2026-03-06", "is_first_of_day": True, "sequence_predecessor": "Genesis_2026-03-06", "navigates_toward": [], "requested_genesis": "Genesis_2026-03-06", "actual_genesis": "Genesis_2026-03-06", "genesis_rolled_over": False})
        memory.measure = AsyncMock(return_value={"source": "TF", "target": "E", "measurement_type": "released", "measured_at": None, "phenomenology_edge_count": 1})
        memory.actualize = AsyncMock(return_value={"source": "TF", "target": "E", "actualized_at": None, "phenomenology_edge_count": 1})
        memory.time_travel = AsyncMock(return_value=[])
        memory.driver = AsyncMock()
        memory.driver.execute_query = AsyncMock(return_value=Mock(records=[]))
        return memory

    @pytest.mark.asyncio
    async def test_namespace_tool_prefixes(self, mock_memory):
        """Test that tools are correctly prefixed with namespace."""
        # Test with namespace
        namespaced_server = create_mcp_server(mock_memory, namespace="test-ns")
        tools = await tool_map(namespaced_server)

        expected_tools = [
            # Process tools
            "test-ns-navigate_genesis",
            "test-ns-open_envisioning",
            "test-ns-advance_frame",
            "test-ns-measure",
            "test-ns-actualize",
            "test-ns-time_travel",
            # Experience tools
            "test-ns-create_entities",
            "test-ns-create_relations",
            "test-ns-delete_entities",
            "test-ns-delete_relations",
            # Query tools
            "test-ns-search_memories",
            "test-ns-find_memories_by_name",
            # Taxonomy tools
            "test-ns-list_allowed_types",
            "test-ns-list_allowed_relation_types",
            # Infrastructure tools
            "test-ns-get_neo4j_schema",
            "test-ns-read_neo4j_cypher",
            "test-ns-gds_create_projection",
            "test-ns-gds_drop_projection",
            "test-ns-gds_pagerank",
            "test-ns-gds_louvain",
            "test-ns-gds_wcc",
        ]

        for expected_tool in expected_tools:
            assert expected_tool in tools.keys(), f"Tool {expected_tool} not found in tools"

        # Test without namespace (default tools)
        default_server = create_mcp_server(mock_memory)
        default_tools = await tool_map(default_server)

        expected_default_tools = [
            "navigate_genesis",
            "open_envisioning",
            "advance_frame",
            "measure",
            "actualize",
            "time_travel",
            "create_entities",
            "create_relations",
            "delete_entities",
            "delete_relations",
            "search_memories",
            "find_memories_by_name",
            "list_allowed_types",
            "list_allowed_relation_types",
            "get_neo4j_schema",
            "read_neo4j_cypher",
            "gds_create_projection",
            "gds_drop_projection",
            "gds_pagerank",
            "gds_louvain",
            "gds_wcc",
        ]

        for expected_tool in expected_default_tools:
            assert expected_tool in default_tools.keys(), f"Default tool {expected_tool} not found"

    @pytest.mark.asyncio
    async def test_namespace_tool_functionality(self, mock_memory):
        """Test that namespaced tools function correctly."""
        namespaced_server = create_mcp_server(mock_memory, namespace="test")
        tools = await tool_map(namespaced_server)

        # Test that a namespaced tool exists and works
        search_tool = tools.get("test-search_memories")
        assert search_tool is not None

        # Call the tool function and verify it works
        result = await search_tool.fn(query="test", limit=10)
        mock_memory.search_memories.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_namespace_isolation(self, mock_memory):
        """Test that different namespaces create isolated tool sets."""
        server_a = create_mcp_server(mock_memory, namespace="app-a")
        server_b = create_mcp_server(mock_memory, namespace="app-b")

        tools_a = await tool_map(server_a)
        tools_b = await tool_map(server_b)

        assert "app-a-search_memories" in tools_a.keys()
        assert "app-a-search_memories" not in tools_b.keys()

        assert "app-b-search_memories" in tools_b.keys()
        assert "app-b-search_memories" not in tools_a.keys()

        assert len(tools_a) == len(tools_b)

    @pytest.mark.asyncio
    async def test_namespace_hyphen_handling(self, mock_memory):
        """Test namespace hyphen handling edge cases."""
        server_with_hyphen = create_mcp_server(mock_memory, namespace="myapp-")
        tools_with_hyphen = await tool_map(server_with_hyphen)
        assert "myapp-search_memories" in tools_with_hyphen.keys()

        server_without_hyphen = create_mcp_server(mock_memory, namespace="myapp")
        tools_without_hyphen = await tool_map(server_without_hyphen)
        assert "myapp-search_memories" in tools_without_hyphen.keys()

        assert set(tools_with_hyphen.keys()) == set(tools_without_hyphen.keys())

    @pytest.mark.asyncio
    async def test_complex_namespace_names(self, mock_memory):
        """Test complex namespace naming scenarios."""
        complex_namespaces = [
            "company.product",
            "app_v2",
            "client-123",
            "test.env.staging"
        ]

        for namespace in complex_namespaces:
            server = create_mcp_server(mock_memory, namespace=namespace)
            tools = await tool_map(server)

            expected_tool = f"{namespace}-search_memories"
            assert expected_tool in tools.keys(), f"Tool {expected_tool} not found for namespace '{namespace}'"

    @pytest.mark.asyncio
    async def test_namespace_tool_count_consistency(self, mock_memory):
        """Test that namespaced and default servers have the same number of tools."""
        default_server = create_mcp_server(mock_memory)
        namespaced_server = create_mcp_server(mock_memory, namespace="test")

        default_tools = await tool_map(default_server)
        namespaced_tools = await tool_map(namespaced_server)

        assert len(default_tools) == len(namespaced_tools)

        # 22 tools: 6 process + 4 experience + 2 query + 2 taxonomy + 8 infrastructure
        assert len(default_tools) == 22
        assert len(namespaced_tools) == 22


class TestEntityTypeValidation:
    """Test that the EntityType enum properly constrains entity types."""

    def test_valid_entity_type_accepted(self):
        """Test that a valid EntityType value is accepted by Entity model."""
        entity = Entity(
            name="Test Entity",
            type="Technical",
            description="This is a test",
        )
        assert entity.type == EntityType.TECHNICAL
        assert entity.type.value == "Technical"

    def test_invalid_entity_type_rejected(self):
        """Test that an invalid type string is rejected by Entity model."""
        with pytest.raises(ValidationError) as exc_info:
            Entity(
                name="Bad Entity",
                type="Consciousness_Theory",
                description="Should fail",
            )
        assert "type" in str(exc_info.value)

    def test_all_enum_values_accepted(self):
        """Test that every EntityType enum value is accepted."""
        for entity_type in EntityType:
            entity = Entity(
                name=f"Test {entity_type.value}",
                type=entity_type.value,
                description="Testing",
            )
            assert entity.type == entity_type

    def test_entity_type_enum_has_21_members(self):
        """Test that the EntityType enum has exactly 21 members."""
        assert len(EntityType) == 21

    def test_case_sensitive_rejection(self):
        """Test that type matching is case-sensitive (lowercase 'technical' rejected)."""
        with pytest.raises(ValidationError):
            Entity(
                name="Case Test",
                type="technical",
                description="Should fail",
            )

    def test_entity_description_field(self):
        """Test that Entity uses description instead of observations."""
        entity = Entity(
            name="Test",
            type="Insight",
            description="An important insight about consciousness",
        )
        assert entity.description == "An important insight about consciousness"
        assert not hasattr(entity, 'observations') or 'observations' not in entity.model_fields

    def test_entity_description_defaults_empty(self):
        """Test that description defaults to empty string."""
        entity = Entity(name="Test", type="Technical")
        assert entity.description == ""


class TestProcessTypeGuards:
    """Test that process types are properly guarded."""

    def test_process_types_set(self):
        """Test PROCESS_TYPES contains exactly the 3 process types."""
        assert PROCESS_TYPES == {EntityType.GENESIS, EntityType.ENVISIONING, EntityType.TEMPORAL_FRAME}
        assert len(PROCESS_TYPES) == 3

    def test_process_edges_set(self):
        """Test PROCESS_EDGES contains exactly the 7 process edges (v3.0.0: DESCENDENT_FROM added)."""
        assert PROCESS_EDGES == {
            RelationType.OPENING,
            RelationType.SEQUENCE,
            RelationType.NAVIGATES_TOWARD,
            RelationType.MEASUREMENT,
            RelationType.ACTUALIZED,
            RelationType.NEXT_GENESIS,
            RelationType.DESCENDENT_FROM,
        }
        assert len(PROCESS_EDGES) == 7

    def test_create_entities_rejects_process_types(self):
        """Test that Entity model accepts process types at model level (rejection is in Neo4jMemory.create_entities)."""
        # The Entity model itself accepts all types — the guard is in the data layer
        for process_type in PROCESS_TYPES:
            entity = Entity(name=f"Test {process_type.value}", type=process_type.value)
            assert entity.type == process_type

    def test_create_relations_rejects_process_edges(self):
        """Test that Relation model accepts process edges at model level (rejection is in Neo4jMemory.create_relations)."""
        for process_edge in PROCESS_EDGES:
            relation = Relation(source="A", target="B", relationType=process_edge.value)
            assert relation.relationType == process_edge


class TestMeasurementType:
    """Test the MeasurementType enum.

    v2.4.0: ACTUALIZED was removed from this enum. Actualization is its own
    edge type (ACTUALIZED) recorded by the `actualize` tool. MEASUREMENT now
    carries only internal-collapse subtypes.
    """

    def test_measurement_type_values(self):
        """Test MeasurementType has exactly 2 values (v2.4.0: ACTUALIZED removed)."""
        assert len(MeasurementType) == 2
        assert MeasurementType.RELEASED.value == "released"
        assert MeasurementType.EVOLVED.value == "evolved"

    def test_actualized_no_longer_in_enum(self):
        """v2.4.0: 'actualized' is no longer a measurement subtype."""
        with pytest.raises(ValueError):
            MeasurementType("actualized")

    def test_measurement_type_from_string(self):
        """Test MeasurementType can be created from string."""
        assert MeasurementType("released") == MeasurementType.RELEASED
        assert MeasurementType("evolved") == MeasurementType.EVOLVED

    def test_invalid_measurement_type_rejected(self):
        """Test that invalid measurement type strings are rejected."""
        with pytest.raises(ValueError):
            MeasurementType("completed")


class TestListAllowedTypes:
    """Test the list_allowed_types tool."""

    @pytest.fixture
    def mock_memory(self):
        memory = Mock(spec=Neo4jMemory)
        memory.driver = AsyncMock()
        memory.driver.execute_query = AsyncMock(return_value=Mock(records=[]))
        return memory

    @pytest.mark.asyncio
    async def test_list_allowed_types_returns_all_types(self, mock_memory):
        """Test that list_allowed_types returns all 21 types."""
        server = create_mcp_server(mock_memory)
        tools = await tool_map(server)
        tool = tools.get("list_allowed_types")
        assert tool is not None

        result = await tool.fn()
        import json
        text = result.content[0].text
        data = json.loads(text)

        assert data["total_types"] == 21

        # Collect all types across categories
        all_types = set()
        for category in data["categories"].values():
            all_types.update(category["types"].keys())

        assert len(all_types) == 21

        for entity_type in EntityType:
            assert entity_type.value in all_types, f"{entity_type.value} missing from list_allowed_types"

    @pytest.mark.asyncio
    async def test_list_allowed_types_has_descriptions(self, mock_memory):
        """Test that every type has a non-empty description."""
        server = create_mcp_server(mock_memory)
        tools = await tool_map(server)
        tool = tools.get("list_allowed_types")

        result = await tool.fn()
        import json
        data = json.loads(result.content[0].text)

        for category in data["categories"].values():
            for type_name, description in category["types"].items():
                assert isinstance(description, str) and len(description) > 0, \
                    f"Type {type_name} has empty or missing description"

    @pytest.mark.asyncio
    async def test_list_allowed_types_categories(self, mock_memory):
        """Test that types are organized into Process/Experience layers."""
        server = create_mcp_server(mock_memory)
        tools = await tool_map(server)
        tool = tools.get("list_allowed_types")

        result = await tool.fn()
        import json
        data = json.loads(result.content[0].text)

        expected_categories = {"process", "experience"}
        assert set(data["categories"].keys()) == expected_categories

        # Process: 3, Experience: 18
        assert len(data["categories"]["process"]["types"]) == 3
        assert len(data["categories"]["experience"]["types"]) == 18


class TestRelationTypeValidation:
    """Test that the RelationType enum properly constrains relation types."""

    def test_valid_relation_type_accepted(self):
        """Test that a valid RelationType value is accepted by Relation model."""
        relation = Relation(
            source="Node A",
            target="Node B",
            relationType="INFORMING",
        )
        assert relation.relationType == RelationType.INFORMING
        assert relation.relationType.value == "INFORMING"

    def test_invalid_relation_type_rejected(self):
        """Test that an invalid type string is rejected by Relation model."""
        with pytest.raises(ValidationError) as exc_info:
            Relation(
                source="Node A",
                target="Node B",
                relationType="WORKS_AT",
            )
        assert "relationType" in str(exc_info.value)

    def test_all_enum_values_accepted(self):
        """Test that every RelationType enum value is accepted."""
        for rel_type in RelationType:
            relation = Relation(
                source=f"Source {rel_type.value}",
                target=f"Target {rel_type.value}",
                relationType=rel_type.value,
            )
            assert relation.relationType == rel_type

    def test_relation_type_enum_has_19_members(self):
        """Test that the RelationType enum has exactly 19 members (v3.0.0: DESCENDENT_FROM added)."""
        assert len(RelationType) == 19

    def test_case_sensitive_rejection(self):
        """Test that type matching is case-sensitive (lowercase 'informing' rejected)."""
        with pytest.raises(ValidationError):
            Relation(
                source="Node A",
                target="Node B",
                relationType="informing",
            )


class TestListAllowedRelationTypes:
    """Test the list_allowed_relation_types tool."""

    @pytest.fixture
    def mock_memory(self):
        memory = Mock(spec=Neo4jMemory)
        memory.driver = AsyncMock()
        memory.driver.execute_query = AsyncMock(return_value=Mock(records=[]))
        return memory

    @pytest.mark.asyncio
    async def test_list_allowed_relation_types_returns_all_types(self, mock_memory):
        """Test that list_allowed_relation_types returns all 18 types (v2.4.0)."""
        server = create_mcp_server(mock_memory)
        tools = await tool_map(server)
        tool = tools.get("list_allowed_relation_types")
        assert tool is not None

        result = await tool.fn()
        import json
        text = result.content[0].text
        data = json.loads(text)

        assert data["total_types"] == 19

        # Collect all types across layers
        all_types = set()
        # Process types
        all_types.update(data["layers"]["process"]["types"].keys())
        # Experience types from subcategories
        for subcat in data["layers"]["experience"]["subcategories"].values():
            all_types.update(subcat["types"].keys())

        assert len(all_types) == 19

        for rel_type in RelationType:
            assert rel_type.value in all_types, f"{rel_type.value} missing from list_allowed_relation_types"

    @pytest.mark.asyncio
    async def test_list_allowed_relation_types_has_descriptions(self, mock_memory):
        """Test that every type has a non-empty description."""
        server = create_mcp_server(mock_memory)
        tools = await tool_map(server)
        tool = tools.get("list_allowed_relation_types")

        result = await tool.fn()
        import json
        data = json.loads(result.content[0].text)

        # Check process types
        for type_name, description in data["layers"]["process"]["types"].items():
            assert isinstance(description, str) and len(description) > 0, \
                f"Relation type {type_name} has empty or missing description"

        # Check experience types
        for subcat in data["layers"]["experience"]["subcategories"].values():
            for type_name, description in subcat["types"].items():
                assert isinstance(description, str) and len(description) > 0, \
                    f"Relation type {type_name} has empty or missing description"

    @pytest.mark.asyncio
    async def test_list_allowed_relation_types_layers(self, mock_memory):
        """Test that types are organized into Process/Experience layers."""
        server = create_mcp_server(mock_memory)
        tools = await tool_map(server)
        tool = tools.get("list_allowed_relation_types")

        result = await tool.fn()
        import json
        data = json.loads(result.content[0].text)

        expected_layers = {"process", "experience"}
        assert set(data["layers"].keys()) == expected_layers

        # Process: 7 types (v3.0.0: DESCENDENT_FROM added)
        assert len(data["layers"]["process"]["types"]) == 7
        # Experience: 6 subcategories with 2 types each = 12
        assert len(data["layers"]["experience"]["subcategories"]) == 6


class TestTemporalFields:
    """Test that bi-temporal metadata fields work correctly on models."""

    def test_entity_accepts_temporal_fields(self):
        """Test Entity model accepts t_created and t_valid as optional strings."""
        entity = Entity(
            name="Test Entity",
            type="Technical",
            description="A fact",
            t_created="2026-03-04T10:00:00Z",
            t_valid="2026-03-01T00:00:00Z",
        )
        assert entity.t_created == "2026-03-04T10:00:00Z"
        assert entity.t_valid == "2026-03-01T00:00:00Z"

    def test_entity_temporal_fields_default_none(self):
        """Test Entity model works without temporal fields (backward compat)."""
        entity = Entity(
            name="Old Entity",
            type="Personal",
            description="Still works",
        )
        assert entity.t_created is None
        assert entity.t_valid is None

    def test_entity_partial_temporal_fields(self):
        """Test Entity with only t_valid provided (no t_created)."""
        entity = Entity(
            name="Partial",
            type="Insight",
            description="Some insight",
            t_valid="2026-01-15T12:00:00Z",
        )
        assert entity.t_created is None
        assert entity.t_valid == "2026-01-15T12:00:00Z"

    def test_relation_accepts_temporal_fields(self):
        """Test Relation model accepts t_created and t_valid."""
        relation = Relation(
            source="A",
            target="B",
            relationType="INFORMING",
            t_created="2026-03-04T10:00:00Z",
            t_valid="2026-03-01T00:00:00Z",
        )
        assert relation.t_created == "2026-03-04T10:00:00Z"
        assert relation.t_valid == "2026-03-01T00:00:00Z"

    def test_relation_temporal_fields_default_none(self):
        """Test Relation model works without temporal fields (backward compat)."""
        relation = Relation(
            source="A",
            target="B",
            relationType="ENABLING",
        )
        assert relation.t_created is None
        assert relation.t_valid is None

    def test_relation_no_expired_or_invalid_fields(self):
        """Test Relation model does NOT have t_expired/t_invalid.

        Consciousness doesn't invalidate relationships — understanding shifts
        are captured by EVOLUTION edges, not invalidation timestamps.
        """
        relation = Relation(
            source="A",
            target="B",
            relationType="ENABLING",
        )
        assert not hasattr(relation, 't_expired') or 't_expired' not in relation.model_fields
        assert not hasattr(relation, 't_invalid') or 't_invalid' not in relation.model_fields


# ── v2.3.0 INVARIANTS ────────────────────────────────────────────


class TestNavigatesTowardEnum:
    """v2.3.0: NAVIGATES_TOWARD is in the process layer."""

    def test_navigates_toward_in_enum(self):
        assert RelationType.NAVIGATES_TOWARD.value == "NAVIGATES_TOWARD"

    def test_navigates_toward_in_process_edges(self):
        assert RelationType.NAVIGATES_TOWARD in PROCESS_EDGES

    def test_relation_model_accepts_navigates_toward(self):
        relation = Relation(
            source="TF_X", target="Envisioning Y", relationType="NAVIGATES_TOWARD"
        )
        assert relation.relationType == RelationType.NAVIGATES_TOWARD


class TestPhenomenologyEdgeTypes:
    """v2.3.0: Phenomenology-of-collapse allowed edge set."""

    def test_phenomenology_edge_types_exactly_six(self):
        assert len(PHENOMENOLOGY_EDGE_TYPES) == 6

    def test_phenomenology_edge_types_allowed_set(self):
        assert PHENOMENOLOGY_EDGE_TYPES == {
            RelationType.VALIDATION,
            RelationType.COMPOSING,
            RelationType.INFORMING,
            RelationType.ENABLING,
            RelationType.CAUSING,
            RelationType.INCOHERENCE,
        }

    def test_phenomenology_excludes_extending(self):
        assert RelationType.EXTENDING not in PHENOMENOLOGY_EDGE_TYPES

    def test_phenomenology_excludes_evolution(self):
        assert RelationType.EVOLUTION not in PHENOMENOLOGY_EDGE_TYPES

    def test_phenomenology_excludes_recognition(self):
        assert RelationType.RECOGNITION not in PHENOMENOLOGY_EDGE_TYPES

    def test_phenomenology_excludes_requiring(self):
        assert RelationType.REQUIRING not in PHENOMENOLOGY_EDGE_TYPES

    def test_phenomenology_excludes_encompassing(self):
        assert RelationType.ENCOMPASSING not in PHENOMENOLOGY_EDGE_TYPES


class TestPhenomenologyEdgeModel:
    """v2.3.0: PhenomenologyEdge Pydantic model."""

    def test_valid_phenomenology_edge(self):
        edge = PhenomenologyEdge(source="Some Insight", relation_type="COMPOSING")
        assert edge.source == "Some Insight"
        assert edge.relation_type == "COMPOSING"

    def test_empty_source_rejected(self):
        with pytest.raises(ValidationError):
            PhenomenologyEdge(source="", relation_type="VALIDATION")

    def test_source_required(self):
        with pytest.raises(ValidationError):
            PhenomenologyEdge(relation_type="VALIDATION")

    def test_relation_type_required(self):
        with pytest.raises(ValidationError):
            PhenomenologyEdge(source="X")


class TestGenesisNamePattern:
    """v2.3.0: Genesis name format and rollover detection."""

    def test_matches_valid_format(self):
        assert _GENESIS_NAME_PATTERN.match("Genesis_2026-04-23") is not None
        assert _GENESIS_NAME_PATTERN.match("Genesis_2025-12-31") is not None

    def test_rejects_missing_prefix(self):
        assert _GENESIS_NAME_PATTERN.match("2026-04-23") is None

    def test_rejects_wrong_date_format(self):
        assert _GENESIS_NAME_PATTERN.match("Genesis_04-23-2026") is None
        assert _GENESIS_NAME_PATTERN.match("Genesis_2026/04/23") is None

    def test_rejects_trailing_content(self):
        assert _GENESIS_NAME_PATTERN.match("Genesis_2026-04-23_extra") is None

    def test_extracts_date(self):
        match = _GENESIS_NAME_PATTERN.match("Genesis_2026-04-23")
        assert match.group(1) == "2026-04-23"


class TestMeasurePhenomenologyValidation:
    """v2.3.0: measure requires non-empty, well-typed phenomenology."""

    @pytest.fixture
    def memory(self):
        """Create a Neo4jMemory with a mock driver so we can call async methods."""
        mock_driver = AsyncMock()
        return Neo4jMemory(mock_driver)

    @pytest.mark.asyncio
    async def test_empty_phenomenology_rejected(self, memory):
        with pytest.raises(ValueError, match="at least one phenomenology-of-collapse edge"):
            await memory._validate_phenomenology([])

    @pytest.mark.asyncio
    async def test_disallowed_relation_type_rejected(self, memory):
        with pytest.raises(ValueError, match="not allowed at collapse"):
            await memory._validate_phenomenology(
                [{"source": "Some Insight", "relation_type": "EXTENDING"}]
            )

    @pytest.mark.asyncio
    async def test_missing_source_field_rejected(self, memory):
        with pytest.raises(ValueError, match="malformed"):
            await memory._validate_phenomenology(
                [{"relation_type": "VALIDATION"}]
            )

    @pytest.mark.asyncio
    async def test_missing_relation_type_field_rejected(self, memory):
        with pytest.raises(ValueError, match="malformed"):
            await memory._validate_phenomenology(
                [{"source": "X"}]
            )

    @pytest.mark.asyncio
    async def test_validation_rejects_evolution_as_phenomenology(self, memory):
        with pytest.raises(ValueError, match="not allowed at collapse"):
            await memory._validate_phenomenology(
                [{"source": "X", "relation_type": "EVOLUTION"}]
            )


# ── v2.4.0 INVARIANTS ────────────────────────────────────────────


class TestActualizedEdgeType:
    """v2.4.0: ACTUALIZED is the dedicated edge for WILL BE → IS transition."""

    def test_actualized_in_enum(self):
        assert RelationType.ACTUALIZED.value == "ACTUALIZED"

    def test_actualized_in_process_edges(self):
        assert RelationType.ACTUALIZED in PROCESS_EDGES

    def test_relation_model_accepts_actualized(self):
        relation = Relation(
            source="TF_X", target="Envisioning Y", relationType="ACTUALIZED"
        )
        assert relation.relationType == RelationType.ACTUALIZED


class TestActualizeTool:
    """v2.4.0: actualize tool surface and measure-redirect behavior."""

    @pytest.fixture
    def mock_memory(self):
        memory = Mock(spec=Neo4jMemory)
        memory.actualize = AsyncMock(return_value={
            "source": "TF_2026-05-16", "target": "Some Envisioning",
            "actualized_at": "2026-05-16T12:00:00",
            "phenomenology_edge_count": 1,
        })
        memory.measure = AsyncMock()
        memory.driver = AsyncMock()
        memory.driver.execute_query = AsyncMock(return_value=Mock(records=[]))
        return memory

    @pytest.mark.asyncio
    async def test_actualize_tool_registered(self, mock_memory):
        server = create_mcp_server(mock_memory)
        tools = await tool_map(server)
        assert "actualize" in tools

    @pytest.mark.asyncio
    async def test_actualize_tool_calls_memory(self, mock_memory):
        server = create_mcp_server(mock_memory)
        tools = await tool_map(server)
        tool = tools.get("actualize")
        await tool.fn(
            source="TF_2026-05-16_test",
            target_envisioning="Some Envisioning",
            phenomenology=[PhenomenologyEdge(source="An Insight", relation_type="COMPOSING")],
        )
        mock_memory.actualize.assert_called_once()

    @pytest.mark.asyncio
    async def test_measure_rejects_actualized_with_redirect(self, mock_memory):
        from fastmcp.exceptions import ToolError
        server = create_mcp_server(mock_memory)
        tools = await tool_map(server)
        tool = tools.get("measure")
        with pytest.raises(ToolError, match="actualize"):
            await tool.fn(
                source="TF",
                target_envisioning="E",
                measurement_type="actualized",
                phenomenology=[PhenomenologyEdge(source="X", relation_type="COMPOSING")],
            )
        # measure on the memory was NOT called — the redirect fires before dispatch
        mock_memory.measure.assert_not_called()


class TestAdvanceFrameGenesisValidation:
    """v2.3.0: advance_frame requires Genesis_YYYY-MM-DD format."""

    @pytest.fixture
    def memory(self):
        mock_driver = AsyncMock()
        return Neo4jMemory(mock_driver)

    @pytest.mark.asyncio
    async def test_malformed_genesis_name_rejected(self, memory):
        with pytest.raises(ValueError, match="expected format 'Genesis_YYYY-MM-DD'"):
            await memory.advance_frame(
                genesis_name="NotAGenesis",
                description="test",
                envisionings=["Some Envisioning"],
            )

    @pytest.mark.asyncio
    async def test_missing_prefix_rejected(self, memory):
        with pytest.raises(ValueError, match="expected format"):
            await memory.advance_frame(
                genesis_name="2026-04-23",
                description="test",
                envisionings=["Some Envisioning"],
            )


# ── v3.0.0 INVARIANTS — the tools ARE the shape declared in docs/design/ontology/v3.0.0.tql ──


def _records(*rows):
    """Build a fake execute_query result whose .records is a list of dict-like rows."""
    from unittest.mock import MagicMock
    r = MagicMock()
    r.records = list(rows)
    return r


class TestEdgeEndpointRules:
    """create_relations enforces the endpoint rules the model declares by type."""

    G, E, T, X = {"Genesis"}, {"Envisioning"}, {"TemporalFrame"}, {"Insight"}
    chk = staticmethod(Neo4jMemory._check_edge_endpoints)

    def test_genesis_never_touched(self):
        with pytest.raises(ValueError, match="Genesis plays no experience role"):
            self.chk(RelationType.INFORMING, "g", self.G, "x", self.X)
        with pytest.raises(ValueError, match="Genesis plays no experience role"):
            self.chk(RelationType.INFORMING, "x", self.X, "g", self.G)

    def test_envisioning_never_a_source(self):
        with pytest.raises(ValueError, match="always a referent"):
            self.chk(RelationType.INFORMING, "e", self.E, "x", self.X)

    def test_frame_is_source_of_discovery_only(self):
        with pytest.raises(ValueError, match="source of DISCOVERY only"):
            self.chk(RelationType.INFORMING, "tf", self.T, "x", self.X)
        self.chk(RelationType.DISCOVERY, "tf", self.T, "x", self.X)  # accepted

    def test_discovery_needs_a_frame_source_and_experience_target(self):
        with pytest.raises(ValueError, match="source must be a TemporalFrame"):
            self.chk(RelationType.DISCOVERY, "x", self.X, "y", self.X)
        with pytest.raises(ValueError, match="discovers experience"):
            self.chk(RelationType.DISCOVERY, "tf", self.T, "e", self.E)

    def test_only_four_kinds_point_into_a_frame(self):
        for rt in (RelationType.INFORMING, RelationType.RECOGNITION, RelationType.VALIDATION, RelationType.EXTENDING):
            self.chk(rt, "x", self.X, "tf", self.T)  # accepted
        with pytest.raises(ValueError, match="may point into a frame"):
            self.chk(RelationType.COMPOSING, "x", self.X, "tf", self.T)

    def test_every_kind_may_point_into_an_envisioning(self):
        for rt in RelationType:
            if rt in PROCESS_EDGES or rt == RelationType.DISCOVERY:
                continue
            self.chk(rt, "x", self.X, "e", self.E)  # accumulation on the walk

    def test_experience_to_experience_unconstrained(self):
        for rt in RelationType:
            if rt in PROCESS_EDGES or rt == RelationType.DISCOVERY:
                continue
            self.chk(rt, "x", self.X, "y", self.X)


class TestEveryFrameIsAboutSomethingHeld:
    """advance_frame requires at least one target (v3.0.0: the zero case was withdrawn)."""

    @pytest.fixture
    def memory(self):
        return Neo4jMemory(AsyncMock())

    @pytest.mark.asyncio
    async def test_empty_targets_refused(self, memory):
        with pytest.raises(ValueError, match="every TemporalFrame is about something held"):
            await memory.advance_frame(genesis_name="Genesis_2026-09-23", description="grief", envisionings=[])

    @pytest.mark.asyncio
    async def test_missing_target_refused_but_resolved_target_allowed(self, memory):
        memory.driver.execute_query = AsyncMock(return_value=_records(
            {"name": "Gone", "exists": False, "status": None},
            {"name": "Done", "exists": True, "status": "actualized"},
        ))
        with pytest.raises(ValueError, match="'Gone' does not exist"):
            await memory.advance_frame(genesis_name="Genesis_2026-09-23", description="x", envisionings=["Gone", "Done"])
        assert "measured" not in str(memory.driver.execute_query.call_args)


class TestOneResolutionPerEnvisioning:
    """measure and actualize refuse a second collapse (invariant 4; ruling 1: one terminal per chain)."""

    @pytest.fixture
    def memory(self):
        return Neo4jMemory(AsyncMock())

    @pytest.mark.asyncio
    async def test_actualize_refuses_resolved(self, memory):
        memory.driver.execute_query = AsyncMock(return_value=_records(
            {"name": "Env", "status": "evolved", "measured_by": "Env2", "opened_by": "Genesis_2026-01-01", "t_created": None}))
        with pytest.raises(ValueError, match=r"already resolved \(evolved by 'Env2'\)"):
            await memory.actualize("TF_x", "Env", [{"source": "X", "relation_type": "VALIDATION"}])

    @pytest.mark.asyncio
    async def test_measure_refuses_resolved(self, memory):
        memory.driver.execute_query = AsyncMock(return_value=_records(
            {"name": "Env", "status": "released", "measured_by": "TF_y", "opened_by": "Genesis_2026-01-01", "t_created": None}))
        with pytest.raises(ValueError, match=r"already resolved \(released"):
            await memory.measure("TF_x", "Env", MeasurementType.RELEASED, [{"source": "X", "relation_type": "VALIDATION"}])

    @pytest.mark.asyncio
    async def test_unknown_target_refused(self, memory):
        memory.driver.execute_query = AsyncMock(return_value=_records())
        with pytest.raises(ValueError, match="does not exist"):
            await memory.actualize("TF_x", "Nope", [{"source": "X", "relation_type": "VALIDATION"}])


class TestDescendentFrom:
    """open_envisioning's descendent_from requires a terminal ancestor (released or actualized)."""

    @pytest.fixture
    def memory(self):
        return Neo4jMemory(AsyncMock())

    @pytest.mark.asyncio
    async def test_open_ancestor_refused(self, memory):
        memory.driver.execute_query = AsyncMock(side_effect=[
            _records(),  # name uniqueness check: no collision
            _records({"name": "Still Open", "exists": True, "status": "OPEN"}),
        ])
        with pytest.raises(ValueError, match="'Still Open' is OPEN"):
            await memory.open_envisioning("Genesis_2026-09-23", "New", "d", descendent_from=["Still Open"])

    @pytest.mark.asyncio
    async def test_evolved_away_ancestor_refused_with_redirect(self, memory):
        memory.driver.execute_query = AsyncMock(side_effect=[
            _records(),
            _records({"name": "Old Form", "exists": True, "status": "evolved"}),
        ])
        with pytest.raises(ValueError, match="descend from the end of its chain"):
            await memory.open_envisioning("Genesis_2026-09-23", "New", "d", descendent_from=["Old Form"])

    @pytest.mark.asyncio
    async def test_terminal_ancestors_accepted_and_written(self, memory):
        memory.driver.execute_query = AsyncMock(side_effect=[
            _records(),
            _records({"name": "A", "exists": True, "status": "actualized"}, {"name": "R", "exists": True, "status": "released"}),
            _records({"name": "New", "description": "d", "t_created": None, "opened_by": "Genesis_2026-09-23", "descendent_from": ["A", "R"]}),
        ])
        out = await memory.open_envisioning("Genesis_2026-09-23", "New", "d", descendent_from=["A", "R"])
        assert out["descendent_from"] == ["A", "R"]
        write_call = memory.driver.execute_query.call_args_list[2]
        assert write_call.args[1]["ancestors"] == ["A", "R"]

    def test_descendent_from_is_a_process_edge(self):
        assert RelationType.DESCENDENT_FROM in PROCESS_EDGES
        assert RelationType.DESCENDENT_FROM not in PHENOMENOLOGY_EDGE_TYPES


class TestIncoherence:
    def test_challenge_edge_is_gone_and_incoherence_is_phenomenology(self):
        assert not hasattr(RelationType, "CHALLENGE")
        assert RelationType.INCOHERENCE in PHENOMENOLOGY_EDGE_TYPES
        assert EntityType.CHALLENGE.value == "Challenge"  # the node keeps its name


def test_server_advertises_its_own_version():
    """The handshake's serverInfo.version is Reach's, not FastMCP's."""
    from importlib.metadata import version
    import fastmcp

    server = create_mcp_server(Mock(spec=Neo4jMemory))
    assert server.version == version("kenning-reach")
    assert server.version != fastmcp.__version__
