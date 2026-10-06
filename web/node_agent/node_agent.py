import os
import time
import httpx
import logging
import random
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

API_URL = os.environ.get("API_URL", "http://backend:8000/api")
NODE_ID = os.environ.get("NODE_ID", f"edge-node-{random.randint(100, 999)}")
NODE_NAME = os.environ.get("NODE_NAME", f"Edge Node {NODE_ID}")
REGION = os.environ.get("REGION", "EU-West")
CPU = int(os.environ.get("CAPACITY_CPU", "4"))
MEM = int(os.environ.get("CAPACITY_MEMORY", "8192"))
LATENCY = float(os.environ.get("TRUE_LATENCY_MS", "15.0"))
NODE_TYPE = os.environ.get("NODE_TYPE", "HONEST_STABLE")
CAPABILITIES = os.environ.get("CAPABILITIES", "docker,python").split(",")

def register():
    payload = {
        "id": NODE_ID,
        "name": NODE_NAME,
        "region": REGION,
        "capacity_cpu": CPU,
        "capacity_memory": MEM,
        "true_latency_ms": LATENCY,
        "node_type": NODE_TYPE,
        "capabilities": CAPABILITIES
    }
    try:
        res = httpx.post(f"{API_URL}/nodes", json=payload, timeout=5.0)
        res.raise_for_status()
        logging.info(f"Registered node {NODE_ID} successfully.")
        return True
    except Exception as e:
        logging.error(f"Failed to register node {NODE_ID}: {e}")
        return False

def heartbeat():
    try:
        res = httpx.post(f"{API_URL}/nodes/{NODE_ID}/heartbeat", timeout=5.0)
        res.raise_for_status()
        logging.info(f"[{NODE_ID}] Heartbeat OK")
    except Exception as e:
        logging.error(f"[{NODE_ID}] Heartbeat failed: {e}")

def main():
    time.sleep(5)  # Wait for backend
    while not register():
        time.sleep(3)
        
    while True:
        time.sleep(10)
        heartbeat()

if __name__ == "__main__":
    main()
