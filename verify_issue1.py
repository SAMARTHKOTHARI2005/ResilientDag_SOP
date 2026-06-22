from experiments.run_experiments import run_once

# Run Attack Scenario
res_attack = run_once(N=100, scenario="attack", seed=0, sim_time=6.0)

# Run Recovered Scenario
res_recovered = run_once(N=100, scenario="recovered", seed=0, sim_time=6.0)

print("--- N = 100 | Seed = 0 ---")
print(f"Attack Injected:    {res_attack['injected']}")
print(f"Recovered Injected: {res_recovered['injected']}")
print("--------------------------")
print(f"Attack Throughput:    {res_attack['throughput']:.3f}")
print(f"Recovered Throughput: {res_recovered['throughput']:.3f}")
print(f"Attack Overhead:      {res_attack['overhead_pct']:.3f}%")
print(f"Recovered Overhead:   {res_recovered['overhead_pct']:.3f}%")