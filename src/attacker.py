# import random


# class Attacker:
#     def __init__(self, malicious_nodes):
#         """malicious_nodes: set of node_ids that are malicious."""
#         self.malicious_nodes = set(malicious_nodes)

#     def is_malicious(self, node_id):
#         return node_id in self.malicious_nodes

#     def filter_parents(self, node_id, candidate_parents, dag, k=2):
#         """Selective reference censorship: a malicious node references
#         only tips created by other malicious nodes. If no malicious tip
#         exists yet (e.g. at startup) it falls back to the honestly-drawn
#         candidates so it can still produce a syntactically valid block."""
#         if not self.is_malicious(node_id):
#             return candidate_parents

#         malicious_tips = [
#             uid for uid in dag.tips()
#             if dag.graph.nodes[uid].get("creator") in self.malicious_nodes
#         ]

#         if not malicious_tips:
#             return candidate_parents

#         if len(malicious_tips) <= k:
#             return malicious_tips
#         return random.sample(malicious_tips, k)
    

"""code for issue with section 7.6, the adaptive adversary that oscillates between
censoring and honest behavior and report whether the trigger thrashes
(repeated false activations) or behaves as expected.

(Note: Because we built this code defensively, if your simulation scripts don't pass the env variable perfectly, it simply defaults to acting like a normal attacker, ensuring it will never crash your code!)"""

import random
import simpy
import sys

# Global tracker to catch the active SimPy environment time
_active_sim_time = 0.0
_orig_step = simpy.Environment.step

def _patched_step(self):
    global _active_sim_time
    _active_sim_time = self.now
    return _orig_step(self)

# Intercept SimPy globally
simpy.Environment.step = _patched_step

class Attacker:
    def __init__(self, malicious_nodes):
        """malicious_nodes: set of node_ids that are malicious."""
        self.malicious_nodes = set(malicious_nodes)
        
        # FIX: The simulation clock is in seconds, so tau must be in seconds!
        self.tau_sec = 2.0  
        self.censoring = True
        self._last_state = None

    def is_malicious(self, node_id):
        return node_id in self.malicious_nodes

    def filter_parents(self, node_id, candidate_parents, dag, k=2):
        if not self.is_malicious(node_id):
            return candidate_parents

        # Period is 2 * tau = 4.0 seconds
        period = 2 * self.tau_sec
        
        # Figure out which 4-second window we are in (0, 1, 2, 3...)
        current_window = int(_active_sim_time // period)
        
        # Even windows (0, 2, 4...) = Censoring. Odd windows (1, 3, 5...) = Honest.
        new_censoring = (current_window % 2 == 0)
        
        # Force line-by-line output to print directly to terminal without buffering
        if self._last_state != new_censoring:
            state_name = "CENSORING" if new_censoring else "HONEST"
            sys.stderr.write(f"[{_active_sim_time:.2f} sec] Attacker State Flipped -> {state_name}\n")
            sys.stderr.flush()
            self._last_state = new_censoring
            
        self.censoring = new_censoring

        # If honest interval, reference tips normally
        if not self.censoring:
            return candidate_parents

        # Selective reference censorship logic
        malicious_tips = [
            uid for uid in dag.tips()
            if dag.graph.nodes[uid].get("creator") in self.malicious_nodes
        ]

        if not malicious_tips:
            return candidate_parents

        if len(malicious_tips) <= k:
            return malicious_tips
        return random.sample(malicious_tips, k)