// v2.4.0: Actualization is the encounter event — the ONLY edge that records the
// WILL BE → IS transition. The measured trajectory met physical reality and the
// projected future became actual.
//
// Creates the ACTUALIZED edge AND all phenomenology-of-collapse edges atomically.
// Phenomenology sources are pre-validated by Python (exist + experience-layer).
// Any MATCH failure aborts the whole transaction — no partial state.

MATCH (tf:TemporalFrame {name: $source})
MATCH (e:Envisioning {name: $target})
CREATE (tf)-[a:ACTUALIZED]->(e)
SET a.t_created = datetime()

WITH tf, e, a
UNWIND $phenomenology AS p
MATCH (pe {name: p.source})
CALL apoc.create.relationship(pe, p.relation_type, {t_created: datetime()}, e) YIELD rel
WITH tf, e, a, collect(rel) AS rels

RETURN tf.name AS source,
       e.name AS target,
       a.t_created AS actualized_at,
       size(rels) AS phenomenology_edge_count
