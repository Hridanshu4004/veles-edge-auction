import os
import json
import math
import copy
import random
import numpy as np
import pandas as pd
from collections import defaultdict
import datetime
from multiprocessing import Pool

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from simulator.data_generator import DataGenerator
from common.models import Bid, Claim, Task, TrustProfile
from simulator.node_models import NodeBehavior
from mechanisms.baselines import greedy_cheapest
from mechanisms.trust_vcg import trust_vcg_allocation, calculate_slashing_and_scoring
from mechanisms.variants import variant_allocation, variant_payment

# Force temporary access log for tests
os.environ['ACCESS_LOG_PATH'] = '/tmp/regret_access_log.jsonl'

NUM_SEEDS = 20
MECHANISMS = ['greedy', 'trust_vcg', 'contingent', 'capped', 'proper_scoring', 'audits']
NUM_TASKS = 200
NUM_NODES = 10
SAMPLE_SIZE = 3 # number of nodes to test deviation for

def simulate_outcome(mechanism, tasks, nodes, ground_truth, dev_node_id, dev_bid_params, seed):
    utility = 0.0
    rng = random.Random(seed)
    
    trust_profiles = {n_id: TrustProfile(node_id=n_id) for n_id in nodes}
    
    for task in tasks:
        bids = []
        for n_id, n_data in nodes.items():
            base_price, claim = NodeBehavior.generate_bid("HONEST_STABLE", n_data, task.model_dump())
            bid_price = base_price
            
            if n_id == dev_node_id:
                c_mult, cap_mult, rel_diff = dev_bid_params
                
                claimed_capacity = n_data["cpu_capacity"] * cap_mult
                claimed_latency = n_data["true_latency_ms"] + (task.work_units / max(0.1, claimed_capacity))
                
                bid_price = base_price * c_mult
                claim.latency_p50_ms = claimed_latency
                claim.success_probability = min(1.0, max(0.0, claim.success_probability + rel_diff))
                
            bids.append(Bid(task_id=task.task_id, node_id=n_id, price=bid_price, claim=claim))
            
        # Allocation
        if mechanism == 'greedy':
            allocation = greedy_cheapest(task, bids)
        elif mechanism == 'trust_vcg':
            allocation = trust_vcg_allocation(task, bids, trust_profiles)
        else:
            allocation = variant_allocation(task, bids, trust_profiles, mechanism)
            
        if allocation and allocation.node_id == dev_node_id:
            actual_success = ground_truth[(task.task_id, dev_node_id)]["actual_success"]
            
            # Payment
            if mechanism == 'greedy':
                payment = allocation.winning_bid.price
            elif mechanism == 'trust_vcg':
                res = calculate_slashing_and_scoring(allocation, allocation.winning_bid, trust_profiles[dev_node_id], actual_success)
                payment = allocation.winning_bid.price + 50.0 * (1.0 - 2.0 * res["brier_score"]) - res["slashed_amount"]
            else:
                random.seed(rng.random())
                payment = variant_payment(allocation, actual_success, mechanism)
                
            utility += payment - ground_truth[(task.task_id, dev_node_id)]["node_cost"]
            
    return utility

def run_seed(seed):
    gen = DataGenerator(seed=seed)
    config = {"node_type_weights": [0.4, 0.2, 0.2, 0.2, 0.0, 0.0, 0.0]}
    scenario = gen.generate_scenario("MIXED_ADVERSARY", num_nodes=NUM_NODES, num_tasks=NUM_TASKS, config=config)
    
    nodes = {n["node_id"]: n for n in scenario["nodes"]}
    tasks = [Task(**t) for t in scenario["tasks"]]
    ground_truth = {(gt["task_id"], gt["node_id"]): gt for gt in scenario["ground_truth"]}
    
    sampled_nodes = list(nodes.keys())[:SAMPLE_SIZE]
    
    c_mults = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
    cap_mults = [0.5, 1.0, 1.5, 2.0]
    
    seed_results = []
    
    for mech in MECHANISMS:
        for node_id in sampled_nodes:
            true_rel = nodes[node_id]["true_success_probability"]
            rel_diffs = [-0.2, 0.0, min(1.0 - true_rel, 0.2)]
            
            truthful_params = (1.0, 1.0, 0.0)
            truthful_util = simulate_outcome(mech, tasks, nodes, ground_truth, node_id, truthful_params, seed)
            
            max_cost_util = -float('inf')
            max_rel_util = -float('inf')
            max_joint_util = -float('inf')
            
            for c in c_mults:
                for cap in cap_mults:
                    for r in rel_diffs:
                        util = simulate_outcome(mech, tasks, nodes, ground_truth, node_id, (c, cap, r), seed)
                        max_joint_util = max(max_joint_util, util)
                        
                        if cap == 1.0 and r == 0.0:
                            max_cost_util = max(max_cost_util, util)
                        if c == 1.0 and cap == 1.0:
                            max_rel_util = max(max_rel_util, util)
                            
            cost_regret = max_cost_util - truthful_util
            rel_regret = max_rel_util - truthful_util
            joint_regret = max_joint_util - truthful_util
            
            seed_results.append({
                'seed': seed,
                'mechanism': mech,
                'node_id': node_id,
                'cost_regret': cost_regret,
                'rel_regret': rel_regret,
                'joint_regret': joint_regret,
                'truthful_util': truthful_util
            })
            
    return seed_results

def compute_ci(data):
    if len(data) < 2: return 0.0
    return 1.96 * np.std(data) / np.sqrt(len(data))

if __name__ == "__main__":
    import concurrent.futures
    all_results = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [executor.submit(run_seed, seed) for seed in range(42, 42 + NUM_SEEDS)]
        for f in concurrent.futures.as_completed(futures):
            all_results.extend(f.result())
            
    df = pd.DataFrame(all_results)
    
    os.makedirs('experiments/results', exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f'experiments/results/regret_{ts}.csv'
    df.to_csv(out_path, index=False)
    
    print(f"{'Mechanism':<20} | {'Cost Regret':<15} | {'Rel Regret':<15} | {'Joint Regret':<15} | {'Honest Util':<15}")
    print("-" * 88)
    
    for mech in MECHANISMS:
        mech_df = df[df['mechanism'] == mech]
        
        c_mean, c_ci = mech_df['cost_regret'].mean(), compute_ci(mech_df['cost_regret'])
        r_mean, r_ci = mech_df['rel_regret'].mean(), compute_ci(mech_df['rel_regret'])
        j_mean, j_ci = mech_df['joint_regret'].mean(), compute_ci(mech_df['joint_regret'])
        u_mean, u_ci = mech_df['truthful_util'].mean(), compute_ci(mech_df['truthful_util'])
        
        print(f"{mech:<20} | {c_mean:>6.2f} ± {c_ci:>4.2f} | {r_mean:>6.2f} ± {r_ci:>4.2f} | {j_mean:>6.2f} ± {j_ci:>4.2f} | {u_mean:>6.2f} ± {u_ci:>4.2f}")
        
    print("\nFirst 10 rows of raw data:")
    print(df.head(10).to_string())
