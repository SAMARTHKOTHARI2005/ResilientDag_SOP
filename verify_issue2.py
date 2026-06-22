from experiments.run_experiments import run_once

# Run all 3 scenarios
res_base = run_once(N=100, scenario="baseline", seed=0, sim_time=6.0)
res_attack = run_once(N=100, scenario="attack", seed=0, sim_time=6.0)
res_recovered = run_once(N=100, scenario="recovered", seed=0, sim_time=6.0)

print("--- N = 100 | Seed = 0 ---")
print("Scenario   | Throughput | Latency (ms)")
print("--------------------------------------")
print(f"Baseline   | {res_base['throughput']:.3f}      | {res_base['mean_latency_ms']:.3f}")
print(f"Attack     | {res_attack['throughput']:.3f}      | {res_attack['mean_latency_ms']:.3f}")
print(f"Recovered  | {res_recovered['throughput']:.3f}      | {res_recovered['mean_latency_ms']:.3f}")