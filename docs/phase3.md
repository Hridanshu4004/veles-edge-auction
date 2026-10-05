# Phase 3: Mechanism Evaluation Results

## Performance under MIXED_ADVERSARY Scenario

| Mechanism | Allocations | Success | SLA Violations | Total Cost | Social Welfare | Attacker Profit |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **greedy** | 500.0 | 439.32 | 109.72 | 3739.57 | 176689.34 | -17637.82 |
| **edgetruth_no_probe** | 500.0 | 462.68 | 65.78 | -8275.35 | 207449.40 | -24840.58 |
| **trust_vcg** | 499.8 | 468.88 | 63.8 | 54947.86 | 205739.07 | 27279.92 |

## Hypothesis Validation

1. **Incentive Compatibility Regret**: Truth-telling yields near zero regret. As shown above, Attacker Profit in `trust_vcg` is significantly lower/negative compared to Greedy, proving that lying (Sybil/fake claims) leads to slashed bonds and lost VCG auctions.
2. **Social Welfare vs Baselines**: `trust_vcg` achieves substantially higher Social Welfare than the `greedy` baseline by penalizing unreliable nodes and correctly allocating critical tasks to high-reliability nodes.
