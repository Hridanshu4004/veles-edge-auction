from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional
import sys, os, random, asyncio, csv
from datetime import datetime, timedelta, timezone
import numpy as np
from scipy import stats as scipy_stats

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from mechanisms.variants import variant_allocation, variant_payment
from mechanisms.baselines import greedy_cheapest
from common.models import Task as CommonTask, Bid as CommonBid, Claim as CommonClaim, TrustProfile
from experiments.runner import ExperimentRunner, compute_ci
from simulator.data_generator import DataGenerator

from . import models
from .database import engine, get_db, SessionLocal

models.Base.metadata.create_all(bind=engine)

MECH_RENAME = {
    "trust-ranked_vcg": "trust-ranked allocation + proper-scoring",
    "greedy": "greedy",
    "contingent": "contingent",
    "capped": "capped",
    "proper_scoring": "proper-scoring",
    "audits": "audits",
    "observed_rel_contingent": "observed-reliability + contingent",
}

# Global state for current live mechanism
LIVE_MECHANISM = "observed-reliability + contingent"

def ci95(arr):
    a = np.array(arr, dtype=float)
    n = len(a)
    if n < 2: return 0.0
    return float(scipy_stats.sem(a) * scipy_stats.t.ppf(0.975, n - 1))

def load_real_regret():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    path = os.path.join(repo_root, "experiments", "results", "regret_aggregated.csv")
    if not os.path.exists(path):
        return {}
    result = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            result[row["mechanism"]] = {
                "mean": float(row["regret_mean"]),
                "ci95": float(row["regret_ci95"]),
                "n_seeds": int(row["n_seeds"]),
            }
    return result

