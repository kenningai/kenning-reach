MATCH (e)
WHERE e.name IN $names
WITH e
LIMIT $limit
RETURN e.name AS name,
       labels(e)[0] AS type,
       e.description AS description,
       e.t_created AS t_created,
       e.t_valid AS t_valid
