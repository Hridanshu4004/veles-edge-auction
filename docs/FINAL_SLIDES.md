# Final Presentation Slides

## SLIDE 1
**Title:** EdgeTruth: Don't trust the node. Price the promise.
**Points:**
- Decentralized task allocation
- Empirical reliability tracking
- Risk-adjusted pricing
**Visual:** The EdgeTruth logo or simple clean title slide.
**Presenter says:** "Welcome. Today we present EdgeTruth, a mechanism that stops asking nodes to promise reliability, and starts pricing what they actually deliver."

## SLIDE 2
**Title:** The Problem: Cheapest is not Cheapest in Expectation
**Points:**
- Nodes bid low prices but fail to execute
- Task failures cause SLA breaches
- Buyers suffer hidden economic losses
**Visual:** Diagram showing a cheap node failing vs a reliable node succeeding.
**Presenter says:** "If you blindly pick the cheapest node, and that node fails, you lose money on SLA penalties. Cheapest upfront does not mean cheapest in expectation."

## SLIDE 3
**Title:** The EdgeTruth Insight
**Points:**
- Discard self-reported reliability claims
- Use historical execution as Bayesian evidence
- Compute risk-adjusted utility before allocating
**Visual:** A node lying about its reliability, crossed out, pointing to a server tracking actual success rates.
**Presenter says:** "Our insight is simple: treat execution history as evidence. We estimate true reliability from actual outcomes, and adjust every bid by its mathematical risk of failure."

## SLIDE 4
**Title:** The Mechanism
**Points:**
- Score = $p_i(V - P_i) - (1 - p_i)(V/2)$
- Perfectly aligned in monetary units
- O(N) allocation per task
- Contingent payment (paid only on success)
**Visual:** The equation displayed cleanly and prominently.
**Presenter says:** "This is the core equation. We weigh the expected surplus of a successful task against the expected penalty of failure. It scales naturally, allocating high-value tasks only to highly reliable nodes, in strictly O(N) time."

## SLIDE 5
**Title:** Architecture & Live Demo
**Points:**
- Generator -> Auction -> Nodes -> Evidence Loop
- Simulating Azure 2019 workloads
**Visual:** The ASCII feedback loop Architecture Diagram. 
*(Switch to terminal for Live Demo)*
**Presenter says:** "Let's see it in action. EdgeTruth evaluates bids, selects nodes, observes outcomes, and updates reliability scores instantly in a feedback loop."

## SLIDE 6
**Title:** Evaluation & Adversarial Resistance
**Points:**
- Achieves ~85% of omniscient oracle welfare
- Empirically robust against tested 2, 3, 5-node collusion
- Contingent payments eliminate Win-Then-Drop utility
**Visual:** The dashboard results table comparing Greedy and EdgeTruth.
**Presenter says:** "EdgeTruth dramatically improves SLA fulfillment over greedy allocation, capturing ~85% of theoretical optimal welfare. Moreover, it prevents malicious Sybils from extracting profit through 'Win-Then-Drop' behavior."

## SLIDE 7
**Title:** Limitations & Conclusion
**Points:**
- Fresh identities use optimistic initialization
- Highly reliable nodes can extract surplus
- Don't trust the node. Price the promise.
**Visual:** Bullet points with the final tagline.
**Presenter says:** "We don't claim universal Sybil-proofness—fresh nodes get optimistic starts—and reliable nodes can inflate prices. But EdgeTruth doesn't ask if a node promises reliability; it asks if it has earned the right to be trusted. Don't trust the node. Price the promise."
