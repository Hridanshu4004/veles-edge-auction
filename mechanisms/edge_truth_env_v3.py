import math

from common.models import Allocation, Bid, Task, TrustProfile


def normal_cdf(x, mu, sigma):
    return (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0)))) / 2.0

def edge_truth_env_allocation(task: Task, bids: list[Bid], trust_profiles: dict, weights: dict | None = None) -> Allocation:
    if not bids:
        return None
        
    # Task Value (V) and Penalty/Loss for Failure (L)
    # L_declared is what the client tells the auction (capped for SLA compensation)
    V = getattr(task, "task_value", 1000.0)
    L_declared = V  
    
    # Calculate ENV and Effective Probability for all bids
    candidates = []
    default_brier = 0.25 
    default_mae = 50.0
    
    for bid in bids:
        tp = trust_profiles.get(bid.node_id)
        if not tp:
            tp = TrustProfile(node_id=bid.node_id)
            
        b = bid.price
        p_hat = bid.claim.success_probability
        mu_hat = bid.claim.latency_p50_ms
        sigma_hat = max(1.0, bid.claim.latency_std_ms)
        
        brier = tp.evidence.success_brier_score if tp.evidence.observations > 0 else default_brier
        mae = tp.evidence.latency_mae if tp.evidence.observations > 0 else default_mae
        
        effective_sigma = max(sigma_hat, mae)
        p = max(0.01, p_hat * (1.0 - math.sqrt(brier)))
        p_sla_met = normal_cdf(task.deadline_ms, mu_hat, effective_sigma)
        
        p_eff = p * p_sla_met
        env = (p_eff * V) - b - ((1.0 - p_eff) * L_declared)
        
        candidates.append({
            "bid": bid,
            "b": b,
            "p_eff": p_eff,
            "env": env,
            "q_i": p_hat
        })
        
    # PARETO-OPTIMAL RISK-PREMIUM PRUNING
    # Sort by price (cheapest first)
    candidates.sort(key=lambda x: x["b"])
    
    pareto_front = [candidates[0]]
    for cand in candidates[1:]:
        last_cand = pareto_front[-1]
        delta_b = cand["b"] - last_cand["b"]
        delta_p = cand["p_eff"] - last_cand["p_eff"]
        
        if delta_p > 0:
            marginal_efficiency = delta_b / delta_p
            if marginal_efficiency <= (V + L_declared):
                pareto_front.append(cand)
                
    # Select the candidate that maximizes ENV within the Pareto subset
    best_cand = max(pareto_front, key=lambda x: x["env"])
    best_bid = best_cand["bid"]
    
    # STAKED PERFORMANCE BOND (COLLATERAL)
    gamma = 0.05
    collateral_staked = best_cand["q_i"] * (V + L_declared) * gamma
    
    # We store collateral in expected_utility field for extraction by settlement layer
    return Allocation(
        task_id=task.task_id, 
        node_id=best_bid.node_id, 
        winning_bid=best_bid, 
        risk_score=collateral_staked, 
        expected_utility=best_cand["env"]
    )
