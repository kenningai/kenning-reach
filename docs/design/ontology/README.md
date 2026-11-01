# Kenning Reach — ontology design

The category-1 conscious experience graph, modeled formally before any code is
changed. This folder is the claim; the implementation is gated against it.

| File | What it is |
|---|---|
| `v3.0.0.tql` | The ontology as held in the written record at v2.4.0, declared strictly. Loads into TypeDB CE 3.12.3. |
| `gate.py` | Two-sided proof on synthetic data: 11 accept, 33 refuse, 5 post-conditions each shown to count a planted violation. `./gate.py --reset` |
| `audit_live.py` | Imports the LIVE graph into the model and counts what the model refuses, by class. `AUDIT_ENV=<env file> uv run python docs/design/ontology/audit_live.py` |

A green load means the model is consistent, not that it is right. A model that
says yes to everything is not a gate; a model that cannot say yes is not a model.

## What the formalism settled by itself

- **Challenge is one symbol in Neo4j and two things.** `:Challenge` (node label)
  and `CHALLENGE` (edge type) coexist in a property graph. TypeQL has one
  namespace, so the model names the node `challenge-node`. That collision is a
  nomenclature defect in the held ontology, not in the model.
- **`phase` on Envisioning was unguarded by construction.** Before it was
  dropped (ruling 6), the gate showed an Envisioning claiming `phase =
  actualized` with no ACTUALIZED edge loads green. A property that restates a
  walk is exactly the drift invitation the "no `type` property" rule was
  written against.
- **The source kind of a MEASUREMENT is its subtype.** `released` is TF → Env,
  `evolved` is Env → Env. A released edge from an Envisioning is not a bad
  value; it is a sentence the query language cannot compose (INF11 at compile).

## Rulings, 2026-09-16

6. **`phase` dropped.** "If there's an ACTUALIZED edge you can walk from the
   Envisioning to its terminus and look. If the ultimate edge is ACTUALIZED then
   by definition the Envisioning is not potentiated." The assessment is the
   walk; topology is the meaning. A property restating a walk is the drift the
   no-`type`-property rule forbids. The attribute is gone from the model and
   the gate refuses it (R24).
7. **The edge is INCOHERENCE; the node stays Challenge.** "They are not all
   CHALLENGES from the inside. They are INCOHERENCE; every single one is shaped
   like a thing that obfuscates the envisioned actualization. The labels? All
   of those are types of Challenges." The TypeQL entity is now `challenge`
   with no suffix; the collision is gone.

## Rulings, 2026-09-18 and 2026-09-22

8. **Every TemporalFrame is about something held.** The zero case (rule 13) was
   wrongly shaped: "to have catharsis what must be prior?"
   The model now requires `navigates-toward:frame @card(1..)` and the
   gate refuses a frame reaching toward nothing. A frame may reach toward a possibility already actualized
   or released: "reaching for what was actualized so we can create a new
   envisioning to actualize the evolution of that."
9. **DESCENDENT_FROM.** A new Envisioning that would not be if not for a prior
   one that was actualized or released. "The envisioning to be would not be if
   not for the actualized that was. Descendent_from is the temporal causality
   of that relation." Any new possibility may descend from any prior with a
   terminal resolution. Lineage, not resolution: the ancestor keeps its one
   terminal and is not re-actualized; the potentiated walk still ends at
   ACTUALIZED.

## Rule labels used in the code

The model, the gate, the audit and the server cite rules by label. Each label
and what it states:

| Label | States |
|---|---|
| rule 1 | The Genesis backbone is continuous: one NEXT_GENESIS chain, every Genesis but the newest has a successor. |
| rule 2 | Every Envisioning has exactly one OPENING, from a Genesis. |
| rule 3 | Every TemporalFrame has exactly one inbound SEQUENCE: from the Genesis if it is the first frame of its day, else from the prior frame. |
| rule 12 | Envisioning names are unique. |
| rule 13 | The zero case: a TemporalFrame reaching toward nothing. Withdrawn by ruling 8; every frame reaches toward at least one Envisioning. |
| rule 14 | A TemporalFrame's day equals the day of the Genesis its SEQUENCE chain starts from. |
| rule 15 | A resolved Envisioning has at least one inbound phenomenology edge (VALIDATION, COMPOSING, INFORMING, ENABLING, CAUSING, INCOHERENCE). |
| invariant 4 | One resolution per Envisioning, across released, evolved and actualized together. |
| invariant 8 | No experience edge between two process nodes. |
| invariant 10 | Every node and every edge carries t_created. |
| invariant 13 | MEASUREMENT carries measurement_type; no other edge carries anything beyond t_created, except an optional t_valid. |
| ruling 1 | One terminal per chain: an evolved-away form is resolved, and releasing or actualizing it later is refused. |
| ruling 2 | A TemporalFrame is the source of DISCOVERY only; INFORMING, RECOGNITION, VALIDATION and EXTENDING may point into it. |
| ruling 3 | An Envisioning is never the source of an edge. |
| ruling 4 | Every experience kind may point into an Envisioning; it accumulates as the trajectory toward it is walked. |
| AP1 | A Genesis plays no experience role: nothing experience-layer touches it. |

Rulings 6 to 9 are stated in full above.

## Loading it yourself

TypeDB CE 3.12.3, HTTP API on `localhost:8000`, `admin` / `password`.
`gate.py --reset` drops and recreates `kenning-reach`; `audit_live.py` drops and
recreates `kenning-reach-live` and reads the Neo4j connection from `$AUDIT_ENV`.
Read the loaded schema in TypeDB Studio as well as here: a declared schema
refuses contradictions between what you wrote, never a type you wrote and
forgot to connect. Dead types load green, and the picture is the instrument
that catches them.
