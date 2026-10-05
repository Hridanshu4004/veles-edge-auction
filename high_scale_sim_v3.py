import time

import numpy as np
import scipy.special
from data_pipeline import DataPipeline


def run_simulation(num_nodes=100000, num_tasks=10000, gamma=0.05):
    print("=== HIGH SCALE INDUSTRY SIMULATION: PHASE 3 HARDENING ===")
    pipeline = DataPipeline(seed=42)
    nodes_df = pipeline.generate_nodes_vectorized(num_nodes)
    tasks_df = pipeline.generate_tasks_vectorized(num_tasks)
    
    trust_brier = np.full(num_nodes, 0.25)
    trust_mae = np.full(num_nodes, 50.0)
    observations = np.zeros(num_nodes)
    
    for mech in ["greedy", "edgetruth_env_v3"]:
        print(f"\nRunning Mechanism: {mech.upper()}")
        trust_brier.fill(0.25)
        trust_mae.fill(50.0)
        observations.fill(0.0)
        
        metrics = {
            "success": 0, "sla_miss": 0, 
            "base_cost": 0.0, "failure_penalties": 0.0, 
            "collateral_forfeited": 0.0, "welfare": 0.0
        }
        start_time = time.time()
        
        for idx, task in tasks_df.iterrows():
            # True values (hidden from mechanism unless truthfully reported)
            V_true = task["value"]
            L_true = V_true 
            D = task["deadline_ms"]
            
            # Client Declared Values
            # (Assuming truthful for this simulation, but protocol enforces L_declared cap)
            V = V_true
            L_declared = L_true 
            
            sample_idx = pipeline.rng.choice(num_nodes, size=100, replace=False)
            bidders = nodes_df.iloc[sample_idx]
            b = bidders["bid_price"].values
            
            if mech == "greedy":
                winner_idx_in_sample = np.argmin(b)
                collateral_staked = 0.0
            else:
                p_hat = bidders["claim_success"].values
                mu_hat = bidders["claim_latency_p50"].values
                sigma_hat = np.maximum(1.0, bidders["claim_latency_std"].values)
                
                mae, brier = trust_mae[sample_idx], trust_brier[sample_idx]
                effective_sigma = np.maximum(sigma_hat, mae)
                p = np.maximum(0.01, p_hat * (1.0 - np.sqrt(brier)))
                
                z = (D - mu_hat) / (effective_sigma * np.sqrt(2.0))
                p_sla_met = (1.0 + scipy.special.erf(z)) / 2.0
                p_eff = p * p_sla_met
                
                # ENV calculation
                env = (p_eff * V) - b - ((1.0 - p_eff) * L_declared)
                
                # PARETO PRUNING
                # Filter candidates by comparing to the greedy baseline
                # Sort indices by bid price (cheapest first)
                sorted_indices = np.argsort(b)
                pareto_front = [sorted_indices[0]]
                
                for i in sorted_indices[1:]:
                    last_idx = pareto_front[-1]
                    delta_b = b[i] - b[last_idx]
                    delta_p = p_eff[i] - p_eff[last_idx]
                    
                    if delta_p > 0:
                        marginal_efficiency = delta_b / delta_p
                        # If marginal efficiency is below threshold, it's a valid pareto jump
                        if marginal_efficiency <= (V + L_declared):
                            pareto_front.append(i)
                            
                # From pareto front, select the one that maximizes ENV
                pareto_env = env[pareto_front]
                best_pareto_idx = np.argmax(pareto_env)
                winner_idx_in_sample = pareto_front[best_pareto_idx]
                
            winner = bidders.iloc[winner_idx_in_sample]
            winner_global_idx = sample_idx[winner_idx_in_sample]
            
            # STAKED PERFORMANCE BOND
            if mech == "edgetruth_env_v3":
                q_i = winner["claim_success"]
                collateral_staked = q_i * (V + L_declared) * gamma
            else:
                collateral_staked = 0.0
                
            # Ground Truth Execution
            actual_success, actual_latency = pipeline.simulate_execution(task, winner)
            sla_met = actual_success and (actual_latency <= D)
            
            # Cost Tracking & SLA Compensation Cap
            metrics["base_cost"] += winner["bid_price"]
            
            if not actual_success:
                # Task completely fails
                actual_loss = L_true
                min(L_declared, actual_loss) # Insurance Cap
                
                metrics["failure_penalties"] += actual_loss
                
                if mech == "edgetruth_env_v3":
                    metrics["collateral_forfeited"] += collateral_staked
                    # Node loses bid + collateral
                    metrics["welfare"] -= (winner["bid_price"] + actual_loss)
                else:
                    metrics["welfare"] -= (winner["bid_price"] + actual_loss)
                    
            elif not sla_met:
                # Partial failure / SLA miss
                actual_loss = L_true * 0.5
                min(L_declared * 0.5, actual_loss)  # type: ignore
                
                metrics["sla_miss"] += 1
                metrics["failure_penalties"] += actual_loss
                
                if mech == "edgetruth_env_v3":
                    metrics["collateral_forfeited"] += collateral_staked
                    metrics["welfare"] -= (winner["bid_price"] + actual_loss)
                else:
                    metrics["welfare"] -= (winner["bid_price"] + actual_loss)
            else:
                metrics["success"] += 1
                metrics["welfare"] += V_true - winner["bid_price"]
                
            # Trust Update
            if mech == "edgetruth_env_v3":
                alpha = 0.1 if observations[winner_global_idx] > 0 else 1.0
                trust_brier[winner_global_idx] = (1-alpha)*trust_brier[winner_global_idx] + alpha*(winner["claim_success"] - float(actual_success))**2
                if actual_success:
                    trust_mae[winner_global_idx] = (1-alpha)*trust_mae[winner_global_idx] + alpha*abs(actual_latency - winner["claim_latency_p50"])
                observations[winner_global_idx] += 1
                
        print(f"Time: {time.time() - start_time:.2f}s")
        print(f"Success: {metrics['success']} / {num_tasks}")
        print(f"Cost Breakdown: Base: ${metrics['base_cost']:,.0f} | Penalties: ${metrics['failure_penalties']:,.0f}")
        if mech == "edgetruth_env_v3":
            print(f"Collateral Forfeited (Paid to Client): ${metrics['collateral_forfeited']:,.0f}")
        print(f"Actual Social Welfare: ${metrics['welfare']:,.0f}")

if __name__ == "__main__":
    run_simulation()
