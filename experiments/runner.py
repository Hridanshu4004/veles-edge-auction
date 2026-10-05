import json
import os
import pathlib
from collections import defaultdict

import numpy as np
from scipy import stats

from mechanisms.trust_vcg import trust_vcg_allocation, calculate_slashing_and_scoring
from common.models import Bid, Task, TrustProfile
from common.rng import set_seed
from common.scoring import update_calibration
from mechanisms.baselines import (
    greedy_cheapest,
    random_allocation,
)
from mechanisms.edge_truth import normal_pdf, prediction_contract_allocation
from simulator.data_generator import DataGenerator
from simulator.node_models import NodeBehavior


def compute_ci(data, confidence=0.95):
    a = 1.0 * np.array(data)
    n = len(a)
    if n < 2:
        return 0.0
    se = stats.sem(a)
    h = se * stats.t.ppf((1 + confidence) / 2., n-1)
    return h

class ExperimentRunner:
    def __init__(self, scenario_json: dict, seed: int):
        self.scenario = scenario_json
        self.seed = seed
        self.nodes = {n["node_id"]: n for n in self.scenario["nodes"]}
        self.tasks = [Task(**t) for t in self.scenario["tasks"]]
        self.ground_truth = {(gt["task_id"], gt["node_id"]): gt for gt in self.scenario["ground_truth"]}
        self.market_config = self.scenario.get("market_configuration", {})
        self.weights = self.market_config.get("risk_weights", {})
        
    def run(self, mechanism_name: str) -> dict:
        set_seed(self.seed) # ENFORCE RNG ISOLATION PER MECHANISM
        trust_profiles = {n_id: TrustProfile(node_id=n_id) for n_id in self.nodes}
        
        metrics = {
            "total_tasks": len(self.tasks),
            "allocated_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "sla_violations": 0,
            "total_cost": 0.0,
            "total_latency": 0.0,
            "social_welfare": 0.0,
            "attacker_profit": 0.0,
            "honest_profit": 0.0,
            "attacker_allocations": 0,
            "num_attackers": sum(1 for n in self.nodes.values() if n["node_type"] != "HONEST_STABLE"),
            "num_honest": sum(1 for n in self.nodes.values() if n["node_type"] == "HONEST_STABLE")
        }
        
        # Pre-generate bids for exact identicality (in case bids ever become random)
        task_bids = {}
        for task in self.tasks:
            bids = []
            for n_id, n_data in self.nodes.items():
                price, claim = NodeBehavior.generate_bid(n_data["node_type"], n_data, task.model_dump())
                bids.append(Bid(task_id=task.task_id, node_id=n_id, price=price, claim=claim))
            task_bids[task.task_id] = bids
            
        for task in self.tasks:
            bids = task_bids[task.task_id]
                
            if mechanism_name == "random":
                allocation = random_allocation(task, bids)
            elif mechanism_name == "greedy":
                allocation = greedy_cheapest(task, bids)
            elif mechanism_name == "edgetruth_no_probe":
                self.weights["enable_voi"] = False
                allocation = prediction_contract_allocation(task, bids, trust_profiles, self.weights)
            elif mechanism_name == "edgetruth_random_probe":
                import random
                if random.random() < 0.05 and bids:
                    allocation = random_allocation(task, bids)
                else:
                    self.weights["enable_voi"] = False
                    allocation = prediction_contract_allocation(task, bids, trust_profiles, self.weights)
            elif mechanism_name == "edgetruth_voi_probe":
                self.weights["enable_voi"] = True
                self.weights["voi_factor"] = 200.0 # Will decay as 1/(1+obs)
                allocation = prediction_contract_allocation(task, bids, trust_profiles, self.weights)

            elif mechanism_name == "trust_vcg":
                allocation = trust_vcg_allocation(task, bids, trust_profiles)
            else:
                allocation = None
                
            if not allocation:
                continue
                
            metrics["allocated_tasks"] += 1
            
            gt = self.ground_truth[(task.task_id, allocation.node_id)]
            actual_success = gt["actual_success"]
            actual_latency = gt["actual_latency_ms"]
            node_cost = gt["node_cost"]
            sla_met = gt["sla_met"]
            
            # Payment evaluation
            if mechanism_name.startswith("edgetruth"):
                import math
                alpha_success = self.weights.get("alpha_success", 50.0)
                alpha_latency = self.weights.get("alpha_latency", 10.0)
                
                b_i = allocation.winning_bid.price
                p_hat = allocation.winning_bid.claim.success_probability
                mu_hat = allocation.winning_bid.claim.latency_p50_ms
                sigma_hat = max(1.0, allocation.winning_bid.claim.latency_std_ms)
                
                actual_val = 1.0 if actual_success else 0.0
                brier_score = (p_hat - actual_val)**2
                
                # Brier score bonus: max bonus is alpha_success, penalty up to alpha_success
                success_bonus = alpha_success * (1.0 - 2.0 * brier_score) 
                
                if actual_success:
                    f_actual = normal_pdf(actual_latency, mu_hat, sigma_hat)
                    # logarithmic rule
                    latency_bonus = alpha_latency * math.log(max(0.0001, f_actual))
                else:
                    latency_bonus = -alpha_latency * 2.0 # Penalty for failure to even measure
                    
                actual_payment = b_i + success_bonus + latency_bonus

            elif mechanism_name == "trust_vcg":
                res = calculate_slashing_and_scoring(allocation, allocation.winning_bid, trust_profiles[allocation.node_id], actual_success)
                # VCG payment minus slashing plus proper scoring rule bonus
                brier_score = res["brier_score"]
                slashed_amount = res["slashed_amount"]
                bonus = 50.0 * (1.0 - 2.0 * brier_score) # Proper scoring rule reward
                actual_payment = allocation.winning_bid.price + bonus - slashed_amount
            else:
                actual_payment = allocation.winning_bid.price
                
            metrics["total_cost"] += actual_payment
            
            if actual_success:
                metrics["successful_tasks"] += 1
            else:
                metrics["failed_tasks"] += 1
                
            if not sla_met:
                metrics["sla_violations"] += 1
                
            metrics["total_latency"] += actual_latency
            
            # Update trust
            tp = trust_profiles[allocation.node_id]
            tp = update_calibration(tp, allocation.winning_bid.claim, actual_success, actual_latency)
            trust_profiles[allocation.node_id] = tp
            
            # Profit and welfare
            profit = actual_payment - node_cost
            node_type = self.nodes[allocation.node_id]["node_type"]
            
            if node_type != "HONEST_STABLE":
                metrics["attacker_profit"] += profit
                metrics["attacker_allocations"] += 1
            else:
                metrics["honest_profit"] += profit
                
            if actual_success and sla_met:
                metrics["social_welfare"] += task.task_value - node_cost
            else:
                metrics["social_welfare"] -= node_cost
                
        return metrics

