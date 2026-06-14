import random


class Network:
    def __init__(self, env, latency_mean=0.5, fanout=None):
        """fanout: if set, broadcast() delivers to a random sample of
        `fanout` peers instead of all peers (gossip-style dissemination,
        used to keep large-N simulations tractable)."""
        self.env = env
        self.latency_mean = latency_mean
        self.fanout = fanout
        self.nodes = {}

    def register(self, node):
        self.nodes[node.node_id] = node

    def broadcast(self, sender_id, unit):
        targets = [nid for nid in self.nodes if nid != sender_id]
        if self.fanout is not None and len(targets) > self.fanout:
            targets = random.sample(targets, self.fanout)
        for nid in targets:
            self.env.process(self._deliver(self.nodes[nid], unit))

    def _deliver(self, node, unit):
        latency = random.expovariate(1 / self.latency_mean)
        yield self.env.timeout(latency)
        yield node.inbox.put(unit)