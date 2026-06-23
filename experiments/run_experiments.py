"""
RESILIENTDAG experiment runner.

Runs the discrete-event simulator across network sizes, scenarios and
seeds and writes per-configuration aggregated results (mean +/- std over
seeds) to CSV. Drives the paper's experiments and generates the figure
assets used in the report.

Confirmation metric
--------------------
Blocks are grouped into DAG rounds derived from the true parent depth of
each unit, so the round assignment is computed in parents-before-children
order rather than by time-window timestamps. A round r confirms when:
  (i)  it contains at least 2f+1 blocks (Eq. 2 of the paper), and
  (ii) -- only when an adversarial coalition is present -- at least f+1
       of those blocks carry a *cross-faction* reference, i.e. at least
       one of their parents was created by a node of the opposite
       faction (honest/adversarial), or by a backup (witness) node.
Condition (ii) operationalises the paper's claim that censorship
degrades liveness through *fragmentation*: under selective reference
censorship, adversarial blocks never reference honest tips, so the
number of cross-faction (bridging) blocks per round collapses; witness
injection restores it.
"""
import argparse
import csv
import random
import statistics as stats
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

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

SCENARIOS = ["baseline", "attack", "recovered", "weighted"]
TAU = 2.0          # liveness timeout (s) == 2000 ms in the paper
W = 1.0 / 9.5       # round window width (s)


def faction(dag, uid, malicious_ids):
    creator = dag.graph.nodes[uid].get("creator")
    if isinstance(creator, str) and creator.startswith("backup"):
        return "W"
    return "M" if creator in malicious_ids else "H"


def run_once(N, scenario, seed, sim_time, fanout=None):
    random.seed(seed)

    env = simpy.Environment()
    dag = DAG()
    network = Network(env, latency_mean=0.05, fanout=0)

    malicious = scenario in ("attack", "recovered", "weighted")
    num_malicious = int(0.3 * N) if malicious else 0
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
        for i in range(f + 2):
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
    recovery_trigger_time = None

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

        # BUGFIX: finalize completed rounds strictly in ascending order. This
        # prevents a later window from being emitted before an earlier one,
        # which would otherwise make a higher round appear to confirm first.
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
            if env.now - effective_last > TAU:
                for b in backup_nodes:
                    b.inject_witness_block(dag, network)
                    injected += 1
                triggered = True
                recovery_trigger_time = env.now

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

    return {
        "confirmed_rounds": confirmed_rounds,
        "confirmation_times": confirmation_times,
        "latencies_ms": latencies,
        "mean_latency_ms": mean_latency,
        "throughput": throughput,
        "overhead_pct": overhead,
        "total_blocks": total_blocks,
        "injected": injected,
        "recovery_trigger_time": recovery_trigger_time,
    }


