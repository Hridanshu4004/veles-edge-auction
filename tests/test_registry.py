from fastapi.testclient import TestClient

from services.registry.main import app

client = TestClient(app)

def test_registry_lifecycle():
    # Register
    rv = {"cpu_cores": 4.0, "ram_gb": 8.0, "bandwidth_mbps": 100.0, "latency_ms": 10.0, "energy_cost": 0.1, "availability_probability": 0.99}
    node = {"node_id": "test-node", "node_type": "HONEST_STABLE", "capacity": rv, "network_zone": "default"}
    
    resp = client.post("/register", json=node)
    assert resp.status_code == 200
    
    # Get Nodes
    resp = client.get("/nodes")
    assert resp.status_code == 200
    nodes = resp.json()
    assert len(nodes) == 1
    assert nodes[0]["node_id"] == "test-node"
    
    # Get Node by ID
    resp = client.get("/nodes/test-node")
    assert resp.status_code == 200
    assert resp.json()["node_id"] == "test-node"

    # Heartbeat
    resp = client.post("/heartbeat", json={"node_id": "test-node"})
    assert resp.status_code == 200
    
    # Deregister
    resp = client.post("/deregister", json={"node_id": "test-node"})
    assert resp.status_code == 200
    
    # Get Nodes empty
    resp = client.get("/nodes")
    assert resp.status_code == 200
    assert len(resp.json()) == 0
