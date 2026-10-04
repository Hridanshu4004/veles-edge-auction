import json
from common.rng import set_seed
from simulator.data_generator import DataGenerator
from experiments.runner import ExperimentRunner

def run_sensitivity():
    print("=== PHASE 6 & 12: SENSITIVITY AND FAILURE BOUNDARIES ===")
    gen = DataGenerator(seed=101)
    scenario = gen.generate_scenario("SENSITIVITY", num_nodes=10, num_tasks=200, config={"node_type_weights": [0.4, 0.2, 0.2, 0.2, 0.0, 0.0, 0.0]})
    
    alphas = [0.0, 10.0, 50.0, 200.0]
    task_values = [10.0, 1000.0, 10000.0]
    
    results = []
    
    for val in task_values:
        # Override task values
        for t in scenario["tasks"]:
            t["task_value"] = val
            
        for a in alphas:
            runner = ExperimentRunner(scenario, seed=101)
            # Greedy baseline
            greedy_res = runner.run("greedy")
            
            # EdgeTruth with specific params
            runner.weights = {"alpha_success": a, "alpha_latency": a/5.0}
            et_res = runner.run("edgetruth_no_probe")
            
            results.append({
                "task_value": val,
                "alpha": a,
                "greedy_welfare": greedy_res["social_welfare"],
                "et_welfare": et_res["social_welfare"],
                "et_wins": et_res["social_welfare"] > greedy_res["social_welfare"]
            })
            
    for r in results:
        winner = "EdgeTruth" if r["et_wins"] else "Greedy"
        print(f"TaskVal: {r['task_value']:7.0f} | Alpha: {r['alpha']:5.1f} | Greedy W: ${r['greedy_welfare']:9.0f} | ET W: ${r['et_welfare']:9.0f} | Winner: {winner}")

if __name__ == "__main__":
    run_sensitivity()
