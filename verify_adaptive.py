from experiments.run_experiments import run_once

print("--- Running Adaptive Adversary Simulation ---")
print("Network Size: N = 100")
print("Scenario: Recovered (Backup Pool Enabled)")
print("Simulation Time: 45.0 seconds (Allows for >10 oscillation cycles)")
print("---------------------------------------------")

# Run the single experiment for 45 seconds
res = run_once(N=100, scenario="recovered", seed=0, sim_time=45.0)

print("---------------------------------------------")
print("FINAL RESULTS:")
print(f"Total Backup Blocks Injected: {res['injected']}")
print(f"Final Throughput: {res['throughput']:.3f} rds/s")
print("---------------------------------------------")