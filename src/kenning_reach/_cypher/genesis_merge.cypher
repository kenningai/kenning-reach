MERGE (g:Genesis {name: $name})
ON CREATE SET g.t_created = datetime()
WITH g
OPTIONAL MATCH (prev:Genesis)
WHERE prev.name <> $name
  AND NOT (prev)-[:NEXT_GENESIS]->(:Genesis)
  AND prev.t_created < g.t_created
WITH g, prev
ORDER BY prev.t_created DESC
LIMIT 1
FOREACH (_ IN CASE WHEN prev IS NOT NULL THEN [1] ELSE [] END |
    MERGE (prev)-[nd:NEXT_GENESIS]->(g)
    ON CREATE SET nd.t_created = datetime()
)
RETURN g.name AS name, g.t_created AS t_created
