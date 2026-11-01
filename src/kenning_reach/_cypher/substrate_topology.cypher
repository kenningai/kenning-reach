// Substrate topology: label distribution across the entire graph.
// Returns one row per label, ordered by count descending.
// Bounded by the number of entity types (max 21). Cannot grow unboundedly.
MATCH (n)
RETURN labels(n)[0] AS type, count(*) AS count
ORDER BY count DESC
