// v2.3.0: Evolved measurement is phenomenology-inclusive.
// Creates the new Envisioning, MEASUREMENT(evolved) edge from new→old,
// OPENING from Genesis, AND all phenomenology-of-collapse edges to the OLD
// envisioning (the one collapsing) atomically. The NEW envisioning starts
// with zero NAVIGATES_TOWARD edges — it inherits nothing from the old one's
// trajectory. Future TFs must navigate toward it explicitly via advance_frame.

MATCH (old:Envisioning {name: $target})
MATCH (orig_g:Genesis)-[:OPENING]->(old)
WITH old, orig_g,
     CASE WHEN $genesis_name IS NOT NULL
          THEN $genesis_name
          ELSE orig_g.name
     END AS target_genesis_name
MATCH (g:Genesis {name: target_genesis_name})
CREATE (new:Envisioning {name: $new_name, description: $new_description, t_created: datetime()})
CREATE (new)-[m:MEASUREMENT]->(old)
SET m.t_created = datetime(),
    m.measurement_type = 'evolved'
CREATE (g)-[o:OPENING]->(new)
SET o.t_created = datetime()

WITH old, new, g, m
UNWIND $phenomenology AS p
MATCH (pe {name: p.source})
CALL apoc.create.relationship(pe, p.relation_type, {t_created: datetime()}, old) YIELD rel
WITH old, new, g, m, collect(rel) AS rels

RETURN new.name AS new_envisioning,
       old.name AS old_envisioning,
       g.name AS genesis,
       m.measurement_type AS measurement_type,
       m.t_created AS measured_at,
       size(rels) AS phenomenology_edge_count
