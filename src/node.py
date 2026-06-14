import simpy
import uuid

class Node:
    def __init__(self, node_id, env, network, dag, attacker=None,
                 create_interval=1.0, policy="random"):
        self.node_id = node_id
        self.env = env
        self.network = network
        self.dag = dag
        self.attacker = attacker
        self.policy = policy  # "random" (baseline/attack) or "weighted" (defense)

        self.inbox = simpy.Store(env)
        self.create_interval = create_interval

        env.process(self._receive_loop())
        env.process(self._create_loop())

    def _receive_loop(self):
        while True:
            unit = yield self.inbox.get()
            self.dag.add_unit(unit)

    def _create_loop(self):
        while True:
            yield self.env.timeout(self.create_interval)

            if self.policy == "weighted":
                parents = self.dag.select_parents_weighted(k=2)
            else:
                parents = self.dag.select_parents(k=2)

            if self.attacker is not None:
                parents = self.attacker.filter_parents(
                    self.node_id, parents, self.dag, k=2
                )

            unit = {
                "unit_id": str(uuid.uuid4()),
                "creator": self.node_id,
                "parents": parents,
                "timestamp": self.env.now,
            }

            self.dag.add_unit(unit)
            self.network.broadcast(self.node_id, unit)