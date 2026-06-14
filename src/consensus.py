import networkx as nx


class Consensus:
    """
    Depth-based round assignment and confirmation rule (Eq. 1-2 of the
    paper).

    BUGFIX (was: "Round 4 confirms before Round 1"):
    `add_unit` stores edges as (child -> parent). The previous
    implementation iterated `dag.graph.nodes(data=True)` in *insertion*
    order and computed a unit's round from `self.unit_round.get(parent, 1)`.
    Because of network/asynchrony, a child unit can be inserted into the
    graph (and therefore visited) before its parent is. In that case the
    parent's round was not yet known and was silently defaulted to 1,
    so the child's round was computed as 1 + 1 = 2 regardless of the
    parent's true depth -- under-counting rounds for early children and
    letting later, correctly-computed deep units cross the confirmation
    threshold (2f+1) for a *high* round number before shallow units ever
    push round 1 over the threshold. The fix processes units in a true
    parents-before-children (topological) order on every call, so a
    unit's round is always derived from its parents' *final* round
    values, eliminating the ordering artifact.
    """

    def __init__(self, dag, n_nodes):
        self.dag = dag
        self.n = n_nodes
        self.f = (n_nodes - 1) // 3
        self.commit_threshold = 2 * self.f + 1
        self.last_commit_time = None
        self.triggered = False

        self.unit_round = {}
        self.round_counts = {}
        self.committed_rounds = set()
        self.commit_times = {}
        self.pending = set()
        self.seen = set()

    def compute_round(self, unit):
        parents = unit["parents"]
        if not parents:
            return 1
        parent_rounds = [self.unit_round[p] for p in parents if p in self.unit_round]
        if not parent_rounds:
            return 1
        return 1 + max(parent_rounds)

    def process_new_units(self, current_time):
        """Incrementally assign rounds to newly-added units, in
        parents-before-children order, and check the commit rule.

        Rather than re-running a full topological sort of the entire DAG
        on every discrete-event step (O(V+E) each call -- prohibitively
        slow), we keep a `pending` set of units whose round is not yet
        known. On each call we add any new graph nodes to `pending`, then
        repeatedly sweep it: a unit can be assigned a round as soon as
        every parent of it that is currently in the graph already has an
        assigned round. This converges to the same parents-before-children
        order as a topological sort, but only touches units that changed.
        """
        graph = self.dag.graph
        for uid in graph.nodes:
            if uid not in self.seen:
                self.seen.add(uid)
                self.pending.add(uid)

        progress = True
        while progress and self.pending:
            progress = False
            for uid in list(self.pending):
                data = graph.nodes[uid]
                parents = data.get("parents", [])
                if any(p in graph and p not in self.unit_round for p in parents):
                    continue

                r = self.compute_round(data)
                self.unit_round[uid] = r
                self.round_counts[r] = self.round_counts.get(r, 0) + 1
                self.pending.discard(uid)
                progress = True

                if (
                    self.round_counts[r] >= self.commit_threshold
                    and r not in self.committed_rounds
                ):
                    self.committed_rounds.add(r)
                    self.commit_times[r] = current_time
                    self.last_commit_time = current_time

    def check_liveness(self, current_time, threshold=2.0):
        if self.last_commit_time is None:
            return False
        return (current_time - self.last_commit_time) > threshold