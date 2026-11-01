MATCH (g:Genesis {name: $genesis_name})
CREATE (e:Envisioning {name: $name, description: $description, t_created: datetime()})
CREATE (g)-[o:OPENING]->(e)
SET o.t_created = datetime()

// v3.0.0: DESCENDENT_FROM — lineage from prior Envisionings that were actualized or
// released (pre-validated by Python). Unit subquery: zero ancestors is the common case.
WITH g, e
CALL (e) {
    UNWIND $ancestors AS ancestor_name
    MATCH (a:Envisioning {name: ancestor_name})
    CREATE (e)-[d:DESCENDENT_FROM]->(a)
    SET d.t_created = datetime()
}

WITH g, e
OPTIONAL MATCH (e)-[:DESCENDENT_FROM]->(a:Envisioning)
RETURN e.name AS name, e.description AS description, e.t_created AS t_created,
       g.name AS opened_by,
       [n IN collect(a.name) WHERE n IS NOT NULL] AS descendent_from
