# Judge Demo Script

**Target Time:** 3 minutes maximum.

---

**0:00–0:20 — PROBLEM**
"Edge computing has a simple problem: a node can claim that it is cheap and reliable, but a scheduler has to make decisions before it knows whether that promise is true. If we just pick the cheapest node, and that node fails, we incur retries, SLA breaches, and massive hidden economic losses. Cheapest does not mean cheapest in expectation."

**0:20–0:45 — EDGE TRUTH**
"EdgeTruth treats execution history as evidence. It ignores what a node claims and tracks what a node actually does. When a node bids, we calculate an estimated reliability from its past successes. We allocate based on that risk, the node executes, and we update its reliability posterior for the future. A node can lie once. It cannot easily lie forever."

**0:45–1:15 — MATHEMATICAL CORE**
"The core of EdgeTruth is this simple, O(N) allocation equation:
`Score_i = p_i(V - P_i) - (1 - p_i)(V/2)`
Here, `p_i` is the observed probability of successful execution, `V` is the task value, and `P_i` is the node's bid price. We weigh the expected surplus against the expected penalty of failure. All terms are in monetary units, perfectly aligning risk and reward."

**1:15–1:50 — LIVE DEMO**
*(Run `make demo` in terminal)*
"Let's run the system. We're generating tasks from Azure 2019 dataset traces. 
Here are the nodes and their bids. EdgeTruth calculates the risk-adjusted score for each, allocates the task, observes the execution outcome, and immediately updates the reliability evidence for the next round."

**1:50–2:15 — ADVERSARIAL BEHAVIOR**
"A malicious node can attempt to claim high reliability and win work, but when its actual execution fails—like in a Win-Then-Drop attack—the contingent payment prevents that failure from becoming a profitable extraction strategy. It gets paid zero, and its observed reliability plummets. We demonstrate resistance to the tested Win-Then-Drop Sybil attacks, but we do not claim universal Sybil-proofness. Fresh identities currently receive optimistic initialization."

**2:15–2:40 — RESULTS**
*(Open `dashboard.html`)*
"Looking at the generated results dashboard, EdgeTruth dramatically outperforms the Greedy allocator on SLA success by avoiding failure-prone nodes. Under the evaluated workload, EdgeTruth achieved approximately 85% of the welfare obtained by the evaluated omniscient oracle. We pay a higher upfront price to reliable nodes, but we save massive downstream failure penalties."

**2:40–3:00 — LIMITATIONS + CLOSE**
"We deliberately do not claim universal Sybil-proofness, collusion-proofness or truthful price bidding. We tested 2-, 3-, and 5-node collusion strategies and observed no positive gain in those tested scenarios, but highly reliable nodes can inflate their prices strategically. 
EdgeTruth does not ask whether a node promises reliability. It asks whether the node has earned the right to be trusted. Don't trust the node. Price the promise."
