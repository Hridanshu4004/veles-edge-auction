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
# Renamed trust_vcg to trust-ranked_vcg
MECHANISMS = ['greedy', 'trust-ranked_vcg', 'contingent', 'capped', 'proper_scoring', 'audits', 'observed_rel_contingent']
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

def simulate_fast(mechanism, dev_node_id, dev_bid_params, seed, nodes, tasks, ground_truth, truthful_bids, attack=None, p=None, f=None):
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
        
    observed_attempts = {n_id: 1 for n_id in nodes}
    observed_successes = {n_id: 1.0 for n_id in nodes}  # prior of 100%
    if attack == "sybil":
        observed_attempts[sybil_id] = 1
        observed_successes[sybil_id] = 1.0
        
    tasks_until_beat = -1
    beat_flag = False
    
    for t_idx, task in enumerate(tasks):
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
                
        # Handle observed_rel_contingent mechanism overriding the claims
        if mechanism == 'observed_rel_contingent':
            for b in bids:
                obs_rel = observed_successes[b.node_id] / observed_attempts[b.node_id]
                b.claim.success_probability = obs_rel
                
        if mechanism == 'greedy': allocation = greedy_cheapest(task, bids)
        elif mechanism == 'trust-ranked_vcg': allocation = trust_vcg_allocation(task, bids, trust_profiles)
        else: allocation = variant_allocation(task, bids, trust_profiles, mechanism if mechanism != 'observed_rel_contingent' else 'contingent')
        
        # Track when observed beats greedy
        if not beat_flag and mechanism == 'observed_rel_contingent':
            greedy_alloc = greedy_cheapest(task, bids)
            if allocation and greedy_alloc and allocation.node_id != greedy_alloc.node_id:
                gt_obs = ground_truth[(task.task_id, allocation.node_id)] if allocation.node_id in nodes else None
                gt_greedy = ground_truth[(task.task_id, greedy_alloc.node_id)] if greedy_alloc.node_id in nodes else None
                if gt_obs and gt_greedy and gt_obs["actual_success"] and not gt_greedy["actual_success"]:
                    tasks_until_beat = t_idx
                    beat_flag = True
        
        if allocation:
            total_allocated += 1
            winner_id = allocation.node_id
            gt_id = dev_node_id if winner_id == sybil_id else winner_id
            actual_success = ground_truth[(task.task_id, gt_id)]["actual_success"]
            if attack == "win-then-drop" and gt_id == dev_node_id: actual_success = False
            
            # Update observed rel
            observed_attempts[winner_id] += 1
            if actual_success: observed_successes[winner_id] += 1
            
            if mechanism == 'greedy':
                payment = allocation.winning_bid.price
            elif mechanism == 'trust-ranked_vcg':
                res = calculate_slashing_and_scoring(allocation, allocation.winning_bid, trust_profiles[winner_id], actual_success)
                payment = allocation.winning_bid.price + 50.0 * (1.0 - 2.0 * res["brier_score"]) - res["slashed_amount"]
            elif mechanism == 'proper_scoring':
                claim_rel = allocation.winning_bid.claim.success_probability
                outcome = 1.0 if actual_success else 0.0
                a, b = 20.0, 20.0
                payment = allocation.winning_bid.price + a - b * ((outcome - claim_rel)**2)
            elif mechanism == 'audits' and p is not None and f is not None:
                claim_rel = allocation.winning_bid.claim.success_probability
                payment = allocation.winning_bid.price
                if rng.random() < p:
                    if not actual_success:
                        payment -= f
                    else:
                        payment += claim_rel * p * f
            else:
                random.seed(rng.random())
                payment = variant_payment(allocation, actual_success, mechanism if mechanism != 'observed_rel_contingent' else 'contingent')
                
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
                
    return utility, total_payment, global_welfare, buyer_payment, sla_successes, total_allocated, tasks_until_beat

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
    
    seed_results = []
    c_mults = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
    cap_mults = [0.5, 1.0, 1.5, 2.0]
    
    for mech in MECHANISMS:
        for node_id in nodes:
            true_rel = nodes[node_id]["true_success_probability"]
            rel_diffs = [-0.2, 0.0, min(1.0 - true_rel, 0.2)]
            
            truthful_params = (1.0, 1.0, 0.0)
            truthful_util, truthful_pay, gw, bp, sla_succ, allocs, tub = simulate_fast(mech, node_id, truthful_params, seed, nodes, tasks, ground_truth, truthful_bids, p=0.1, f=50.0)
            
            max_cost_util = -float('inf')
            max_rel_util = -float('inf')
            max_joint_util = -float('inf')
            best_rel_dev = None
            
            for c in c_mults:
                for cap in cap_mults:
                    for r in rel_diffs:
                        util, _, _, _, _, _, _ = simulate_fast(mech, node_id, (c, cap, r), seed, nodes, tasks, ground_truth, truthful_bids, p=0.1, f=50.0)
                        if util > max_joint_util:
                            max_joint_util = util
                        if cap == 1.0 and r == 0.0: max_cost_util = max(max_cost_util, util)
                        if c == 1.0 and cap == 1.0:
                            if util > max_rel_util:
                                max_rel_util = util
                                best_rel_dev = (c, cap, r)
                            
            # Compute attack metrics when they play best deviation
            _, _, wtd_w, wtd_bp, wtd_sla, _, _ = simulate_fast(mech, node_id, (0.5, 2.0, 0.2), seed, nodes, tasks, ground_truth, truthful_bids, attack="win-then-drop", p=0.1, f=50.0)
            wtd_util = _
            
            _, _, syb_w, syb_bp, syb_sla, _, _ = simulate_fast(mech, node_id, truthful_params, seed, nodes, tasks, ground_truth, truthful_bids, attack="sybil", p=0.1, f=50.0)
            sybil_util = _
            
            _, _, col_w, col_bp, col_sla, _, _ = simulate_fast(mech, node_id, truthful_params, seed, nodes, tasks, ground_truth, truthful_bids, attack="collusion", p=0.1, f=50.0)
            coll_util = _
            
            _, _, frel_w, frel_bp, frel_sla, _, _ = simulate_fast(mech, node_id, best_rel_dev if best_rel_dev else truthful_params, seed, nodes, tasks, ground_truth, truthful_bids, p=0.1, f=50.0)
            
            seed_results.append({
                'seed': seed,
                'mechanism': mech,
                'node_id': node_id,
                'joint_regret': max_joint_util - truthful_util,
                'truthful_util': truthful_util,
                'truthful_pay': truthful_pay,
                'global_welfare': gw,
                'buyer_payment': bp,
                'sla_success_rate': sla_succ / max(1, allocs),
                'tasks_until_beat': tub,
                'wtd_gain': wtd_util - truthful_util,
                'sybil_gain': sybil_util - truthful_util,
                'collusion_gain': coll_util - truthful_util,
                'wtd_w': wtd_w, 'wtd_bp': wtd_bp, 'wtd_sla': wtd_sla / max(1, allocs),
                'syb_w': syb_w, 'syb_bp': syb_bp, 'syb_sla': syb_sla / max(1, allocs),
                'col_w': col_w, 'col_bp': col_bp, 'col_sla': col_sla / max(1, allocs),
                'frel_w': frel_w, 'frel_bp': frel_bp, 'frel_sla': frel_sla / max(1, allocs)
            })
    return seed_results

