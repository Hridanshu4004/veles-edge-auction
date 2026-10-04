import numpy as np
import pandas as pd
from typing import Dict, List, Tuple

class DataPipeline:
    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)

    def ingest_alibaba_trace(self, filepath: str) -> pd.DataFrame:
        """Parses Alibaba Cluster Trace (2018/2021) for realistic node CPU/RAM and crash rates."""
        try:
            df = pd.read_csv(filepath, usecols=['machine_id', 'cpu_capacity', 'failure_event_flag'])
            df['true_success'] = 1.0 - df['failure_event_flag'].rolling(window=100, min_periods=1).mean()
            return df
        except FileNotFoundError:
            print("Alibaba trace not found. Using synthetic fallback.")
            return None

    def ingest_azure_functions(self, filepath: str) -> pd.DataFrame:
        """Parses Azure Public Dataset for edge function timeout probabilities."""
        try:
            df = pd.read_csv(filepath)
            df['timeout_prob'] = df['ExecTime'] > 200.0
            return df
        except FileNotFoundError:
            print("Azure trace not found. Using synthetic fallback.")
            return None

    def ingest_google_borg(self, filepath: str) -> pd.DataFrame:
        """Parses Google Borg Trace for task-value prioritization and arrival rates."""
        try:
            df = pd.read_csv(filepath)
            df['task_value'] = df['scheduling_class'].map({0: 10, 1: 100, 2: 5000, 3: 10000})
            return df
        except FileNotFoundError:
            print("Borg trace not found. Using synthetic fallback.")
            return None

    def generate_nodes_vectorized(self, num_nodes: int) -> pd.DataFrame:
        """
        Generates nodes with correlated features. 
        Cheap nodes have higher variance (latency_std) and lower true success rate.
        Expensive nodes have tight SLAs.
        """
        node_ids = np.array([f"n_{i}" for i in range(num_nodes)])
        
        # Node Type distribution
        types = self.rng.choice(
            ["HONEST_STABLE", "CHEAP_UNSTABLE", "LIAR", "STRATEGIC"],
            size=num_nodes,
            p=[0.4, 0.3, 0.2, 0.1]
        )
        
        # Base capacities
        cpu = self.rng.uniform(1.0, 16.0, size=num_nodes)
        
        # Pricing: Cheap nodes are cheap, stable are expensive
        true_cost = np.where(types == "CHEAP_UNSTABLE", self.rng.uniform(1, 5, num_nodes), self.rng.uniform(10, 20, num_nodes))
        
        # Bids: Liars bid lower than cost
        bid_price = np.where(types == "LIAR", true_cost * 0.5, true_cost * 1.1)
        
        # True performance
        true_latency_p50 = self.rng.uniform(10, 100, size=num_nodes)
        
        # Variance correlated with type
        true_latency_std = np.where(types == "HONEST_STABLE", 2.0, self.rng.uniform(20, 50, num_nodes))
        true_success = np.where(types == "HONEST_STABLE", 0.99, self.rng.uniform(0.5, 0.8, num_nodes))
        
        # Claims (what they tell the mechanism)
        claim_success = np.where(types == "LIAR", 0.99, true_success)
        claim_latency_std = np.where(types == "LIAR", 1.0, true_latency_std)
        claim_latency_p50 = np.where(types == "LIAR", true_latency_p50 * 0.5, true_latency_p50)
        
        df = pd.DataFrame({
            "node_id": node_ids,
            "type": types,
            "cpu": cpu,
            "true_cost": true_cost,
            "bid_price": bid_price,
            "true_latency_p50": true_latency_p50,
            "true_latency_std": true_latency_std,
            "true_success": true_success,
            "claim_success": claim_success,
            "claim_latency_std": claim_latency_std,
            "claim_latency_p50": claim_latency_p50
        })
        
        return df

    def generate_tasks_vectorized(self, num_tasks: int) -> pd.DataFrame:
        """
        Generates a continuous stream of tasks.
        Includes Low-value (background) and High-value (critical) tasks.
        """
        task_ids = np.array([f"t_{i}" for i in range(num_tasks)])
        
        # Task values: heavy tail (pareto) or bimodal
        task_types = self.rng.choice(["LOW", "HIGH"], size=num_tasks, p=[0.8, 0.2])
        values = np.where(task_types == "HIGH", self.rng.uniform(5000, 10000, num_tasks), self.rng.uniform(10, 100, num_tasks))
        deadlines = self.rng.uniform(50, 200, size=num_tasks)
        
        df = pd.DataFrame({
            "task_id": task_ids,
            "task_type": task_types,
            "value": values,
            "deadline_ms": deadlines
        })
        
        return df
        
    def simulate_execution(self, task_row: pd.Series, node_row: pd.Series) -> Tuple[bool, float]:
        """Ground truth execution"""
        success = self.rng.random() < node_row["true_success"]
        if not success:
            return False, 0.0
            
        latency = self.rng.normal(node_row["true_latency_p50"], node_row["true_latency_std"])
        return True, max(1.0, latency)

if __name__ == "__main__":
    pipeline = DataPipeline()
    nodes = pipeline.generate_nodes_vectorized(100000)
    print(f"Generated {len(nodes)} nodes.")
    print(nodes.head())
    
    tasks = pipeline.generate_tasks_vectorized(10000)
    print(f"Generated {len(tasks)} tasks.")
    print(tasks.head())
