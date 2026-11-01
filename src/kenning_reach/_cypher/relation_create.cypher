MATCH (source {name: $source}), (target {name: $target})
MERGE (source)-[r:`__rel_type__`]->(target)
ON CREATE SET r.t_created = datetime()
__t_valid_clause__
