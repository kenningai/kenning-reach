#!/usr/bin/env python3
"""Import the LIVE experience graph (Neo4j) into the v3.0.0 model (TypeDB) and count
what the model refuses, by class.

This is the falsification: the model says what the ontology IS; the import says
whether what is there IS that shape. Every refusal is a place where the held
ontology and the actualized graph disagree — an ontological finding, not an
implementation bug — and the report names them so a ruling can be made.

One on-the-fly translation is applied and reported separately: a graph written
before ACTUALIZED became its own edge (v2.4.0) encodes actualization as
MEASUREMENT {measurement_type: "actualized"}. Those edges are imported as
ACTUALIZED so the rest of the audit sees the graph as the model intends it.

    ./audit_live.py [--db kenning-reach-live] [--model v3.0.0.tql]
Reads NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD / NEO4J_DATABASE from $AUDIT_ENV (default ../../../.env)
"""
import argparse, collections, json, os, re, sys, time
from gate import TypeDB, count, HERE
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(os.environ.get("AUDIT_ENV", os.path.join(HERE, "..", "..", "..", ".env")))

LABEL = {"TemporalFrame": "temporal-frame", "GraphRegistry": "graph-registry"}
REL = {"CHALLENGE": "incoherence"}   # graphs written before the rename say CHALLENGE; the model says INCOHERENCE
PROCESS = {"Genesis", "Envisioning", "TemporalFrame"}
PHENO = {"VALIDATION", "COMPOSING", "INFORMING", "ENABLING", "CAUSING", "CHALLENGE", "INCOHERENCE"}
EXP_ONLY = {"EVOLUTION", "EXTENDING", "RECOGNITION", "REQUIRING", "ENCOMPASSING"}


def tql_label(l):
    return LABEL.get(l, l.lower())


def q(s):
    if s is None:
        return None
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ") + '"'


def dt(s):
    """Neo4j datetime string -> TypeQL datetime literal (tz dropped, millisecond precision)."""
    if not s:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?", s)
    if not m:
        return None
    frac = (m.group(2) or "")[:4]
    return m.group(1) + frac


def node_insert(label, name, desc, tc, tv):
    parts = [f"$n isa {tql_label(label)}", f"has name {q(name)}"]
    if label != "Genesis" and desc is not None:
        parts.append(f"has description {q(desc)}")
    if tc:
        parts.append(f"has t-created {tc}")
    if tv and label != "Genesis":
        parts.append(f"has t-valid {tv}")
    return ", ".join(parts) + ";"


