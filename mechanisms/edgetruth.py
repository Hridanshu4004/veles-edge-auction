from common.models import Task, Bid, TrustProfile
from typing import List, Optional, Dict

class EdgeTruthAllocation:
    def __init__(self, node_id: str, winning_bid: Bid, score: float):
        self.node_id = node_id
        self.winning_bid = winning_bid
        self.score = score

def edgetruth_allocation(task: Task, bids: List[Bid], observed_successes: Dict[str, float], observed_attempts: Dict[str, float]) -> Optional[EdgeTruthAllocation]:
    """
    Phase 5 Unified Economic Decision Rule
    EU_i = P_i * V_j - (1 - P_i) * (0.5 * V_j) - P_i * Price_i
    Score = P_i * (1.5 * V_j - Price_i) - 0.5 * V_j
    """
    best_bid = None
    best_score = -float('inf')
    
    for b in bids:
        # Bayesian posterior estimate of reliability
        p_i = observed_successes.get(b.node_id, 1.0) / max(1.0, observed_attempts.get(b.node_id, 1.0))
        
        # Self-scaling economic score
        score = p_i * (task.task_value - b.price) - (1.0 - p_i) * (0.5 * task.task_value)
        
        if score > best_score:
            best_score = score
            best_bid = b
            
    if best_bid:
        return EdgeTruthAllocation(best_bid.node_id, best_bid, best_score)
    return None

def edgetruth_payment(allocation: EdgeTruthAllocation, actual_success: bool) -> float:
    """
    Contingent Payment Rule
    """
    if actual_success:
        return allocation.winning_bid.price
    return 0.0
