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

def run_sybil_scenario(mechanism, num_sybils, strategy, seed, nodes, tasks, ground_truth, truthful_bids):
    rng = random.Random(seed)
    # Pick a random node to be the attacker
    attacker_id = list(nodes.keys())[rng.randint(0, len(nodes)-1)]
    attacker_group = [attacker_id] + [f"{attacker_id}_sybil_{i}" for i in range(num_sybils)]
    
    # Setup trust profiles and observed stats for all nodes + sybils
    trust_profiles = {n_id: TrustProfile(node_id=n_id) for n_id in nodes}
    observed_attempts = {n_id: 1 for n_id in nodes}
    observed_successes = {n_id: 1.0 for n_id in nodes}
    for s_id in attacker_group[1:]:
        trust_profiles[s_id] = TrustProfile(node_id=s_id)
        observed_attempts[s_id] = 1
        observed_successes[s_id] = 1.0

    attacker_utility = 0.0
    allocated_count = 0
    welfare = 0.0
    buyer_pay = 0.0
    sla_successes = 0
    
    for task in tasks:
        bids = []
        for n_id in nodes:
            if n_id == attacker_id:
                # Add original node
                orig_bid = copy.deepcopy(truthful_bids[task.task_id][n_id])
                if strategy == "Collusion_Threshold":
                    orig_bid.price *= 10.0 # original bids high
                bids.append(orig_bid)
                
                # Add sybils
                for s_id in attacker_group[1:]:
                    s_bid = copy.deepcopy(truthful_bids[task.task_id][n_id])
                    s_bid.node_id = s_id
                    if strategy == "Discount":
                        s_bid.price *= 0.9
                    elif strategy == "WTD":
                        s_bid.price *= 0.9
                        s_bid.claim.success_probability = 1.0
                    elif strategy == "Collusion_Threshold":
                        s_bid.price *= 0.5
                        s_bid.claim.success_probability = 1.0
                    bids.append(s_bid)
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
            
            if winner_id in attacker_group:
                if strategy == "WTD": actual_success = False
                else: actual_success = ground_truth[(task.task_id, attacker_id)]["actual_success"]
            else:
                actual_success = ground_truth[(task.task_id, winner_id)]["actual_success"]
                
            observed_attempts[winner_id] += 1
            if actual_success: observed_successes[winner_id] += 1
            
            # Payment calc
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
                
            buyer_pay += payment
            
            if winner_id in attacker_group:
                allocated_count += 1
                if strategy == "WTD": cost = 0.0 # WTD saves execution cost
                else: cost = ground_truth[(task.task_id, attacker_id)]["node_cost"]
                attacker_utility += payment - cost
                
            if actual_success:
                welfare += task.task_value
                if winner_id in attacker_group and strategy == "WTD": pass # cost=0
                elif winner_id in attacker_group: welfare -= ground_truth[(task.task_id, attacker_id)]["node_cost"]
                else: welfare -= ground_truth[(task.task_id, winner_id)]["node_cost"]
                sla_successes += 1
            else:
                welfare -= 0.5 * task.task_value # fail penalty
                
    return attacker_utility, allocated_count, welfare, buyer_pay, sla_successes / len(tasks)


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
    strategies = ["Discount", "WTD", "Collusion_Threshold"]
    sybil_counts = [0, 1, 2, 5, 10]
    
    for mech in MECHANISMS:
        # Baseline (0 sybils)
        base_util, base_alloc, base_wel, base_bp, base_sla = run_sybil_scenario(mech, 0, "Discount", seed, nodes, tasks, ground_truth, truthful_bids)
        
        for num in sybil_counts[1:]:
            for strat in strategies:
                util, alloc, wel, bp, sla = run_sybil_scenario(mech, num, strat, seed, nodes, tasks, ground_truth, truthful_bids)
                res.append({
                    "seed": seed,
                    "mechanism": mech,
                    "sybils": num,
                    "strategy": strat,
                    "sybil_gain": util - base_util,
                    "alloc_share": alloc / NUM_TASKS,
                    "welfare_diff": wel - base_wel,
                    "bp_diff": bp - base_bp,
                    "sla_diff": sla - base_sla
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
    
    print("--- PHASE 3: STRONGER SYBIL ATTACK ---")
    
    for strat in ["Discount", "WTD", "Collusion_Threshold"]:
        print(f"\n=== STRATEGY: {strat} ===")
        print(f"{'Mechanism':<25} | {'Sybils':<6} | {'Sybil Gain':<12} | {'Alloc Share':<12} | {'SLA Diff':<10}")
        strat_df = df[df['strategy'] == strat]
        for mech in MECHANISMS:
            for num in [1, 2, 5, 10]:
                mdf = strat_df[(strat_df['mechanism'] == mech) & (strat_df['sybils'] == num)]
                seed_agg = mdf.groupby('seed').mean(numeric_only=True)
                
                mean_gain = seed_agg['sybil_gain'].mean()
                ci_gain = get_ci(seed_agg['sybil_gain'])
                
                mean_alloc = seed_agg['alloc_share'].mean() * 100
                mean_sla = seed_agg['sla_diff'].mean() * 100
                
                print(f"{mech:<25} | {num:<6} | {mean_gain:>5.1f}±{ci_gain:<4.1f} | {mean_alloc:>11.1f}% | {mean_sla:>8.1f}%")

