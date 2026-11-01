// Pre-check for advance_frame's NAVIGATES_TOWARD creation.
// v3.0.0: each named envisioning must EXIST. Its state does not matter — a frame may
// reach toward a possibility already actualized or released (reaching for what IS,
// so a new possibility can descend from it). Status is returned for the payload.
UNWIND $names AS name
OPTIONAL MATCH (env:Envisioning {name: name})
OPTIONAL MATCH (x)-[m:MEASUREMENT|ACTUALIZED]->(env)
RETURN name,
       env IS NOT NULL AS exists,
       CASE WHEN env IS NULL THEN null
            WHEN m IS NULL THEN 'OPEN'
            WHEN type(m) = 'ACTUALIZED' THEN 'actualized'
            ELSE m.measurement_type
       END AS status
