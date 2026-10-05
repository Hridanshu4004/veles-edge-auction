from common.models import Bid, Claim, Node, ResourceVector, TrustProfile


def test_models():
    # Test ResourceVector
    rv = ResourceVector(cpu_cores=4.0, ram_gb=8.0, bandwidth_mbps=100.0, latency_ms=10.0, energy_cost=0.1, availability_probability=0.99)
    assert rv.cpu_cores == 4.0
    
    # Test Node
    node = Node(node_id="test-1", capacity=rv)
    assert node.node_id == "test-1"
    assert node.node_type == "HONEST_STABLE"
    
    # Test Claim & Bid
    claim = Claim(success_probability=0.95, latency_p50_ms=12.0, latency_p95_ms=25.0, energy_estimate=0.15, confidence=0.9)
    bid = Bid(task_id="task-1", node_id="test-1", price=1.5, claim=claim)
    assert bid.price == 1.5
    
    # Test TrustProfile
    tp = TrustProfile(node_id="test-1")
    assert tp.capacity_calibration == 1.0
    assert tp.evidence.prediction_count == 0
