CALL db.index.fulltext.queryNodes('consciousness_index', $filter) YIELD node, score
WITH node, score
ORDER BY score DESC
LIMIT $limit
RETURN node.name AS name, labels(node)[0] AS type, node.description AS description,
       score, node.t_created AS t_created, node.t_valid AS t_valid
