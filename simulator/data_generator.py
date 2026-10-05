import json
import pathlib
import random
from typing import Any

from common.rng import set_seed


class DataGenerator:
    def __init__(self, seed: int):
        self.seed = seed
        set_seed(seed)
        
    def generate_nodes(self, count: int, config: dict[str, Any]) -> list[dict[str, Any]]:
        nodes = []
        for i in range(count):
            node_type = random.choices(
                population=["HONEST_STABLE", "OVERREPORTER", "LATENCY_LIAR", "SUCCESS_LIAR", "STRATEGIC_NODE", "COLLUDING_NODE", "SYBIL_NODE"],
                weights=config.get("node_type_weights", [1.0] + [0.0]*6),
                k=1
            )[0]
            
            cpu = random.choice([2.0, 4.0, 8.0, 16.0])
            ram = cpu * random.choice([2.0, 4.0])
            bandwidth = random.uniform(50.0, 1000.0)
            
            node = {
                "node_id": f"node-{i:03d}",
                "node_type": node_type,
                "cpu_capacity": cpu,
                "ram_capacity": ram,
                "bandwidth_capacity": bandwidth,
                "true_latency_ms": random.uniform(10.0, 100.0),
                "true_success_probability": random.uniform(0.75, 0.999),
                "true_energy_rate": random.uniform(0.05, 0.5),
                "true_availability": random.uniform(0.8, 0.999),
                "network_zone": random.choice(["zone-a", "zone-b", "zone-c"]),
                "reliability_profile": "constant"
            }
            nodes.append(node)
        return nodes
        
    def generate_tasks(self, count: int) -> list[dict[str, Any]]:
        tasks = []
        for i in range(count):
            work_units = random.uniform(10.0, 500.0)
            max_latency = random.uniform(20.0, 150.0)
            # Tighter deadlines: minimum execution time on a fast CPU is work_units / 16.0 + latency
            fastest_possible = (work_units / 16.0) + max_latency
            deadline_ms = fastest_possible * random.uniform(1.2, 5.0)
            
            task_value = work_units * random.uniform(1.0, 3.0) + (1000.0 / max_latency)
            
            tasks.append({
                "task_id": f"task-{i:04d}",
                "task_type": random.choice(["compute_heavy", "latency_sensitive"]),
                "cpu_required": random.uniform(0.1, 4.0),
                "ram_required": random.uniform(0.1, 8.0),
                "bandwidth_required": random.uniform(1.0, 50.0),
                "max_latency_ms": max_latency,
                "deadline_ms": deadline_ms,
                "priority": random.uniform(0.1, 1.0),
                "work_units": work_units,
                "task_value": task_value,
                "arrival_epoch": random.randint(0, count)
            })
        tasks.sort(key=lambda x: x["arrival_epoch"])
        return tasks
        
    def generate_network(self, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        network = []
        zones = ["zone-a", "zone-b", "zone-c"]
        for src in zones:
            for dst in zones:
                network.append({
                    "source_zone": src,
                    "destination_zone": dst,
                    "latency_ms": 5.0 if src == dst else random.uniform(20.0, 100.0),
                    "packet_loss": 0.001 if src == dst else random.uniform(0.01, 0.05),
                    "bandwidth_mbps": 1000.0 if src == dst else random.uniform(100.0, 500.0)
                })
        return network

    def generate_ground_truth(self, nodes: list[dict[str, Any]], tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        truth = []
        for t in tasks:
            for n in nodes:
                base_latency = n["true_latency_ms"]
                success = random.random() <= n["true_success_probability"]
                time_taken = t["work_units"] / max(0.1, n["cpu_capacity"]) + base_latency
                actual_energy = n["true_energy_rate"] * time_taken
                node_cost = actual_energy * 2.0  # arbitrary financial cost of energy
                
                truth.append({
                    "task_id": t["task_id"],
                    "node_id": n["node_id"],
                    "actual_success": success,
                    "actual_latency_ms": base_latency * random.uniform(0.9, 1.1),
                    "actual_energy": actual_energy,
                    "actual_completion_time": time_taken,
                    "node_cost": node_cost,
                    "actual_resource_usage": {"cpu": t["cpu_required"], "ram": t["ram_required"]},
                    "sla_met": success and (time_taken <= t["deadline_ms"])
                })
        return truth
        
    def generate_attack_config(self, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        attacks = []
        for n in nodes:
            if n["node_type"] != "HONEST_STABLE":
                attacks.append({
                    "node_id": n["node_id"],
                    "attack_type": n["node_type"],
                    "start_epoch": random.randint(0, 50),
                    "end_epoch": random.randint(200, 1000),
                    "severity": random.uniform(0.5, 1.0)
                })
        return attacks
        
    def generate_scenario(self, name: str, num_nodes: int, num_tasks: int, config: dict[str, Any]) -> dict[str, Any]:
        nodes = self.generate_nodes(num_nodes, config)
        tasks = self.generate_tasks(num_tasks)
        network = self.generate_network(nodes)
        attacks = self.generate_attack_config(nodes)
        ground_truth = self.generate_ground_truth(nodes, tasks)
        
        scenario = {
            "scenario_name": name,
            "seed": self.seed,
            "market_configuration": {
                "epoch_duration_ms": 1000,
                "max_epochs": 1000,
                "risk_weights": {"latency": 1.0, "failure": 1.0, "energy": 0.5, "probe_cost": 5.0}
            },
            "nodes": nodes,
            "tasks": tasks,
            "network": network,
            "attacks": attacks,
            "ground_truth": ground_truth
        }
        return scenario

def create_scenarios(output_dir: str):
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    num_tasks = 500
    
    # 1. CLEAN_MARKET
    gen = DataGenerator(seed=42)
    s1 = gen.generate_scenario("CLEAN_MARKET", num_nodes=10, num_tasks=num_tasks, config={"node_type_weights": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]})
    with open(f"{output_dir}/clean.json", "w") as f:
        json.dump(s1, f, indent=2)
        
    # 2. RESOURCE_LIARS
    gen = DataGenerator(seed=43)
    s2 = gen.generate_scenario("RESOURCE_LIARS", num_nodes=10, num_tasks=num_tasks, config={"node_type_weights": [0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0]})
    with open(f"{output_dir}/liars.json", "w") as f:
        json.dump(s2, f, indent=2)
        
    # 3. MIXED_ADVERSARY
    gen = DataGenerator(seed=44)
    s3 = gen.generate_scenario("MIXED_ADVERSARY", num_nodes=10, num_tasks=num_tasks, config={"node_type_weights": [0.4, 0.2, 0.2, 0.2, 0.0, 0.0, 0.0]})
    with open(f"{output_dir}/mixed_adversary.json", "w") as f:
        json.dump(s3, f, indent=2)

if __name__ == "__main__":
    create_scenarios("scenarios")
    print("Scenarios generated successfully.")
