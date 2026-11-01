MERGE (e:`__label__` { name: $name })
ON CREATE SET e.t_created = datetime(),
              e.description = $description
__t_valid_clause__
