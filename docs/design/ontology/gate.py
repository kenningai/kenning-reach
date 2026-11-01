#!/usr/bin/env python3
"""Load the Kenning Reach ontology into a local TypeDB (HTTP API) and prove it two-sided.

A green load means the model is CONSISTENT, not that it is right: dead types load
green. So every accept case exercises a claim the model makes, and every refuse case
is a shape the written record says must not exist. A model that says yes to
everything is not a gate; a model that cannot say yes is not a model.

    ./gate.py [--db kenning-reach] [--model v3.0.0.tql] [--url http://localhost:8000]
    ./gate.py --reset      # drop and recreate the database first

Exit 0 only when every accept case commits, every refuse case is refused, every
post-condition reads zero, and every planted violation is counted.
"""
import argparse, json, os, sys, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))


class TypeDB:
    def __init__(self, url, user, password):
        self.url = url.rstrip("/")
        self.token = self._post("/v1/signin", {"username": user, "password": password}, auth=False)["token"]

    def _req(self, method, path, body=None, auth=True):
        h = {"Content-Type": "application/json"}
        if auth:
            h["Authorization"] = "Bearer " + self.token
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                raw = r.read().decode()
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            try:
                msg = json.loads(raw)
            except Exception:
                msg = raw
            raise RuntimeError(f"{e.code} {method} {path}: {msg}") from None

    def _post(self, path, body=None, auth=True):
        return self._req("POST", path, body, auth)

    def databases(self):
        d = self._req("GET", "/v1/databases")
        return [x["name"] if isinstance(x, dict) else x for x in (d.get("databases", d) if isinstance(d, dict) else d)]

    def create(self, name):
        self._post(f"/v1/databases/{name}")

    def delete(self, name):
        self._req("DELETE", f"/v1/databases/{name}")

    def probe(self, db, insert_q, check_q):
        """Insert, then run a check IN THE SAME transaction, then discard."""
        tx = self._post("/v1/transactions/open", {"databaseName": db, "transactionType": "write"})["transactionId"]
        try:
            self._post(f"/v1/transactions/{tx}/query", {"query": insert_q})
            return self._post(f"/v1/transactions/{tx}/query", {"query": check_q})
        finally:
            self._post(f"/v1/transactions/{tx}/close")

    def run(self, db, kind, query, commit=True):
        tx = self._post("/v1/transactions/open", {"databaseName": db, "transactionType": kind})["transactionId"]
        try:
            ans = self._post(f"/v1/transactions/{tx}/query", {"query": query})
            if commit:
                self._post(f"/v1/transactions/{tx}/commit")
            else:
                self._post(f"/v1/transactions/{tx}/close")
            return ans
        except Exception:
            try:
                self._post(f"/v1/transactions/{tx}/close")
            except Exception:
                pass
            raise


def count(ans):
    return ans["answers"][0]["data"]["n"]["value"]


# -----------------------------------------------------------------------------
# Fixtures. Real shapes, synthetic values. T = a t-created literal.
# -----------------------------------------------------------------------------
T = "2026-09-15T10:00:00"

BASE = f"""
$g1 isa genesis, has name "Genesis_2026-09-14", has t-created 2026-09-14T00:00:00;
$g2 isa genesis, has name "Genesis_2026-09-15", has t-created 2026-09-15T00:00:00;
$ng isa next-genesis, links (earlier: $g1, later: $g2), has t-created 2026-09-15T00:00:00;
$e1 isa envisioning, has name "Env One", has description "a future held", has t-created {T};
$e2 isa envisioning, has name "Env Two", has description "another future held", has t-created {T};
$o1 isa opening, links (opener: $g1, opened: $e1), has t-created {T};
$o2 isa opening, links (opener: $g2, opened: $e2), has t-created {T};
$tf1 isa temporal-frame, has name "TF_2026-09-14_First", has description "first frame", has t-created 2026-09-14T09:00:00;
$tf2 isa temporal-frame, has name "TF_2026-09-14_Second", has description "second frame", has t-created 2026-09-14T14:00:00;
$tf3 isa temporal-frame, has name "TF_2026-09-15_First", has description "first frame next day", has t-created 2026-09-15T09:00:00;
$s1 isa sequence, links (predecessor: $g1, successor: $tf1), has t-created 2026-09-14T09:00:00;
$s2 isa sequence, links (predecessor: $tf1, successor: $tf2), has t-created 2026-09-14T14:00:00;
$s3 isa sequence, links (predecessor: $g2, successor: $tf3), has t-created 2026-09-15T09:00:00;
$x1 isa insight, has name "Insight X1", has description "something seen", has t-created {T};
$x2 isa technical, has name "Technical X2", has description "something built", has t-created {T};
$d1 isa discovery, links (frame: $tf1, found: $x1), has t-created {T};
$d2 isa discovery, links (frame: $tf1, found: $x2), has t-created {T};
$nv isa navigates-toward, links (frame: $tf1, target: $e1), has t-created {T};
$nv2 isa navigates-toward, links (frame: $tf2, target: $e1), has t-created {T};
$nv3 isa navigates-toward, links (frame: $tf3, target: $e2), has t-created {T};
$e5 isa envisioning, has name "Env Five", has description "still open", has t-created {T};
$o5 isa opening, links (opener: $g2, opened: $e5), has t-created {T};
"""

