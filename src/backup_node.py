import simpy
import uuid
import random


class BackupNode:
    def __init__(self, node_id, env, network, dag, malicious_nodes=None):
        self.node_id = node_id
        self.env = env
        self.network = network
        self.dag = dag
        self.malicious_nodes = set(malicious_nodes or [])

        self.inbox = simpy.Store(env)
        env.process(self._receive_loop())

    def _receive_loop(self):
        while True:
            unit = yield self.inbox.get()
            self.dag.add_unit(unit)

    def inject_witness_block(self, dag, network):
        """Algorithm 1: create a payload-free witness block whose parents
        span tips of the honest subgraph (T_H) and the adversarial
        subgraph (T_A), bridging the two fragments."""
        tips = dag.tips()
        if not tips:
            return

        honest_tips = [
            t for t in tips
            if dag.graph.nodes[t].get("creator") not in self.malicious_nodes
        ]
        adversarial_tips = [
            t for t in tips
            if dag.graph.nodes[t].get("creator") in self.malicious_nodes
        ]

        parents = []
        if honest_tips:
            parents.append(random.choice(honest_tips))
        if adversarial_tips:
            parents.append(random.choice(adversarial_tips))
        if not parents:
            parents = random.sample(tips, min(2, len(tips)))

        unit = {
            "unit_id": str(uuid.uuid4()),
            "creator": self.node_id,
            "parents": parents,
            "timestamp": self.env.now,
            "witness": True,
        }

        dag.add_unit(unit)
        network.broadcast(self.node_id, unit)