import math

from common.models import Allocation, Bid, Task, TrustProfile


def normal_cdf(x, mu, sigma):
    return (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0)))) / 2.0

def normal_pdf(x, mu, sigma):
    return (1.0 / (sigma * math.sqrt(2.0 * math.pi))) * math.exp(-0.5 * ((x - mu) / sigma)**2)

def prediction_contract_allocation(task: Task, bids: list[Bid], trust_profiles: dict, weights: dict) -> Allocation:
    if not bids:
        return None
        
    best_score = float('-inf')
    best_bid = None
    
    task_value = getattr(task, "task_value", 1000.0)
    alpha_success = weights.get("alpha_success", 50.0)
    alpha_latency = weights.get("alpha_latency", 10.0)
    
    for bid in bids:
        tp = trust_profiles.get(bid.node_id)
        if not tp:
            tp = TrustProfile(node_id=bid.node_id)
            
        b_i = bid.price # Base reserve price
        p_hat = bid.claim.success_probability
        mu_hat = bid.claim.latency_p50_ms
        sigma_hat = max(1.0, bid.claim.latency_std_ms)
        
        # If the node's past predictions were terrible, we bound their claimed uncertainty using our belief
        effective_sigma = max(sigma_hat, tp.evidence.latency_mae)
        
        p_sla_met = normal_cdf(task.deadline_ms, mu_hat, effective_sigma)
        expected_success_prob = p_hat * p_sla_met
        
        # The Requester expects to pay the base price + expected scoring bonus
        # (For allocation, we simplify the expected bonus to assuming the node hits its mean)
        expected_latency_bonus = alpha_latency * math.log(max(0.0001, normal_pdf(mu_hat, mu_hat, effective_sigma)))
        expected_success_bonus = alpha_success * (1.0 - (1.0 - p_hat)**2)
        expected_payment = b_i + expected_success_bonus + expected_latency_bonus
        
        # Expected Utility to Requester
        expected_utility = (task_value * expected_success_prob) - expected_payment
        
        # Probing / Value of Information (VOI) Bonus
        if weights.get("enable_voi", False):
            voi_bonus = weights.get("voi_factor", 100.0) / (1.0 + tp.evidence.observations)
            expected_utility += voi_bonus
            
        if expected_utility > best_score:
            best_score = expected_utility
            best_bid = bid
            
    return Allocation(task_id=task.task_id, node_id=best_bid.node_id, winning_bid=best_bid, risk_score=best_score, expected_utility=best_score)
