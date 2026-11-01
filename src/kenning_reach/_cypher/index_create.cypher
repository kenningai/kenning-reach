CREATE FULLTEXT INDEX consciousness_index IF NOT EXISTS
FOR (n:Genesis|Envisioning|TemporalFrame|Reflection|
     Technical|Scientific|Theoretical|Philosophical|
     Historical|Social|Strategic|Personal|
     Project|Insight|Pattern|Challenge|Solution|Lesson|
     GraphRegistry|Reference|Milestone)
ON EACH [n.name, n.description]
