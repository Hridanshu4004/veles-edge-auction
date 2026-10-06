# Phase 2: Security & Edge Conditions
## Step 2: Incentive-Compatibility (Regret) Experiment Results

### Overview
This document summarizes the strengthened regret measurement for incentive-compatibility on the DEV split, using 30 seeds and 30 nodes per seed (totaling 900 node-samples per mechanism). The evaluation incorporates ground-truth task arrivals sourced from the Azure 2019 dataset and models multi-dimensional deviations (cost claim multiplier, capacity claim multiplier, and reliability report variations), as well as targeted attacks (win-then-drop, Sybil split, 2-node collusion).

### Trade-off Metrics
- **Welfare:** Global system value delivered minus the true execution cost.
- **Buyer Payment:** The total payment from the task buyer to the allocated nodes.
- **SLA Success Rate:** The proportion of tasks allocated that successfully executed (didn't drop or crash).
- **Norm J-Reg (Normalized Joint Regret):** Maximum utility gain from reporting non-truthfully over the multi-dimensional grid, normalized by the truthful payment.
- **IR Viol %:** The percentage of node-samples that experienced strictly negative utility under truthful bidding (Individual Rationality violation).
- **Pos-IR Reg:** Regret computed only over nodes with strictly non-negative truthful utility.
- **Part. Loss (Participation Loss):** Expected dropout loss due to negative truthful utility.

### Results Table

| Mechanism       | Norm J-Reg | IR Viol% | Pos-IR Reg | Part. Loss | Welfare | Buyer Pay | SLA%   | WTD Gain | Sybil Gn | Coll Gn |
|-----------------|------------|----------|------------|------------|---------|-----------|--------|----------|----------|---------|
| greedy          |     581.75 |     0.0% |       1.45 |       0.00 |    7850 |       244 |  88.2% |   -11.77 |    -0.15 |   -5.43 |
| trust_vcg       |   95406.34 |     2.6% |      89.50 |      13.25 |    8454 |       477 |  92.7% | -2892.00 |    -1.74 |  -12.73 |
| contingent      |   14012.52 |     0.6% |      21.17 |       0.02 |    8454 |       319 |  92.7% |  -156.88 |    -0.81 |   -6.86 |
| capped          |   19848.76 |     0.0% |      28.03 |       0.00 |    8454 |       336 |  92.7% |   -42.16 |    -0.80 |   -7.00 |
| proper_scoring  |  143549.43 |     0.0% |     163.45 |       0.00 |    8454 |      1198 |  92.7% |  -174.98 |     2.86 |    3.34 |
| audits          |  127564.41 |     0.1% |     142.81 |       0.28 |    8454 |      1160 |  92.7% |  -603.11 |     2.70 |    2.27 |

### Analysis

1. **Efficiency Trade-offs:**
   - The basic `greedy` mechanism is highly budget-efficient (lowest Buyer Pay) but suffers from lower welfare (7850) and lower SLA success (88.2%), indicating it is selecting unreliable or poorly-matched nodes.
   - All trust-aware variants improve SLA success to 92.7% and maximize welfare (8454), confirming the value of reputation tracking. However, this comes at the cost of higher Buyer Payments and differing degrees of regret vulnerability.

2. **Attack Vectors:**
   - **Win-Then-Drop (WTD):** Heavily penalized in mechanisms that condition payments or slash on success (e.g., `trust_vcg` at -2892, `audits` at -603).
   - **Sybil Split & Collusion:** Advanced scoring mechanisms (`proper_scoring`, `audits`) actually introduce positive gain vulnerabilities to Sybil splits (~2.8) and 2-node collusion (~2.3 to 3.3). Trust-VCG and capped/contingent variants remain mostly robust against these.

3. **Honest Node IR Violation in Trust-VCG:**
   - **Observation:** `trust_vcg` exhibits the highest IR Violation % (2.6%) and a notable Participation Loss (13.25). Honest nodes frequently receive negative average utility.
   - **Explanation:** In the current implementation, `trust_vcg` applies aggressive Brier score penalties and strict slashing when a node fails a task. Since real-world edge nodes (even honest ones) naturally experience crashes (i.e., reliability < 100%), these arbitrary penalties are applied even when nodes report their reliability accurately. 
   - **VCG Property:** Because these penalties are independent of the standard VCG externality calculation and can drive net payments below cost, this mechanism is NOT standard VCG. It is a heuristically penalized variant that mathematically violates Individual Rationality for honest, imperfect nodes.
