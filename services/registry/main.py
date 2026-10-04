from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List
import time
from common.models import Node

app = FastAPI(title="EdgeTruth Registry")

# In-memory stores
registered_nodes: Dict[str, Node] = {}
heartbeats: Dict[str, float] = {}

TTL_SECONDS = 30.0  # Node is considered offline if no heartbeat in 30s

class HeartbeatRequest(BaseModel):
    node_id: str

class DeregisterRequest(BaseModel):
    node_id: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/register")
def register(node: Node):
    registered_nodes[node.node_id] = node
    heartbeats[node.node_id] = time.time()
    return {"status": "registered", "node_id": node.node_id}

@app.post("/heartbeat")
def heartbeat(req: HeartbeatRequest):
    if req.node_id not in registered_nodes:
        raise HTTPException(status_code=404, detail="Node not registered")
    heartbeats[req.node_id] = time.time()
    return {"status": "heartbeat_received", "node_id": req.node_id}

@app.post("/deregister")
def deregister(req: DeregisterRequest):
    if req.node_id in registered_nodes:
        del registered_nodes[req.node_id]
    if req.node_id in heartbeats:
        del heartbeats[req.node_id]
    return {"status": "deregistered", "node_id": req.node_id}

@app.get("/nodes")
def get_nodes() -> List[Node]:
    current_time = time.time()
    active_nodes = []
    for node_id, node in registered_nodes.items():
        last_seen = heartbeats.get(node_id, 0)
        if current_time - last_seen <= TTL_SECONDS:
            active_nodes.append(node)
    return active_nodes

@app.get("/nodes/{node_id}")
def get_node(node_id: str) -> Node:
    if node_id not in registered_nodes:
        raise HTTPException(status_code=404, detail="Node not found")
    
    current_time = time.time()
    last_seen = heartbeats.get(node_id, 0)
    if current_time - last_seen > TTL_SECONDS:
        raise HTTPException(status_code=404, detail="Node offline (TTL expired)")
        
    return registered_nodes[node_id]
