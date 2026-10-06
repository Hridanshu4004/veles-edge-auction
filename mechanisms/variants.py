# HISTORICAL / ANALYSIS ONLY / NON-FINAL

import math
import random

from common.models import Allocation, TrustProfile


def normal_cdf(x, mu, sigma):
    return (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0)))) / 2.0

def eval_bid_p_eff(bid, tp, deadline_ms):
    brier = tp.evidence.success_brier_score if tp.evidence.observations > 0 else 0.25
    mae = tp.evidence.latency_mae if tp.evidence.observations > 0 else 50.0
    
    p_hat = bid.claim.success_probability
    p = max(0.01, p_hat * (1.0 - math.sqrt(brier)))
    
    effective_sigma = max(max(1.0, bid.claim.latency_std_ms), mae)
    p_sla = normal_cdf(deadline_ms, bid.claim.latency_p50_ms, effective_sigma)
    return p * p_sla

def variant_allocation(task, bids, trust_profiles, variant_name):
    if not bids: return None
    V = getattr(task, "task_value", 1000.0)
    
    candidates = []
    for bid in bids:
        tp = trust_profiles.get(bid.node_id, TrustProfile(node_id=bid.node_id))
        p_eff = eval_bid_p_eff(bid, tp, task.deadline_ms)
        
        # All variants will sort by Expected Net Value (like edgetruth_no_probe)
        welfare = (p_eff * V) - bid.price
        candidates.append({"bid": bid, "welfare": welfare, "p_eff": p_eff})
        
    candidates.sort(key=lambda x: x["welfare"], reverse=True)
    if not candidates or candidates[0]["welfare"] < 0:
        return None
        
    winner = candidates[0]
    return Allocation(
        task_id=task.task_id, 
        node_id=winner["bid"].node_id, 
        winning_bid=winner["bid"], 
        risk_score=1.0 - winner["p_eff"], 
        expected_utility=winner["welfare"]
    )

def variant_payment(allocation, actual_success, variant_name):
    base_price = allocation.winning_bid.price
    V = 1000.0 # Default task value
    
    if variant_name == "contingent":
        return base_price if actual_success else 0.0
        
    elif variant_name == "capped":
        return min(base_price, V)
        
    elif variant_name == "proper_scoring":
        p_hat = allocation.winning_bid.claim.success_probability
        outcome = 1.0 if actual_success else 0.0
        brier = (p_hat - outcome)**2
        # Max bonus 50, max penalty -50
        bonus = 50.0 * (1.0 - 2.0 * brier)
        return max(0.0, base_price + bonus)
        
    elif variant_name == "audits":
        p_hat = allocation.winning_bid.claim.success_probability
        outcome = 1.0 if actual_success else 0.0
        brier = (p_hat - outcome)**2
        bonus = 50.0 * (1.0 - 2.0 * brier)
        
        # Audit logic: p=0.1, F=500
        slashed = 0.0
        if not actual_success and random.random() < 0.1:
            slashed = 500.0
            
        return base_price + bonus - slashed
        
    return base_price
