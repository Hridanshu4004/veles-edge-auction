import hashlib
import os
import csv
import copy
import random
import numpy as np
import concurrent.futures

from common.loaders import Azure2019Loader
from simulator.data_generator import DataGenerator
from common.models import Bid, Task, TrustProfile
from simulator.node_models import NodeBehavior

# Historical mechanisms for baseline
from mechanisms.baselines import greedy_cheapest
# Final mechanism
from mechanisms.edgetruth import edgetruth_allocation, edgetruth_payment

NUM_SEEDS = 30
NUM_TASKS = 300
NUM_NODES = 30

def get_azure_tasks():
    loader = Azure2019Loader('data/raw/azure/2019')
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
        print("Fallback to synthetic tasks:", e)
        return []

AZURE_TASKS = get_azure_tasks()

def run_scenario(mechanism, seed, nodes, tasks, ground_truth, truthful_bids):
    rng = random.Random(seed)
    
    observed_attempts = {n_id: 1.0 for n_id in nodes}
    observed_successes = {n_id: 1.0 for n_id in nodes}

    metrics = {
        'seed': seed,
        'mechanism': mechanism,
        'task_count': len(tasks),
        'successes': 0,
        'failures': 0,
        'retries': 0,
        'sla_success': 0,
        'buyer_payment': 0.0,
        'welfare': 0.0
    }
    
    for task in tasks:
        bids = [truthful_bids[task.task_id][n_id] for n_id in nodes]
        
        # First Try
        if mechanism == 'greedy': 
            allocation = greedy_cheapest(task, bids)
        elif mechanism == 'edgetruth': 
            allocation = edgetruth_allocation(task, bids, observed_successes, observed_attempts)
        else: 
            allocation = None
        
        if allocation:
            winner_id = allocation.node_id
            actual_success = ground_truth[(task.task_id, winner_id)]["actual_success"]
            
            observed_attempts[winner_id] += 1.0
            if actual_success: observed_successes[winner_id] += 1.0
            
            if mechanism == 'greedy':
                payment = allocation.winning_bid.price
            elif mechanism == 'edgetruth':
                payment = edgetruth_payment(allocation, actual_success)
            else:
                payment = 0.0
                
            if actual_success:
                metrics['successes'] += 1
                metrics['sla_success'] += 1
                metrics['buyer_payment'] += payment
                metrics['welfare'] += task.task_value - ground_truth[(task.task_id, winner_id)]["node_cost"]
            else:
                metrics['failures'] += 1
                metrics['buyer_payment'] += payment
                metrics['retries'] += 1
                
                # Retry logic
                bids_retry = [b for b in bids if b.node_id != winner_id]
                
                if mechanism == 'greedy': 
                    retry_alloc = greedy_cheapest(task, bids_retry)
                elif mechanism == 'edgetruth': 
                    retry_alloc = edgetruth_allocation(task, bids_retry, observed_successes, observed_attempts)
                else: 
                    retry_alloc = None
                
                if retry_alloc:
                    retry_winner = retry_alloc.node_id
                    retry_success = ground_truth[(task.task_id, retry_winner)]["actual_success"]
                    
                    observed_attempts[retry_winner] += 1.0
                    if retry_success: observed_successes[retry_winner] += 1.0
                    
                    if mechanism == 'greedy': 
                        r_pay = retry_alloc.winning_bid.price
                    elif mechanism == 'edgetruth': 
                        r_pay = edgetruth_payment(retry_alloc, retry_success)
                    else:
                        r_pay = 0.0
                    
                    metrics['buyer_payment'] += r_pay
                    if retry_success:
                        metrics['successes'] += 1
                        metrics['sla_success'] += 1
                        metrics['welfare'] += task.task_value - ground_truth[(task.task_id, retry_winner)]["node_cost"] - ground_truth[(task.task_id, winner_id)]["node_cost"]
                    else:
                        metrics['failures'] += 1
                        metrics['welfare'] -= 0.5 * task.task_value + ground_truth[(task.task_id, retry_winner)]["node_cost"] + ground_truth[(task.task_id, winner_id)]["node_cost"]
                else:
                    metrics['welfare'] -= 0.5 * task.task_value + ground_truth[(task.task_id, winner_id)]["node_cost"]
                    
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
            # Deterministic success
            rng = random.Random(seed + int(hashlib.md5((t.task_id + n_id).encode()).hexdigest(), 16) % 1000000)
            success = rng.random() <= n["true_success_probability"]
            time_taken = t.work_units / max(0.1, n["cpu_capacity"]) + base_latency
            ground_truth[(t.task_id, n_id)] = {
                "actual_success": success,
                "node_cost": n["true_energy_rate"] * time_taken * 2.0
            }

    truthful_bids = {}
    for t in tasks:
        truthful_bids[t.task_id] = {}
        for n_id, n_data in nodes.items():
            price, claim = NodeBehavior.generate_bid("HONEST_STABLE", n_data, t.model_dump())
            truthful_bids[t.task_id][n_id] = Bid(task_id=t.task_id, node_id=n_id, price=price, claim=claim)
            
    res = []
    # Baseline comparison vs Final
    for mech in ['greedy', 'edgetruth']:
        res.append(run_scenario(mech, seed, nodes, tasks, ground_truth, truthful_bids))
    return res

if __name__ == "__main__":
    print("[1/4] Initializing simulation")
    all_results = []
    
    print("[2/4] Running EdgeTruth (and greedy baseline)")
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [executor.submit(run_seed, seed) for seed in range(42, 42 + NUM_SEEDS)]
        for f in concurrent.futures.as_completed(futures):
            all_results.extend(f.result())
    all_results.sort(key=lambda x: (x['mechanism'], x['seed']))
            
    print("[3/4] Writing final results")
    os.makedirs('experiments/results', exist_ok=True)
    csv_path = 'experiments/results/edgetruth_final.csv'
    
    if all_results:
        keys = all_results[0].keys()
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_results)
            
    print("[4/4] Generating dashboard")
    # Will be handled by the Makefile calling generate_dashboard.py
    import sys
    os.system(f'{sys.executable} scripts/generate_dashboard.py')
    print("COMPLETE")
