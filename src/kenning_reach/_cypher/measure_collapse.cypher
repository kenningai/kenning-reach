// v2.4.0: MEASUREMENT is internal collapse within possibility space.
// This cypher serves the "released" path (TF → Envisioning). The "evolved" path
// uses measure_evolved.cypher. The "actualized" path was split out into a
// separate edge type (ACTUALIZED) — see actualize.cypher.
//
// Creates the MEASUREMENT edge AND all phenomenology-of-collapse edges atomically.
// Phenomenology sources are pre-validated by Python (exist + experience-layer).
// Any MATCH failure aborts the whole transaction — no partial state.

MATCH (tf:TemporalFrame {name: $source})
MATCH (e:Envisioning {name: $target})
CREATE (tf)-[m:MEASUREMENT]->(e)
SET m.t_created = datetime(),
    m.measurement_type = $measurement_type

WITH tf, e, m
UNWIND $phenomenology AS p
MATCH (pe {name: p.source})
CALL apoc.create.relationship(pe, p.relation_type, {t_created: datetime()}, e) YIELD rel
WITH tf, e, m, collect(rel) AS rels

RETURN tf.name AS source,
       e.name AS target,
       m.measurement_type AS measurement_type,
       m.t_created AS measured_at,
       size(rels) AS phenomenology_edge_count
