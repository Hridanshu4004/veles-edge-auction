# EdgeTruth
## Don't trust the node. Price the promise.

### 1. Problem
Edge nodes compete to execute tasks while reporting price and resource characteristics. 
The central problem: **A node's reported reliability cannot automatically be trusted.**

### 2. EdgeTruth Idea
EdgeTruth estimates reliability from observed execution outcomes and incorporates expected failure risk into allocation.

```text
    Node bids
        ↓
    Historical execution evidence
        ↓
    Estimated success probability
        ↓
    Risk-adjusted economic score
        ↓
    Winner selection
        ↓
    Contingent execution payment
        ↓
    Outcome becomes new evidence
```

### 3. Core Mechanism
The implemented allocation equation is:
`Score_i = p_i(V - P_i) - (1 - p_i)(V/2)`

Where:
- `p_i`: The empirical Bayesian probability of successful execution (dimensionless).
- `V`: The monetary task value ($).
- `P_i`: The monetary bid price of the node ($).

The score is measured strictly in monetary units.

### 4. Why It Matters
Choosing only the cheapest node can be dangerous:
```text
    Cheap unreliable node
        → failure
        → retry
        → SLA loss
        → hidden cost
```
versus:
```text
    Risk-aware node selection
        → higher immediate price if justified
        → lower expected failure loss
```

### 5. Architecture
```text
    Task Generator
          ↓
    Auction / Allocation
          ↓
    EdgeTruth
          ↓
    Node Agents
          ↓
    Execution Outcome
          ↓
    Reliability Evidence
          ↺
```

### 6. Complexity
EdgeTruth allocation is O(N) per task.

### 7. Evaluation
We evaluated EdgeTruth using 30 random seeds, running compute-heavy workloads derived from the Azure 2019 dataset trace. We benchmarked it against a Greedy allocator baseline and adversarial nodes employing Win-Then-Drop strategies.

EdgeTruth substantially improves SLA fulfillment by avoiding failures, and achieves ~85% of the theoretical welfare of an omniscient oracle, all while paying nodes via a contingent payment rule to naturally align incentives.

### 8. Security / Adversarial Evaluation
**TESTED**:
- Win-Then-Drop Sybil behavior
- 2-node collusion
- 3-node collusion
- 5-node collusion
- multidimensional misreporting
- failure scenarios

**NOT CLAIMED**:
- We do not claim the mechanism is universally attack-proof.

### 9. Limitations
- Fresh identities currently receive optimistic initialization.
- Complete Sybil-proofness is not claimed.
- Price bidding remains strategic.
- Collusion resistance is empirical for tested strategies.
- Runtime benchmark is not claimed.
- Highly reliable nodes can extract surplus through price inflation.
- Results are based on the evaluated workloads and threat models.

### 10. Run
`make demo`

This will:
1. Initialize deterministic execution seeds.
2. Run the EdgeTruth simulation over 300 Azure tasks.
3. Write the results to `experiments/results/edgetruth_final.csv`.
4. Generate the `dashboard.html` visualizer.

### 11. Final Status
EdgeTruth is the final mechanism used by the submission demo.
Historical mechanisms in `/mechanisms/` are retained only for analytical provenance.
