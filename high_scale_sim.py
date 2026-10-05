import math
import time

import numpy as np
from data_pipeline import DataPipeline


def normal_cdf(x, mu, sigma):
    return (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0)))) / 2.0

def run_simulation(num_nodes=100000, num_tasks=10000):
    print("=== HIGH SCALE SIMULATION ===")
    pipeline = DataPipeline(seed=42)
    nodes_df = pipeline.generate_nodes_vectorized(num_nodes)
    tasks_df = pipeline.generate_tasks_vectorized(num_tasks)
    
    # We will track trust using standard arrays (vectorized)
    # trust_brier starts at 0.25 (i.e. 50% success prior), trust_mae starts at 50.0
    trust_brier = np.full(num_nodes, 0.25)
    trust_mae = np.full(num_nodes, 50.0)
    observations = np.zeros(num_nodes)
    
    mechanisms = ["greedy", "edgetruth_env"]
    
    for mech in mechanisms:
        print(f"\nRunning Mechanism: {mech.upper()}")
        trust_brier.fill(0.25)
        trust_mae.fill(50.0)
        observations.fill(0.0)
        
        metrics = {
            "success": 0,
            "sla_miss": 0,
            "base_cost": 0.0,
            "retry_cost": 0.0, # Not doing retries here to keep it simple, just failure loss
            "failure_penalties": 0.0,
            "actual_social_welfare": 0.0
        }
        
        start_time = time.time()
        
        for idx, task in tasks_df.iterrows():
            V = task["value"]
            L = V # Failure penalty
            D = task["deadline_ms"]
            
            # Select 1000 random nodes to bid to keep it realistic
            sample_idx = pipeline.rng.choice(num_nodes, size=100, replace=False)
            bidders = nodes_df.iloc[sample_idx]
            
            b = bidders["bid_price"].values
            
            if mech == "greedy":
                winner_idx_in_sample = np.argmin(b)
            else:
                p_hat = bidders["claim_success"].values
                mu_hat = bidders["claim_latency_p50"].values
                sigma_hat = np.maximum(1.0, bidders["claim_latency_std"].values)
                
                mae = trust_mae[sample_idx]
                brier = trust_brier[sample_idx]
                
                effective_sigma = np.maximum(sigma_hat, mae)
                p = np.maximum(0.01, p_hat * (1.0 - np.sqrt(brier)))
                
                # Vectorized CDF is tricky with math.erf, use numpy for speed
                z = (D - mu_hat) / (effective_sigma * np.sqrt(2.0))
                import scipy.special
                p_sla_met = (1.0 + scipy.special.erf(z)) / 2.0
                
                p_eff = p * p_sla_met
                env = (p_eff * V) - b - ((1.0 - p_eff) * L)
                
                winner_idx_in_sample = np.argmax(env)
                
            winner = bidders.iloc[winner_idx_in_sample]
            winner_global_idx = sample_idx[winner_idx_in_sample]
            
            # Execution
            actual_success, actual_latency = pipeline.simulate_execution(task, winner)
            
            # Cost breakdown
            metrics["base_cost"] += winner["bid_price"]
            
            sla_met = actual_success and (actual_latency <= D)
            if not actual_success:
                metrics["failure_penalties"] += L
            elif not sla_met:
                metrics["sla_miss"] += 1
                metrics["failure_penalties"] += L * 0.5 # Partial penalty for SLA miss
            else:
                metrics["success"] += 1
                
            # Welfare
            if sla_met:
                metrics["actual_social_welfare"] += V - winner["bid_price"]
            else:
                metrics["actual_social_welfare"] -= (winner["bid_price"] + (L if not actual_success else L * 0.5))
                
            # Update trust
            if mech == "edgetruth_env":
                obs = observations[winner_global_idx]
                alpha = 0.1 if obs > 0 else 1.0
                
                brier_upd = (winner["claim_success"] - float(actual_success))**2
                trust_brier[winner_global_idx] = (1-alpha)*trust_brier[winner_global_idx] + alpha*brier_upd
                
                if actual_success:
                    mae_upd = abs(actual_latency - winner["claim_latency_p50"])
                    trust_mae[winner_global_idx] = (1-alpha)*trust_mae[winner_global_idx] + alpha*mae_upd
                    
                observations[winner_global_idx] += 1
                
        elapsed = time.time() - start_time
        print(f"Time: {elapsed:.2f}s")
        print(f"Success: {metrics['success']} / {num_tasks}")
        print(f"SLA Misses: {metrics['sla_miss']}")
        print(f"Cost Breakdown: Base: ${metrics['base_cost']:,.0f} | Penalties: ${metrics['failure_penalties']:,.0f}")
        print(f"Actual Social Welfare: ${metrics['actual_social_welfare']:,.0f}")

if __name__ == "__main__":
    run_simulation()
