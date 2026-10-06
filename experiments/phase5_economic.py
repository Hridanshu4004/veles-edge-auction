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
        return tasks
    except Exception as e:
        return None

AZURE_TASKS = get_azure_tasks()

def edgetruth_allocation(task, bids, observed_successes, observed_attempts):
    # Phase 5 Unified Economic Decision Rule
    # EU_i = P_i * V_j - (1 - P_i) * (0.5 * V_j) - P_i * Price_i (Assuming contingent payment)
    # Score = P_i * (1.5 * V_j - Price_i) - 0.5 * V_j
    best_bid = None
    best_score = -float('inf')
    for b in bids:
        p_i = observed_successes[b.node_id] / observed_attempts[b.node_id]
        # P_i * V_j (value on success) - P_i * Price (cost on success) - (1-P_i)*0.5*V_j (penalty on fail)
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

def run_economic_scenario(mechanism, task_value_override, seed, nodes, tasks, ground_truth, truthful_bids):
    rng = random.Random(seed)
    trust_profiles = {n_id: TrustProfile(node_id=n_id) for n_id in nodes}
    observed_attempts = {n_id: 1 for n_id in nodes}
    observed_successes = {n_id: 1.0 for n_id in nodes}

    welfare = 0.0
    buyer_pay = 0.0
    sla_successes = 0
    selected_prices = []
    selected_rels = []
    
    for task in tasks:
        # Override task value for regime testing
        t_val = task_value_override
        task.task_value = t_val
        
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
            
            selected_prices.append(allocation.winning_bid.price)
            selected_rels.append(ground_truth[(task.task_id, winner_id)]["true_rel"])
            
            if mechanism == 'greedy': payment = allocation.winning_bid.price
            elif mechanism == 'edgetruth':
                # Contingent payment
                payment = allocation.winning_bid.price if actual_success else 0.0
            elif mechanism == 'proper_scoring':
                claim_rel = allocation.winning_bid.claim.success_probability
                outcome = 1.0 if actual_success else 0.0
                payment = allocation.winning_bid.price + 20.0 - 20.0 * ((outcome - claim_rel)**2)
            else:
                random.seed(rng.random())
                payment = variant_payment(allocation, actual_success, mechanism if mechanism != 'observed_rel_contingent' else 'contingent')
                
            buyer_pay += payment
            
            if actual_success:
                welfare += t_val - ground_truth[(task.task_id, winner_id)]["node_cost"]
                sla_successes += 1
            else:
                welfare -= 0.5 * t_val
                
    return welfare, buyer_pay, sla_successes / len(tasks), np.mean(selected_prices), np.mean(selected_rels)

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
    mechanisms = ['greedy', 'proper_scoring', 'observed_rel_contingent', 'edgetruth']
    task_values = [10, 50, 100, 500, 1000, 5000]
    
    for mech in mechanisms:
        for t_val in task_values:
            wel, bp, sla, p_mean, r_mean = run_economic_scenario(mech, t_val, seed, nodes, tasks, ground_truth, truthful_bids)
            res.append({
                "seed": seed,
                "mechanism": mech,
                "task_value": t_val,
                "welfare": wel,
                "buyer_pay": bp,
                "sla": sla,
                "avg_selected_price": p_mean,
                "avg_selected_rel": r_mean
            })
    return res

if __name__ == "__main__":
    all_results = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [executor.submit(run_seed, seed) for seed in range(42, 42 + NUM_SEEDS)]
        for f in concurrent.futures.as_completed(futures):
            all_results.extend(f.result())
            
    df = pd.DataFrame(all_results)
    
    print("--- PHASE 5: ECONOMIC DECISION & TASK VALUE REGIMES ---")
    
    for t_val in [10, 50, 100, 500, 1000, 5000]:
        print(f"\n=== TASK VALUE = {t_val} ===")
        print(f"{'Mechanism':<25} | {'Welfare':<10} | {'SLA%':<8} | {'Avg Price':<10} | {'Avg Rel':<8}")
        tdf = df[df['task_value'] == t_val]
        for mech in ['greedy', 'proper_scoring', 'observed_rel_contingent', 'edgetruth']:
            mdf = tdf[tdf['mechanism'] == mech]
            seed_agg = mdf.groupby('seed').mean(numeric_only=True)
            
            wel = seed_agg['welfare'].mean()
            sla = seed_agg['sla'].mean() * 100
            price = seed_agg['avg_selected_price'].mean()
            rel = seed_agg['avg_selected_rel'].mean()
            
            print(f"{mech:<25} | {wel:>10.0f} | {sla:>7.1f}% | {price:>10.2f} | {rel:>7.3f}")

