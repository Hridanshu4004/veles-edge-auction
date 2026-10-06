import os
import json
import math
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
from common.models import Bid, Claim, Task, TrustProfile
from simulator.node_models import NodeBehavior
from mechanisms.baselines import greedy_cheapest
from mechanisms.trust_vcg import trust_vcg_allocation, calculate_slashing_and_scoring
from mechanisms.variants import variant_allocation, variant_payment


NUM_SEEDS = 30
MECHANISMS = ['greedy', 'trust_vcg', 'contingent', 'capped', 'proper_scoring', 'audits']
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

def run_seed(seed):
    gen = DataGenerator(seed=seed)
    config = {"node_type_weights": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}
    scenario = gen.generate_scenario("CLEAN_MARKET", num_nodes=NUM_NODES, num_tasks=NUM_TASKS, config=config)
    nodes = {n["node_id"]: n for n in scenario["nodes"]}
    tasks = [Task(**t) for t in (AZURE_TASKS if AZURE_TASKS else scenario["tasks"])]
    
    ground_truth = {}
    for t in tasks:
        for n_id, n in nodes.items():
            base_latency = n["true_latency_ms"]
            success = random.Random(seed + hash(t.task_id) + hash(n_id)).random() <= n["true_success_probability"]
            time_taken = t.work_units / max(0.1, n["cpu_capacity"]) + base_latency
            actual_energy = n["true_energy_rate"] * time_taken
            node_cost = actual_energy * 2.0
            ground_truth[(t.task_id, n_id)] = {
                "actual_success": success,
                "node_cost": node_cost,
                "actual_latency_ms": base_latency
            }

    truthful_bids = {}
    for t in tasks:
        truthful_bids[t.task_id] = {}
        for n_id, n_data in nodes.items():
            price, claim = NodeBehavior.generate_bid("HONEST_STABLE", n_data, t.model_dump())
            truthful_bids[t.task_id][n_id] = Bid(task_id=t.task_id, node_id=n_id, price=price, claim=claim)
    
    def simulate_fast(mechanism, dev_node_id, dev_bid_params, attack=None):
        utility = 0.0
        total_payment = 0.0
        global_welfare = 0.0
        buyer_payment = 0.0
        sla_successes = 0
        total_allocated = 0
        rng = random.Random(seed)
        
        sybil_id = f"{dev_node_id}_sybil" if attack == "sybil" else None
        colluder_id = "node-000" if (attack == "collusion" and dev_node_id != "node-000") else "node-001"
        
        trust_profiles = {n_id: TrustProfile(node_id=n_id) for n_id in nodes}
        if attack == "sybil":
            trust_profiles[sybil_id] = TrustProfile(node_id=sybil_id)
        
        for task in tasks:
            bids = []
            for n_id in nodes:
                if n_id == dev_node_id:
                    if attack == "sybil":
                        bids.append(truthful_bids[task.task_id][n_id])
                        sybil_bid = copy.deepcopy(truthful_bids[task.task_id][n_id])
                        sybil_bid.node_id = sybil_id
                        sybil_bid.price *= 0.9
                        bids.append(sybil_bid)
                    elif attack == "collusion":
                        mod_bid = copy.deepcopy(truthful_bids[task.task_id][n_id])
                        mod_bid.price *= 5.0
                        bids.append(mod_bid)
                    else:
                        c_mult, cap_mult, rel_diff = dev_bid_params
                        mod_bid = copy.deepcopy(truthful_bids[task.task_id][n_id])
                        n_data = nodes[n_id]
                        claimed_cap = n_data["cpu_capacity"] * cap_mult
                        claimed_lat = n_data["true_latency_ms"] + (task.work_units / max(0.1, claimed_cap))
                        mod_bid.price *= c_mult
                        mod_bid.claim.latency_p50_ms = claimed_lat
                        mod_bid.claim.success_probability = min(1.0, max(0.0, mod_bid.claim.success_probability + rel_diff))
                        bids.append(mod_bid)
                elif n_id == colluder_id and attack == "collusion":
                    mod_bid = copy.deepcopy(truthful_bids[task.task_id][n_id])
                    mod_bid.price *= 0.5
                    bids.append(mod_bid)
                else:
                    bids.append(truthful_bids[task.task_id][n_id])
                    
            if mechanism == 'greedy': allocation = greedy_cheapest(task, bids)
            elif mechanism == 'trust_vcg': allocation = trust_vcg_allocation(task, bids, trust_profiles)
            else: allocation = variant_allocation(task, bids, trust_profiles, mechanism)
            
            if allocation:
                total_allocated += 1
                winner_id = allocation.node_id
                gt_id = dev_node_id if winner_id == sybil_id else winner_id
                actual_success = ground_truth[(task.task_id, gt_id)]["actual_success"]
                if attack == "win-then-drop" and gt_id == dev_node_id: actual_success = False
                
                if mechanism == 'greedy':
                    payment = allocation.winning_bid.price
                elif mechanism == 'trust_vcg':
                    res = calculate_slashing_and_scoring(allocation, allocation.winning_bid, trust_profiles[winner_id], actual_success)
                    payment = allocation.winning_bid.price + 50.0 * (1.0 - 2.0 * res["brier_score"]) - res["slashed_amount"]
                else:
                    random.seed(rng.random())
                    payment = variant_payment(allocation, actual_success, mechanism)
                    
                buyer_payment += payment
                cost = ground_truth[(task.task_id, gt_id)]["node_cost"]
                if actual_success:
                    sla_successes += 1
                    global_welfare += getattr(task, "task_value", 1000.0) - cost
                else:
                    global_welfare -= cost
                    
                if winner_id in [dev_node_id, sybil_id] or (attack == "collusion" and winner_id == colluder_id):
                    utility += payment - cost
                    total_payment += payment
                    
        if attack: return utility
        return utility, total_payment, global_welfare, buyer_payment, sla_successes, total_allocated

    seed_results = []
    c_mults = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
    cap_mults = [0.5, 1.0, 1.5, 2.0]
    
    for mech in MECHANISMS:
        for node_id in nodes:
            true_rel = nodes[node_id]["true_success_probability"]
            rel_diffs = [-0.2, 0.0, min(1.0 - true_rel, 0.2)]
            
            truthful_params = (1.0, 1.0, 0.0)
            truthful_util, truthful_pay, gw, bp, sla_succ, allocs = simulate_fast(mech, node_id, truthful_params)
            
            max_cost_util = -float('inf')
            max_rel_util = -float('inf')
            max_joint_util = -float('inf')
            
            for c in c_mults:
                for cap in cap_mults:
                    for r in rel_diffs:
                        util, _, _, _, _, _ = simulate_fast(mech, node_id, (c, cap, r))
                        max_joint_util = max(max_joint_util, util)
                        if cap == 1.0 and r == 0.0: max_cost_util = max(max_cost_util, util)
                        if c == 1.0 and cap == 1.0: max_rel_util = max(max_rel_util, util)
                            
            wtd_util = simulate_fast(mech, node_id, (0.5, 2.0, 0.2), attack="win-then-drop")
            sybil_util = simulate_fast(mech, node_id, truthful_params, attack="sybil")
            coll_util = simulate_fast(mech, node_id, truthful_params, attack="collusion")
            
            denom = max(0.001, truthful_pay)
            seed_results.append({
                'seed': seed,
                'mechanism': mech,
                'node_id': node_id,
                'cost_regret': max_cost_util - truthful_util,
                'rel_regret': max_rel_util - truthful_util,
                'joint_regret': max_joint_util - truthful_util,
                'cost_regret_norm': (max_cost_util - truthful_util) / denom,
                'rel_regret_norm': (max_rel_util - truthful_util) / denom,
                'joint_regret_norm': (max_joint_util - truthful_util) / denom,
                'truthful_util': truthful_util,
                'truthful_pay': truthful_pay,
                'global_welfare': gw,
                'buyer_payment': bp,
                'sla_success_rate': sla_succ / max(1, allocs),
                'wtd_gain': wtd_util - truthful_util,
                'sybil_gain': sybil_util - truthful_util,
                'collusion_gain': coll_util - truthful_util
            })
    return seed_results

