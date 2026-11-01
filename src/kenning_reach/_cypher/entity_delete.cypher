UNWIND $entities as name
MATCH (e {name: name})
DETACH DELETE e
