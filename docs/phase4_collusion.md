# Phase 4 & 11: Stronger Collusion Analysis

We expanded the collusion analysis to test rings of $N \in \{2, 3, 5\}$ nodes under coordinated attack strategies. 

### Strategies Evaluated
1. **High_Low_Pricing:** One ring member bids 0.5x to capture the task, others bid 10x to push up VCG prices (or avoid winning).
2. **Winner_Manipulation:** One node claims 1.0 reliability and 0.1x price to guarantee a win, but intentionally drops the task (Win-Then-Drop). Others bid normally. The ring aims to knock out honest competitors while saving execution costs.
3. **Coordinated_Reliability:** All members in the ring falsely claim 1.0 reliability to maximize arbitrary reliability bonuses or manipulate thresholds.

### Results Highlights

**1. High_Low_Pricing Strategy:**
- Under a first-price-like allocation (which most of the variants essentially use), lowering the bid price directly hurts the winner's utility. 
- Most mechanisms yielded strictly negative gains ($-20$ to $-45$) for the ring.
- `trust_ranked_vcg` shows massive instability (gain of $+33.5 \pm 171.7$ at $N=2$), showing structural weakness to VCG manipulation in edge conditions.

**2. Winner_Manipulation Strategy:**
- `greedy` is maximally exploited (gain of $+115.1$) because it does not have a native penalty for dropped tasks, allowing the ring to steal task allocations and get paid without incurring execution costs.
- `capped` ($+100.5$) and `proper_scoring` ($+77.1$) are also highly vulnerable.
- `trust_ranked_vcg` destroys the attacker ($-10409.8$) via unbounded slashing.
- `contingent`, `audits` (default $F=50$), and `observed_rel_contingent` successfully bound the collusion gain to $\le 0$. 

**3. Coordinated_Reliability Strategy:**
- The `proper_scoring` mechanism sees massive positive collusion gains ($+98.4$ for 2 nodes, scaling up to $+144.8$ for 5 nodes). The rigid algebraic bonus can be actively farmed by the ring if they all collectively claim 1.0 reliability and don't care about the drop penalty on the margin.
- `contingent`, `capped`, and `audits` also see moderate positive gains ($+11$ to $+43$).
- **`observed_rel_contingent` completely nullifies this attack (Gain = 0.0)** because the mechanism structurally ignores self-reported reliability claims, making any coordination on the $q_i$ dimension useless.

### Conclusion on Collusion Resistance
The analysis reveals structural weaknesses in `proper_scoring`, `capped`, and `greedy` when facing multi-node coordinated attacks. **No mechanism is universally collusion-proof**, but `observed_rel_contingent` successfully neutralizes reliability coordination and bounds the Winner_Manipulation exploit to zero gain across all tested ring sizes.
