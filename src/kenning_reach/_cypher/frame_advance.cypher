// v2.3.0: Strict temporal SEQUENCE + NAVIGATES_TOWARD (0..N cardinality).
// SEQUENCE is now strictly temporal succession within a Genesis's day:
//   First TF of day:       Genesis → SEQUENCE → new_tf
//   Subsequent TFs of day: prior_TF → SEQUENCE → new_tf
// NAVIGATES_TOWARD carries the intentional trajectory separately:
//   new_tf → NAVIGATES_TOWARD → Envisioning  (0..N per TF)
// Envisionings are pre-validated by Python layer to exist and be OPEN.

MATCH (current_g:Genesis {name: $genesis_name})

// Find the most recent TF reachable from current_g via SEQUENCE*.
// If none exists, this TF is first-of-day and SEQUENCE comes from Genesis itself.
OPTIONAL MATCH (current_g)-[:SEQUENCE*]->(prior_tf:TemporalFrame)
WITH current_g, prior_tf
ORDER BY prior_tf.t_created DESC
LIMIT 1

WITH current_g,
     CASE WHEN prior_tf IS NULL THEN current_g ELSE prior_tf END AS predecessor,
     prior_tf IS NULL AS is_first_of_day

CREATE (new_tf:TemporalFrame {
    name: $tf_name,
    description: $description,
    t_created: datetime()
})
CREATE (predecessor)-[s:SEQUENCE]->(new_tf)
SET s.t_created = datetime()

// Neo4j 5.x requires WITH between a write clause (SET) and CALL.
WITH new_tf, current_g, predecessor, is_first_of_day

// Create NAVIGATES_TOWARD edges as a unit subquery (side-effects only).
// Unit subqueries preserve outer row count even when UNWIND is empty,
// so the zero-case (envisionings=[]) is handled cleanly.
// Uses Neo4j 5.x+ scope-clause syntax: CALL (var) { ... }
CALL (new_tf) {
    UNWIND $envisionings AS env_name
    MATCH (env:Envisioning {name: env_name})
    CREATE (new_tf)-[n:NAVIGATES_TOWARD]->(env)
    SET n.t_created = datetime()
}

// Gather trajectory names for return payload.
WITH new_tf, current_g, predecessor, is_first_of_day
OPTIONAL MATCH (new_tf)-[:NAVIGATES_TOWARD]->(env:Envisioning)
WITH new_tf, current_g, predecessor, is_first_of_day,
     [n IN collect(env.name) WHERE n IS NOT NULL] AS navigates_toward

RETURN new_tf.name AS name,
       new_tf.description AS description,
       new_tf.t_created AS t_created,
       current_g.name AS temporal_ground,
       predecessor.name AS sequence_predecessor,
       is_first_of_day,
       navigates_toward
