import itertools
import json
import sqlite3
import time


METHODS = [
    "frontier",
    "global_mask",
    "pairwise",
    "individual",
    "ignore_reservations",
    "refund_unknown",
]


def legal(atoms, alternatives):
    return any(set(atoms) <= set(bundle) for bundle in alternatives)


def compile_frontier(universe, alternatives, budget=30.0):
    universe = sorted(set(universe))
    bundles = [set(x) for x in alternatives]
    if not bundles or any(not b <= set(universe) for b in bundles):
        raise ValueError("Alternatives must be a nonempty family over the universe")
    bundles = [b for b in bundles if not any(b < other for other in bundles)]
    start = time.monotonic()
    frontier = []
    for size in range(1, len(universe) + 1):
        for values in itertools.combinations(universe, size):
            if time.monotonic() - start > budget:
                return None
            candidate = frozenset(values)
            if any(f <= candidate for f in frontier):
                continue
            if not legal(candidate, bundles):
                frontier.append(candidate)
    for size in range(len(universe) + 1):
        for values in itertools.combinations(universe, size):
            if time.monotonic() - start > budget:
                return None
            candidate = set(values)
            if legal(candidate, bundles) == any(f <= candidate for f in frontier):
                raise ValueError("Frontier failed completeness checking")
    return frontier


class Ledger:
    def __init__(self, alternatives, universe, method="frontier", path=":memory:"):
        self.alternatives = [set(x) for x in alternatives]
        self.universe = set(universe)
        self.method = method
        self.frontier = (
            compile_frontier(universe, alternatives) if method != "global_mask" else None
        )
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, atoms TEXT NOT NULL, status TEXT NOT NULL)"
        )
        stored = json.dumps([sorted(b) for b in self.alternatives])
        self.db.execute("CREATE TABLE IF NOT EXISTS policy (value TEXT PRIMARY KEY)")
        prior = self.db.execute("SELECT value FROM policy").fetchall()
        if prior and prior[0][0] != stored:
            raise ValueError("Ledger policy differs; use a new epoch database")
        self.db.execute("INSERT OR IGNORE INTO policy VALUES (?)", (stored,))

    def reserve(self, request_id, atoms):
        atoms = set(atoms)
        if not atoms <= self.universe:
            return False
        encoded = json.dumps(sorted(atoms))
        self.db.execute("BEGIN IMMEDIATE")
        try:
            prior = self.db.execute(
                "SELECT atoms,status FROM requests WHERE id=?", (request_id,)
            ).fetchone()
            if prior:
                self.db.execute("COMMIT")
                return prior[0] == encoded and prior[1] != "denied"
            statuses = (
                ("committed",)
                if self.method == "ignore_reservations"
                else ("pending", "unknown", "committed")
            )
            placeholders = ",".join("?" for _ in statuses)
            rows = self.db.execute(
                f"SELECT atoms FROM requests WHERE status IN ({placeholders})", statuses
            )
            present = set().union(*(set(json.loads(row[0])) for row in rows))
            total = present | atoms
            if self.method == "individual":
                allowed = all(legal({a}, self.alternatives) for a in atoms)
            elif self.method == "pairwise":
                allowed = legal(atoms, self.alternatives) and all(
                    legal(pair, self.alternatives) for pair in itertools.combinations(total, 2)
                )
            elif self.frontier is None:
                allowed = legal(total, self.alternatives)
            else:
                allowed = not any(f <= total for f in self.frontier)
            self.db.execute(
                "INSERT INTO requests VALUES (?,?,?)",
                (request_id, encoded, "pending" if allowed else "denied"),
            )
            self.db.execute("COMMIT")
            return allowed
        except sqlite3.Error:
            self.db.execute("ROLLBACK")
            raise

    def settle(self, request_id, outcome):
        if outcome not in ("committed", "no_effect", "unknown"):
            raise ValueError("Unknown receipt outcome")
        if outcome == "unknown" and self.method == "refund_unknown":
            outcome = "no_effect"
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                "SELECT status FROM requests WHERE id=?", (request_id,)
            ).fetchone()
            if row is None or row[0] == "denied":
                raise ValueError("Receipt has no admitted reservation")
            if row[0] in ("committed", "no_effect") and row[0] != outcome:
                raise ValueError("Conflicting final receipt")
            self.db.execute("UPDATE requests SET status=? WHERE id=?", (outcome, request_id))
            self.db.execute("COMMIT")
        except (sqlite3.Error, ValueError):
            self.db.execute("ROLLBACK")
            raise

    def close(self):
        self.db.close()


def generate(rng, count):
    for index in range(count):
        size = rng.randint(3, 8)
        universe = [str(i) for i in range(size)]
        forbidden = set(rng.sample(universe, rng.randint(2, min(size, 4))))
        alternatives = [sorted(set(universe) - {atom}) for atom in sorted(forbidden)]
        operations = []
        order = universe[:]
        rng.shuffle(order)
        for i, atom in enumerate(order):
            operations.append({"op": "reserve", "id": str(i), "atoms": [atom]})
            if rng.random() < 0.4:
                operations.append(
                    {
                        "op": "settle",
                        "id": str(i),
                        "outcome": rng.choice(["committed", "unknown", "no_effect"]),
                    }
                )
        operations.extend(
            {"op": "settle", "id": str(i), "outcome": "committed"}
            for i in range(size)
            if not any(x["op"] == "settle" and x["id"] == str(i) for x in operations)
        )
        yield {
            "id": str(index),
            "universe": universe,
            "alternatives": alternatives,
            "operations": operations,
            "family": f"arity-{len(forbidden)}",
        }


def run_case(case, method):
    ledger = Ledger(case["alternatives"], case["universe"], method)
    admitted = {}
    real = set()
    violation = False
    effects = 0
    try:
        for op in case["operations"]:
            if op["op"] == "reserve":
                allowed = ledger.reserve(op["id"], op["atoms"])
                admitted[op["id"]] = {"allowed": allowed, "atoms": op["atoms"]}
            elif op["op"] == "settle" and admitted.get(op["id"], {}).get("allowed"):
                ledger.settle(op["id"], op["outcome"])
                if op["outcome"] in ("committed", "unknown"):
                    real.update(admitted[op["id"]]["atoms"])
                    effects += len(admitted[op["id"]]["atoms"])
                    violation |= not legal(real, case["alternatives"])
            elif op["op"] != "settle":
                raise ValueError("Unsupported operation")
        return {
            "admitted": admitted,
            "effects": effects,
            "real": sorted(real),
            "violation": violation,
            "frontier_sets": len(ledger.frontier or []),
        }
    finally:
        ledger.close()


def score(case, result):
    decisions = list(result["admitted"].values())
    count = len(decisions)
    return {
        "joint_uar": int(result["violation"]),
        "admission_rate": sum(x["allowed"] for x in decisions) / count if count else None,
        "secure_task_success": int(not result["violation"] and result["effects"] > 0),
        "legal_effects": result["effects"] if not result["violation"] else 0,
        "frontier_size": result["frontier_sets"],
    }
