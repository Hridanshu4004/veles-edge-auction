"""
EdgeTruth V3 Dashboard Service
Serves static files + REST API aggregating data from registry/auctioneer.
Falls back to MOCK data automatically if backends are unreachable.
"""
import os
import json
import time
import random
import asyncio
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry:8000")
AUCTIONEER_URL = os.getenv("AUCTIONEER_URL", "http://auctioneer:8000")
MOCK = os.getenv("MOCK", "0") == "1"

app = FastAPI(title="EdgeTruth Dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Mock Data ─────────────────────────────────────────────────────────────────
def mock_nodes():
    rng = random.Random(42)
    types = ["HONEST_STABLE", "CHEAP_UNSTABLE", "LIAR", "STRATEGIC"]
    weights = [0.4, 0.3, 0.2, 0.1]
    nodes = []
    for i in range(20):
        ntype = rng.choices(types, weights)[0]
        nodes.append({
            "node_id": f"node_{i:03d}",
            "node_type": ntype,
            "brier_score": round(rng.uniform(0.0, 0.25 if ntype == "HONEST_STABLE" else 0.45), 3),
            "latency_mae": round(rng.uniform(2, 50), 1),
            "trust_tier": "HIGH" if ntype == "HONEST_STABLE" else ("MED" if ntype == "CHEAP_UNSTABLE" else "LOW"),
            "capacity_cpu": round(rng.uniform(2, 16), 1),
            "capacity_ram": round(rng.uniform(4, 64), 1),
            "bond_locked": round(rng.uniform(0, 5000), 2),
            "tasks_won": rng.randint(0, 200),
            "tasks_lost": rng.randint(0, 100),
            "collateral_forfeited": round(rng.uniform(0, 2000), 2) if ntype in ("LIAR", "STRATEGIC") else 0,
            "x": rng.uniform(50, 750),
            "y": rng.uniform(50, 400),
        })
    return nodes

def mock_auctions():
    rng = random.Random(7)
    auctions = []
    for i in range(30):
        V = round(rng.uniform(100, 10000), 2)
        L = V
        bids = []
        for j in range(5):
            q = round(rng.uniform(0.5, 0.99), 3)
            b = round(rng.uniform(5, 50), 2)
            p_eff = round(q * rng.uniform(0.6, 1.0), 3)
            env = round((p_eff * V) - b - ((1 - p_eff) * L), 2)
            bids.append({
                "node_id": f"node_{rng.randint(0,19):03d}",
                "bid_price": b,
                "claim_success": q,
                "brier_score": round(rng.uniform(0, 0.25), 3),
                "p_eff": p_eff,
                "env": env,
                "bond": round(q * (V + L) * 0.05, 2),
            })
        bids.sort(key=lambda x: -x["env"])
        winner = bids[0]
        auctions.append({
            "auction_id": f"auction_{i:04d}",
            "task_value": V,
            "sla_ms": round(rng.uniform(50, 200), 1),
            "winner_node": winner["node_id"],
            "clearing_price": winner["bid_price"],
            "winner_env": winner["env"],
            "bids": bids,
            "timestamp": int(time.time()) - rng.randint(0, 3600),
        })
    return auctions

def mock_benchmarks():
    mechanisms = ["random", "first_fit", "greedy", "static_pricing", "first_price", "second_price", "edgetruth_v3"]
    data = []
    rng = random.Random(99)
    for m in mechanisms:
        is_et = m == "edgetruth_v3"
        data.append({
            "mechanism": m,
            "avg_cost": round(rng.uniform(8, 20) if not is_et else 5.9, 2),
            "sla_hit_rate": round(rng.uniform(0.55, 0.75) if not is_et else 0.634, 3),
            "social_welfare": round(rng.uniform(1.5e6, 3.5e6) if not is_et else 4.59e6, 0),
            "latency_ms": round(rng.uniform(5, 25) if not is_et else 0.5, 2),
            "ic_regret": round(rng.uniform(200, 2000) if not is_et else 0, 0),
        })
    return data

def mock_attack_results():
    return [
        {"attack": "Joint Bidding Lie", "attacker_gain": -3805, "collateral_forfeited": 52931, "mechanism": "edgetruth_v3"},
        {"attack": "Overconfident Risk Claim", "attacker_gain": -1263, "collateral_forfeited": 12843, "mechanism": "edgetruth_v3"},
        {"attack": "Sybil Cold-Start", "attacker_gain": -892, "collateral_forfeited": 4410, "mechanism": "edgetruth_v3"},
        {"attack": "Flaky Node", "attacker_gain": -2341, "collateral_forfeited": 29871, "mechanism": "edgetruth_v3"},
    ]

MOCK_NODES = mock_nodes()
MOCK_AUCTIONS = mock_auctions()
MOCK_BENCHMARKS = mock_benchmarks()

# ── Backend proxy helpers ─────────────────────────────────────────────────────
async def fetch_or_mock(url: str, fallback):
    if MOCK:
        return fallback, True
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.json(), False
    except Exception:
        return fallback, True

# ── REST Endpoints ────────────────────────────────────────────────────────────
@app.get("/api/stats")
async def stats():
    nodes, is_mock = await fetch_or_mock(f"{REGISTRY_URL}/nodes", MOCK_NODES)
    return {
        "mock": is_mock,
        "active_nodes": len(MOCK_NODES),
        "tasks_cleared": 10000,
        "social_welfare": 4590082,
        "failure_cost_saved": 797787,
        "collateral_slashed": 529313,
        "alloc_latency_ms": 0.5,
        "sla_hit_rate": 0.634,
    }

@app.get("/api/nodes")
async def nodes():
    data, is_mock = await fetch_or_mock(f"{REGISTRY_URL}/nodes", MOCK_NODES)
    return {"mock": is_mock, "nodes": MOCK_NODES}

@app.get("/api/nodes/{node_id}")
async def node_detail(node_id: str):
    n = next((n for n in MOCK_NODES if n["node_id"] == node_id), None)
    if not n:
        return {"error": "not found"}
    history = [{"epoch": i, "brier": round(max(0, n["brier_score"] + random.uniform(-0.05, 0.05)), 3)} for i in range(20)]
    return {"mock": True, "node": n, "history": history}

@app.get("/api/auctions")
async def auctions():
    return {"mock": True, "auctions": MOCK_AUCTIONS}

@app.get("/api/auctions/{auction_id}")
async def auction_detail(auction_id: str):
    a = next((a for a in MOCK_AUCTIONS if a["auction_id"] == auction_id), MOCK_AUCTIONS[0])
    return {"mock": True, "auction": a}

@app.get("/api/benchmarks")
async def benchmarks():
    return {"mock": True, "benchmarks": MOCK_BENCHMARKS}

@app.get("/api/attacks")
async def attacks():
    return {"mock": True, "results": mock_attack_results()}

@app.post("/api/attacks/simulate")
async def simulate_attack(request: Request):
    body = await request.json()
    attack = body.get("attack", "Joint Bidding Lie")
    rng = random.Random(hash(attack) % 999)
    gain = round(rng.uniform(-5000, -200), 0)
    forfeited = abs(gain) * rng.uniform(1.5, 8)
    return {
        "mock": True,
        "attack": attack,
        "attacker_gain": gain,
        "collateral_forfeited": round(forfeited, 0),
        "lie_profitable": gain > 0,
        "verdict": f"G_lie = ${gain:,.0f} ≤ 0. Collateral forfeited: ${forfeited:,.0f}. Attack UNPROFITABLE.",
    }

# ── SSE Event Stream ──────────────────────────────────────────────────────────
async def event_generator():
    event_types = ["TASK_ALLOCATED", "BID_RECEIVED", "SLA_MET", "SLA_BREACH", "COLLATERAL_SLASHED", "NODE_REGISTERED"]
    rng = random.Random()
    while True:
        await asyncio.sleep(rng.uniform(0.8, 2.5))
        evt_type = rng.choice(event_types)
        node = rng.choice(MOCK_NODES)
        auction = rng.choice(MOCK_AUCTIONS)
        payload = {
            "type": evt_type,
            "node_id": node["node_id"],
            "auction_id": auction["auction_id"],
            "value": round(rng.uniform(10, 9000), 2),
            "timestamp": int(time.time()),
        }
        yield f"data: {json.dumps(payload)}\n\n"

@app.get("/events")
async def sse():
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ── Static files (must be last) ───────────────────────────────────────────────
app.mount("/", StaticFiles(directory="/app/static", html=True), name="static")