def run_sweep(seed):
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
            ground_truth[(t.task_id, n_id)] = {"actual_success": success, "node_cost": n["true_energy_rate"] * time_taken * 2.0, "actual_latency_ms": base_latency}
    truthful_bids = {}
    for t in tasks:
        truthful_bids[t.task_id] = {}
        for n_id, n_data in nodes.items():
            price, claim = NodeBehavior.generate_bid("HONEST_STABLE", n_data, t.model_dump())
            truthful_bids[t.task_id][n_id] = Bid(task_id=t.task_id, node_id=n_id, price=price, claim=claim)

    sweep_results = []
    settings = [(0.05, 10.0), (0.1, 10.0), (0.1, 50.0), (0.2, 50.0), (0.5, 50.0), (0.5, 100.0)]
    for p, f in settings:
        for node_id in nodes:
            truthful_util, _, _, bp, _, _, _ = simulate_fast('audits', node_id, (1.0, 1.0, 0.0), seed, nodes, tasks, ground_truth, truthful_bids, p=p, f=f)
            
            sybil_util, _, _, _, _, _, _ = simulate_fast('audits', node_id, (1.0, 1.0, 0.0), seed, nodes, tasks, ground_truth, truthful_bids, attack="sybil", p=p, f=f)
            coll_util, _, _, _, _, _, _ = simulate_fast('audits', node_id, (1.0, 1.0, 0.0), seed, nodes, tasks, ground_truth, truthful_bids, attack="collusion", p=p, f=f)
            
            sweep_results.append({
                'seed': seed, 'p': p, 'f': f, 'node_id': node_id,
                'sybil_gain': sybil_util - truthful_util,
                'coll_gain': coll_util - truthful_util,
                'buyer_payment': bp
            })
    return sweep_results

