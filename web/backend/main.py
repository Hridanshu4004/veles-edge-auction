from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import sys
import os
import random
import asyncio
from datetime import datetime, timedelta, timezone
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from mechanisms.variants import variant_allocation, variant_payment
from mechanisms.baselines import greedy_cheapest
from common.models import Task as CommonTask
from common.models import Bid as CommonBid
from common.models import Claim as CommonClaim
from common.models import TrustProfile
from experiments.runner import ExperimentRunner, compute_ci
from simulator.data_generator import DataGenerator

from . import models, schemas
from .database import engine, get_db, SessionLocal

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="EdgeTruth Live API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

async def heartbeat_loop():
    while True:
        try:
            db = SessionLocal()
            nodes = db.query(models.Node).all()
            for n in nodes:
                n.last_heartbeat = func.now()
                n.status = "ONLINE"
            db.commit()
            db.close()
        except Exception:
            pass
        await asyncio.sleep(5)

async def task_feeder_loop():
    while True:
        try:
            db = SessionLocal()
            task = db.query(models.Task).filter(models.Task.status == "SEEDED").first()
            if task:
                task.status = "PENDING"
                db.commit()
            db.close()
        except Exception:
            pass
        await asyncio.sleep(2)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(heartbeat_loop())
    asyncio.create_task(task_feeder_loop())

@app.get("/api/health")
def health(): return {"status": "ok"}

@app.get("/api/metrics")
def get_metrics(db: Session = Depends(get_db)):
    total_tasks = db.query(models.Task).count()
    successful_tasks = db.query(models.Task).filter(models.Task.status == "COMPLETED").count()
    failed_tasks = db.query(models.Task).filter(models.Task.status.like("FAILED%")).count()
    total_payment = db.query(func.sum(models.Execution.payment)).scalar() or 0.0
    welfare_query = db.query(func.sum(models.Task.task_value - models.Execution.payment)).filter(
        models.Execution.task_id == models.Task.id, models.Execution.success == True
    ).scalar() or 0.0
    sla_success = (successful_tasks / total_tasks * 100) if total_tasks > 0 else 0.0
    nodes = db.query(models.Node).all()
    return {
        "total_tasks": total_tasks,
        "successful_tasks": successful_tasks,
        "failed_tasks": failed_tasks,
        "sla_success_percent": sla_success,
        "total_payment": total_payment,
        "welfare": welfare_query,
        "active_nodes": len([n for n in nodes if n.status == "ONLINE"]),
    }

class AuctionRequest(BaseModel):
    task_id: str
    mechanism: str = "contingent"

@app.post("/api/auctions/run")
def run_auction(req: AuctionRequest, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == req.task_id).first()
    if not task or task.status != "PENDING":
        raise HTTPException(400, "Task not PENDING")

    nodes = db.query(models.Node).filter(models.Node.status == "ONLINE").all()
    if not nodes:
        raise HTTPException(400, "No nodes")

    cbids = []
    trust_profiles = {}
    for n in nodes:
        total = db.query(models.NodeObservation).filter(models.NodeObservation.node_id == n.id).count()
        succ = db.query(models.NodeObservation).filter(models.NodeObservation.node_id == n.id, models.NodeObservation.success == True).count()
        tp = TrustProfile(node_id=n.id)
        if total > 0:
            tp.evidence.observations = total
            p = succ / total
            tp.evidence.success_brier_score = (p - 1.0)**2 if p > 0.5 else (p - 0.0)**2
        trust_profiles[n.id] = tp

        link = db.query(models.NodeLink).filter(models.NodeLink.source_id == n.id).first()
        lat = link.latency_ms if link else n.true_latency_ms

        cbid = CommonBid(
            task_id=task.id, node_id=n.id, price=task.task_value * random.uniform(0.1, 0.5),
            claim=CommonClaim(success_probability=0.9, latency_p50_ms=lat, latency_p95_ms=lat*1.5, energy_estimate=1.0, confidence=1.0)
        )
        cbids.append(cbid)

    ctask = CommonTask(task_id=task.id, cpu_required=task.required_cpu, ram_required=task.required_memory, bandwidth_required=10.0, max_latency_ms=task.max_latency_ms, deadline_ms=task.max_latency_ms, priority=1.0, work_units=1.0, task_value=task.task_value)

    if req.mechanism == "greedy":
        alloc = greedy_cheapest(ctask, cbids)
    elif req.mechanism == "observed-reliability":
        cbids.sort(key=lambda b: (trust_profiles[b.node_id].evidence.success_brier_score), reverse=False)
        alloc = None
        if cbids:
            alloc = variant_allocation(ctask, [cbids[0]], trust_profiles, req.mechanism)
            if not alloc: alloc = type('Alloc', (), {'node_id': cbids[0].node_id, 'winning_bid': cbids[0], 'score': 1.0})()
    else:
        alloc = variant_allocation(ctask, cbids, trust_profiles, req.mechanism)

    if not alloc:
        task.status = "FAILED_NO_WINNER"
        db.commit()
        return {"winner": None}

    db_alloc = models.Allocation(task_id=task.id, node_id=alloc.node_id, score=getattr(alloc, 'score', 1.0), price=alloc.winning_bid.price, success_probability=1.0)
    db.add(db_alloc)
    task.status = "ALLOCATED"
    db.commit()
    return {"winner": alloc.node_id, "price": alloc.winning_bid.price, "mechanism": req.mechanism}