app = FastAPI(title="EdgeTruth Live API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

async def heartbeat_loop():
    while True:
        try:
            db = SessionLocal()
            db.query(models.Node).update({"status": "ONLINE", "last_heartbeat": func.now()})
            db.commit()
            db.close()
        except Exception:
            pass
        await asyncio.sleep(5)

async def task_worker_loop():
    while True:
        try:
            db = SessionLocal()
            # 1. Move a seeded task to pending
            seeded = db.query(models.Task).filter(models.Task.status == "SEEDED").first()
            if seeded:
                seeded.status = "PENDING"
                db.commit()
            
            # 2. Process a pending task
            task = db.query(models.Task).filter(models.Task.status == "PENDING").first()
            if task:
                # Auction
                nodes = db.query(models.Node).filter(models.Node.status == "ONLINE").all()
                if nodes:
                    cbids, trust_profiles = [], {}
                    for n in nodes:
                        total = db.query(models.NodeObservation).filter(models.NodeObservation.node_id == n.id).count()
                        succ = db.query(models.NodeObservation).filter(models.NodeObservation.node_id == n.id, models.NodeObservation.success == True).count()
                        tp = TrustProfile(node_id=n.id)
                        if total > 0:
                            tp.evidence.observations = total
                            p = succ / total
                            tp.evidence.success_brier_score = (p - 1.0)**2 if p > 0.5 else p**2
                        trust_profiles[n.id] = tp
                        link = db.query(models.NodeLink).filter(models.NodeLink.source_id == n.id).first()
                        lat = link.latency_ms if link else n.true_latency_ms
                        cbids.append(CommonBid(
                            task_id=task.id, node_id=n.id, price=task.task_value * random.uniform(0.1, 0.5),
                            claim=CommonClaim(success_probability=0.9, latency_p50_ms=lat, latency_p95_ms=lat * 1.5, energy_estimate=1.0, confidence=1.0)
                        ))

                    ctask = CommonTask(task_id=task.id, cpu_required=task.required_cpu, ram_required=task.required_memory, bandwidth_required=10.0, max_latency_ms=task.max_latency_ms, deadline_ms=task.max_latency_ms, priority=1.0, work_units=1.0, task_value=task.task_value)
                    
                    if LIVE_MECHANISM == "greedy":
                        alloc = greedy_cheapest(ctask, cbids)
                    else:
                        alloc = variant_allocation(ctask, cbids, trust_profiles, LIVE_MECHANISM)
                    
                    if not alloc:
                        task.status = "FAILED_NO_WINNER"
                    else:
                        task.status = "ALLOCATED"
                        db.add(models.Allocation(task_id=task.id, node_id=alloc.node_id, score=getattr(alloc, "score", 1.0), price=alloc.winning_bid.price, success_probability=1.0))
                        db.commit() # save alloc

                        # Execute
                        node = db.query(models.Node).filter(models.Node.id == alloc.node_id).first()
                        actual_success = random.random() <= (node.reliability or 0.85)
                        actual_latency = node.true_latency_ms if actual_success else 0.0

                        class _Alloc:
                            node_id = alloc.node_id
                            class winning_bid:
                                price = alloc.winning_bid.price
                                class claim:
                                    success_probability = 1.0

                        payment = variant_payment(_Alloc(), actual_success, LIVE_MECHANISM)
                        db.add(models.Execution(task_id=task.id, node_id=node.id, success=actual_success, latency_ms=actual_latency, payment=payment))
                        db.add(models.NodeObservation(node_id=node.id, task_id=task.id, success=actual_success, latency_ms=actual_latency))
                        task.status = "COMPLETED" if actual_success else "FAILED_EXECUTION"
                        
                        # Save event
                        db.add(models.Event(task_id=task.id, event_type="EXECUTION", description=f"Executed on {node.id}, success={actual_success}, payment={payment:.2f}"))

                db.commit()
            db.close()
        except Exception as e:
            import traceback
            print("ERROR IN WORKER:", e)
            traceback.print_exc()
        await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(heartbeat_loop())
    asyncio.create_task(task_worker_loop())

@app.get("/", response_class=HTMLResponse)
def dashboard():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    with open(os.path.join(repo_root, "web", "backend", "dashboard.html")) as f:
        return f.read()

@app.get("/api/health")
def health(): return {"status": "ok"}

class MechanismSwitch(BaseModel):
    mechanism: str
@app.post("/api/mechanism")
def switch_mechanism(req: MechanismSwitch):
    global LIVE_MECHANISM
    LIVE_MECHANISM = req.mechanism
    return {"status": "success", "mechanism": LIVE_MECHANISM}

@app.get("/api/metrics")
def get_metrics(db: Session = Depends(get_db)):
    total_tasks = db.query(models.Task).count()
    successful_tasks = db.query(models.Task).filter(models.Task.status == "COMPLETED").count()
    failed_tasks = db.query(models.Task).filter(models.Task.status.like("FAILED%")).count()
    pending_tasks = db.query(models.Task).filter(models.Task.status == "PENDING").count()
    seeded_tasks = db.query(models.Task).filter(models.Task.status == "SEEDED").count()
    total_payment = db.query(func.sum(models.Execution.payment)).scalar() or 0.0
    welfare_query = db.query(func.sum(models.Task.task_value - models.Execution.payment)).filter(
        models.Execution.task_id == models.Task.id, models.Execution.success == True
    ).scalar() or 0.0
    sla_success = (successful_tasks / total_tasks * 100) if total_tasks > 0 else 0.0
    nodes = db.query(models.Node).all()
    events = db.query(models.Event).order_by(models.Event.id.desc()).limit(5).all()
    return {
        "live_mechanism": LIVE_MECHANISM,
        "total_tasks": total_tasks,
        "successful_tasks": successful_tasks,
        "failed_tasks": failed_tasks,
        "pending_tasks": pending_tasks,
        "seeded_tasks": seeded_tasks,
        "sla_success_percent": round(sla_success, 2),
        "total_payment": round(total_payment, 4),
        "welfare": round(float(welfare_query), 4),
        "active_nodes": len([n for n in nodes if n.status == "ONLINE"]),
        "total_nodes": len(nodes),
        "recent_events": [{"task": e.task_id, "desc": e.description} for e in events]
    }

@app.get("/api/nodes")
def get_nodes(db: Session = Depends(get_db)):
    return [{"id": n.id, "country": n.country, "lat": n.lat, "lon": n.lon, "status": n.status, "cost": n.cost, "reliability": n.reliability} for n in db.query(models.Node).all()]

@app.get("/api/tasks")
def get_tasks(db: Session = Depends(get_db)):
    tasks = db.query(models.Task).limit(50).all()
    return [{"id": t.id[:16]+"...", "task_value_SYNTHETIC": t.task_value, "max_latency_ms_SYNTHETIC": t.max_latency_ms, "required_cpu": t.required_cpu, "required_memory": t.required_memory, "status": t.status, "data_source": t.data_source} for t in tasks]

class ScenarioRequest(BaseModel):
    seed: int
    n_tasks: int
    mechanisms: List[str]
    attackers: List[str] = []

@app.post("/api/scenarios/run")
def run_scenario(req: ScenarioRequest):
    N_SEEDS = 20
    # TASK 3: "If capped uses greedy allocation by mistake, fix it or remove it from the comparison"
    # We remove 'capped' from comparison to avoid confusion since it uses greedy allocation.
    mechanisms = [m for m in req.mechanisms if m != "capped"]
    results = {}

    runner_map = {
        "greedy": "greedy",
        "observed-reliability + contingent": "edgetruth_no_probe",
        "trust-ranked allocation + proper-scoring": "trust_vcg",
    }

    greedy_sla_per_seed = []
    per_mech_sla = {m: [] for m in mechanisms}

    for s in range(req.seed, req.seed + N_SEEDS):
        w = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        if "liar" in req.attackers: w = [0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0]
        gen = DataGenerator(seed=s)
        scenario = gen.generate_scenario("CUSTOM", num_nodes=10, num_tasks=req.n_tasks, config={"node_type_weights": w})
        runner = ExperimentRunner(scenario, seed=s)

        for mech in mechanisms:
            rname = runner_map.get(mech, "greedy")
            res = runner.run(rname)
            total = res["total_tasks"] or 1
            sla = res["successful_tasks"] / total * 100
            per_mech_sla[mech].append(sla)
            if mech == "greedy":
                greedy_sla_per_seed.append(sla)

    real_regret = load_real_regret()

    for mech in mechanisms:
        vals = np.array(per_mech_sla[mech])
        greedy_vals = np.array(greedy_sla_per_seed)
        diffs = vals - greedy_vals
        diff_mean = float(np.mean(diffs))
        diff_ci = ci95(diffs)
        excludes_zero = (diff_mean - diff_ci > 0) or (diff_mean + diff_ci < 0)

        regret_str = "not measured"
        if mech in real_regret:
            r = real_regret[mech]
            regret_str = f"{r['mean']:.4f} ± {r['ci95']:.4f}"

        results[mech] = {
            "SLA%": f"{np.mean(vals):.2f} ± {ci95(vals):.2f}",
            "Regret (real)": regret_str,
            "Delta_vs_greedy": f"{diff_mean:+.2f} ± {diff_ci:.2f}",
            "CI_excludes_zero": excludes_zero,
            "seeds": N_SEEDS,
        }

    results_dir = os.path.join(os.path.dirname(__file__), "../../experiments/results")
    os.makedirs(results_dir, exist_ok=True)
    with open(os.path.join(results_dir, "latest_experiment.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Mechanism", "SLA%", "Regret (real)", "Delta_vs_greedy", "CI_excludes_zero"])
        for m, d in results.items():
            w.writerow([m, d["SLA%"], d["Regret (real)"], d["Delta_vs_greedy"], d["CI_excludes_zero"]])

    return results

@app.get("/api/results")
def get_results():
    results_dir = os.path.join(os.path.dirname(__file__), "../../experiments/results")
    regret_path = os.path.join(results_dir, "regret_aggregated.csv")
    scenario_path = os.path.join(results_dir, "latest_experiment.csv")

    regret_data = {}
    if os.path.exists(regret_path):
        with open(regret_path) as f:
            for row in csv.DictReader(f):
                regret_data[row["mechanism"]] = {
                    "regret": f"{float(row['regret_mean']):.4f} ± {float(row['regret_ci95']):.4f}",
                    "n_seeds": int(row["n_seeds"]),
                }

    scenario_csv = ""
    if os.path.exists(scenario_path):
        with open(scenario_path) as f:
            scenario_csv = f.read()

    return {
        "provenance": {
            "arrivals": "REAL — Azure 2019 DEV split",
            "durations": "REAL — Azure 2019 DEV split",
            "memory": "REAL — Azure 2019 DEV split",
            "node_locations": "REAL — WS-DREAM dataset",
            "node_costs_reliability": "SYNTHETIC",
            "task_value": "SYNTHETIC",
            "max_latency_ms": "SYNTHETIC (floored at 200ms vs derived link 5-335ms)",
            "link_latency": "DERIVED — Haversine distance * 0.02 + 5ms",
        },
        "real_regret": regret_data if regret_data else "not measured",
        "latest_scenario_csv": scenario_csv,
    }
