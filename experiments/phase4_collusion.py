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
from mechanisms.trust_vcg import trust_vcg_allocation, calculate_slashing_and_scoring
from mechanisms.variants import variant_allocation, variant_payment

NUM_SEEDS = 30
MECHANISMS = ['greedy', 'trust_ranked_vcg', 'contingent', 'capped', 'proper_scoring', 'audits', 'observed_rel_contingent']
NUM_TASKS = 30
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
        if len(tasks) == 0: raise ValueError("No tasks")
        return tasks
    except Exception as e:
        print("Fallback to synthetic tasks due to loader error:", e)
        return None

AZURE_TASKS = get_azure_tasks()

def run_collusion_scenario(mechanism, num_colluders, strategy, seed, nodes, tasks, ground_truth, truthful_bids):
    rng = random.Random(seed)
    all_node_ids = list(nodes.keys())
    rng.shuffle(all_node_ids)
    collusion_ring = all_node_ids[:num_colluders]
    
    trust_profiles = {n_id: TrustProfile(node_id=n_id) for n_id in nodes}
    observed_attempts = {n_id: 1 for n_id in nodes}
    observed_successes = {n_id: 1.0 for n_id in nodes}

    ring_utility = 0.0
    
    for task in tasks:
        bids = []
        for n_id in nodes:
            if n_id in collusion_ring:
                mod_bid = copy.deepcopy(truthful_bids[task.task_id][n_id])
                if strategy == "High_Low_Pricing":
                    if n_id == collusion_ring[0]:
                        mod_bid.price *= 0.5
                    else:
                        mod_bid.price *= 10.0
                elif strategy == "Winner_Manipulation":
                    if n_id == collusion_ring[0]:
                        mod_bid.price *= 0.1
                        mod_bid.claim.success_probability = 1.0
                    else:
                        mod_bid.price *= 1.5
                elif strategy == "Coordinated_Reliability":
                    mod_bid.claim.success_probability = 1.0
                bids.append(mod_bid)
            else:
                bids.append(truthful_bids[task.task_id][n_id])
                
        if mechanism == 'observed_rel_contingent':
            for b in bids:
                b.claim.success_probability = observed_successes[b.node_id] / observed_attempts[b.node_id]
                
        if mechanism == 'greedy': allocation = greedy_cheapest(task, bids)
        elif mechanism == 'trust_ranked_vcg': allocation = trust_vcg_allocation(task, bids, trust_profiles)
        else: allocation = variant_allocation(task, bids, trust_profiles, mechanism if mechanism != 'observed_rel_contingent' else 'contingent')
        
        if allocation:
            winner_id = allocation.node_id
            
            if strategy == "Winner_Manipulation" and winner_id == collusion_ring[0]:
                actual_success = False # WTD behaviour
            else:
                actual_success = ground_truth[(task.task_id, winner_id)]["actual_success"]
                
            observed_attempts[winner_id] += 1
            if actual_success: observed_successes[winner_id] += 1
            
            if mechanism == 'greedy': payment = allocation.winning_bid.price
            elif mechanism == 'trust_ranked_vcg':
                res = calculate_slashing_and_scoring(allocation, allocation.winning_bid, trust_profiles[winner_id], actual_success)
                payment = allocation.winning_bid.price + 50.0 * (1.0 - 2.0 * res["brier_score"]) - res["slashed_amount"]
            elif mechanism == 'proper_scoring':
                claim_rel = allocation.winning_bid.claim.success_probability
                outcome = 1.0 if actual_success else 0.0
                payment = allocation.winning_bid.price + 20.0 - 20.0 * ((outcome - claim_rel)**2)
            elif mechanism == 'audits':
                claim_rel = allocation.winning_bid.claim.success_probability
                payment = allocation.winning_bid.price
                if rng.random() < 0.1:
                    if not actual_success: payment -= 50.0
                    else: payment += claim_rel * 5.0
            else:
                random.seed(rng.random())
                payment = variant_payment(allocation, actual_success, mechanism if mechanism != 'observed_rel_contingent' else 'contingent')
                
            if winner_id in collusion_ring:
                if strategy == "Winner_Manipulation" and winner_id == collusion_ring[0]:
                    cost = 0.0 # WTD saves execution cost
                else:
                    cost = ground_truth[(task.task_id, winner_id)]["node_cost"]
                ring_utility += payment - cost
                
    return ring_utility


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
                "actual_latency_ms": base_latency
            }

    truthful_bids = {}
    for t in tasks:
        truthful_bids[t.task_id] = {}
        for n_id, n_data in nodes.items():
            price, claim = NodeBehavior.generate_bid("HONEST_STABLE", n_data, t.model_dump())
            truthful_bids[t.task_id][n_id] = Bid(task_id=t.task_id, node_id=n_id, price=price, claim=claim)
            
    res = []
    strategies = ["High_Low_Pricing", "Winner_Manipulation", "Coordinated_Reliability"]
    ring_sizes = [2, 3, 5]
    
    for mech in MECHANISMS:
        for num in ring_sizes:
            base_util = run_collusion_scenario(mech, num, "Truthful", seed, nodes, tasks, ground_truth, truthful_bids)
            for strat in strategies:
                col_util = run_collusion_scenario(mech, num, strat, seed, nodes, tasks, ground_truth, truthful_bids)
                res.append({
                    "seed": seed,
                    "mechanism": mech,
                    "ring_size": num,
                    "strategy": strat,
                    "collusion_gain": col_util - base_util
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
    
    print("--- PHASE 4: STRONGER COLLUSION ANALYSIS ---")
    
    for strat in ["High_Low_Pricing", "Winner_Manipulation", "Coordinated_Reliability"]:
        print(f"\n=== STRATEGY: {strat} ===")
        print(f"{'Mechanism':<25} | {'Ring Size':<10} | {'Collusion Gain':<15}")
        strat_df = df[df['strategy'] == strat]
        for mech in MECHANISMS:
            for num in [2, 3, 5]:
                mdf = strat_df[(strat_df['mechanism'] == mech) & (strat_df['ring_size'] == num)]
                seed_agg = mdf.groupby('seed').mean(numeric_only=True)
                mean_gain = seed_agg['collusion_gain'].mean()
                ci_gain = get_ci(seed_agg['collusion_gain'])
                print(f"{mech:<25} | {num:<10} | {mean_gain:>8.1f}±{ci_gain:<5.1f}")
