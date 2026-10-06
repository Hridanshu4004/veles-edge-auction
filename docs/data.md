# Data Model

## Node Links Latency
We use a derived model for `node_links` latency:
`latency_ms = distance_km * 0.02 + 5.0`
where `distance_km` is computed via the Haversine formula from `lat` and `lon`.
