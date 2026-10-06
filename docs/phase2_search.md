# Phase 2: Stronger Strategic Search

We performed a systematic multidimensional deviation search across the following grid for every node over 30 seeds (30 nodes per seed):
- **Price Multipliers:** 0.5, 1.0, 1.5, 2.0
- **Capacity Multipliers:** 0.5, 1.0, 2.0
- **Latency Multipliers:** 0.5, 1.0, 2.0
- **Reliability Claims:** -0.2, 0.0, +0.2

For each mechanism, we computed the maximum achievable utility for a node across all 108 multidimensional deviations and calculated the regret ($G_i = U_i(best) - U_i(truthful)$).

### Results

| Mechanism | Mean Regret | Median Regret | Max Regret | Pos-Regret Freq | Attacker Share |
|---|---|---|---|---|---|
| `greedy` | 0.7 ± 0.4 | 0.0 | 136.2 | 1.8% | 3.0% |
| `trust_ranked_vcg` | 107.1 ± 17.5 | 10.5 | 1381.4 | 38.8% | 14.2% |
| `contingent` | 18.9 ± 4.3 | 0.0 | 341.9 | 20.7% | 7.5% |
| `capped` | 24.5 ± 5.4 | 0.0 | 341.9 | 22.4% | 8.3% |
| `proper_scoring` | 68.8 ± 9.5 | 10.1 | 614.8 | 44.3% | 23.1% |
| `audits` | 24.6 ± 5.3 | 0.0 | 341.9 | 23.2% | 8.2% |
| `observed_rel_contingent` | 1.8 ± 0.5 | 0.0 | 191.0 | 7.2% | 3.1% |

**Analysis:**
- **`observed_rel_contingent`** strongly bounds the attacker's gains across all dimensions (Pos-Regret frequency of 7.2%, with nearly 0 median regret), second only to pure greedy but with much higher system reliability (as previously established).
- **`proper_scoring`** creates massive vulnerabilities to price/capacity/latency manipulation despite its rigorous theoretical guarantee for reliability reporting in isolation. Nearly 44.3% of nodes find profitable multidimensional deviations.
- **`trust_ranked_vcg`** exposes extreme regret (Max: 1381.4) due to the VCG pricing interacting poorly with capacity/latency misreporting under arbitrary SLA penalties.

**Conclusion:** Multidimensional deviations are highly profitable under the complex mechanisms, while the Bayesian posterior mechanism (`observed_rel_contingent`) effectively limits attack surface across all dimensions.
