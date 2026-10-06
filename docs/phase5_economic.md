# Phase 5: Reliability Premium and Economic Decision Rule

We eliminated the arbitrary `Alpha` parameter and the simple hardcoded thresholds, deriving a **unified, self-scaling economic decision rule** directly from the system's welfare definition.

### The Unified Economic Objective
The expected economic utility $EU_i$ for the buyer when selecting node $i$ under a contingent payment mechanism (where the buyer only pays $Price_i$ upon success) is:
$$EU_i = P_i(V_j - Price_i) - (1 - P_i) \times L_F$$
where $L_F$ is the penalty or loss incurred upon task failure. Since our system models a failure penalty of $0.5 \times V_j$, this becomes:
$$EU_i = P_i(V_j - Price_i) - (1 - P_i)(0.5 \times V_j)$$

This allocation rule naturally answers the question: *How much is reliability worth?*
For two nodes A and B, Node B's higher reliability ($P_B > P_A$) justifies its higher price ($Price_B > Price_A$) **only if**:
$$(P_B - P_A)(1.5 \times V_j) > P_B \times Price_B - P_A \times Price_A$$
This mathematically establishes that **the maximum premium scales linearly with the task value**. A $10 task justifies almost no premium for reliability, whereas a $5000 task justifies paying significantly higher prices to avoid the massive $0.5 \times V_j$ failure penalty.

### Phase 5A & 5C: Task-Value Regimes (Empirical Results)
We swept $V_j \in \{10, 50, 100, 500, 1000, 5000\}$ to observe if mechanisms automatically scale their risk sensitivity.

| Mechanism | $V_j$ | Welfare | SLA% | Avg Selected Price |
|---|---|---|---|---|
| `greedy` | 10 | 58 | 87.3% | $10.61 |
| `edgetruth` | 10 | 57 | 88.4% | $10.84 |
| `greedy` | 500 | 11965 | 87.3% | $10.61 |
| `edgetruth` | 500 | 12229 | 88.9% | $15.34 |
| `greedy` | 5000 | 121315 | 87.3% | $10.61 |
| `edgetruth` | 5000 | 124729 | 88.9% | $15.34 |

**Observations:**
1. **Greedy is static:** It always selects the cheapest node ($10.61), completely ignoring the massive failure penalty at high task values, resulting in static 87.3% SLA and lower welfare at scale.
2. **EdgeTruth (New Unified Rule) is self-scaling (Parameter-free):** It dynamically increases the average price it is willing to pay (from $10.84 to $15.34) as $V_j$ increases, buying more reliable nodes to protect the buyer from the failure penalty. It naturally caps out around $15.34 once the marginal cost of reliability exceeds the expected gain.
3. **No Overfitting (Phase 5B):** We completely removed the arbitrary `Alpha` parameter in favor of direct monetary expectation $E[Utility]$. Dimensional consistency is perfectly maintained (all terms are in raw $ units).