def save_figure(fig, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def generate_plots(plot_dir, seeds=30):
    plot_dir.mkdir(parents=True, exist_ok=True)

    fig1, ax1 = plt.subplots(figsize=(7, 4))
    styles = {
        "baseline": {"color": "tab:blue", "linestyle": "-", "marker": "o"},
        "attack": {"color": "tab:orange", "linestyle": "-", "marker": "o"},
        "recovered": {"color": "tab:green", "linestyle": "--", "marker": "s"},
    }
    for scenario in ["baseline", "attack", "recovered"]:
        result = run_once(100, scenario, seed=0, sim_time=6.0)
        rounds = [round_num for round_num, _ in result["confirmation_times"]]
        style = styles[scenario]
        ax1.plot(
            rounds,
            result["latencies_ms"],
            marker=style["marker"],
            linewidth=1.8,
            linestyle=style["linestyle"],
            color=style["color"],
            label=scenario.capitalize(),
            zorder=3 if scenario == "attack" else 2,
        )
    ax1.axhline(TAU * 1000.0, color="black", linestyle="--", label=r"$\tau$")
    ax1.set_xlabel("Confirmed round")
    ax1.set_ylabel("Latency (ms)")
    ax1.set_title("Latency per confirmed round")
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    save_figure(fig1, plot_dir / "figure1_latency_per_round.png")

    fig2, axes = plt.subplots(1, 2, figsize=(10, 4))
    before_graph = nx.DiGraph()
    before_graph.add_nodes_from(range(12), faction="H")
    honest_nodes = list(range(6))
    malicious_nodes = list(range(6, 12))
    for node in honest_nodes:
        before_graph.nodes[node]["faction"] = "H"
    for node in malicious_nodes:
        before_graph.nodes[node]["faction"] = "M"
    before_graph.add_edges_from([(1, 0), (2, 0), (3, 1), (4, 2), (5, 3)])
    before_graph.add_edges_from([(7, 6), (8, 6), (9, 7), (10, 8), (11, 9)])
    pos_before = nx.shell_layout(before_graph, nlist=[honest_nodes, malicious_nodes])
    colors_before = ["tab:blue" if before_graph.nodes[n]["faction"] == "H" else "tab:red" for n in before_graph.nodes]
    nx.draw(before_graph, pos_before, ax=axes[0], with_labels=True, node_color=colors_before, node_size=550, arrows=True, edge_color="gray")
    axes[0].set_title("Before witness injection")

    after_graph = before_graph.copy()
    after_graph.add_nodes_from([12, 13], faction="W")
    after_graph.add_edges_from([(12, 5), (12, 9), (13, 4), (13, 10)])
    pos_after = nx.shell_layout(after_graph, nlist=[honest_nodes, malicious_nodes, [12, 13]])
    colors_after = ["tab:blue" if after_graph.nodes[n]["faction"] == "H" else "tab:red" if after_graph.nodes[n]["faction"] == "M" else "tab:green" for n in after_graph.nodes]
    nx.draw(after_graph, pos_after, ax=axes[1], with_labels=True, node_color=colors_after, node_size=550, arrows=True, edge_color="gray")
    axes[1].set_title("After witness injection")
    save_figure(fig2, plot_dir / "figure2_dag_before_after.png")

    fig3, ax3 = plt.subplots(figsize=(7, 4))
    styles = {
        "baseline": {"color": "tab:blue", "linestyle": "-", "marker": "o"},
        "attack": {"color": "tab:orange", "linestyle": "-", "marker": "o"},
        "recovered": {"color": "tab:green", "linestyle": "--", "marker": "s"},
    }
    for scenario in ["baseline", "attack", "recovered"]:
        result = run_once(100, scenario, seed=0, sim_time=6.0)
        times = [t for _, t in result["confirmation_times"]]
        cumulative = list(range(1, len(times) + 1))
        style = styles[scenario]
        ax3.plot(
            times,
            cumulative,
            marker=style["marker"],
            linewidth=1.8,
            linestyle=style["linestyle"],
            color=style["color"],
            label=scenario.capitalize(),
            zorder=3 if scenario == "attack" else 2,
        )
    ax3.axvline(0.0, color="gray", linestyle=":", label="Attack onset")
    if any((run_once(100, "recovered", seed=0, sim_time=6.0)["recovery_trigger_time"] is not None) for _ in [0]):
        recovered_result = run_once(100, "recovered", seed=0, sim_time=6.0)
        if recovered_result["recovery_trigger_time"] is not None:
            ax3.axvline(recovered_result["recovery_trigger_time"], color="tab:green", linestyle="--", label="Recovery trigger")
    ax3.set_xlabel("Time (s)")
    ax3.set_ylabel("Confirmed rounds")
    ax3.set_title("Throughput over time")
    ax3.grid(True, alpha=0.3)
    ax3.legend()
    save_figure(fig3, plot_dir / "figure3_throughput_over_time.png")

    fig4, ax4 = plt.subplots(figsize=(7, 4))
    scenarios_to_plot = ["baseline", "attack", "weighted"]
    colors = {"baseline": "tab:blue", "attack": "tab:orange", "weighted": "tab:purple"}
    for scenario in scenarios_to_plot:
        time_grid, mean_series, std_series = aggregate_confirmed_series(100, scenario, seeds, sim_time=6.0, dt=0.1)
        if scenario == "weighted":
            ax4.plot(
                time_grid,
                mean_series,
                linewidth=4.0,
                color=colors[scenario],
                linestyle="--",
                marker="s",
                markersize=10,
                markeredgewidth=1.8,
                markeredgecolor="black",
                markerfacecolor="white",
                label="Weighted defense",
                zorder=6,
            )
            ax4.annotate(
                "Weighted",
                xy=(time_grid[-1], mean_series[-1]),
                xytext=(-28, 20),
                textcoords="offset points",
                color=colors[scenario],
                fontsize=11,
                fontweight="bold",
                arrowprops={"arrowstyle": "->", "color": colors[scenario], "lw": 1.5},
                zorder=7,
            )
        else:
            ax4.plot(
                time_grid,
                mean_series,
                linewidth=2.0,
                color=colors[scenario],
                linestyle="-",
                marker="o",
                markersize=4,
                alpha=0.45 if scenario == "attack" else 0.8,
                label=scenario.capitalize(),
                zorder=3 if scenario == "attack" else 2,
            )
        ax4.fill_between(
            time_grid,
            [m - s for m, s in zip(mean_series, std_series)],
            [m + s for m, s in zip(mean_series, std_series)],
            color=colors[scenario],
            alpha=0.1,
            linewidth=0,
            zorder=5 if scenario == "weighted" else 1,
        )
    ax4.set_xlabel("Time (s)")
    ax4.set_ylabel("Confirmed rounds")
    ax4.set_title("Weighted-defense comparison (30-seed mean ± std)")
    ax4.grid(True, alpha=0.3)
    ax4.legend()
    save_figure(fig4, plot_dir / "figure4_weighted_defense_comparison.png")


def confirmed_counts_at_times(result, time_grid):
    confirmation_times = [t for _, t in result["confirmation_times"]]
    counts = []
    idx = 0
    for t in time_grid:
        while idx < len(confirmation_times) and confirmation_times[idx] <= t:
            idx += 1
        counts.append(idx)
    return counts


def aggregate_confirmed_series(N, scenario, seeds, sim_time, dt=0.1):
    time_grid = [round(i * dt, 8) for i in range(int(sim_time / dt) + 1)]
    seed_series = []
    for seed in range(seeds):
        result = run_once(N, scenario, seed, sim_time)
        seed_series.append(confirmed_counts_at_times(result, time_grid))
    mean_series = [safe_mean(values) for values in zip(*seed_series)]
    std_series = [safe_std(values) for values in zip(*seed_series)]
    return time_grid, mean_series, std_series


def safe_mean(xs):
    xs = [x for x in xs if x != float("inf")]
    return stats.mean(xs) if xs else float("inf")


def safe_std(xs):
    xs = [x for x in xs if x != float("inf")]
    return stats.pstdev(xs) if len(xs) > 1 else 0.0


def aggregate_results(configs, seeds=30, sim_time=6.0):
    rows = []
    for N, fanout in configs:
        for scenario in SCENARIOS:
            lat_means, tputs, overheads = [], [], []
            for seed in range(seeds):
                r = run_once(N, scenario, seed, sim_time, fanout=fanout)
                lat_means.append(r["mean_latency_ms"])
                tputs.append(r["throughput"])
                overheads.append(r["overhead_pct"])

            rows.append({
                "N": N,
                "scenario": scenario,
                "latency_ms_mean": safe_mean(lat_means),
                "latency_ms_std": safe_std(lat_means),
                "throughput_mean": safe_mean(tputs),
                "throughput_std": safe_std(tputs),
                "overhead_mean": safe_mean(overheads),
                "overhead_std": safe_std(overheads),
            })
            print(
                f"N={N} scenario={scenario}: latency={rows[-1]['latency_ms_mean']:.2f} ± {rows[-1]['latency_ms_std']:.2f} ms, "
                f"throughput={rows[-1]['throughput_mean']:.3f} ± {rows[-1]['throughput_std']:.3f}, overhead={rows[-1]['overhead_mean']:.2f} ± {rows[-1]['overhead_std']:.2f}%"
            )
    return rows


def format_table_summary(rows):
    header = "| N | Scenario | Latency (ms) | Throughput | Overhead (%) |"
    divider = "|---|---|---|---|---|"
    lines = [header, divider]
    for row in rows:
        lines.append(
            f"| {row['N']} | {row['scenario']} | {row['latency_ms_mean']:.3f} ± {row['latency_ms_std']:.3f} | "
            f"{row['throughput_mean']:.3f} ± {row['throughput_std']:.3f} | {row['overhead_mean']:.3f} ± {row['overhead_std']:.3f} |"
        )
    return "\n".join(lines)


def write_table_summary(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_table_summary(rows) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--sim-time", type=float, default=6.0)
    ap.add_argument("--out", default="data/results.csv")
    ap.add_argument("--plot-dir", default="paper/figures")
    ap.add_argument("--table-out", default="paper/table_i.md")
    args = ap.parse_args()

    if args.seeds < 30:
        ap.error("--seeds must be at least 30 to match the paper's Table I protocol")

    configs = [(100, None), (500, 30), (1000, 20)]
    rows = aggregate_results(configs, seeds=args.seeds, sim_time=args.sim_time)

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {args.out}")

    table_out = Path(args.table_out)
    write_table_summary(rows, table_out)
    print(f"Wrote {table_out}")

    plot_dir = Path(args.plot_dir)
    generate_plots(plot_dir, seeds=args.seeds)
    print(f"Wrote plots to {plot_dir}")


if __name__ == "__main__":
    main()