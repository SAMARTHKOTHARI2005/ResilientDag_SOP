"""
Standalone sweep script for ResilientDAG.
Runs the censorship-fraction sweep and sensitivity sweep (over |B| and tau)
for N=100 without disrupting the core experiment file.
"""
import csv
import random
import sys
import statistics as stats
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import simpy
except ImportError:
    from src import simpy_lite as simpy

from src.backup_node import BackupNode
from src.dag import DAG
from src.network import Network
from src.node import Node
from src.attacker import Attacker

W = 1.0 / 9.5  # round window width (s)

def faction(dag, uid, malicious_ids):
    creator = dag.graph.nodes[uid].get("creator")
    if isinstance(creator, str) and creator.startswith("backup"):
        return "W"
    return "M" if creator in malicious_ids else "H"

def run_once_sweep(N, scenario, seed, sim_time, censorship_fraction, tau_s, b_size):
    random.seed(seed)
    env = simpy.Environment()
    dag = DAG()
    network = Network(env, latency_mean=0.05, fanout=0)

    malicious = scenario in ("attack", "recovered", "weighted")
    num_malicious = int(censorship_fraction * N) if malicious else 0
    malicious_ids = set(range(num_malicious))
    attacker = Attacker(malicious_ids) if num_malicious else None
    
    f = (N - 1) // 3
    threshold = 2 * f + 1
    bridge_threshold = f + 1

    policy = "weighted" if scenario == "weighted" else "random"

    for i in range(N):
        node = Node(
            node_id=i,
            env=env,
            network=network,
            dag=dag,
            attacker=attacker if i in malicious_ids else None,
            create_interval=random.uniform(0.1, 0.2),
            policy=policy,
        )
        network.register(node)

    backup_nodes = []
    if scenario == "recovered":
        # Dynamic backup pool size for the sweep
        for i in range(b_size):
            b = BackupNode(
                node_id=f"backup-{i}",
                env=env,
                network=network,
                dag=dag,
                malicious_nodes=malicious_ids,
            )
            network.register(b)
            backup_nodes.append(b)

    round_counts = {}
    bridge_counts = {}
    is_bridging = {}
    seen = set()
    injected = 0
    confirmed_rounds = []
    confirmation_times = []
    last_confirm_time = 0.0
    last_finalized_round = -1
    triggered = False

    while env.now < sim_time:
        env.step()

        for uid in list(dag.graph.nodes):
            if uid in seen:
                continue
            seen.add(uid)
            data = dag.graph.nodes[uid]
            round_num = int(data["timestamp"] // W)
            round_counts[round_num] = round_counts.get(round_num, 0) + 1

            own = faction(dag, uid, malicious_ids)
            parents = data.get("parents", [])
            direct_cross = any(
                p in dag.graph and faction(dag, p, malicious_ids) != own
                for p in parents
            )
            witness_lineage = own == "W" or any(
                is_bridging.get(p, False) for p in parents
            )
            is_bridging[uid] = witness_lineage
            if own == "W" or direct_cross or witness_lineage:
                bridge_counts[round_num] = bridge_counts.get(round_num, 0) + 1

        current_window = int(env.now // W)
        for round_num in range(last_finalized_round + 1, current_window):
            ok = round_counts.get(round_num, 0) >= threshold and (
                not malicious or bridge_counts.get(round_num, 0) >= bridge_threshold
            )
            if ok:
                confirmed_rounds.append(round_num)
                confirmation_times.append((round_num, (round_num + 1) * W))
                last_confirm_time = (round_num + 1) * W
                triggered = False
            last_finalized_round = round_num

        if scenario == "recovered" and not triggered:
            effective_last = last_confirm_time if last_confirm_time > 0.0 else 0.0
            # Dynamic TAU for the sweep
            if env.now - effective_last > tau_s:
                for b in backup_nodes:
                    b.inject_witness_block(dag, network)
                    injected += 1
                triggered = True

    total_blocks = len(seen)
    confirmed_rounds.sort()
    confirmation_times = sorted(confirmation_times, key=lambda item: item[0])

    latencies = []
    prev = 0.0
    for _, t in confirmation_times:
        latencies.append((t - prev) * 1000.0)
        prev = t

    throughput = len(confirmed_rounds) / sim_time if sim_time > 0 else 0.0
    overhead = (injected / total_blocks * 100.0) if total_blocks else 0.0
    mean_latency = stats.mean(latencies) if latencies else float("inf")

    return mean_latency, throughput, overhead

def safe_mean(xs):
    xs = [x for x in xs if x != float("inf")]
    return stats.mean(xs) if xs else float("inf")

def safe_std(xs):
    xs = [x for x in xs if x != float("inf")]
    return stats.pstdev(xs) if len(xs) > 1 else 0.0

def main():
    print("Starting Sweeps for N=100...")
    N = 100
    seeds = 30
    sim_time = 6.0
    rows = []

    # 1. Censorship Fraction Sweep (5% to 33%)
    # Holding |B| = f+2 (35 for N=100), tau = 2.0s
    fractions = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.33]
    print("\n--- Running Censorship Fraction Sweep ---")
    for frac in fractions:
        for scenario in ["attack", "recovered"]:
            lat_means, tputs, overheads = [], [], []
            for seed in range(seeds):
                lat, tp, oh = run_once_sweep(N, scenario, seed, sim_time, frac, 2.0, ((N-1)//3)+2)
                lat_means.append(lat)
                tputs.append(tp)
                overheads.append(oh)
            
            rows.append({
                "sweep_type": "censorship_fraction",
                "parameter_value": frac,
                "scenario": scenario,
                "latency_mean": safe_mean(lat_means),
                "throughput_mean": safe_mean(tputs),
                "overhead_mean": safe_mean(overheads),
            })
            print(f"Fraction={frac:.2f} Scenario={scenario}: Tput={rows[-1]['throughput_mean']:.3f}, Overhead={rows[-1]['overhead_mean']:.2f}%")

    # 2. Sensitivity Sweep (|B| and Tau)
    # Holding censorship = 30%. Only runs on 'recovered' since Baseline/Attack don't use backup nodes or tau.
    b_sizes = [1, 3, 5, 10]
    taus = [0.5, 1.0, 2.0, 4.0]
    
    print("\n--- Running Sensitivity Sweep (|B| and Tau) ---")
    for b in b_sizes:
        for t in taus:
            lat_means, tputs, overheads = [], [], []
            for seed in range(seeds):
                lat, tp, oh = run_once_sweep(N, "recovered", seed, sim_time, 0.30, t, b)
                lat_means.append(lat)
                tputs.append(tp)
                overheads.append(oh)
            
            rows.append({
                "sweep_type": "sensitivity_b_tau",
                "parameter_value": f"B={b}, Tau={t}s",
                "scenario": "recovered",
                "latency_mean": safe_mean(lat_means),
                "throughput_mean": safe_mean(tputs),
                "overhead_mean": safe_mean(overheads),
            })
            print(f"|B|={b}, Tau={t}s: Tput={rows[-1]['throughput_mean']:.3f}, Overhead={rows[-1]['overhead_mean']:.2f}%")

    # Save to CSV
    out_path = PROJECT_ROOT / "data" / "sweep_results.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nAll sweeps complete! Data saved to {out_path}")

if __name__ == "__main__":
    main()