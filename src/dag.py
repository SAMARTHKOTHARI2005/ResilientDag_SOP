import networkx as nx
import random


class DAG:
    def __init__(self):
        self.graph = nx.DiGraph()
        self._seq = 0  # insertion order, used as an age proxy for tips

    def add_unit(self, unit):
        uid = unit["unit_id"]

        if uid in self.graph:
            return

        self._seq += 1
        self.graph.add_node(uid, seq=self._seq, **unit)

        for parent in unit["parents"]:
            if parent in self.graph:
                self.graph.add_edge(uid, parent)

    def tips(self):
        """A tip is a block not yet referenced (approved) by any other
        block, i.e. it has in-degree 0."""
        return [n for n in self.graph.nodes if self.graph.in_degree(n) == 0]

    def select_parents(self, k=2):
        """Baseline / attack policy: uniform random over current tips."""
        candidates = self.tips()
        if not candidates:
            candidates = list(self.graph.nodes)
        if len(candidates) <= k:
            return candidates.copy()
        return random.sample(candidates, k)

    def select_parents_weighted(self, k=2):
        """Defense policy (weighted/restricted tip selection, cf. [9]):
        favours older, under-approved tips so no group of tips is
        systematically starved of references."""
        candidates = self.tips()
        if not candidates:
            candidates = list(self.graph.nodes)
        if len(candidates) <= k:
            return candidates.copy()

        max_seq = max(self.graph.nodes[n]["seq"] for n in candidates)
        pool = [(n, 1.0 + (max_seq - self.graph.nodes[n]["seq"])) for n in candidates]
        chosen = []
        while len(chosen) < k and pool:
            total = sum(w for _, w in pool)
            r = random.uniform(0, total)
            upto = 0
            for i, (c, w) in enumerate(pool):
                upto += w
                if upto >= r:
                    chosen.append(c)
                    pool.pop(i)
                    break
        return chosen