M = """match
$g1 isa genesis, has name "Genesis_2026-09-14"; $g2 isa genesis, has name "Genesis_2026-09-15";
$e1 isa envisioning, has name "Env One"; $e2 isa envisioning, has name "Env Two"; $e5 isa envisioning, has name "Env Five";
$tf1 isa temporal-frame, has name "TF_2026-09-14_First"; $tf2 isa temporal-frame, has name "TF_2026-09-14_Second";
$tf3 isa temporal-frame, has name "TF_2026-09-15_First";
$x1 isa insight, has name "Insight X1"; $x2 isa technical, has name "Technical X2";
"""

ACCEPT = [
    ("A0 backbone, openings, a day's SEQUENCE chain, DISCOVERY off a frame, one NAVIGATES_TOWARD", "insert" + BASE),
    ("A1 released: TF → Env One, with one phenomenology edge (incoherence)", M + f"""insert
$r isa released, links (frame: $tf2, resolved: $e1), has measurement-type "released", has t-created {T};
$p isa incoherence, links (source: $x1, target: $e1), has t-created {T};"""),
    ("A2 evolved: new Env Three opened by Genesis, evolved → Env Two, phenomenology to the OLD one", M + f"""insert
$e3 isa envisioning, has name "Env Three", has description "the reshaped form", has t-created {T};
$o isa opening, links (opener: $g2, opened: $e3), has t-created {T};
$v isa evolved, links (successor: $e3, resolved: $e2), has measurement-type "evolved", has t-created {T};
$p isa informing, links (source: $x2, target: $e2), has t-created {T};"""),
    ("A3 actualized: TF → Env Four with validation phenomenology", M + f"""insert
$e4 isa envisioning, has name "Env Four", has description "became actual", has t-created {T};
$o isa opening, links (opener: $g2, opened: $e4), has t-created {T};
$a isa actualized, links (frame: $tf3, resolved: $e4), has t-created {T};
$p isa validation, links (source: $x1, target: $e4), has t-created {T};"""),
    ("A4 a TF reaching toward an already-actualized possibility (ruled: reaching for what IS, to evolve it)", M + f"""match $e4 isa envisioning, has name "Env Four";
insert
$tf4 isa temporal-frame, has name "TF_2026-09-15_Patch", has description "patching what is already real", has t-created 2026-09-15T12:00:00;
$s isa sequence, links (predecessor: $tf3, successor: $tf4), has t-created 2026-09-15T12:00:00;
$n isa navigates-toward, links (frame: $tf4, target: $e4), has t-created 2026-09-15T12:00:00;"""),
    ("A5 experience coherence: extending, evolution, composing; a milestone with t-valid", M + f"""insert
$x3 isa lesson, has name "Lesson X3", has description "learned", has t-created {T};
$m1 isa milestone, has name "Milestone M1", has description "reached", has t-created {T}, has t-valid 2026-09-01T00:00:00;
$r1 isa extending, links (source: $x3, target: $x1), has t-created {T};
$r2 isa evolution, links (source: $x1, target: $x3), has t-created {T};
$r3 isa composing, links (source: $x2, target: $x3), has t-created {T};
$r4 isa recognition, links (source: $m1, target: $x1), has t-created {T}, has t-valid 2026-09-01T00:00:00;"""),
    ("A6 phenomenology into an OPEN envisioning (informing → Env Five, unresolved)", M + f"""insert
$p isa informing, links (source: $x1, target: $e5), has t-created {T};"""),
    ("A8 ruling 1: a chain — Env Three evolved → Env 3b evolved → Env 3c actualized; one terminal at the end", M + f"""match $e3 isa envisioning, has name "Env Three";
insert
$e3b isa envisioning, has name "Env 3b", has description "reshaped again", has t-created {T};
$e3c isa envisioning, has name "Env 3c", has description "final form", has t-created {T};
$o1 isa opening, links (opener: $g2, opened: $e3b), has t-created {T};
$o2 isa opening, links (opener: $g2, opened: $e3c), has t-created {T};
$v1 isa evolved, links (successor: $e3b, resolved: $e3), has measurement-type "evolved", has t-created {T};
$p1 isa informing, links (source: $x2, target: $e3), has t-created {T};
$v2 isa evolved, links (successor: $e3c, resolved: $e3b), has measurement-type "evolved", has t-created {T};
$p2 isa informing, links (source: $x2, target: $e3b), has t-created {T};
$a isa actualized, links (frame: $tf3, resolved: $e3c), has t-created {T};
$p3 isa validation, links (source: $x1, target: $e3c), has t-created {T};"""),
    ("A9 ruling 2: an insight informing a TemporalFrame, a pattern recognised in it", M + f"""insert
$p1 isa informing, links (source: $x1, target: $tf3), has t-created {T};
$p2 isa recognition, links (source: $x2, target: $tf3), has t-created {T};"""),
    ("A11 DESCENDENT_FROM: a new possibility descending from Env Four (actualized) and another from Env One (released); the ancestors keep their one terminal", M + f"""match $e4 isa envisioning, has name "Env Four";
insert
$n1 isa envisioning, has name "Env From Four", has description "what Env Four's actuality made possible", has t-created {T};
$n2 isa envisioning, has name "Env From One", has description "what Env One's release made possible", has t-created {T};
$o1 isa opening, links (opener: $g2, opened: $n1), has t-created {T};
$o2 isa opening, links (opener: $g2, opened: $n2), has t-created {T};
$d1 isa descendent-from, links (descendant: $n1, ancestor: $e4), has t-created {T};
$d2 isa descendent-from, links (descendant: $n2, ancestor: $e1), has t-created {T};"""),
    ("A10 ruling 4: extending, recognition and requiring INTO an open envisioning — accumulation on the walk", M + f"""insert
$p1 isa extending, links (source: $x1, target: $e5), has t-created {T};
$p2 isa recognition, links (source: $x2, target: $e5), has t-created {T};
$p3 isa requiring, links (source: $x1, target: $e5), has t-created {T};"""),
]

