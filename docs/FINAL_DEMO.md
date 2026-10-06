# EdgeTruth — 60-Second Demo Flow

## STEP 1 — Problem
"Cheapest does not necessarily mean cheapest in expectation."
The system receives a stream of edge computing tasks. It must assign them to nodes. Naive allocators simply pick the node with the lowest bid. But if that node is unreliable, the task fails, SLAs are breached, and the system loses economic value.

## STEP 2 — Node behavior
We visualize our network of edge nodes. Some nodes have excellent historical reliability. Others have a history of intermittent failures or dropping tasks to save power.

## STEP 3 — Bidding
For a high-value task, all nodes submit a price bid. The highly reliable node submits a higher price. The unreliable node submits a low, attractive price. 

## STEP 4 — EdgeTruth
EdgeTruth ignores self-reported reliability promises. It calculates a risk-adjusted score:
`Score_i = p_i(V - P_i) - (1 - p_i)(V/2)`
using the node's empirically observed success rate `p_i`.

## STEP 5 — Allocation
Despite the higher price, the reliable node wins the task because the risk-adjusted expected utility to the buyer is mathematically higher. 

## STEP 6 — Failure/adversarial behavior
We simulate a node attempting a "Win-Then-Drop" Sybil attack: it bids cheaply, wins the task, and intentionally drops it to save compute costs.

## STEP 7 — Learning
Because EdgeTruth uses contingent payment, the node receives $0 for the dropped task. Simultaneously, the system updates its Bayesian posterior for that node, dropping its empirical `p_i`.

## STEP 8 — Future allocation
On the next task, the malicious node bids cheaply again. But its reduced `p_i` severely penalizes its EdgeTruth score. It loses the auction. It is economically quarantined.

## STEP 9 — Comparison
We compare the final dashboards. The naive Greedy baseline suffers a massive SLA penalty due to failures. EdgeTruth avoids the failures, achieving ~85% of theoretical omniscient welfare.

## STEP 10 — Conclusion
"A node can lie once. It cannot easily lie forever." EdgeTruth mathematically aligns economic risk with empirical evidence.
