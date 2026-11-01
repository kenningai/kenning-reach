MATCH (s {name: $source}), (t {name: $target})
RETURN labels(s) AS source_labels, labels(t) AS target_labels
