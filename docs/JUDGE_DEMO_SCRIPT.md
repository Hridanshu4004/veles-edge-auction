# Judge Demo Script

**Target Time:** 2.5 - 3 minutes

---

**(00:00 - 00:20) Problem**
"Welcome. In decentralized edge computing, nodes constantly compete for tasks. The naive approach is to allocate tasks to the node that bids the lowest price. But cheapest does not mean cheapest in expectation. If a cheap node is unreliable, the task fails, SLAs are breached, and the buyer suffers a massive hidden economic loss. The core problem is: you cannot blindly trust a node's self-reported reliability."

**(00:20 - 00:50) EdgeTruth Concept**
"To solve this, we built EdgeTruth. EdgeTruth entirely discards self-reported promises. Instead, it observes execution outcomes to build an empirical, Bayesian estimate of a node's true reliability. It then evaluates bids not just on price, but on the expected economic risk of failure."

**(00:50 - 01:20) Algorithm/Equation**
"The mechanism uses a simple, dimensionally consistent equation. For a task with value V, and a node bidding price P with an observed success rate of p, EdgeTruth scores the node as: p times the surplus (V minus P), minus the expected penalty of failure. This naturally scales: a high-value task heavily penalizes risk, justifying a higher payment for a reliable node. Furthermore, allocation takes O(N) time, making it highly scalable."

**(01:20 - 01:50) Live Execution/Demo**
*(Presenter runs `make demo` in the terminal)*
"Let's run the simulation. The system is generating a stream of real-world tasks based on the Azure 2019 dataset. EdgeTruth processes the bids, updates reliability posteriors, and generates our final dashboard."
*(Presenter opens dashboard.html)*

**(01:50 - 02:20) Adversarial Example**
"Notice how the mechanism defends against attacks. If an attacker uses a 'Win-Then-Drop' Sybil strategy—bidding cheaply to win tasks but dropping them to save compute costs—our contingent payment rule pays them exactly zero. Simultaneously, their observed reliability drops, mathematically preventing them from winning future high-value tasks. Their gain is strictly bounded to zero or less."

**(02:20 - 02:45) Evaluation**
"As you can see on the dashboard, this risk-aware routing makes a massive difference. Compared to a baseline greedy allocator, EdgeTruth dramatically increases SLA fulfillment. In our 30-seed validation, EdgeTruth successfully achieves approximately 85% of the absolute maximum welfare that a theoretical, omniscient oracle could achieve."

**(02:45 - 03:00) Limitations + Closing**
"We acknowledge limitations: fresh identities receive optimistic initialization, and highly reliable nodes can leverage their reputation to inflate prices. However, it empirically resists the multidimensional and collusion exploits that break VCG. EdgeTruth does not ask whether a node promises reliability. It asks whether the node has earned the right to be trusted. Thank you."