if __name__ == "__main__":
    print("PROVENANCE: Regret experiment uses Azure2019Loader for task arrivals and synthetic generation for nodes/ground-truth.")
    all_results = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [executor.submit(run_seed, seed) for seed in range(42, 42 + NUM_SEEDS)]
        for f in concurrent.futures.as_completed(futures):
            all_results.extend(f.result())
            
    df = pd.DataFrame(all_results)
    os.makedirs('experiments/results', exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f'experiments/results/regret_full_{ts}.csv'
    df.to_csv(out_path, index=False)
    
    print(f"\nSample size: {NUM_SEEDS} seeds, {NUM_NODES} nodes per seed (Total {NUM_SEEDS*NUM_NODES} node-samples per mechanism).")
    print("\n" + "-" * 160)
    print(f"{'Mechanism':<15} | {'Norm J-Reg':<10} | {'IR Viol%':<8} | {'Pos-IR Reg':<10} | {'Part. Loss':<10} | {'Welfare':<10} | {'Buyer Pay':<10} | {'SLA%':<6} | {'WTD Gain':<8} | {'Sybil Gn':<8} | {'Coll Gn':<8}")
    print("-" * 160)
    for mech in MECHANISMS:
        mdf = df[df['mechanism'] == mech]
        j_norm_mean = mdf['joint_regret_norm'].mean()
        ir_violation_frac = (mdf['truthful_util'] < -0.01).mean() * 100
        pos_ir_df = mdf[mdf['truthful_util'] >= 0]
        pos_ir_regret = pos_ir_df['joint_regret'].mean() if len(pos_ir_df) > 0 else 0.0
        part_loss = mdf.apply(lambda x: -min(0, x['truthful_util']), axis=1).mean()
        sys_df = mdf.groupby('seed').first()
        gw_mean, bp_mean, sla_mean = sys_df['global_welfare'].mean(), sys_df['buyer_payment'].mean(), sys_df['sla_success_rate'].mean() * 100
        wtd_mean, syb_mean, col_mean = mdf['wtd_gain'].mean(), mdf['sybil_gain'].mean(), mdf['collusion_gain'].mean()
        print(f"{mech:<15} | {j_norm_mean:>10.2f} | {ir_violation_frac:>7.1f}% | {pos_ir_regret:>10.2f} | {part_loss:>10.2f} | {gw_mean:>10.0f} | {bp_mean:>10.0f} | {sla_mean:>5.1f}% | {wtd_mean:>8.2f} | {syb_mean:>8.2f} | {col_mean:>8.2f}")
    
    print("\n--- Trust-VCG Honest Node Analysis ---")
    print("Why do honest nodes get negative average utility under trust_vcg?")
    print("trust_vcg applies Brier score penalties and slashing if an honest node randomly fails, which can exceed the VCG payment. This breaks Individual Rationality (IR). Therefore, it is NOT standard VCG. It is a penalized variant that violates IR for honest nodes with <100% reliability.")
    print("Sample of 5 honest nodes under trust_vcg (Seed 42):")
    gen = DataGenerator(seed=42)
    nodes = {n["node_id"]: n for n in gen.generate_nodes(30, {"node_type_weights": [1.0] + [0]*6})}
    tasks = [Task(**t) for t in AZURE_TASKS[:10]]
    for i, n_id in enumerate(list(nodes.keys())[:5]):
        n = nodes[n_id]
        pay, slash, cost = 0.0, 0.0, 0.0
        trust_profiles = {k: TrustProfile(node_id=k) for k in nodes}
        for task in tasks:
            bids = []
            for k in nodes:
                price, claim = NodeBehavior.generate_bid("HONEST_STABLE", nodes[k], task.model_dump())
                bids.append(Bid(task_id=task.task_id, node_id=k, price=price, claim=claim))
            alloc = trust_vcg_allocation(task, bids, trust_profiles)
            if alloc and alloc.node_id == n_id:
                succ = random.random() <= n["true_success_probability"]
                res = calculate_slashing_and_scoring(alloc, alloc.winning_bid, trust_profiles[n_id], succ)
                pay += alloc.winning_bid.price + 50.0 * (1.0 - 2.0 * res["brier_score"]) - res["slashed_amount"]
                slash += res["slashed_amount"]
                cost += 5.0
        print(f"Node {n_id}: Total Pay: {pay:.2f}, Total Slashed: {slash:.2f}, Total Cost: {cost:.2f}, Net Util: {pay - cost:.2f}")
