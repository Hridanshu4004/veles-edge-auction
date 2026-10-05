from common.models import Bid, Task, TrustProfile
from common.rng import set_seed
from common.scoring import update_calibration
from mechanisms.baselines import greedy_cheapest
from mechanisms.edge_truth import prediction_contract_allocation
from simulator.data_generator import DataGenerator
from simulator.node_models import NodeBehavior


def run_recovery_scenario():
    print("=== PHASE 9: FAILURE RECOVERY EVALUATION ===")
    gen = DataGenerator(seed=999)
    scenario = gen.generate_scenario("RECOVERY", num_nodes=10, num_tasks=500, config={"node_type_weights": [0.4, 0.2, 0.2, 0.2, 0.0, 0.0, 0.0]})
    nodes = {n["node_id"]: n for n in scenario["nodes"]}
    tasks = [Task(**t) for t in scenario["tasks"]]
    gt = {(g["task_id"], g["node_id"]): g for g in scenario["ground_truth"]}
    
    mechanisms = ["greedy", "edgetruth_no_probe"]
    
    for mech in mechanisms:
        set_seed(999)
        trust_profiles = {n_id: TrustProfile(node_id=n_id) for n_id in nodes}
        
        metrics = {"success": 0, "failed_final": 0, "total_cost": 0.0, "retries": 0}
        
        for task in tasks:
            bids = []
            for n_id, n_data in nodes.items():
                price, claim = NodeBehavior.generate_bid(n_data["node_type"], n_data, task.model_dump())
                bids.append(Bid(task_id=task.task_id, node_id=n_id, price=price, claim=claim))
                
            available_bids = bids.copy()
            task_success = False
            attempts = 0
            
            while not task_success and attempts < 3 and available_bids:
                if mech == "greedy":
                    allocation = greedy_cheapest(task, available_bids)
                else:
                    allocation = prediction_contract_allocation(task, available_bids, trust_profiles, {"alpha_success": 50, "alpha_latency": 10})
                
                if not allocation:
                    break
                    
                attempts += 1
                res = gt[(task.task_id, allocation.node_id)]
                actual_success = res["actual_success"]
                actual_latency = res["actual_latency_ms"]
                
                # Payment
                if mech == "edgetruth_no_probe":
                    tp = trust_profiles[allocation.node_id]
                    trust_profiles[allocation.node_id] = update_calibration(tp, allocation.winning_bid.claim, actual_success, actual_latency)
                    # simplified payment
                    cost = allocation.winning_bid.price
                else:
                    cost = allocation.winning_bid.price
                    
                metrics["total_cost"] += cost
                
                if actual_success:
                    task_success = True
                    metrics["success"] += 1
                else:
                    metrics["retries"] += 1
                    # Remove the failed bid
                    available_bids = [b for b in available_bids if b.node_id != allocation.node_id]
            
            if not task_success:
                metrics["failed_final"] += 1
                
        print(f"Mechanism: {mech:20s} | Success: {metrics['success']:4d} | Final Fails: {metrics['failed_final']:4d} | Retries: {metrics['retries']:4d} | Total Cost: ${metrics['total_cost']:.2f}")

if __name__ == "__main__":
    run_recovery_scenario()
