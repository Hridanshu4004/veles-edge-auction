# Phase 2: Security & Edge Conditions
## Step 2: Incentive-Compatibility (Regret) Experiment Results

### Overview
This document summarizes the strengthened regret measurement for incentive-compatibility on the DEV split, using 30 seeds and 30 nodes per seed (totaling 900 node-samples per mechanism). 

**Provenance:** 
Azure2019 arrivals (DEV). Synthetic costs/rel/cap. WS-DREAM NOT used.

### Analyzed Attacks
- **Fake Reliability Claims:** Nodes claim higher or lower reliability than their true reliability to game scoring rules.
- **Win-then-drop:** Nodes claim high reliability and capacity to win a task, but intentionally drop it, saving execution costs.
- **Sybil Attack:** Nodes submit an extra bid at a 10% discount under a fake identity to manipulate pricing or secure extra tasks.
- **2-Node Collusion:** One node bids very high (e.g., 5x), the other bids low (0.5x), attempting to force VCG prices up or manipulate contingent rule thresholds.

### Claimed Properties
- **Win-then-drop and Fake Reliability resistance:** All mechanisms (except pure greedy) strongly disincentivize fake reliability and win-then-drop through slashing and/or contingent payments, as shown by negative attacker gains.
- **Proper Scoring Alignment:** Strict proper scoring rules mathematically align the expected payment peak with truthful reporting.
- **Observed Reliability resilience:** The `observed_rel_contingent` mechanism safely mitigates cheap-talk claims over time by ignoring fake claims entirely and allocating based on empirical Bayesian posterior.

### Unclaimed Properties (What we do NOT claim)
- We do NOT claim Sybil-proofness or Collusion-proofness for complex scoring rules (like proper scoring or simple audits at low penalty). These rules can exhibit positive gain vulnerabilities to sophisticated coordination.
- We do NOT claim that `trust-ranked_vcg` satisfies Individual Rationality (IR) for honest, imperfect nodes; honest nodes will sometimes face strictly negative utility due to slashing.

### Hypotheses & Falsification
1. **Hypothesis (Proper Scoring Alignment):** The genuinely proper scoring rule will maximize expected payment exactly when claimed reliability equals true reliability.
   - *Falsification:* If empirical results show a reliable node gaining higher utility by claiming 20% lower than truth, the rule is broken or miscalibrated.
2. **Hypothesis (Audit Bound):** There exists a finite penalty factor (p*F) such that Sybil and Collusion attacks yield strictly negative expected gains under the audit mechanism.
   - *Falsification:* If no reasonably bounded F (e.g., F < 1000) achieves negative gain, or if making them negative causes buyer payments to explode beyond reasonable limits, the audit mechanism is fundamentally vulnerable.
3. **Hypothesis (Observed Rel Dominance):** A mechanism allocating strictly by Bayesian observed reliability will equal or outperform claim-based allocation after a short burn-in period.
   - *Falsification:* If the `tasks_until_beat` metric never fires, or if `observed_rel_contingent` yields significantly worse SLA% on the DEV split, then the burn-in cost is too high for edge environments.
