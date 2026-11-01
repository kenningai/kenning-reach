// v2.4.0: Closing edges include both MEASUREMENT (released, evolved) and ACTUALIZED.
// OPEN = neither inbound MEASUREMENT nor inbound ACTUALIZED.
// CLOSED status is derived from edge type: ACTUALIZED edge → "actualized";
// MEASUREMENT edge → its measurement_type (released, evolved).

MATCH (g:Genesis)-[:OPENING]->(e:Envisioning)
__time_filter__
__envisioning_filter__
OPTIONAL MATCH (x)-[m:MEASUREMENT|ACTUALIZED]->(e)
__measurement_filter__
RETURN e.name AS name, g.name AS opened_by, e.t_created AS t_created,
       e.description AS description,
       CASE WHEN m IS NULL THEN 'OPEN'
            WHEN type(m) = 'ACTUALIZED' THEN 'actualized'
            ELSE m.measurement_type
       END AS status,
       m.t_created AS measured_at,
       CASE WHEN x:TemporalFrame THEN x.name
            WHEN x:Envisioning THEN x.name
            ELSE null
       END AS measured_by
ORDER BY status, e.t_created DESC
LIMIT $limit
