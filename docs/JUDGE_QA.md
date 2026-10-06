# Judge Q&A

**1. Why not simply choose the cheapest node?**
Because the cheapest node might be unreliable. A failure requires a retry, breaches SLAs, and causes severe economic loss to the buyer. Cheapest upfront does not mean cheapest in expectation.

**2. Why should a node report honestly?**
EdgeTruth ignores self-reported reliability entirely. Nodes are evaluated on empirical execution evidence. They report prices strategically, but reliability is judged by action.

**3. Is EdgeTruth incentive compatible?**
EdgeTruth incentivizes reliable execution through observed outcomes and contingent payment, but price bidding remains strategic.

**4. Is EdgeTruth Sybil-proof?**
We demonstrate resistance to the tested Win-Then-Drop Sybil attacks, but we do not claim universal Sybil-proofness. Fresh identities currently receive optimistic initialization.

**5. Is EdgeTruth collusion-proof?**
We tested 2-, 3-, and 5-node collusion strategies and observed no positive gain in those tested scenarios. We do not claim universal collusion-proofness.

**6. Why does contingent payment help?**
It prevents Win-Then-Drop attacks. If an attacker wins a task and drops it to save compute costs, they get paid zero. This bounds their malicious utility gain to zero or less.

**7. What happens when a new node joins?**
New identities currently receive optimistic initialization ($P_i = 1.0$). If they fail their first tasks, their Bayesian posterior drops rapidly, limiting their future allocations for high-value tasks.

**8. What prevents a node from lying about reliability?**
EdgeTruth completely ignores the node's self-reported reliability. It calculates reliability purely from observed empirical evidence (successful executions / total attempts).

**9. Why not use VCG?**
VCG in a multi-dimensional setting with failure risks is computationally expensive and vulnerable to extreme regret and Individual Rationality violations (honest nodes getting negative utility).

**10. Why not use blockchain?**
A blockchain is an infrastructure layer for immutable ledgers, not an allocation algorithm. EdgeTruth operates at the algorithmic/mechanism layer to decide *who* gets the task.

**11. Why not use an LLM?**
LLMs are for generative text and probabilistic reasoning on unstructured data, not for strict, mathematical mechanism design and economic allocation where predictable bounds and execution are required.

**12. What is novel about EdgeTruth?**
Our contribution is the mechanism/system design and its empirical evaluation under adversarial edge behavior. We combine observed execution evidence, reliability-aware economic allocation, contingent payment, and O(N) allocation into one cohesive defense.

**13. What is the computational complexity?**
The allocation step scans N bids once, giving O(N) complexity per task.

**14. What happens if a highly reliable node raises its price?**
Because EdgeTruth heavily penalizes risk, a highly reliable node can inflate its price and still win against a cheap, unreliable node. This is a known limitation where reliable nodes extract surplus.

**15. What is your biggest limitation?**
Fresh identities currently receive optimistic initialization, so complete Sybil-proofness is not claimed. Furthermore, highly reliable nodes can extract significant buyer surplus via price inflation.

**16. How was the system evaluated?**
We evaluated it using deterministic seeds, tasks derived from Azure 2019 traces, and adversarial baseline comparisons (Greedy allocator, VCG, Proper Scoring).

**17. How many seeds were tested?**
We tested across 30 random seeds to ensure empirical robustness.

**18. What does the ~85% welfare figure mean?**
Under the evaluated workload, EdgeTruth achieved approximately 85% of the welfare obtained by the evaluated omniscient oracle (an oracle that perfectly knows the hidden outcome of every stochastic execution in advance).

**19. How do you prevent ground-truth leakage?**
The EdgeTruth allocation function strictly receives only the node bids and the system's empirical observations (`observed_successes`, `observed_attempts`). It never accesses the true underlying failure probabilities used to simulate the environment.

**20. What happens after a node fails?**
It receives $0 payment, its observed success rate drops, its future EdgeTruth score is severely penalized for high-value tasks, and the system immediately attempts to retry the task on a fallback node.