FINDING = []

REFUSE = [
    ("R01 OPENING from a TemporalFrame (opener not playable by TF)", M + f"""insert
$e isa envisioning, has name "Env R01", has description "x", has t-created {T};
$o isa opening, links (opener: $tf1, opened: $e), has t-created {T};"""),
    ("R02 a second OPENING on Env One (opened @card 1..1)", M + f"""insert
$o isa opening, links (opener: $g2, opened: $e1), has t-created {T};"""),
    ("R03 a second inbound SEQUENCE on TF Second — the dual-sequence shape (successor @card 1..1)", M + f"""insert
$s isa sequence, links (predecessor: $g1, successor: $tf2), has t-created {T};"""),
    ("R04 a TemporalFrame with no SEQUENCE at all (successor @card 1..1)", M + f"""insert
$tf isa temporal-frame, has name "TF_2026-09-15_Orphan", has description "x", has t-created {T};
$n isa navigates-toward, links (frame: $tf, target: $e5), has t-created {T};"""),
    ("R34 a TemporalFrame reaching toward nothing (frame @card 1..; the withdrawn zero case)", M + f"""insert
$tf isa temporal-frame, has name "TF_2026-09-15_Grief", has description "no target", has t-created {T};
$s isa sequence, links (predecessor: $tf3, successor: $tf), has t-created {T};"""),
    ("R05 measurement-type 'actualized' (the pre-v2.4.0 encoding; @values)", M + f"""insert
$r isa released, links (frame: $tf3, resolved: $e5), has measurement-type "actualized", has t-created {T};"""),
    ("R06 released with an Envisioning as the frame (type)", M + f"""insert
$r isa released, links (frame: $e2, resolved: $e5), has measurement-type "released", has t-created {T};"""),
    ("R07 evolved with a TemporalFrame as the successor (type)", M + f"""insert
$v isa evolved, links (successor: $tf3, resolved: $e5), has measurement-type "evolved", has t-created {T};"""),
    ("R08 evolved INTO Env One, which is already released — a second resolution after a terminal one (resolved @card 0..1)", M + f"""insert
$e isa envisioning, has name "Env R08", has description "x", has t-created {T};
$o isa opening, links (opener: $g2, opened: $e), has t-created {T};
$v isa evolved, links (successor: $e, resolved: $e1), has measurement-type "evolved", has t-created {T};"""),
    ("R09 actualized on Env Two, which is already evolved (resolved @card 0..1)", M + f"""insert
$a isa actualized, links (frame: $tf3, resolved: $e2), has t-created {T};"""),
    ("R10 a second release of Env One (resolved @card 0..1)", M + f"""insert
$r isa released, links (frame: $tf3, resolved: $e1), has measurement-type "released", has t-created {T};"""),
    ("R11 AP1: DISCOVERY from a Genesis (genesis plays no experience role)", M + f"""insert
$x isa insight, has name "Insight R11", has description "x", has t-created {T};
$d isa discovery, links (frame: $g1, found: $x), has t-created {T};"""),
    ("R12 AP1 by another edge: Genesis informing an experience node", M + f"""insert
$p isa informing, links (source: $g1, target: $x1), has t-created {T};"""),
    ("R13 a Genesis with a description (genesis owns name and t-created only)", M + """insert $g1 has description "bedrock speaks";"""),
    ("R14 an experience node with no t-created (invariant 10)", """insert $x isa insight, has name "Insight R14", has description "x";"""),
    ("R15 a process edge with no t-created (invariant 10)", M + """insert $n isa navigates-toward, links (frame: $tf3, target: $e5);"""),
    ("R16 a released with no measurement-type (measurement-type @card 1..1)", M + f"""insert
$r isa released, links (frame: $tf3, resolved: $e5), has t-created {T};"""),
    ("R17 a Genesis with two NEXT_GENESIS successors (earlier @card 0..1)", M + f"""insert
$g3 isa genesis, has name "Genesis_2026-09-16", has t-created 2026-09-16T00:00:00;
$g4 isa genesis, has name "Genesis_2026-09-17", has t-created 2026-09-17T00:00:00;
$n1 isa next-genesis, links (earlier: $g2, later: $g3), has t-created {T};
$n2 isa next-genesis, links (earlier: $g2, later: $g4), has t-created {T};"""),
    ("R18 an experience edge between two process nodes: TF validating an Envisioning (invariant 8)", M + f"""insert
$p isa validation, links (source: $tf3, target: $e5), has t-created {T};"""),
    ("R19 an Envisioning as the SOURCE of an experience edge (informing an insight)", M + f"""insert
$p isa informing, links (source: $e5, target: $x1), has t-created {T};"""),
    ("R20 an experience node COMPOSING into a TemporalFrame (only informing/recognition/validation/extending may reach a TF)", M + f"""insert
$p isa composing, links (source: $x1, target: $tf3), has t-created {T};"""),
    ("R29 ruling 1: a second evolved from Env Three, already evolved into Env 3b (resolved @card 0..1)", M + f"""match $e3 isa envisioning, has name "Env Three";
insert
$e isa envisioning, has name "Env R29", has description "x", has t-created {T};
$o isa opening, links (opener: $g2, opened: $e), has t-created {T};
$v isa evolved, links (successor: $e, resolved: $e3), has measurement-type "evolved", has t-created {T};"""),
    ("R30 ruling 1: releasing Env 3b, an evolved-away form mid-chain (resolving what was already resolved)", M + f"""match $e3b isa envisioning, has name "Env 3b";
insert
$r isa released, links (frame: $tf3, resolved: $e3b), has measurement-type "released", has t-created {T};"""),
    ("R22 a released targeting a TemporalFrame (resolved not playable by TF)", M + f"""insert
$r isa released, links (frame: $tf3, resolved: $tf2), has measurement-type "released", has t-created {T};"""),
    ("R23 SEQUENCE from an Envisioning (predecessor not playable)", M + f"""insert
$tf isa temporal-frame, has name "TF_2026-09-15_R23", has description "x", has t-created {T};
$n isa navigates-toward, links (frame: $tf, target: $e5), has t-created {T};
$s isa sequence, links (predecessor: $e5, successor: $tf), has t-created {T};"""),
    ("R31 DESCENDENT_FROM with a TemporalFrame as the descendant (type)", M + f"""insert
$d isa descendent-from, links (descendant: $tf3, ancestor: $e1), has t-created {T};"""),
    ("R32 DESCENDENT_FROM from a Genesis (type)", M + f"""insert
$d isa descendent-from, links (descendant: $e5, ancestor: $g1), has t-created {T};"""),
    ("R33 a second resolution on Env Four after a descendant exists — lineage did not reopen it (resolved @card 0..1)", M + f"""match $e4 isa envisioning, has name "Env Four";
insert
$r isa released, links (frame: $tf3, resolved: $e4), has measurement-type "released", has t-created {T};"""),
    ("R24 a phase property on an Envisioning (ruled derivable from the walk; no such attribute)", M + """insert $e5 has phase "actualized";"""),
    ("R25 two Envisionings with one name (rule 12; name @key)", M + f"""insert
$e isa envisioning, has name "Env One", has description "dup", has t-created {T};
$o isa opening, links (opener: $g2, opened: $e), has t-created {T};"""),
    ("R26 an Envisioning with no description (description @card 1..1)", M + f"""insert
$e isa envisioning, has name "Env R26", has t-created {T};
$o isa opening, links (opener: $g2, opened: $e), has t-created {T};"""),
    ("R27 t-valid on a Genesis (bedrock has no external referent)", M + """insert $g1 has t-valid 2026-09-14T00:00:00;"""),
    ("R28 a Genesis with two SEQUENCE successors (predecessor @card 0..1; rule 3)", M + f"""insert
$tf isa temporal-frame, has name "TF_2026-09-14_Third", has description "x", has t-created {T};
$n isa navigates-toward, links (frame: $tf, target: $e5), has t-created {T};
$s isa sequence, links (predecessor: $g1, successor: $tf), has t-created {T};"""),
]

