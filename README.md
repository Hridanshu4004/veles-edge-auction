# EdgeTruth

**"Don't trust the node. Price the promise."**

A trust-aware resource allocation control plane for dynamic edge computing environments. EdgeTruth treats execution outcomes as mathematical evidence, enabling dynamic reallocation in the presence of Sybil attacks, Win-Then-Drop strategies, and unreliable nodes.

**Veles Hack 2026 Challenge 4 Finalist Project.**

---

## The Problem
Edge nodes compete to execute tasks while reporting price and resource characteristics.
The central problem: **A node's reported reliability cannot automatically be trusted.**

## The EdgeTruth Idea
EdgeTruth estimates reliability from observed execution outcomes and incorporates expected failure risk into allocation.

```text
PROMISE → BID → AUCTION → EDGETRUTH ALLOCATION → EXECUTION → EVIDENCE → TRUST UPDATE
```

## Architecture
- **Control Plane**: Highly interactive, observable React + Vite SPA built to visualize live infrastructure (Nginx/React).
- **Auction Engine & API**: FastAPI/Python orchestrating the EdgeTruth auction algorithm.
- **Node Agents**: Dockerized distributed agents executing compute simulations and emitting heartbeats.
- **Persistence**: PostgreSQL preserving observation evidence and Bayesian Trust updates.

## Quickstart (Full Integration)

Bootstrap the entire stack deterministically using Docker Compose:

```bash
docker compose up --build -d
```

### Accessing the Control Plane
Navigate to: [http://localhost:8080/](http://localhost:8080/)
- **Overview**: Explore the live topology, real-time KPI strip, and event stream.
- **Adversarial Lab (`/demo`)**: Watch the EdgeTruth engine penalize manipulative node behavior (Win-Then-Drop) in real-time.

## The EdgeTruth Allocation Equation
The mechanism scores candidates by maximizing expected risk-adjusted utility:
`Score_i = p_i(V - P_i) - (1 - p_i)(V/2)`
Where `p_i` is the observed reliability derived from the Beta distribution of past execution successes/failures.
