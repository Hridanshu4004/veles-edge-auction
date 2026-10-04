import random
from common.models import Task, Bid, Allocation

def random_allocation(task: Task, bids: list[Bid]) -> Allocation:
    if not bids:
        return None
    winner = random.choice(bids)
    return Allocation(task_id=task.task_id, node_id=winner.node_id, winning_bid=winner, risk_score=0.0)

def greedy_cheapest(task: Task, bids: list[Bid]) -> Allocation:
    if not bids:
        return None
    winner = min(bids, key=lambda b: b.price)
    return Allocation(task_id=task.task_id, node_id=winner.node_id, winning_bid=winner, risk_score=0.0)

def price_and_reputation(task: Task, bids: list[Bid], trust_profiles: dict) -> Allocation:
    if not bids:
        return None
    def score(bid: Bid):
        tp = trust_profiles.get(bid.node_id)
        rep = tp.success_calibration if tp else 1.0
        return bid.price / max(0.01, rep)
    
    winner = min(bids, key=score)
    return Allocation(task_id=task.task_id, node_id=winner.node_id, winning_bid=winner, risk_score=score(winner))
    
def expected_utility_naive(task: Task, bids: list[Bid]) -> Allocation:
    import math
    if not bids:
        return None
        
    def normal_cdf(x, mu, sigma):
        return (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0)))) / 2.0
        
    best_score = float('-inf')
    best_bid = None
    task_value = getattr(task, "task_value", 1000.0)
    
    for bid in bids:
        p_failure = 1.0 - bid.claim.success_probability
        
        effective_sigma = max(1.0, bid.claim.latency_std_ms)
        mu = bid.claim.latency_p50_ms
        p_sla_miss = 1.0 - normal_cdf(task.deadline_ms, mu, effective_sigma)
        
        expected_utility = task_value - bid.price - (p_failure * task_value) - (p_sla_miss * (task_value * 0.5))
        
        if expected_utility > best_score:
            best_score = expected_utility
            best_bid = bid
            
    return Allocation(task_id=task.task_id, node_id=best_bid.node_id, winning_bid=best_bid, risk_score=best_score, expected_utility=best_score)

