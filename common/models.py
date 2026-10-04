from pydantic import BaseModel, Field
from typing import Optional, Dict

class ResourceVector(BaseModel):
    cpu_cores: float
    ram_gb: float
    bandwidth_mbps: float
    latency_ms: float
    energy_cost: float
    availability_probability: float = Field(ge=0.0, le=1.0)

class Task(BaseModel):
    task_id: str
    task_type: str = "generic"
    cpu_required: float
    ram_required: float
    bandwidth_required: float
    max_latency_ms: float
    deadline_ms: float
    priority: float
    work_units: float
    task_value: float = 1000.0  # Added financial value
    arrival_epoch: int = 0

class Claim(BaseModel):
    success_probability: float = Field(ge=0.0, le=1.0)
    latency_p50_ms: float
    latency_p95_ms: float
    latency_std_ms: float = 0.0  # Added uncertainty
    energy_estimate: float
    confidence: float = Field(ge=0.0, le=1.0)

class Bid(BaseModel):
    task_id: str
    node_id: str
    price: float
    claim: Claim
    
class Node(BaseModel):
    node_id: str
    node_type: str = "HONEST_STABLE"
    capacity: ResourceVector
    network_zone: str = "default"

class ExecutionResult(BaseModel):
    task_id: str
    node_id: str
    actual_success: bool
    actual_latency_ms: float
    actual_energy: float
    actual_completion_time: float
    node_cost: float = 0.0  # True cost incurred by the node
    sla_met: bool
    
class Evidence(BaseModel):
    observations: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    latency_mae: float = 0.0
    success_brier_score: float = 0.0
    sla_violations: int = 0

class TrustProfile(BaseModel):
    node_id: str
    capacity_calibration: float = 1.0
    latency_calibration: float = 1.0
    success_calibration: float = 1.0
    availability: float = 1.0
    evidence: Evidence = Field(default_factory=Evidence)

class Allocation(BaseModel):
    task_id: str
    node_id: str
    winning_bid: Bid
    risk_score: float
    expected_utility: float = 0.0
