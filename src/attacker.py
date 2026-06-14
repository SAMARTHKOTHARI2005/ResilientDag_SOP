import random


class Attacker:
    def __init__(self, malicious_nodes):
        """malicious_nodes: set of node_ids that are malicious."""
        self.malicious_nodes = set(malicious_nodes)

    def is_malicious(self, node_id):
        return node_id in self.malicious_nodes

    def filter_parents(self, node_id, candidate_parents, dag, k=2):
        """Selective reference censorship: a malicious node references
        only tips created by other malicious nodes. If no malicious tip
        exists yet (e.g. at startup) it falls back to the honestly-drawn
        candidates so it can still produce a syntactically valid block."""
        if not self.is_malicious(node_id):
            return candidate_parents

        malicious_tips = [
            uid for uid in dag.tips()
            if dag.graph.nodes[uid].get("creator") in self.malicious_nodes
        ]

        if not malicious_tips:
            return candidate_parents

        if len(malicious_tips) <= k:
            return malicious_tips
        return random.sample(malicious_tips, k)