import sys
import os
import httpx

API_URL = "http://localhost:8000/api"

nodes = [
    {"id": "edge-node-01", "name": "Berlin Edge A", "region": "EU-Central", "capacity_cpu": 8, "capacity_memory": 16384, "true_latency_ms": 12.0, "node_type": "HONEST_STABLE", "capabilities": ["docker", "python"]},
    {"id": "edge-node-02", "name": "London Edge B", "region": "EU-West", "capacity_cpu": 4, "capacity_memory": 8192, "true_latency_ms": 18.0, "node_type": "HONEST_STABLE", "capabilities": ["docker"]},
    {"id": "edge-node-03", "name": "Cheap Unstable C", "region": "EU-East", "capacity_cpu": 2, "capacity_memory": 4096, "true_latency_ms": 45.0, "node_type": "CHEAP_UNSTABLE", "capabilities": ["python"]},
    {"id": "edge-node-04", "name": "Adversary Sybil", "region": "US-East", "capacity_cpu": 16, "capacity_memory": 32768, "true_latency_ms": 120.0, "node_type": "LIAR", "capabilities": ["docker", "python", "ml"]},
]

tasks = [
    {"id": f"task-10{i}", "task_value": 150.0 + (i*10), "max_latency_ms": 200.0, "required_cpu": 2, "required_memory": 2048}
    for i in range(1, 15)
]

with httpx.Client() as client:
    for n in nodes:
        client.post(f"{API_URL}/nodes", json=n)
    for t in tasks:
        client.post(f"{API_URL}/tasks", json=t)

print("Seeded control plane database.")