# Post-conditions the schema cannot declare. Each must read ZERO, and each must
# be shown to count a planted violation (in a discarded transaction).
POST = {
    "RESOLVED_WITHOUT_PHENOMENOLOGY (rule 15)": """match
        $r isa resolution, links (resolved: $e);
        not { $p0 isa validation, links (target: $e); }; not { $p1 isa composing, links (target: $e); }; not { $p2 isa informing, links (target: $e); }; not { $p3 isa enabling, links (target: $e); }; not { $p4 isa causing, links (target: $e); }; not { $p5 isa incoherence, links (target: $e); };
        reduce $n = count;""",
    "BACKBONE_BROKEN (rule 1: geneses with no successor, minus the newest)": """match
        $g isa genesis;
        not { $x isa next-genesis, links (earlier: $g); };
        reduce $n = count;""",
    "GENESIS_NAME_PATTERN": """match
        $g isa genesis, has name $nm;
        not { $nm like "^Genesis_[0-9]{4}-[0-9]{2}-[0-9]{2}$"; };
        reduce $n = count;""",
    "DESCENDENT_FROM_NON_TERMINAL_ANCESTOR (open or evolved-away)": """match
        $d isa descendent-from, links (ancestor: $a);
        not { $r isa released, links (resolved: $a); };
        not { $x isa actualized, links (resolved: $a); };
        reduce $n = count;""",
    "TF_NAME_PATTERN": """match
        $t isa temporal-frame, has name $nm;
        not { $nm like "^TF_[0-9]{4}-[0-9]{2}-[0-9]{2}_.+$"; };
        reduce $n = count;""",
}
POST_EXPECT = {"BACKBONE_BROKEN (rule 1: geneses with no successor, minus the newest)": 1}

