from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any
import sys
import os
import random
from datetime import datetime, timedelta, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from mechanisms.edgetruth import edgetruth_allocation
from common.models import Task as CommonTask
from common.models import Bid as CommonBid
from common.models import Claim as CommonClaim

from . import models, schemas
from .database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="EdgeTruth Live API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "edgetruth-control-plane"}

@app.get("/api/nodes", response_model=List[schemas.NodeResponse])
def get_nodes(db: Session = Depends(get_db)):
    nodes = db.query(models.Node).all()
    now = datetime.now(timezone.utc)
    for n in nodes:
        if n.last_heartbeat:
            hb = n.last_heartbeat
            if hb.tzinfo is None:
                hb = hb.replace(tzinfo=timezone.utc)
            if now - hb > timedelta(seconds=30):
                n.status = "OFFLINE"
    db.commit()
    return nodes

@app.post("/api/nodes", response_model=schemas.NodeResponse)
def register_node(node: schemas.NodeCreate, db: Session = Depends(get_db)):
    db_node = db.query(models.Node).filter(models.Node.id == node.id).first()
    if db_node:
        db_node.last_heartbeat = func.now()
        db_node.status = "ONLINE"
    else:
        db_node = models.Node(**node.model_dump())
        db.add(db_node)
    db.commit()
    db.refresh(db_node)
    return db_node

@app.post("/api/nodes/{node_id}/heartbeat")
def node_heartbeat(node_id: str, db: Session = Depends(get_db)):
    db_node = db.query(models.Node).filter(models.Node.id == node_id).first()
    if db_node:
        db_node.last_heartbeat = func.now()
        db_node.status = "ONLINE"
        db.commit()
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Node not found")

@app.get("/api/tasks", response_model=List[schemas.TaskResponse])
def get_tasks(db: Session = Depends(get_db)):
    return db.query(models.Task).all()

@app.post("/api/tasks", response_model=schemas.TaskResponse)
def create_task(task: schemas.TaskCreate, db: Session = Depends(get_db)):
    db_task = models.Task(**task.model_dump())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.post("/api/auctions/run", response_model=schemas.AuctionRunResponse)
