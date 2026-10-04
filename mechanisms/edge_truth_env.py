from common.models import Task, Bid, Allocation, TrustProfile
import math

def normal_cdf(x, mu, sigma):
    return (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0)))) / 2.0

def edge_truth_env_allocation(task: Task, bids: list[Bid], trust_profiles: dict, weights: dict = None) -> Allocation:
    if not bids:
        return None
        
    best_env = float('-inf')
    best_bid = None
    
    # Values
    V = getattr(task, "task_value", 1000.0)
    L = V # Assume failure loss is equal to the task value, unless specified
    
    for bid in bids:
        tp = trust_profiles.get(bid.node_id)
        if not tp:
            tp = TrustProfile(node_id=bid.node_id)
            
        b = bid.price
        p_hat = bid.claim.success_probability
        mu_hat = bid.claim.latency_p50_ms
        sigma_hat = max(1.0, bid.claim.latency_std_ms)
        
        # Use Bayesian belief / history to bound uncertainty
        # If node has bad history, trust profile error increases effective sigma and reduces expected success
        effective_sigma = max(sigma_hat, tp.evidence.latency_mae)
        
        # We need an estimate of true success probability p
        # For simplicity, penalize p_hat if Brier score is bad
        # True success probability estimate:
        brier = tp.evidence.success_brier_score
        # A crude mapping: if brier is high, p drops.
        p = max(0.01, p_hat * (1.0 - math.sqrt(brier)))
        
        p_sla_met = normal_cdf(task.deadline_ms, mu_hat, effective_sigma)
        
        # Total effective probability of success meeting SLA
        p_eff = p * p_sla_met
        
        # Expected Net Value (ENV)
        env = (p_eff * V) - b - ((1.0 - p_eff) * L)
        
        if env > best_env:
            best_env = env
            best_bid = bid
            
    return Allocation(task_id=task.task_id, node_id=best_bid.node_id, winning_bid=best_bid, risk_score=best_env, expected_utility=best_env)
