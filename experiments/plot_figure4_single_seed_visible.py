#!/usr/bin/env python3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import runpy
import os

# Load run_once from experiments/run_experiments.py as a script to avoid
# package import issues when running this script directly.
_mod = runpy.run_path(os.path.join('experiments', 'run_experiments.py'))
run_once = _mod.get('run_once')

scenarios = [
    ('baseline', 'black', '-', 'o', 1.5, 'Baseline'),
    ('attack', '#ff7f0e', '-', '^', 2.0, 'Attack'),
    ('weighted', '#9467bd', '--', 's', 3.0, 'Weighted (forced)')
]

N = 100
seed = 0
sim_time = 2.0

out_dir = os.path.join('paper', 'figures')
os.makedirs(out_dir, exist_ok=True)

plt.figure(figsize=(6, 4))
for name, color, linestyle, marker, lw, label in scenarios:
    r = run_once(N, name, seed=seed, sim_time=sim_time)
    times = [t for _, t in r.get('confirmation_times', [])]
    rounds = list(range(1, len(times) + 1))
    if not times:
        continue
    z = 6 if name == 'weighted' else 4
    plt.plot(rounds, times, color=color, linestyle=linestyle, marker=marker,
             linewidth=lw, markersize=6, label=label, alpha=1.0, zorder=z)

plt.xlabel('Round')
plt.ylabel('Confirmation time (s)')
plt.title('Figure 4 — Weighted defense comparison (single seed)')
plt.legend()
plt.grid(True, linestyle=':', alpha=0.6)

png = os.path.join(out_dir, 'figure4_weighted_defense_comparison_visible.png')
pdf = os.path.join(out_dir, 'figure4_weighted_defense_comparison_visible.pdf')
plt.savefig(png, dpi=300, bbox_inches='tight')
plt.savefig(pdf, bbox_inches='tight')
print('Saved', png, pdf)
