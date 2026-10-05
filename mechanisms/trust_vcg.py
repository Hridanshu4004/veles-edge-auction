import math
from typing import List, Dict, Optional

from common.models import Allocation, Bid, Task, TrustProfile

def normal_cdf(x: float, mu: float, sigma: float) -> float:
    return (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0)))) / 2.0

def calculate_effective_probability(bid: Bid, tp: TrustProfile, deadline_ms: float) -> float:
    default_brier = 0.25 
    default_mae = 50.0

    p_hat = bid.claim.success_probability
    mu_hat = bid.claim.latency_p50_ms
    sigma_hat = max(1.0, bid.claim.latency_std_ms)

    brier = tp.evidence.success_brier_score if tp.evidence.observations > 0 else default_brier
    mae = tp.evidence.latency_mae if tp.evidence.observations > 0 else default_mae

    effective_sigma = max(sigma_hat, mae)
    # Trust weighting: discount claimed success prob by Brier score
    p = max(0.01, p_hat * (1.0 - math.sqrt(brier)))
    p_sla_met = normal_cdf(deadline_ms, mu_hat, effective_sigma)
    
    return p * p_sla_met

def trust_vcg_allocation(task: Task, bids: List[Bid], trust_profiles: Dict[str, TrustProfile]) -> Optional[Allocation]:
    """
    Implements Trust-Weighted VCG with Credits, Bonds, and Slashing.
    """
    if not bids:
        return None

    V = getattr(task, "task_value", 1000.0)
    L_declared = V # Loss for failure
    
    candidates = []
    
    # Pre-calculate Expected Net Value (Social Welfare) for each bid
    for bid in bids:
        tp = trust_profiles.get(bid.node_id)
        if not tp:
            tp = TrustProfile(node_id=bid.node_id)
            
        p_eff = calculate_effective_probability(bid, tp, task.deadline_ms)
        
        # Social Welfare = Expected Value - Expected Cost - Expected Loss
        # We assume bid.price is the node's reported cost.
        welfare = V - bid.price - ((1.0 - p_eff) * V)
        
        candidates.append({
            "bid": bid,
            "p_eff": p_eff,
            "welfare": welfare,
        })
        
    # Sort candidates by social welfare descending
    candidates.sort(key=lambda x: x["welfare"], reverse=True)
    
    if not candidates or candidates[0]["welfare"] < 0:
        return None # No one can profitably serve the task
        
    winner = candidates[0]
    
    # Calculate VCG Payment
    # Payment = Cost_winner + (Welfare of others with winner - Welfare of others without winner)
    # In single-item auction, this simplifies to:
    # Payment = Welfare_runner_up - Welfare_winner_excluding_cost
    
    # If there is no runner up, the payment is bounded by the task value
    if len(candidates) > 1 and candidates[1]["welfare"] > 0:
        runner_up = candidates[1]
        welfare_without_winner = runner_up["welfare"]
    else:
        welfare_without_winner = 0.0
        
    # Winner's welfare excluding its own cost
    winner_welfare_ex_cost = (winner["p_eff"] * V) - ((1.0 - winner["p_eff"]) * L_declared)
    
    # The marginal harm equation:
    # VCG Payment = Welfare_without_winner - (Welfare_with_winner - Cost_winner) + Cost_winner
    # => VCG Payment = Welfare_without_winner - Welfare_with_winner + 2 * Cost_winner ... wait no.
    # The standard formula for VCG payment to winner i:
    # p_i = \sum_{j \neq i} v_j(x_{-i}) - \sum_{j \neq i} v_j(x^*) 
    # For single item: p_i = v_2 - 0 = v_2 (this is the value of the alternative)
    # Since we are procuring, we pay the winner to cover their marginal harm to others.
    # Payment = Cost_runner_up_equivalent = winner_welfare_ex_cost - welfare_without_winner
    
    vcg_payment = winner_welfare_ex_cost - welfare_without_winner
    
    # Ensure individual rationality (payment >= bid price)
    vcg_payment = max(vcg_payment, winner["bid"].price)
    
    # Update the winning bid's price to the VCG payment so the runner pays correctly
    winner_bid = winner["bid"]
    winner_bid.price = vcg_payment

    return Allocation(
        task_id=task.task_id,
        node_id=winner_bid.node_id,
        winning_bid=winner_bid,
        risk_score=1.0 - winner["p_eff"],
        expected_utility=winner["welfare"]
    )

def calculate_slashing_and_scoring(allocation: Allocation, bid: Bid, tp: TrustProfile, success: bool) -> dict:
    """
    Applies the Proper Scoring Rule and SLA Slashing based on outcome.
    """
    p_hat = bid.claim.success_probability
    
    # Brier Score (Strictly Proper Scoring Rule)
    # outcome is 1 if success, 0 if failure
    outcome = 1.0 if success else 0.0
    brier = (p_hat - outcome) ** 2
    
    # Slashing Bond
    # If failed, slash a fixed penalty F. F must be large enough to deter fake claims.
    F = 500.0
    slashed = F if not success else 0.0
    
    # Randomized Audits
    # In practice, this would be computed centrally with probability p.
    
    return {
        "brier_score": brier,
        "slashed_amount": slashed
    }
