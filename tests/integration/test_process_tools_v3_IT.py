"""v3.0.0 process-tool rules against a real Neo4j (testcontainers, APOC) — the rules the
mocked suite cannot see, exercised in both directions, in the order a day is lived.

The formal model (docs/design/ontology/v3.0.0.tql) is the claim; this proves the tools
write what it declares and refuse what it refuses.
"""
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from neo4j import AsyncGraphDatabase

from kenning_reach.neo4j_memory import Entity, MeasurementType, Neo4jMemory, Relation


@pytest_asyncio.fixture
async def memory(setup):
    driver = AsyncGraphDatabase.driver(setup.get_connection_url(), auth=(setup.username, setup.password))
    await driver.execute_query("MATCH (n) DETACH DELETE n")
    m = Neo4jMemory(driver)
    await m.create_fulltext_index()
    try:
        yield m
    finally:
        await driver.close()


async def count(memory, cypher, **params):
    r = await memory.driver.execute_query(cypher, params)
    return r.records[0]["n"]


@pytest.mark.asyncio
async def test_a_day_under_the_v3_rules(memory):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    g = (await memory.navigate_genesis(today))["genesis"]
    assert g == f"Genesis_{today}"

    # --- open a possibility; nothing may descend from an OPEN one
    alpha = await memory.open_envisioning(g, "Alpha", "a future held")
    assert alpha["descendent_from"] == []
    with pytest.raises(ValueError, match="'Alpha' is OPEN"):
        await memory.open_envisioning(g, "Too Early", "x", descendent_from=["Alpha"])

    # --- every frame is about something held
    with pytest.raises(ValueError, match="every TemporalFrame is about something held"):
        await memory.advance_frame(g, "grief", envisionings=[])
    tf1 = (await memory.advance_frame(g, "first frame", envisionings=["Alpha"]))["name"]
    assert await count(memory, "MATCH (:TemporalFrame {name:$n})-[:NAVIGATES_TOWARD]->() RETURN count(*) AS n", n=tf1) == 1

    # --- experience, and the endpoint rules by type
    await memory.create_entities([Entity(name="I1", type="Insight", description="seen"),
                                  Entity(name="T1", type="Technical", description="built")])
    ok = [Relation(source=tf1, target="I1", relationType="DISCOVERY"),      # frame discovers experience
          Relation(source="I1", target=tf1, relationType="INFORMING"),      # experience informs the frame
          Relation(source="I1", target="Alpha", relationType="EXTENDING"),  # any kind accumulates on a possibility
          Relation(source="I1", target="T1", relationType="INCOHERENCE")]   # the renamed edge
    await memory.create_relations(ok)
    assert await count(memory, "MATCH ()-[r:INCOHERENCE]->() RETURN count(r) AS n") == 1
    for bad, msg in [
        (Relation(source="I1", target=tf1, relationType="COMPOSING"), "may point into a frame"),
        (Relation(source="Alpha", target="I1", relationType="INFORMING"), "always a referent"),
        (Relation(source=tf1, target="I1", relationType="INFORMING"), "source of DISCOVERY only"),
        (Relation(source="I1", target=g, relationType="INFORMING"), "Genesis plays no experience role"),
        (Relation(source="I1", target="Alpha", relationType="DISCOVERY"), "source must be a TemporalFrame"),
        (Relation(source="I1", target="Nobody", relationType="INFORMING"), "does not exist"),
        (Relation(source="I1", target="T1", relationType="DESCENDENT_FROM"), "Process edges"),
    ]:
        with pytest.raises(ValueError, match=msg):
            await memory.create_relations([bad])

    # --- one terminal per chain
    await memory.actualize(tf1, "Alpha", [{"source": "I1", "relation_type": "VALIDATION"}])
    with pytest.raises(ValueError, match="already resolved \\(actualized"):
        await memory.actualize(tf1, "Alpha", [{"source": "I1", "relation_type": "VALIDATION"}])
    with pytest.raises(ValueError, match="already resolved"):
        await memory.measure(tf1, "Alpha", MeasurementType.RELEASED, [{"source": "I1", "relation_type": "CAUSING"}])

    # --- reaching for what IS, and descending from it
    tf2 = (await memory.advance_frame(g, "second frame", envisionings=["Alpha"]))["name"]
    assert tf2 != tf1
    beta = await memory.open_envisioning(g, "Beta", "what Alpha made possible", descendent_from=["Alpha"])
    assert beta["descendent_from"] == ["Alpha"]
    assert await count(memory, "MATCH (:Envisioning {name:'Beta'})-[:DESCENDENT_FROM]->(:Envisioning {name:'Alpha'}) RETURN count(*) AS n") == 1
    assert await count(memory, "MATCH ()-[m:MEASUREMENT|ACTUALIZED]->(:Envisioning {name:'Alpha'}) RETURN count(m) AS n") == 1  # lineage did not resolve it again

    # --- evolution: names stay unique, and an evolved-away form is not a terminal
    with pytest.raises(ValueError, match="already exists"):
        await memory.measure(tf2, "Beta", MeasurementType.EVOLVED, [{"source": "I1", "relation_type": "INFORMING"}], new_name="Alpha")
    await memory.measure(tf2, "Beta", MeasurementType.EVOLVED, [{"source": "I1", "relation_type": "INFORMING"}],
                         new_name="Gamma", new_description="Beta reshaped")
    with pytest.raises(ValueError, match="descend from the end of its chain"):
        await memory.open_envisioning(g, "Delta", "x", descendent_from=["Beta"])
    gamma_released = await memory.measure(tf2, "Gamma", MeasurementType.RELEASED, [{"source": "T1", "relation_type": "INCOHERENCE"}])
    assert gamma_released["measurement_type"] == "released"
    delta = await memory.open_envisioning(g, "Delta", "after Gamma was let go", descendent_from=["Gamma", "Alpha"])
    assert sorted(delta["descendent_from"]) == ["Alpha", "Gamma"]

    # --- the shape the model declares, read back from the graph
    assert await count(memory, "MATCH (tf:TemporalFrame) WHERE NOT (tf)-[:NAVIGATES_TOWARD]->() RETURN count(tf) AS n") == 0
    assert await count(memory, "MATCH (e:Envisioning) WITH e, COUNT{(x)-[:MEASUREMENT|ACTUALIZED]->(e)} AS c WHERE c > 1 RETURN count(e) AS n") == 0
    assert await count(memory, "MATCH (tf:TemporalFrame) WITH tf, COUNT{(x)-[:SEQUENCE]->(tf)} AS c WHERE c <> 1 RETURN count(tf) AS n") == 0
    assert await count(memory, "MATCH ()-[r]->() WHERE r.t_created IS NULL RETURN count(r) AS n") == 0
    assert await count(memory, "MATCH (e:Envisioning) WHERE NOT (:Genesis)-[:OPENING]->(e) RETURN count(e) AS n") == 0
