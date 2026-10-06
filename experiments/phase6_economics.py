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
NUM_TASKS = 500
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

def run_scenario(mechanism, seed, nodes, tasks, ground_truth, truthful_bids):
    rng = random.Random(seed)
    trust_profiles = {n_id: TrustProfile(node_id=n_id) for n_id in nodes}
    observed_attempts = {n_id: 1 for n_id in nodes}
    observed_successes = {n_id: 1.0 for n_id in nodes}

    metrics = {
        'successes': 0,
        'retries': 0,
        'execution_cost': 0.0,  # Paid on success
        'failure_cost': 0.0,    # Paid on fail
        'retry_cost': 0.0,      # Paid for retry executions
        'sla_loss': 0.0,        # Loss for permanent failure
        'total_welfare': 0.0
    }
    
    for task in tasks:
        bids = [truthful_bids[task.task_id][n_id] for n_id in nodes]
        if mechanism in ['observed_rel_contingent', 'edgetruth']:
            bids_copy = copy.deepcopy(bids)
            for b in bids_copy:
                b.claim.success_probability = observed_successes[b.node_id] / observed_attempts[b.node_id]
            bids = bids_copy
            
        # First Try
        if mechanism == 'greedy': allocation = greedy_cheapest(task, bids)
        elif mechanism == 'edgetruth': allocation = edgetruth_allocation(task, bids, observed_successes, observed_attempts)
        else: allocation = variant_allocation(task, bids, trust_profiles, mechanism if mechanism != 'observed_rel_contingent' else 'contingent')
        
        if allocation:
            winner_id = allocation.node_id
            actual_success = ground_truth[(task.task_id, winner_id)]["actual_success"]
            
            observed_attempts[winner_id] += 1
            if actual_success: observed_successes[winner_id] += 1
            
            if mechanism == 'greedy':
                payment = allocation.winning_bid.price
            elif mechanism == 'edgetruth':
                payment = allocation.winning_bid.price if actual_success else 0.0
            else:
                random.seed(rng.random())
                payment = variant_payment(allocation, actual_success, mechanism if mechanism != 'observed_rel_contingent' else 'contingent')
                
            if actual_success:
                metrics['successes'] += 1
                metrics['execution_cost'] += payment
                metrics['total_welfare'] += task.task_value - ground_truth[(task.task_id, winner_id)]["node_cost"]
            else:
                metrics['failure_cost'] += payment
                # Retry logic
                metrics['retries'] += 1
                bids_retry = [b for b in bids if b.node_id != winner_id]
                
                if mechanism == 'greedy': retry_alloc = greedy_cheapest(task, bids_retry)
                elif mechanism == 'edgetruth': retry_alloc = edgetruth_allocation(task, bids_retry, observed_successes, observed_attempts)
                else: retry_alloc = variant_allocation(task, bids_retry, trust_profiles, mechanism if mechanism != 'observed_rel_contingent' else 'contingent')
                
                if retry_alloc:
                    retry_winner = retry_alloc.node_id
                    retry_success = ground_truth[(task.task_id, retry_winner)]["actual_success"]
                    
                    observed_attempts[retry_winner] += 1
                    if retry_success: observed_successes[retry_winner] += 1
                    
                    if mechanism == 'greedy': r_pay = retry_alloc.winning_bid.price
                    elif mechanism == 'edgetruth': r_pay = retry_alloc.winning_bid.price if retry_success else 0.0
                    else: r_pay = variant_payment(retry_alloc, retry_success, mechanism if mechanism != 'observed_rel_contingent' else 'contingent')
                    
                    metrics['retry_cost'] += r_pay
                    if retry_success:
                        metrics['successes'] += 1
                        metrics['total_welfare'] += task.task_value - ground_truth[(task.task_id, retry_winner)]["node_cost"] - ground_truth[(task.task_id, winner_id)]["node_cost"]
                    else:
                        metrics['sla_loss'] += 0.5 * task.task_value
                        metrics['total_welfare'] -= 0.5 * task.task_value + ground_truth[(task.task_id, retry_winner)]["node_cost"] + ground_truth[(task.task_id, winner_id)]["node_cost"]
                else:
                    metrics['sla_loss'] += 0.5 * task.task_value
                    metrics['total_welfare'] -= 0.5 * task.task_value + ground_truth[(task.task_id, winner_id)]["node_cost"]
                    
    return metrics

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
        metrics = run_scenario(mech, seed, nodes, tasks, ground_truth, truthful_bids)
        metrics['seed'] = seed
        metrics['mechanism'] = mech
        res.append(metrics)
    return res

if __name__ == "__main__":
    all_results = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [executor.submit(run_seed, seed) for seed in range(42, 42 + NUM_SEEDS)]
        for f in concurrent.futures.as_completed(futures):
            all_results.extend(f.result())
            
    df = pd.DataFrame(all_results)
    
    print("--- PHASE 6: FAILURE / RECOVERY ECONOMICS ---")
    print(f"{'Mechanism':<15} | {'Success':<8} | {'Retries':<8} | {'Exec Cost':<10} | {'Fail Cost':<10} | {'Retry Cost':<11} | {'SLA Loss':<10} | {'Total Econ Cost':<15} | {'Welfare':<10}")
    for mech in ['greedy', 'edgetruth']:
        mdf = df[df['mechanism'] == mech]
        seed_agg = mdf.groupby('seed').mean(numeric_only=True)
        
        suc = seed_agg['successes'].mean()
        ret = seed_agg['retries'].mean()
        exec_cost = seed_agg['execution_cost'].mean()
        fail_cost = seed_agg['failure_cost'].mean()
        retry_cost = seed_agg['retry_cost'].mean()
        sla = seed_agg['sla_loss'].mean()
        welfare = seed_agg['total_welfare'].mean()
        
        tot_econ_cost = exec_cost + fail_cost + retry_cost + sla
        
        print(f"{mech:<15} | {suc:>8.1f} | {ret:>8.1f} | {exec_cost:>10.0f} | {fail_cost:>10.0f} | {retry_cost:>11.0f} | {sla:>10.0f} | {tot_econ_cost:>15.0f} | {welfare:>10.0f}")

