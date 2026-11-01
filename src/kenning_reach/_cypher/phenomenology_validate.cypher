// Pre-check for measure's phenomenology coupling.
// For each source name, report whether it exists and whether it is a
// process-type node (Genesis/Envisioning/TemporalFrame). Experience edges
// are forbidden between two process-type nodes (v2.0 invariant) — since
// the target is always an Envisioning (process), sources MUST be experience-layer.

UNWIND $names AS name
OPTIONAL MATCH (n {name: name})
RETURN name,
       n IS NOT NULL AS exists,
       CASE
         WHEN n IS NULL THEN false
         WHEN n:Genesis OR n:Envisioning OR n:TemporalFrame THEN true
         ELSE false
       END AS is_process_type
