# Phase 3: Mechanism Evaluation Results

## Performance under MIXED_ADVERSARY Scenario

| Mechanism | Allocations | Success | SLA Violations | Total Cost | Social Welfare | Attacker Profit |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **greedy** | 500.0 | 439.32 | 109.72 | 3739.57 | 176689.34 | -17637.82 |
| **edgetruth_no_probe** | 500.0 | 462.68 | 65.78 | -8275.35 | 207449.40 | -24840.58 |
| **trust_vcg** | 499.8 | 468.88 | 63.8 | 54947.86 | 205739.07 | 27279.92 |

## Hypothesis Validation

1. **Incentive Compatibility Regret**: **FAILED.** As shown in the data above, Attacker Profit in `trust_vcg` is hugely positive (+27,279) compared to `greedy` (-17,637). This occurs because VCG overpays the winner based on the marginal harm to the rest of the network. If an attacker manages to spoof a high reliability claim alongside a high baseline task value ($V=1000$), the VCG payment formula `payment = (p_eff_winner - p_eff_runner) * V + bid_runner` skyrockets, heavily subsidizing liars. We failed to defend against this because our slashing penalty ($F=500$) is smaller than the enormous VCG surplus they extract.
2. **Social Welfare vs Baselines**: **PASSED.** `trust_vcg` achieves substantially higher Social Welfare (205,739) than the `greedy` baseline (176,689) by penalizing unreliable nodes during the auction and correctly allocating critical tasks to high-reliability nodes. It slightly underperforms `edgetruth_no_probe` because of VCG edge cases dropping a few tasks.
3. **Budget Deficit**: **FAILED (As expected).** The VCG mechanism results in an astronomical Total Cost (54,947) compared to Greedy (3,739). The auctioneer runs a massive deficit, confirming our assumption that VCG procurement is not budget-balanced.