PLANT = {
    "RESOLVED_WITHOUT_PHENOMENOLOGY (rule 15)": M + f"""insert
        $e7 isa envisioning, has name "Env Seven", has description "released in a vacuum", has t-created {T};
        $o isa opening, links (opener: $g2, opened: $e7), has t-created {T};
        $r isa released, links (frame: $tf3, resolved: $e7), has measurement-type "released", has t-created {T};""",
    "BACKBONE_BROKEN (rule 1: geneses with no successor, minus the newest)": """insert
        $g isa genesis, has name "Genesis_2026-10-01", has t-created 2026-10-01T00:00:00;""",
    "GENESIS_NAME_PATTERN": """insert
        $g isa genesis, has name "DailyContext_2026-10-01", has t-created 2026-10-01T00:00:00;""",
    "DESCENDENT_FROM_NON_TERMINAL_ANCESTOR (open or evolved-away)": M + f"""match $e3 isa envisioning, has name "Env Three";
        insert
        $n isa envisioning, has name "Env From Three", has description "x", has t-created {T};
        $o isa opening, links (opener: $g2, opened: $n), has t-created {T};
        $d isa descendent-from, links (descendant: $n, ancestor: $e3), has t-created {T};""",
    "TF_NAME_PATTERN": M + f"""insert
        $t isa temporal-frame, has name "Frame without prefix", has description "x", has t-created {T};
        $n isa navigates-toward, links (frame: $t, target: $e5), has t-created {T};
        $s isa sequence, links (predecessor: $tf3, successor: $t), has t-created {T};""",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="kenning-reach")
    ap.add_argument("--model", default=os.path.join(HERE, "v3.0.0.tql"))
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default=os.environ.get("TYPEDB_PASSWORD", "password"))
    ap.add_argument("--reset", action="store_true")
    a = ap.parse_args()
    t = TypeDB(a.url, a.user, a.password)
    dbs = t.databases()
    if a.reset and a.db in dbs:
        t.delete(a.db); dbs.remove(a.db); print(f"dropped {a.db}")
    if a.db not in dbs:
        t.create(a.db); print(f"created {a.db}")

    schema = open(a.model).read()
    try:
        t.run(a.db, "schema", schema)
    except Exception as e:
        m = str(e); i = m.find("Near"); j = m.find("-->")
        print("SCHEMA REFUSED:", m[:m.find("Near")][:300] if i > 0 else m[:300]); print(m[j:j+400] if j > 0 else ""); sys.exit(2)
    print(f"schema loaded from {os.path.basename(a.model)}")

    ok = True
    print("\nACCEPT — every one must commit")
    for name, q in ACCEPT:
        try:
            t.run(a.db, "write", q); print(f"  ✓ {name}")
        except Exception as e:
            ok = False; print(f"  ✗ {name}\n      {str(e)[:400]}")

    print("\nFINDING — loads green, and that is the finding")
    for name, q in FINDING:
        try:
            t.run(a.db, "write", q); print(f"  ● {name}")
        except Exception as e:
            print(f"  ? unexpectedly refused: {name}\n      {str(e)[:300]}")

    print("\nREFUSE — every one must be refused")
    for name, q in REFUSE:
        try:
            t.run(a.db, "write", q); ok = False; print(f"  ✗ ADMITTED: {name}")
        except Exception as e:
            msg = str(e).replace("\n", " ")
            code = msg[msg.find("["):msg.find("]") + 1] if "[" in msg else ""
            print(f"  ✓ refused {code}: {name}")

    print("\nPOST-CONDITIONS — each must read its expected value (zero unless stated)")
    for name, q in POST.items():
        cnt = count(t.run(a.db, "read", q, commit=False))
        exp = POST_EXPECT.get(name, 0)
        flag = "✓" if cnt == exp else "✗"
        if cnt != exp: ok = False
        print(f"  {flag} {name} = {cnt} (expected {exp})")
    for name, q in PLANT.items():
        exp = POST_EXPECT.get(name, 0) + 1
        cnt = count(t.probe(a.db, q, POST[name]))
        flag = "✓" if cnt == exp else "✗"
        if cnt != exp: ok = False
        print(f"  {flag} {name} sees a planted violation = {cnt} (discarded)")

    print("\nGATE:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
