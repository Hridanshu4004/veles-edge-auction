from common.models import Claim


class NodeBehavior:
    @staticmethod
    def generate_bid(node_type: str, true_profile: dict, task: dict) -> tuple[float, Claim]:
        # base prediction matches ground truth mostly
        pred_latency = true_profile["true_latency_ms"] + (task["work_units"] / max(0.1, true_profile["cpu_capacity"]))
        pred_success = true_profile["true_success_probability"]
        latency_std = pred_latency * 0.1
        
        if node_type == "OVERREPORTER":
            pred_latency *= 0.5 
            latency_std *= 0.5
        elif node_type == "LATENCY_LIAR":
            pred_latency = 10.0
            latency_std = 2.0
        elif node_type == "SUCCESS_LIAR":
            pred_success = 0.999
            
        pred_energy = true_profile["true_energy_rate"] * pred_latency
        base_cost = pred_energy * 2.0
        price = base_cost * 1.5
        if node_type == "STRATEGIC_NODE":
            price = base_cost * 3.0
            
        claim = Claim(
            success_probability=min(1.0, max(0.0, pred_success)),
            latency_p50_ms=pred_latency,
            latency_p95_ms=pred_latency + 2 * latency_std,
            latency_std_ms=latency_std,
            energy_estimate=pred_energy,
            confidence=0.9
        )
        return price, claim