def run_auction(req: schemas.AuctionRunRequest, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == req.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "PENDING":
        raise HTTPException(status_code=400, detail="Task is not PENDING")

    nodes = db.query(models.Node).filter(models.Node.status == "ONLINE").all()
    if not nodes:
        raise HTTPException(status_code=400, detail="No online nodes available")

    def generate_bid_price(n: models.Node, t_val: float):
        if n.node_type == "LIAR": return t_val * random.uniform(0.1, 0.3)
        elif n.node_type == "STRATEGIC": return t_val * random.uniform(0.7, 0.9)
        elif n.node_type == "CHEAP_UNSTABLE": return t_val * random.uniform(0.2, 0.4)
        else: return t_val * random.uniform(0.4, 0.6)

    ctask = CommonTask(
        task_id=task.id,
        cpu_required=float(task.required_cpu),
        ram_required=float(task.required_memory),
        bandwidth_required=10.0,
        max_latency_ms=task.max_latency_ms,
        deadline_ms=task.max_latency_ms,
        priority=1.0,
        work_units=1.0,
        task_value=task.task_value
    )
    
    cbids = []
    observed_successes = {}
    observed_attempts = {}

    for node in nodes:
        total = db.query(models.NodeObservation).filter(models.NodeObservation.node_id == node.id).count()
        successes = db.query(models.NodeObservation).filter(
            models.NodeObservation.node_id == node.id,
            models.NodeObservation.success == True
        ).count()
        
        observed_attempts[node.id] = float(max(1, total))
        observed_successes[node.id] = float(successes)

        cclaim = CommonClaim(
            success_probability=1.0,
            latency_p50_ms=node.true_latency_ms,
            latency_p95_ms=node.true_latency_ms * 1.5,
            energy_estimate=1.0,
            confidence=1.0
        )
        
        cbid = CommonBid(
            task_id=task.id,
            node_id=node.id,
            price=generate_bid_price(node, task.task_value),
            claim=cclaim
        )
        cbids.append(cbid)

    allocation = edgetruth_allocation(
        task=ctask,
        bids=cbids,
        observed_successes=observed_successes,
        observed_attempts=observed_attempts
    )

    if allocation is None:
        task.status = "FAILED_NO_WINNER"
        db.commit()
        return schemas.AuctionRunResponse(
            task_id=task.id,
            winner=None,
            score=None,
            price=None,
            success_probability=None,
            mechanism="EdgeTruth"
        )

    posterior_p = observed_successes.get(allocation.node_id, 1.0) / observed_attempts.get(allocation.node_id, 1.0)

    db_alloc = models.Allocation(
        task_id=task.id,
        node_id=allocation.node_id,
        score=allocation.score,
        price=allocation.winning_bid.price,
        success_probability=posterior_p
    )
    db.add(db_alloc)
    
    task.status = "ALLOCATED"
    db.commit()

    return schemas.AuctionRunResponse(
        task_id=task.id,
        winner=allocation.node_id,
        score=allocation.score,
        price=allocation.winning_bid.price,
        success_probability=posterior_p,
        mechanism="EdgeTruth"
    )

@app.post("/api/executions", response_model=schemas.ExecutionResponse)
def run_execution(req: schemas.ExecutionRequest, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == req.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    alloc = db.query(models.Allocation).filter(models.Allocation.task_id == req.task_id, models.Allocation.node_id == req.node_id).order_by(models.Allocation.id.desc()).first()
    if not alloc:
        raise HTTPException(status_code=400, detail="No allocation found for this node and task")

    payment = alloc.price if req.success else 0.0

    exec_record = models.Execution(
        task_id=req.task_id,
        node_id=req.node_id,
        success=req.success,
        latency_ms=req.latency_ms,
        payment=payment
    )
    db.add(exec_record)

    obs_record = models.NodeObservation(
        node_id=req.node_id,
        task_id=req.task_id,
        success=req.success,
        latency_ms=req.latency_ms
    )
    db.add(obs_record)

    task.status = "COMPLETED" if req.success else "FAILED_EXECUTION"
    db.commit()
    db.refresh(exec_record)

    return exec_record

@app.get("/api/metrics")
def get_metrics(db: Session = Depends(get_db)):
    total_tasks = db.query(models.Task).count()
    successful_tasks = db.query(models.Task).filter(models.Task.status == "COMPLETED").count()
    failed_tasks = db.query(models.Task).filter(models.Task.status.like("FAILED%")).count()
    
    total_payment = db.query(func.sum(models.Execution.payment)).scalar() or 0.0
    
    welfare_query = db.query(func.sum(models.Task.task_value - models.Execution.payment)).filter(
        models.Execution.task_id == models.Task.id,
        models.Execution.success == True
    ).scalar() or 0.0

    sla_success = (successful_tasks / total_tasks * 100) if total_tasks > 0 else 0.0

    nodes = db.query(models.Node).all()
    active_nodes = len([n for n in nodes if n.status == "ONLINE"])
    
    total_cpu = sum(n.capacity_cpu for n in nodes if n.status == "ONLINE")
    total_mem = sum(n.capacity_memory for n in nodes if n.status == "ONLINE")

    return {
        "total_tasks": total_tasks,
        "successful_tasks": successful_tasks,
        "failed_tasks": failed_tasks,
        "sla_success_percent": sla_success,
        "total_payment": total_payment,
        "welfare": welfare_query,
        "active_nodes": active_nodes,
        "total_nodes": len(nodes),
        "total_cpu_cores": total_cpu,
        "total_memory_gb": round(total_mem / 1024, 2)
    }

@app.get("/api/analytics/node/{node_id}")
def get_node_analytics(node_id: str, db: Session = Depends(get_db)):
    obs = db.query(models.NodeObservation).filter(models.NodeObservation.node_id == node_id).all()
    allocs = db.query(models.Allocation).filter(models.Allocation.node_id == node_id).all()
    execs = db.query(models.Execution).filter(models.Execution.node_id == node_id).all()
    
    success_count = sum(1 for o in obs if o.success)
    total_count = len(obs)
    reliability = (success_count / total_count * 100) if total_count > 0 else 100.0
    
    earnings = sum(e.payment for e in execs)
    
    return {
        "node_id": node_id,
        "total_attempts": total_count,
        "successes": success_count,
        "failures": total_count - success_count,
        "reliability_percent": reliability,
        "auctions_won": len(allocs),
        "total_earnings": earnings,
        "posterior_alpha": 1 + success_count,
        "posterior_beta": 1 + (total_count - success_count)
    }

@app.get("/api/events")
def get_events(db: Session = Depends(get_db)):
    allocs = db.query(models.Allocation).order_by(models.Allocation.id.desc()).limit(20).all()
    execs = db.query(models.Execution).order_by(models.Execution.id.desc()).limit(20).all()
    
    events = []
    for a in allocs:
        events.append({"type": "ALLOCATION", "time": a.created_at, "msg": f"Task {a.task_id} allocated to {a.node_id} (Score: {a.score:.2f})"})
    for e in execs:
        status = "SUCCEEDED" if e.success else "FAILED"
        events.append({"type": "EXECUTION", "time": e.created_at, "msg": f"Execution {status}: {e.node_id} processed {e.task_id} (Lat: {e.latency_ms}ms)"})
    
    events.sort(key=lambda x: x["time"], reverse=True)
    return events[:20]

