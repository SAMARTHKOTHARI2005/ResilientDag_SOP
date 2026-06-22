from experiments.run_experiments import run_once

# Run a much longer simulation to force the natural network variance to cause another stall
res_recovered = run_once(N=100, scenario="recovered", seed=0, sim_time=60.0)

print("--- Issue 8: Multi-Stall Verification ---")
print(f"Simulation Time: 60.0 seconds")
print(f"Total Witness Blocks Injected: {res_recovered['injected']}")
print("-----------------------------------------")