def edge_insert(al, an, rt, bl, bn, tc, tv, mt):
    """Returns (class_key, query)."""
    m = f"match $a isa {tql_label(al)}, has name {q(an)}; $b isa {tql_label(bl)}, has name {q(bn)};\ninsert "
    props = (f", has t-created {tc}" if tc else "") + (f", has t-valid {tv}" if tv else "")
    if rt == "NEXT_GENESIS":
        return "NEXT_GENESIS", m + f"$r isa next-genesis, links (earlier: $a, later: $b){props};"
    if rt == "OPENING":
        return "OPENING", m + f"$r isa opening, links (opener: $a, opened: $b){props};"
    if rt == "SEQUENCE":
        return "SEQUENCE", m + f"$r isa sequence, links (predecessor: $a, successor: $b){props};"
    if rt == "NAVIGATES_TOWARD":
        return "NAVIGATES_TOWARD", m + f"$r isa navigates-toward, links (frame: $a, target: $b){props};"
    if rt == "MEASUREMENT":
        if mt == "released":
            return "MEASUREMENT(released)", m + f'$r isa released, links (frame: $a, resolved: $b), has measurement-type "released"{props};'
        if mt == "evolved":
            return "MEASUREMENT(evolved)", m + f'$r isa evolved, links (successor: $a, resolved: $b), has measurement-type "evolved"{props};'
        if mt == "actualized":
            return "MEASUREMENT(actualized)->ACTUALIZED", m + f"$r isa actualized, links (frame: $a, resolved: $b){props};"
        return f"MEASUREMENT({mt})", m + f'$r isa released, links (frame: $a, resolved: $b), has measurement-type {q(str(mt))}{props};'
    if rt == "ACTUALIZED":
        return "ACTUALIZED", m + f"$r isa actualized, links (frame: $a, resolved: $b){props};"
    if rt == "DESCENDENT_FROM":
        return "DESCENDENT_FROM", m + f"$r isa descendent-from, links (descendant: $a, ancestor: $b){props};"
    if rt == "DISCOVERY":
        return "DISCOVERY", m + f"$r isa discovery, links (frame: $a, found: $b){props};"
    if rt in PHENO or rt in EXP_ONLY:
        return rt, m + f"$r isa {REL.get(rt, rt.lower())}, links (source: $a, target: $b){props};"
    return f"UNKNOWN({rt})", None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="kenning-reach-live")
    ap.add_argument("--model", default=os.path.join(HERE, "v3.0.0.tql"))
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default=os.environ.get("TYPEDB_PASSWORD", "password"))
    ap.add_argument("--report", default=os.path.join(HERE, "audit-v3.0.0-live.json"))
    a = ap.parse_args()

    t = TypeDB(a.url, a.user, a.password)
    if a.db in t.databases():
        t.delete(a.db)
    t.create(a.db)
    t.run(a.db, "schema", open(a.model).read())
    print(f"model loaded into {a.db}")

    uri = os.environ["NEO4J_URI"]
    print(f"reading live graph from {uri.split('@')[-1]}")
    drv = GraphDatabase.driver(uri, auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]))
    db = os.environ.get("NEO4J_DATABASE", "neo4j")
    with drv.session(database=db) as s:
        nodes = s.run("MATCH (n) RETURN labels(n)[0] AS l, n.name AS name, n.description AS d, "
                      "toString(n.t_created) AS tc, toString(n.t_valid) AS tv ORDER BY l, name").data()
        edges = s.run("MATCH (a)-[r]->(b) RETURN labels(a)[0] AS al, a.name AS an, type(r) AS rt, labels(b)[0] AS bl, "
                      "b.name AS bn, toString(r.t_created) AS tc, toString(r.t_valid) AS tv, r.measurement_type AS mt").data()
    drv.close()
    print(f"live graph: {len(nodes)} nodes, {len(edges)} edges")

    refused = collections.defaultdict(list)   # class -> [(detail, code, message)]
    accepted = collections.Counter()

    def code_of(ex):
        msg = str(ex); c = msg[msg.find("["):msg.find("]") + 1]
        return c, msg[msg.find("]") + 1:][:140].strip()

    def run1(query):
        """One write transaction. Returns number of answer rows for the last stage (0 = match found nothing)."""
        ans = t.run(a.db, "write", query)
        return len(ans.get("answers", [])) if isinstance(ans, dict) else -1

    by_name = {(n["l"], n["name"]): n for n in nodes}
    inbound = collections.defaultdict(list)
    for e in edges:
        inbound[(e["rt"], e["bl"], e["bn"])].append(e)

    t0 = time.time()
    # ---- 1. Genesis nodes, batched ---------------------------------------------
    gens = [n for n in nodes if n["l"] == "Genesis"]
    for i in range(0, len(gens), 100):
        chunk = gens[i:i + 100]
        stmt = "insert\n" + "\n".join(node_insert(n["l"], n["name"], n["d"], dt(n["tc"]), dt(n["tv"])).replace("$n ", f"$n{j} ", 1) for j, n in enumerate(chunk))
        try:
            t.run(a.db, "write", stmt); accepted["node:Genesis"] += len(chunk)
        except Exception:
            for n in chunk:
                try:
                    t.run(a.db, "write", "insert " + node_insert(n["l"], n["name"], n["d"], dt(n["tc"]), dt(n["tv"]))); accepted["node:Genesis"] += 1
                except Exception as ex:
                    c, m = code_of(ex); refused["node:Genesis"].append((n["name"], c, m))

    # ---- 2. Experience nodes, batched ------------------------------------------
    exps = [n for n in nodes if n["l"] not in PROCESS]
    for i in range(0, len(exps), 100):
        chunk = exps[i:i + 100]
        stmt = "insert\n" + "\n".join(node_insert(n["l"], n["name"], n["d"], dt(n["tc"]), dt(n["tv"])).replace("$n ", f"$n{j} ", 1) for j, n in enumerate(chunk))
        try:
            t.run(a.db, "write", stmt)
            for n in chunk: accepted[f"node:{n['l']}"] += 1
        except Exception:
            for n in chunk:
                try:
                    t.run(a.db, "write", "insert " + node_insert(n["l"], n["name"], n["d"], dt(n["tc"]), dt(n["tv"]))); accepted[f"node:{n['l']}"] += 1
                except Exception as ex:
                    c, m = code_of(ex); refused[f"node:{n['l']}"].append((n["name"], c, m))
    print(f"genesis + experience nodes in {time.time()-t0:.0f}s")

    # ---- 3. Envisionings, each WITH its OPENING (the edge that constitutes it) --
    consumed = set()
    envs = sorted([n for n in nodes if n["l"] == "Envisioning"], key=lambda n: n["tc"] or "")
    for n in envs:
        ops = inbound[("OPENING", "Envisioning", n["name"])]
        node = node_insert("Envisioning", n["name"], n["d"], dt(n["tc"]), dt(n["tv"]))
        if not ops:
            try:
                t.run(a.db, "write", "insert " + node); accepted["node:Envisioning"] += 1
            except Exception as ex:
                c, m = code_of(ex); refused["node:Envisioning WITHOUT OPENING"].append((n["name"], c, m))
            continue
        m_ = "match " + " ".join(f"$g{j} isa genesis, has name {q(o['an'])};" for j, o in enumerate(ops)) + "\ninsert " + node + " " + " ".join(
            f"$o{j} isa opening, links (opener: $g{j}, opened: $n)" + (f", has t-created {dt(o['tc'])}" if dt(o['tc']) else "") + ";" for j, o in enumerate(ops))
        try:
            rows = run1(m_)
            if rows == 0:
                refused["node:Envisioning (its OPENING's Genesis missing)"].append((n["name"], "NOMATCH", "")); continue
            accepted["node:Envisioning"] += 1; accepted["edge:OPENING"] += len(ops)
            for o in ops: consumed.add(id(o))
        except Exception as ex:
            c, m = code_of(ex)
            refused[f"node:Envisioning + its {len(ops)} OPENING(s) as one act"].append((n["name"], c, m))
            for o in ops: consumed.add(id(o))
    print(f"envisionings in {time.time()-t0:.0f}s")

    # ---- 4. TemporalFrames, each WITH its SEQUENCE(s); on refusal retry with the earliest one only
    tfs = sorted([n for n in nodes if n["l"] == "TemporalFrame"], key=lambda n: n["tc"] or "")
    for n in tfs:
        seqs = sorted(inbound[("SEQUENCE", "TemporalFrame", n["name"])], key=lambda e: e["tc"] or "")
        node = node_insert("TemporalFrame", n["name"], n["d"], dt(n["tc"]), dt(n["tv"]))
        def tf_query(ss):
            return "match " + " ".join(f"$p{j} isa {tql_label(e['al'])}, has name {q(e['an'])};" for j, e in enumerate(ss)) + "\ninsert " + node + " " + " ".join(
                f"$s{j} isa sequence, links (predecessor: $p{j}, successor: $n)" + (f", has t-created {dt(e['tc'])}" if dt(e['tc']) else "") + ";" for j, e in enumerate(ss))
        for e in seqs: consumed.add(id(e))
        if not seqs:
            try:
                t.run(a.db, "write", "insert " + node); accepted["node:TemporalFrame"] += 1
            except Exception as ex:
                c, m = code_of(ex); refused["node:TemporalFrame WITHOUT SEQUENCE (rule 3)"].append((n["name"], c, m))
            continue
        try:
            rows = run1(tf_query(seqs))
            if rows == 0:
                refused["node:TemporalFrame (a SEQUENCE predecessor missing)"].append((n["name"], "NOMATCH", "")); continue
            accepted["node:TemporalFrame"] += 1; accepted["edge:SEQUENCE"] += len(seqs)
        except Exception as ex:
            c, m = code_of(ex)
            if len(seqs) > 1:
                try:
                    rows = run1(tf_query(seqs[:1]))
                    if rows == 0:
                        refused["node:TemporalFrame (a SEQUENCE predecessor missing)"].append((n["name"], "NOMATCH", "")); continue
                    accepted["node:TemporalFrame"] += 1; accepted["edge:SEQUENCE"] += 1
                    for e in seqs[1:]:
                        refused[f"edge:SEQUENCE extra inbound (dual-sequence, rule 3) {e['al']}->TemporalFrame"].append((f"{e['an']} -> {n['name']}", c, m))
                except Exception as ex2:
                    c2, m2 = code_of(ex2); refused["node:TemporalFrame + its earliest SEQUENCE"].append((n["name"], c2, m2))
            else:
                refused[f"node:TemporalFrame + its SEQUENCE ({seqs[0]['al']})"].append((n["name"], c, m))
    print(f"temporal frames in {time.time()-t0:.0f}s")

    # ---- 5. every remaining edge, one transaction each, endpoints verified ------
    order = {"NEXT_GENESIS": 0, "NAVIGATES_TOWARD": 3, "MEASUREMENT": 4, "ACTUALIZED": 5, "DESCENDENT_FROM": 6}
    rest = [e for e in edges if id(e) not in consumed and e["rt"] not in ("OPENING", "SEQUENCE")]
    rest.sort(key=lambda e: (order.get(e["rt"], 9), e["tc"] or ""))
    for e in rest:
        cls, qq = edge_insert(e["al"], e["an"], e["rt"], e["bl"], e["bn"], dt(e["tc"]), dt(e["tv"]), e["mt"])
        if qq is None:
            refused[cls].append((f"{e['an']} -> {e['bn']}", "UNMAPPED", "")); continue
        try:
            rows = run1(qq)
            if rows == 0:
                refused[f"edge:{cls} {e['al']}->{e['bl']} (an endpoint was refused earlier)"].append((f"{e['an']} -> {e['bn']}", "NOMATCH", "")); continue
            accepted[f"edge:{cls}"] += 1
        except Exception as ex:
            c, m = code_of(ex)
            refused[f"edge:{cls} {e['al']}->{e['bl']}"].append((f"{e['an']} -> {e['bn']}", c, m))
    print(f"all edges in {time.time()-t0:.0f}s")

    # ---- post-conditions on the live copy --------------------------------------
    POST = {
        "resolved envisionings with zero inbound phenomenology (rule 15)": """match
            $r isa resolution, links (resolved: $e); not { $p0 isa validation, links (target: $e); }; not { $p1 isa composing, links (target: $e); }; not { $p2 isa informing, links (target: $e); }; not { $p3 isa enabling, links (target: $e); }; not { $p4 isa causing, links (target: $e); }; not { $p5 isa incoherence, links (target: $e); }; reduce $n = count;""",
        "geneses with no NEXT_GENESIS successor (rule 1; 1 = the newest)": """match
            $g isa genesis; not { $x isa next-genesis, links (earlier: $g); }; reduce $n = count;""",
        "geneses with no NEXT_GENESIS predecessor (rule 1; 1 = the oldest)": """match
            $g isa genesis; not { $x isa next-genesis, links (later: $g); }; reduce $n = count;""",
        "genesis names off-pattern": """match $g isa genesis, has name $nm; not { $nm like "^Genesis_[0-9]{4}-[0-9]{2}-[0-9]{2}$"; }; reduce $n = count;""",
        "temporal-frame names off-pattern": """match $t isa temporal-frame, has name $nm; not { $nm like "^TF_[0-9]{4}-[0-9]{2}-[0-9]{2}_.+$"; }; reduce $n = count;""",
        "temporal-frames with zero NAVIGATES_TOWARD": """match $t isa temporal-frame; not { $x isa navigates-toward, links (frame: $t); }; reduce $n = count;""",
        "temporal-frames with zero DISCOVERY": """match $t isa temporal-frame; not { $x isa discovery, links (frame: $t); }; reduce $n = count;""",
        "experience nodes with no DISCOVERY and no phenomenology edge (float free of the process layer)": """match
            $x isa experience; not { $d isa discovery, links (found: $x); }; not { $q0 isa validation, links (source: $x); }; not { $q1 isa composing, links (source: $x); }; not { $q2 isa informing, links (source: $x); }; not { $q3 isa enabling, links (source: $x); }; not { $q4 isa causing, links (source: $x); }; not { $q5 isa incoherence, links (source: $x); }; reduce $n = count;""",
        "open envisionings (no resolution)": """match $e isa envisioning; not { $r isa resolution, links (resolved: $e); }; reduce $n = count;""",
    }
    post = {}
    for name, qq in POST.items():
        post[name] = count(t.run(a.db, "read", qq, commit=False))

    # ---- report ----------------------------------------------------------------
    summary = {
        "live": {"nodes": len(nodes), "edges": len(edges)},
        "accepted": dict(accepted),
        "refused": {k: {"count": len(v), "codes": dict(collections.Counter(c for _, c, _ in v)),
                        "examples": [d for d, _, _ in v[:5]], "message": v[0][2] if v else ""} for k, v in refused.items()},
        "post_conditions": post,
    }
    json.dump({"summary": summary, "refused_detail": {k: v for k, v in refused.items()}}, open(a.report, "w"), indent=1)

    print("\nACCEPTED")
    for k, v in sorted(accepted.items()): print(f"  {v:6d}  {k}")
    print("\nREFUSED — the ontological findings")
    for k, v in sorted(refused.items(), key=lambda kv: -len(kv[1])):
        codes = ", ".join(f"{c}×{n}" for c, n in collections.Counter(c for _, c, _ in v).items())
        print(f"  {len(v):6d}  {k}  [{codes}]\n           e.g. {v[0][0][:90]}\n           {v[0][2][:120]}")
    print("\nPOST-CONDITIONS on the live copy")
    for k, v in post.items(): print(f"  {v:6d}  {k}")
    print(f"\nreport: {a.report}")


if __name__ == "__main__":
    main()
