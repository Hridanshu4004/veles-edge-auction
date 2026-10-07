# Data Model & Provenance

## Node Links Latency (DERIVED)
Latency between nodes is computed via Haversine distance:
`latency_ms = distance_km * 0.02 + 5.0`
Range in current DB: min=5.0ms, max=335.2ms, mean=121.8ms.

## Task max_latency_ms (SYNTHETIC)
Azure 2019 provides only: function arrivals (real), execution durations (real), memory (real).
`task_value` and `max_latency_ms` are SYNTHETIC:
- `max_latency_ms` = max(Azure duration_ms, 200ms floor).
  Floor prevents infeasibility vs derived link latencies (5–335ms).
- `task_value` = uniform(1, 100) [SYNTHETIC].
- 500 tasks from Azure 2019 DEV split: 500 feasible (≥ min link latency), 0 infeasible.

## Node Attributes (REAL + SYNTHETIC)
- Country, Lat, Lon, IP: REAL — WS-DREAM dataset (339 users, 5825 services).
- node_id, name: WS-DREAM UserID/IP.
- cost, reliability, capacity_cpu, capacity_memory: SYNTHETIC (uniform random).
