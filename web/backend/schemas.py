from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class NodeCreate(BaseModel):
    id: str
    name: str
    region: str = "default"
    capacity_cpu: int
    capacity_memory: int
    true_latency_ms: float
    node_type: str
    capabilities: List[str] = []

class NodeResponse(NodeCreate):
    status: str
    last_heartbeat: Optional[datetime] = None
    created_at: datetime
    class Config:
        from_attributes = True

class TaskCreate(BaseModel):
    id: str
    task_value: float
    max_latency_ms: float
    required_cpu: int
    required_memory: int

class TaskResponse(TaskCreate):
    status: str
    created_at: datetime
    class Config:
        from_attributes = True

class AuctionRunRequest(BaseModel):
    task_id: str

class AuctionRunResponse(BaseModel):
    task_id: str
    winner: Optional[str]
    score: Optional[float]
    price: Optional[float]
    success_probability: Optional[float]
    mechanism: str

class ExecutionRequest(BaseModel):
    task_id: str
    node_id: str
    success: bool
    latency_ms: float

class ExecutionResponse(ExecutionRequest):
    id: int
    payment: float
    created_at: datetime
    class Config:
        from_attributes = True
