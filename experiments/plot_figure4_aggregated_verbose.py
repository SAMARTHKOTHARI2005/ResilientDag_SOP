#!/usr/bin/env python3
import sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.run_experiments import aggregate_confirmed_series

if __name__ == '__main__':
    out_dir = Path('paper/figures')
    out_dir.mkdir(parents=True, exist_ok=True)
    scenarios = ['baseline', 'attack', 'weighted']
    colors = {'baseline': 'tab:blue', 'attack': 'tab:orange', 'weighted': 'tab:purple'}
    fig, ax = plt.subplots(figsize=(7, 4))
    for scenario in scenarios:
        print(f'Aggregating scenario {scenario}', flush=True)
        time_grid, mean_series, std_series = aggregate_confirmed_series(100, scenario, seeds=30, sim_time=6.0, dt=0.1)
        print(f'  done scenario {scenario}', flush=True)
        ax.plot(
            time_grid,
            mean_series,
            linewidth=2.0,
            color=colors[scenario],
            linestyle='--' if scenario == 'weighted' else '-',
            label='Weighted defense' if scenario == 'weighted' else scenario.capitalize(),
        )
        ax.fill_between(
            time_grid,
            [m - s for m, s in zip(mean_series, std_series)],
            [m + s for m, s in zip(mean_series, std_series)],
            color=colors[scenario],
            alpha=0.15,
            linewidth=0,
        )
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Confirmed rounds')
    ax.set_title('Weighted-defense comparison (30-seed mean ± std)')
    ax.grid(True, alpha=0.3)
    ax.legend()
    out_path = out_dir / 'figure4_weighted_defense_comparison_aggregated.png'
    fig.savefig(out_path, dpi=220, bbox_inches='tight')
    fig.savefig(out_path.with_suffix('.pdf'), bbox_inches='tight')
    print('Saved', out_path, out_path.with_suffix('.pdf'), flush=True)
