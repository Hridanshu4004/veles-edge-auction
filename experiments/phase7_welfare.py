import os
import copy
import random
import numpy as np
import pandas as pd
import concurrent.futures

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common.loaders import Azure2019Loader
from simulator.data_generator import DataGenerator
from common.models import Bid, Task, TrustProfile
from simulator.node_models import NodeBehavior
from mechanisms.baselines import greedy_cheapest
from mechanisms.variants import variant_allocation, variant_payment

NUM_SEEDS = 30
NUM_TASKS = 300
NUM_NODES = 30

def get_azure_tasks():
    loader = Azure2019Loader('/home/hridanshu/veles-edge-auction/data/raw/azure/2019')
    try:
        data = loader.load_and_split(num_funcs=5, allow_test=False)
        df = data['DEV']['tasks']
        tasks = []
        for i, row in df.iterrows():
            if i >= NUM_TASKS: break
            tasks.append({
                "task_id": f"task-{i:04d}",
                "task_type": "compute_heavy",
                "cpu_required": float(row.get('memory_mb', 100)) / 100.0,
                "ram_required": float(row.get('memory_mb', 100)) / 100.0,
                "bandwidth_required": 10.0,
                "max_latency_ms": 100.0,
                "deadline_ms": float(row.get('duration_ms', 100)) * 2.0,
                "priority": 1.0,
                "work_units": float(row.get('duration_ms', 100)),
                "task_value": float(row.get('duration_ms', 100)) * 2.0,
                "arrival_epoch": i
            })
        return tasks
    except Exception as e:
        return None

AZURE_TASKS = get_azure_tasks()

def edgetruth_allocation(task, bids, observed_successes, observed_attempts):
    best_bid = None
    best_score = -float('inf')
    for b in bids:
        p_i = observed_successes[b.node_id] / observed_attempts[b.node_id]
        score = p_i * (task.task_value - b.price) - (1.0 - p_i) * (0.5 * task.task_value)
        if score > best_score:
            best_score = score
            best_bid = b
            
    if best_bid:
        class DummyAlloc:
            def __init__(self, bid):
                self.node_id = bid.node_id
                self.winning_bid = bid
        return DummyAlloc(best_bid)
    return None

def run_welfare_scenario(mechanism, seed, nodes, tasks, ground_truth, truthful_bids):
    rng = random.Random(seed)
    trust_profiles = {n_id: TrustProfile(node_id=n_id) for n_id in nodes}
    observed_attempts = {n_id: 1 for n_id in nodes}
    observed_successes = {n_id: 1.0 for n_id in nodes}

    welfare = 0.0
    omniscient_welfare = 0.0
    
    for task in tasks:
        # Calculate Omniscient Welfare first
        best_omni_welfare = 0.0
        for n_id in nodes:
            if ground_truth[(task.task_id, n_id)]["actual_success"]:
                val = task.task_value - ground_truth[(task.task_id, n_id)]["node_cost"]
                if val > best_omni_welfare:
                    best_omni_welfare = val
        omniscient_welfare += best_omni_welfare
        
        # Calculate Mechanism Welfare
        bids = [truthful_bids[task.task_id][n_id] for n_id in nodes]
        if mechanism in ['observed_rel_contingent', 'edgetruth']:
            bids_copy = copy.deepcopy(bids)
            for b in bids_copy:
                b.claim.success_probability = observed_successes[b.node_id] / observed_attempts[b.node_id]
            bids = bids_copy
            
        if mechanism == 'greedy': allocation = greedy_cheapest(task, bids)
        elif mechanism == 'edgetruth': allocation = edgetruth_allocation(task, bids, observed_successes, observed_attempts)
        else: allocation = variant_allocation(task, bids, trust_profiles, mechanism if mechanism != 'observed_rel_contingent' else 'contingent')
        
        if allocation:
            winner_id = allocation.node_id
            actual_success = ground_truth[(task.task_id, winner_id)]["actual_success"]
            
            observed_attempts[winner_id] += 1
            if actual_success: observed_successes[winner_id] += 1
            
            if actual_success:
                welfare += task.task_value - ground_truth[(task.task_id, winner_id)]["node_cost"]
            else:
                welfare -= 0.5 * task.task_value
                
    return welfare, omniscient_welfare

def run_seed(seed):
    gen = DataGenerator(seed=seed)
    scenario = gen.generate_scenario("CLEAN_MARKET", num_nodes=NUM_NODES, num_tasks=NUM_TASKS, config={"node_type_weights": [1.0] + [0]*6})
    nodes = {n["node_id"]: n for n in scenario["nodes"]}
    tasks = [Task(**t) for t in (AZURE_TASKS if AZURE_TASKS else scenario["tasks"])]
    
    ground_truth = {}
    for t in tasks:
        for n_id, n in nodes.items():
            base_latency = n["true_latency_ms"]
            success = random.Random(seed + hash(t.task_id) + hash(n_id)).random() <= n["true_success_probability"]
            time_taken = t.work_units / max(0.1, n["cpu_capacity"]) + base_latency
            ground_truth[(t.task_id, n_id)] = {
                "actual_success": success,
                "node_cost": n["true_energy_rate"] * time_taken * 2.0,
                "actual_latency_ms": base_latency,
                "true_rel": n["true_success_probability"]
            }

    truthful_bids = {}
    for t in tasks:
        truthful_bids[t.task_id] = {}
        for n_id, n_data in nodes.items():
            price, claim = NodeBehavior.generate_bid("HONEST_STABLE", n_data, t.model_dump())
            truthful_bids[t.task_id][n_id] = Bid(task_id=t.task_id, node_id=n_id, price=price, claim=claim)
            
    res = []
    mechanisms = ['greedy', 'edgetruth']
    
    for mech in mechanisms:
        wel, omni = run_welfare_scenario(mech, seed, nodes, tasks, ground_truth, truthful_bids)
        res.append({
            "seed": seed,
            "mechanism": mech,
            "welfare": wel,
            "omni_welfare": omni,
            "efficiency": wel / omni if omni > 0 else 0
        })
    return res

if __name__ == "__main__":
    all_results = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [executor.submit(run_seed, seed) for seed in range(42, 42 + NUM_SEEDS)]
        for f in concurrent.futures.as_completed(futures):
            all_results.extend(f.result())
            
    df = pd.DataFrame(all_results)
    
    def get_ci(series):
        if len(series) < 2: return 0.0
        return 1.96 * np.std(series, ddof=1) / np.sqrt(len(series))
    
    print("--- PHASE 7: WELFARE VALIDATION ---")
    print(f"{'Mechanism':<15} | {'Welfare':<15} | {'Omni Welfare':<15} | {'Abs Efficiency':<15}")
    for mech in ['greedy', 'edgetruth']:
        mdf = df[df['mechanism'] == mech]
        seed_agg = mdf.groupby('seed').mean(numeric_only=True)
        
        wel = seed_agg['welfare'].mean()
        omni = seed_agg['omni_welfare'].mean()
        eff = seed_agg['efficiency'].mean() * 100
        eff_ci = get_ci(seed_agg['efficiency'] * 100)
        
        print(f"{mech:<15} | {wel:>15.1f} | {omni:>15.1f} | {eff:>9.1f}% ±{eff_ci:<4.1f}%")