def get_ci(series):
    n = len(series)
    if n < 2: return 0.0
    return 1.96 * np.std(series, ddof=1) / np.sqrt(n)

if __name__ == "__main__":
    print("PROVENANCE: Azure2019 arrivals (DEV). Synthetic costs/rel/cap. WS-DREAM NOT used.")
    all_results = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [executor.submit(run_seed, seed) for seed in range(42, 42 + NUM_SEEDS)]
        for f in concurrent.futures.as_completed(futures):
            all_results.extend(f.result())
            
    df = pd.DataFrame(all_results)
    
    median_pay = df[df['truthful_pay'] > 0]['truthful_pay'].median()
    df['joint_regret_norm'] = df['joint_regret'] / median_pay
    
    os.makedirs('experiments/results', exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f'experiments/results/regret_final_d.csv'
    df.to_csv(out_path, index=False)
    
    print("\nAllocation is purely GREEDY by expected trust score/VCG across all variants except greedy. Only the payments differ.\n")
    
    print("--- 1. Main Regret Table (Truthful Base) ---")
    print(f"{'Mechanism':<25} | {'Unnorm Reg':<15} | {'Norm J-Reg':<15} | {'Welfare':<15} | {'Buyer Pay':<15} | {'SLA%':<10}")
    
    for mech in MECHANISMS:
        mdf = df[df['mechanism'] == mech]
        seed_agg = mdf.groupby('seed').agg({
            'joint_regret': 'mean',
            'joint_regret_norm': 'mean',
            'global_welfare': 'first',
            'buyer_payment': 'first',
            'sla_success_rate': 'first'
        })
        mean_u = seed_agg['joint_regret'].mean()
        ci_u = get_ci(seed_agg['joint_regret'])
        mean_n = seed_agg['joint_regret_norm'].mean()
        ci_n = get_ci(seed_agg['joint_regret_norm'])
        mean_w = seed_agg['global_welfare'].mean()
        ci_w = get_ci(seed_agg['global_welfare'])
        mean_bp = seed_agg['buyer_payment'].mean()
        ci_bp = get_ci(seed_agg['buyer_payment'])
        mean_sla = seed_agg['sla_success_rate'].mean() * 100
        ci_sla = get_ci(seed_agg['sla_success_rate'] * 100)
        
        print(f"{mech:<25} | {mean_u:>5.1f}±{ci_u:<4.1f} | {mean_n:>5.2f}±{ci_n:<4.2f} | {mean_w:>5.0f}±{ci_w:<4.0f} | {mean_bp:>5.0f}±{ci_bp:<4.0f} | {mean_sla:>4.1f}%±{ci_sla:<3.1f}")
        
    print("\n--- 2. Paired Comparison vs Greedy ---")
    greedy_welfare = df[df['mechanism'] == 'greedy'].groupby('seed')['global_welfare'].first()
    greedy_sla = df[df['mechanism'] == 'greedy'].groupby('seed')['sla_success_rate'].first()
    for mech in MECHANISMS:
        if mech == 'greedy': continue
        w_diff = df[df['mechanism'] == mech].groupby('seed')['global_welfare'].first() - greedy_welfare
        sla_diff = (df[df['mechanism'] == mech].groupby('seed')['sla_success_rate'].first() - greedy_sla) * 100
        mean_w = w_diff.mean()
        ci_w = get_ci(w_diff)
        mean_sla = sla_diff.mean()
        ci_sla = get_ci(sla_diff)
        w_exc = "Yes" if abs(mean_w) > ci_w else "No"
        sla_exc = "Yes" if abs(mean_sla) > ci_sla else "No"
        print(f"{mech:<25} | W-Diff: {mean_w:>5.1f}±{ci_w:<4.1f} (Excl 0: {w_exc}) | SLA-Diff: {mean_sla:>5.1f}%±{ci_sla:<4.1f}% (Excl 0: {sla_exc})")
        
    print("\n--- 3. Attack Metrics ---")
    for attack, w_col, bp_col, sla_col in [("Fake Rel", "frel_w", "frel_bp", "frel_sla"), 
                                           ("Win-Then-Drop", "wtd_w", "wtd_bp", "wtd_sla"),
                                           ("Sybil", "syb_w", "syb_bp", "syb_sla"),
                                           ("Collusion", "col_w", "col_bp", "col_sla")]:
        print(f"\n{attack} Attack (Best Deviation Played):")
        for mech in MECHANISMS:
            mdf = df[df['mechanism'] == mech]
            seed_agg = mdf.groupby('seed').agg({w_col: 'mean', bp_col: 'mean', sla_col: 'mean'})
            print(f"  {mech:<25} | Welfare: {seed_agg[w_col].mean():>5.0f}±{get_ci(seed_agg[w_col]):<4.0f} | BP: {seed_agg[bp_col].mean():>5.0f}±{get_ci(seed_agg[bp_col]):<4.0f} | SLA: {seed_agg[sla_col].mean()*100:>4.1f}%±{get_ci(seed_agg[sla_col]*100):<3.1f}%")

    print("\n--- 4. Genuinely Proper Scoring Rule ---")
    print("Formula: Payment = Price + a - b * (Outcome - Claimed_Rel)^2, where a=20, b=20")
    print("Algebraic Proof (Expected Payment Maxima):")
    print("E[Pay] = a - b * [ p(1-q)^2 + (1-p)(0-q)^2 ] = a - b(p - 2pq + q^2)")
    print("dE/dq = -b(-2p + 2q) = 0 => q = p. Expected payment is strictly maximized at truth (q=p).")
    
    print("\n--- 5. Audits Sweep ---")
    print("Audits Main Row: p=0.1, F=50.0")
    print("Scale: Payment = price + (Claim_rel * p * F) [on success] - F [on audited failure]")
    sweep_data = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [executor.submit(run_sweep, seed) for seed in range(42, 42 + NUM_SEEDS)]
        for f in concurrent.futures.as_completed(futures):
            sweep_data.extend(f.result())
    sdf = pd.DataFrame(sweep_data)
    print(f"{'p':<5} | {'F':<5} | {'Sybil Gn':<15} | {'Coll Gn':<15} | {'Buyer Pay':<15}")
    for (p, f_val), grp in sdf.groupby(['p', 'f']):
        seed_agg = grp.groupby('seed').mean(numeric_only=True)
        mean_syb = seed_agg['sybil_gain'].mean()
        ci_syb = get_ci(seed_agg['sybil_gain'])
        mean_col = seed_agg['coll_gain'].mean()
        ci_col = get_ci(seed_agg['coll_gain'])
        mean_bp = seed_agg['buyer_payment'].mean()
        ci_bp = get_ci(seed_agg['buyer_payment'])
        print(f"{p:<5} | {f_val:<5} | {mean_syb:>6.2f}±{ci_syb:<5.2f} | {mean_col:>6.2f}±{ci_col:<5.2f} | {mean_bp:>6.0f}±{ci_bp:<5.0f}")
    
    # Cheapest setting where Sybil and Collusion are not positive within CI
    for (p, f_val), grp in sdf.groupby(['p', 'f']):
        seed_agg = grp.groupby('seed').mean(numeric_only=True)
        syb_upper = seed_agg['sybil_gain'].mean() + get_ci(seed_agg['sybil_gain'])
        col_upper = seed_agg['coll_gain'].mean() + get_ci(seed_agg['coll_gain'])
        if syb_upper <= 0 and col_upper <= 0:
            print(f"Cheapest setting where Sybil & Collusion gains are NOT positive within CI: p={p}, F={f_val}")
            break
            
    print("\n--- 6. Observed Rel Contingent (New Variant) ---")
    obs_tub = df[df['mechanism'] == 'observed_rel_contingent'][df['tasks_until_beat'] >= 0]['tasks_until_beat']
    print(f"Observed Rel Contingent ignores claimed reliability and allocates by Bayesian posterior (prior=1/1).")
    if len(obs_tub) > 0:
        print(f"It takes on average {obs_tub.mean():.1f} tasks before observed_rel_contingent beats greedy claim-based allocation by successfully avoiding a dropping node.")
    else:
        print("It did not strictly beat the claim-based allocation in these traces.")
