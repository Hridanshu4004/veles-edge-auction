import os
import copy
import random
import numpy as np
import pandas as pd
import datetime
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
NUM_TASKS = 20
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

def simulate_search(mechanism, dev_node_id, dev_bid_params, seed, nodes, tasks, ground_truth, truthful_bids):
    utility = 0.0
    allocated_count = 0
    rng = random.Random(seed)
    
    trust_profiles = {n_id: TrustProfile(node_id=n_id) for n_id in nodes}
    observed_attempts = {n_id: 1 for n_id in nodes}
    observed_successes = {n_id: 1.0 for n_id in nodes}
    
    c_mult, cap_mult, lat_mult, rel_diff = dev_bid_params
    
    for task in tasks:
        bids = []
        for n_id in nodes:
            if n_id == dev_node_id:
                mod_bid = copy.deepcopy(truthful_bids[task.task_id][n_id])
                n_data = nodes[n_id]
                claimed_cap = n_data["cpu_capacity"] * cap_mult
                claimed_lat = (n_data["true_latency_ms"] * lat_mult) + (task.work_units / max(0.1, claimed_cap))
                mod_bid.price *= c_mult
                mod_bid.claim.latency_p50_ms = claimed_lat
                mod_bid.claim.success_probability = min(1.0, max(0.0, mod_bid.claim.success_probability + rel_diff))
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
            actual_success = ground_truth[(task.task_id, winner_id)]["actual_success"]
            
            observed_attempts[winner_id] += 1
            if actual_success: observed_successes[winner_id] += 1
            
            if winner_id == dev_node_id:
                allocated_count += 1
                if mechanism == 'greedy':
                    payment = allocation.winning_bid.price
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
                    if rng.random() < 0.1: # p=0.1
                        if not actual_success:
                            payment -= 50.0 # F=50
                        else:
                            payment += claim_rel * 5.0 # p*F
                else:
                    random.seed(rng.random())
                    payment = variant_payment(allocation, actual_success, mechanism if mechanism != 'observed_rel_contingent' else 'contingent')
                    
                cost = ground_truth[(task.task_id, winner_id)]["node_cost"]
                utility += payment - cost
                
    return utility, allocated_count

def run_seed_search(seed):
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
    
    seed_results = []
    
    # 4 x 3 x 3 x 3 = 108 combinations
    c_mults = [0.5, 1.0, 1.5, 2.0]
    cap_mults = [0.5, 1.0, 2.0]
    lat_mults = [0.5, 1.0, 2.0]
    rel_diffs = [-0.2, 0.0, 0.2]
    
    for mech in MECHANISMS:
        for node_id in nodes:
            truthful_params = (1.0, 1.0, 1.0, 0.0)
            truthful_util, truthful_allocs = simulate_search(mech, node_id, truthful_params, seed, nodes, tasks, ground_truth, truthful_bids)
            
            max_util = -float('inf')
            max_allocs = 0
            
            for c in c_mults:
                for cap in cap_mults:
                    for lat in lat_mults:
                        for r in rel_diffs:
                            util, allocs = simulate_search(mech, node_id, (c, cap, lat, r), seed, nodes, tasks, ground_truth, truthful_bids)
                            if util > max_util:
                                max_util = util
                                max_allocs = allocs
                            
            regret = max_util - truthful_util
            seed_results.append({
                'seed': seed,
                'mechanism': mech,
                'node_id': node_id,
                'truthful_util': truthful_util,
                'max_dev_util': max_util,
                'regret': regret,
                'positive_regret': 1 if regret > 0.01 else 0,
                'attacker_alloc_share': max_allocs / max(1, len(tasks))
            })
            
    return seed_results

def get_ci(series):
    n = len(series)
    if n < 2: return 0.0
    return 1.96 * np.std(series, ddof=1) / np.sqrt(n)

if __name__ == "__main__":
    all_results = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [executor.submit(run_seed_search, seed) for seed in range(42, 42 + NUM_SEEDS)]
        for f in concurrent.futures.as_completed(futures):
            all_results.extend(f.result())
            
    df = pd.DataFrame(all_results)
    print("--- PHASE 2: SYSTEMATIC MULTIDIMENSIONAL DEVIATION SEARCH ---")
    print(f"Search grid: Price [0.5, 1, 1.5, 2], Capacity [0.5, 1, 2], Latency [0.5, 1, 2], Reliability [-0.2, 0, +0.2]")
    print(f"{'Mechanism':<25} | {'Mean':<10} | {'Median':<10} | {'Max Regret':<12} | {'Pos-Regret Freq':<15} | {'Attacker Share':<15}")
    for mech in MECHANISMS:
        mdf = df[df['mechanism'] == mech]
        
        # We group by seed first for proper CIs over seeds
        seed_agg = mdf.groupby('seed').agg({
            'regret': ['mean', 'median', 'max'],
            'positive_regret': 'mean',
            'attacker_alloc_share': 'mean'
        })
        seed_agg.columns = ['mean_regret', 'median_regret', 'max_regret', 'pos_freq', 'alloc_share']
        
        mean_regret = seed_agg['mean_regret'].mean()
        ci_regret = get_ci(seed_agg['mean_regret'])
        
        median_regret = seed_agg['median_regret'].mean()
        max_regret = seed_agg['max_regret'].max()
        
        pos_freq = seed_agg['pos_freq'].mean() * 100
        alloc_share = seed_agg['alloc_share'].mean() * 100
        
        print(f"{mech:<25} | {mean_regret:>5.1f}±{ci_regret:<4.1f} | {median_regret:>10.1f} | {max_regret:>12.1f} | {pos_freq:>14.1f}% | {alloc_share:>14.1f}%")

