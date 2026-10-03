# Phase 0: Deconstruct

### FACTS
- **Challenge:** Veles Hack 2026, Challenge 4 (Smart Edge Resource Auctions).
- **Core themes:** Cloud-native device registration, dynamic node discovery, game-theory-inspired auctions, decentralized allocation, autonomous smart Edge agents.
- **Constraints:** Python, Docker, REST APIs, JSON. Deterministic/replayable (seeded RNG). Must run on one laptop via `docker compose up`. No blockchain. No LLM unless it provably improves the mechanism.

### ASSUMPTIONS
- **Role Mixing:** Nodes can act as both consumers (buyers) and providers (sellers) of resources dynamically. *(THIS IS AN ASSUMPTION)*
- **Network Topology:** The Edge environment implies varying latencies and partial network graphs, not a fully connected zero-latency LAN. *(THIS IS AN ASSUMPTION)*
- **Task Granularity:** Resources are leased for discrete time windows (epochs) or specific task completions, rather than indefinite periods. *(THIS IS AN ASSUMPTION)*
- **Adversarial Presence:** Some nodes will act maliciously or selfishly (e.g., lying about capacity, dropping tasks). *(THIS IS AN ASSUMPTION)*

### DESIGN DECISIONS
- **The Actual Underlying Technical Problem:**
  Efficiently clearing a multi-sided, spatially distributed market for heterogeneous computational resources where participants have asymmetric information, incentive to lie, and unreliable physical infrastructure.
- **Dynamic Registration Practically Means:**
  - *Identity:* Cryptographic or UUID-based unique handles.
  - *Capability Advertisement:* Initial declaration of (falsifiable) resource vectors (CPU, RAM, bandwidth).
  - *Liveness & Heartbeats:* Periodic TTL-based pings to prove availability and measure latency.
  - *Deregistration/Re-registration:* Graceful exit vs. crash failure; state recovery and penalization upon reconnection.
- **Resource Allocation Means:**
  Matching a set of tasks (demand) to a set of nodes (supply) such that constraints (latency, hardware) are met and some global objective (e.g., social welfare, utilization) is maximized, while respecting individual node rationality.
- **Realistically Auctionable Resources:**
  CPU cycles, memory allocation, network bandwidth, latency budgets, energy/battery drain, storage space, accelerator (GPU/TPU) time, and specific time slots/reservations.
- **Buyers vs. Sellers vs. Auctioneer:**
  - *Buyers:* Edge devices needing computation offload (e.g., IoT sensors).
  - *Sellers:* Edge gateways or idle devices offering computation.
  - *Auctioneer:* Could be centralized (a dedicated tracker), distributed (elected leaders), or fully decentralized (gossip-based clearing). Roles are fluid; a seller today is a buyer tomorrow.
- **Knowledge Asymmetry (Public vs. Private):**
  - *Public:* Auction rules, clearing prices, node network location, SLA/reputation history.
  - *Private:* True resource capacity, true operational cost (energy/computation), true valuation of a task, immediate local load.
- **Why Game Theory is Needed:**
  Because nodes are rational and self-interested. Without incentive compatibility, nodes will bid untruthfully (e.g., overstate capacity to win bids, then fail; or understate costs to dump prices). The mechanism must align private incentives with global efficiency.
- **Why Decentralized Scheduling is Hard:**
  - *Partial Information:* No single node sees the whole state of the network.
  - *Latency & Races:* State changes before bids clear.
  - *Failures:* Nodes crash mid-auction or mid-task.
  - *Strategic Behavior:* Nodes exploit temporal or spatial monopolies (e.g., "I'm the only node in this subnet").
- **Naive vs. Advanced Implementation:**
  - *Naive:* Centralized registry, nodes submit static CPU counts, first-price auction, highest bidder gets the task, no verification.
  - *Advanced:* Decentralized registry, multi-dimensional combinatorial bidding, truth-telling mechanisms (VCG variants, scoring rules, or reputation collateral), SLA verification, and dynamic repricing based on network uncertainty.
- **What Judges Find Impressive:**
  Mathematical rigor translated into working code. A system that explicitly anticipates and survives adversarial behavior. Reproducible metrics (graphs/tables) showing *why* the mechanism works (e.g., proving incentive-compatibility regret is near zero).
- **What Most Teams Will Ignore:**
  The fact that self-reported metrics are lies. They will build dashboards instead of defenses against Sybil attacks, shill bidding, and resource spoofing.

### HYPOTHESES
- **The Deepest Opportunity:**
  Treating *trust and reliability* as first-class, quantifiable resources. The winning mechanism will not just auction "CPU"; it will auction "CPU with a 99% probability of completion." By pricing uncertainty and penalizing lies (via reputation slashing, SLA bonds, or probabilistic audits), we create an environment where truth-telling is a dominant strategy, completely destroying the naive solutions of other teams in adversarial benchmarks.

### EVALUATION OF CHALLENGE 4
- **Technical Depth:** *High.* Mechanism design combined with distributed systems presents complex challenges.
- **Difficulty:** *High.* Bridging theoretical game theory with asynchronous asynchronous REST/Docker code requires careful handling of race conditions.
- **Implementation Complexity:** *Medium-High.* We must abstract the network layer cleanly and focus heavily on the mechanism, avoiding the complexity of building a full consensus protocol.
- **Differentiation Potential:** *Significant.* We hypothesize that many teams may focus on standard CRUD application patterns rather than complex mechanism design.
- **Demo Potential:** *High.* Visualizing a node being penalized and the system self-healing could be compelling.
- **Research Novelty:** *High.* Applying rigorous mechanism design to volatile, trustless Edge environments is an active research area.
- **Judge Appeal:** *Strong.* Judges generally appreciate mathematically sound, resilient systems that explicitly state and prove their assumptions.
- **Resource Availability:** *Good.* Python libraries (SciPy, NumPy) and Docker facilitate simulation.
- **Likelihood Others Stay Basic:** *High.* The phrase "Smart Edge" may lead teams to build IoT dashboards instead of auction algorithms. *(THIS IS AN ASSUMPTION)*
- **Our Strategy for Success:** *Uncertain but promising.* We will aim to build an Adversary Arena to demonstrate our mechanism's resilience compared to naive solutions.

### QUESTIONS FOR THE ORGANIZERS
1. Is there a provided simulation environment or workload generator, or are we expected to build our own task arrival models?
2. Are there strict constraints on the network topology we must simulate (e.g., star vs. mesh), or can we define our own latency/partition models?
3. In the context of the hackathon, is the "auctioneer" allowed to be a logically centralized (but Dockerized) service, or is fully leaderless decentralized clearing a hard requirement?
4. Are nodes allowed to have persistent storage (e.g., to maintain reputation scores across restarts)?
5. Will the judges evaluate the system primarily on theoretical soundness, throughput/latency metrics, or resilience to adversarial behavior?