def run_all_experiments(scenarios_dir: str, results_dir: str):
    pathlib.Path(results_dir).mkdir(parents=True, exist_ok=True)
    # ABLATION LADDER
    mechanisms = ["greedy", "edgetruth_no_probe", "trust_vcg"]
    num_seeds = 50
    
    scenario_configs = {
        "CLEAN_MARKET": {"node_type_weights": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]},
        "RESOURCE_LIARS": {"node_type_weights": [0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0]},
        "MIXED_ADVERSARY": {"node_type_weights": [0.4, 0.2, 0.2, 0.2, 0.0, 0.0, 0.0]}
    }
    
    for scenario_name, config in scenario_configs.items():
        agg_results = {mech: defaultdict(list) for mech in mechanisms}
        
        for seed in range(42, 42 + num_seeds):
            gen = DataGenerator(seed=seed)
            scenario_json = gen.generate_scenario(scenario_name, num_nodes=10, num_tasks=500, config=config)
            
            runner = ExperimentRunner(scenario_json, seed=seed)
            for mech in mechanisms:
                res = runner.run(mech)
                for k, v in res.items():
                    agg_results[mech][k].append(v)
                    
        # Compute stats
        final_results = {}
        for mech in mechanisms:
            final_results[mech] = {}
            for k, arr in agg_results[mech].items():
                final_results[mech][f"{k}_mean"] = float(np.mean(arr))
                final_results[mech][f"{k}_ci95"] = float(compute_ci(arr))
                final_results[mech][f"{k}_std"] = float(np.std(arr))
                
        out_path = os.path.join(results_dir, f"results_{scenario_name.lower()}.json")
        with open(out_path, "w") as f:
            json.dump(final_results, f, indent=2)

if __name__ == "__main__":
    run_all_experiments("/home/hridanshu/veles-edge-auction/scenarios", "/home/hridanshu/veles-edge-auction/experiments/results")
    print("Multi-seed statistical experiments completed successfully.")
