import json
import time

from common.models import Bid, Claim, Task, TrustProfile
from mechanisms.edge_truth import prediction_contract_allocation


def test_timing():
    results = {}
    Ns = [10, 50, 100, 500, 1000]
    task = Task(task_id="t1", data_size_bytes=1000, deadline_ms=100.0, task_value=1000.0, cpu_required=4, ram_required=1024, bandwidth_required=10, max_latency_ms=100, priority=1, work_units=100)
    trust_profiles = {}
    
    for N in Ns:
        bids = []
        for i in range(N):
            node_id = f"n{i}"
            bids.append(Bid(
                task_id="t1",
                node_id=node_id,
                price=10.0,
                claim=Claim(
                    cpu_cores=4, memory_mb=1024,
                    latency_p50_ms=50.0, latency_std_ms=10.0, latency_p95_ms=60.0,
                    success_probability=0.99, energy_estimate=10.0, confidence=0.99
                )
            ))
            trust_profiles[node_id] = TrustProfile(node_id=node_id)
            
        times = []
        for _ in range(100):
            start = time.perf_counter()
            _ = prediction_contract_allocation(task, bids, trust_profiles, {"alpha_success": 50, "alpha_latency": 10})
            times.append((time.perf_counter() - start) * 1000) # ms
            
        times.sort()
        results[N] = {
            "p50": times[50],
            "p95": times[95],
            "p99": times[99],
            "max": times[-1]
        }
        
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    test_timing()
