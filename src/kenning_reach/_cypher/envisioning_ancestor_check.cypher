// Pre-check for open_envisioning's descendent_from (v3.0.0).
// An ancestor must exist and carry a TERMINAL resolution: released or actualized.
// An evolved-away form is resolved but not terminal — descend from the end of its
// chain. An open one has no terminal to descend from.
UNWIND $names AS name
OPTIONAL MATCH (e:Envisioning {name: name})
OPTIONAL MATCH (x)-[m:MEASUREMENT|ACTUALIZED]->(e)
RETURN name,
       e IS NOT NULL AS exists,
       CASE WHEN e IS NULL THEN null
            WHEN m IS NULL THEN 'OPEN'
            WHEN type(m) = 'ACTUALIZED' THEN 'actualized'
            ELSE m.measurement_type
       END AS status