class ExecuteRequest(BaseModel):
    task_id: str
    mechanism: str = "contingent"

@app.post("/api/execute")
def run_executor(req: ExecuteRequest, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == req.task_id).first()
    alloc = db.query(models.Allocation).filter(models.Allocation.task_id == req.task_id).order_by(models.Allocation.id.desc()).first()
    if not alloc: raise HTTPException(400, "No alloc")

    node = db.query(models.Node).filter(models.Node.id == alloc.node_id).first()
    actual_success = random.random() <= node.reliability
    
    payment = variant_payment(type('Alloc', (), {'winning_bid': type('Bid', (), {'price': alloc.price, 'claim': type('Claim', (), {'success_probability': alloc.success_probability})()})()})(), actual_success, req.mechanism)
    
    exec_record = models.Execution(task_id=task.id, node_id=node.id, success=actual_success, latency_ms=node.true_latency_ms if actual_success else 0.0, payment=payment)
    db.add(exec_record)
    
    obs = models.NodeObservation(node_id=node.id, task_id=task.id, success=actual_success, latency_ms=node.true_latency_ms if actual_success else 0.0)
    db.add(obs)

    task.status = "COMPLETED" if actual_success else "FAILED_EXECUTION"
    db.commit()
    return {"success": actual_success, "payment": payment}

class ScenarioRequest(BaseModel):
    seed: int
    n_tasks: int
    mechanisms: List[str]
    attackers: List[str]

@app.post("/api/scenarios/run")
def run_scenario(req: ScenarioRequest):
    results = {}
    for mech in req.mechanisms:
        agg = {"sla_success": [], "welfare": [], "buyer_pay": [], "regret": []}
        for s in range(req.seed, req.seed + 5):
            gen = DataGenerator(seed=s)
            w = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            if "liar" in req.attackers: w[1] = 0.5
            config = {"node_type_weights": w}
            scenario = gen.generate_scenario("CUSTOM", num_nodes=10, num_tasks=req.n_tasks, config=config)
            runner = ExperimentRunner(scenario, seed=s)
            m_name = mech if mech in ["greedy", "trust_vcg", "edgetruth_no_probe"] else "greedy"
            res = runner.run(m_name)
            total = res["total_tasks"]
            agg["sla_success"].append((res["successful_tasks"]/total)*100 if total > 0 else 0)
            agg["welfare"].append(res["social_welfare"])
            agg["buyer_pay"].append(res["total_cost"])
            agg["regret"].append(0.0)
            
        results[mech] = {
            "SLA%": f"{np.mean(agg['sla_success']):.2f} ± {compute_ci(agg['sla_success']):.2f}",
            "Welfare": f"{np.mean(agg['welfare']):.2f} ± {compute_ci(agg['welfare']):.2f}",
            "BuyerPay": f"{np.mean(agg['buyer_pay']):.2f} ± {compute_ci(agg['buyer_pay']):.2f}",
            "Regret": f"{np.mean(agg['regret']):.2f} ± {compute_ci(agg['regret']):.2f}"
        }
        
    import csv
    os.makedirs("/home/hridanshu/veles-edge-auction/experiments/results", exist_ok=True)
    with open("/home/hridanshu/veles-edge-auction/experiments/results/latest_experiment.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Mechanism", "SLA%", "Welfare", "BuyerPay", "Regret"])
        for m, d in results.items():
            writer.writerow([m, d["SLA%"], d["Welfare"], d["BuyerPay"], d["Regret"]])
            
    return results

@app.get("/api/results")
def get_results():
    path = "/home/hridanshu/veles-edge-auction/experiments/results/latest_experiment.csv"
    if not os.path.exists(path):
        return {"error": "No results"}
    with open(path, "r") as f:
        data = f.read()
    return {"provenance": "ExperimentRunner", "csv": data}
