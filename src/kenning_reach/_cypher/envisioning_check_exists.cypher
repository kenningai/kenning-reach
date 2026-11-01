// Check if an Envisioning with this name already exists.
// Returns full diagnostic info so the caller can tell the LLM what they collided with.
// Name uniqueness is a structural invariant — envisionings must be uniquely named so
// they can be unambiguously referenced by measure, actualize, advance_frame, and queries.
//
// v2.4.0: Closing edges are MEASUREMENT (released, evolved) OR ACTUALIZED.
// Status is derived from edge type: ACTUALIZED → "actualized"; MEASUREMENT → its
// measurement_type value.
MATCH (e:Envisioning {name: $name})
OPTIONAL MATCH (g:Genesis)-[:OPENING]->(e)
OPTIONAL MATCH (x)-[m:MEASUREMENT|ACTUALIZED]->(e)
RETURN e.name AS name,
       e.description AS description,
       e.t_created AS t_created,
       g.name AS opened_by,
       CASE WHEN m IS NULL THEN 'OPEN'
            WHEN type(m) = 'ACTUALIZED' THEN 'actualized'
            ELSE m.measurement_type
       END AS status,
       CASE WHEN x:TemporalFrame THEN x.name
            WHEN x:Envisioning THEN x.name
            ELSE null
       END AS measured_by
LIMIT 1
