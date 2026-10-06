# Phase 3 & 10: Stronger Sybil Attack Analysis

We expanded the Sybil attack vector to test combinations of $N \in \{1, 2, 5, 10\}$ Sybils across three different strategies:
1. **Discount:** Clones bid at a 10% discount on price, truthful otherwise.
2. **WTD (Win-Then-Drop):** Clones bid at a 10% discount, claim 1.0 reliability, but always drop the task (saving execution costs).
3. **Collusion_Threshold:** The original node bids very high (10x), clones bid very low (0.5x) and claim 1.0 reliability.

### Results Highlights

**1. Discount Strategy:**
Sybil identities providing straightforward discounts do not yield a positive gain in almost any mechanism because they merely cannibalize the original node's allocations and force the attacker to execute tasks for less money. `trust_ranked_vcg` shows a slight positive gain (3.9) purely due to edge cases in VCG pricing thresholds, but it does not scale with $N$.

**2. Win-Then-Drop (WTD) Strategy:**
- `trust_ranked_vcg` destroys the attacker (-1261.4) via severe slashing.
- `contingent` and `observed_rel_contingent` yield negative gains (-0.5 to -4.0) because dropped tasks pay nothing and hurt future allocations.
- However, `capped`, `proper_scoring`, and `audits` (with default $p=0.1, F=50$) are **highly vulnerable** to WTD Sybils, yielding positive gains between +32.0 and +48.7. The clones successfully grab allocation share (8.6%) and drop tasks, stealing surplus while avoiding execution costs. The gain does not scale heavily beyond $N=1$ because a single highly attractive Sybil is already enough to capture the available tasks the attacker targets.

**3. Collusion_Threshold Strategy:**
Most mechanisms handle this well with negative gains. `proper_scoring` is the only mechanism vulnerable to this threshold manipulation (gain of +33.3), likely because the proper scoring rule's rigid bonus offsets the lowered price in a way that creates a localized exploit for the attacker.

### Conclusion on Sybil Resistance
We **DO NOT** claim universal Sybil-proofness. The `proper_scoring`, `capped`, and default `audits` mechanisms exhibit strict vulnerabilities to Sybils that employ Win-Then-Drop strategies. Only `contingent` (and Bayesian `observed_rel_contingent`) successfully mathematically bound the Sybil WTD gain to $\le 0$.
