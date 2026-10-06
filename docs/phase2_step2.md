# Phase 2: Security & Edge Conditions
## Step 2: Incentive-Compatibility (Regret) Experiment Results

### Overview
This document summarizes the strengthened regret measurement for incentive-compatibility on the DEV split, using 30 seeds and 30 nodes per seed (totaling 900 node-samples per mechanism). 

**Provenance:** 
Regret experiment uses Azure2019Loader for task arrivals (DEV split). Synthetic generation is used ONLY for node attributes (costs, reliability, capacity) and ground-truth success outcomes. WS-DREAM dataset is NOT used in this experiment.

### Normalization
**Formula:** `Norm J-Reg = joint_regret / median_positive_truthful_pay`
Since un-normalized regret metrics are in units of abstract task value/currency, computing a fraction over the truthful payment scale standardizes them. We use the median of strictly positive truthful payments (Median Pay = 243.79) to avoid division by near-zero.
*Sample Denominator Rows:*
Node node-014 (Mech: greedy): Raw Regret = 1.44, Truthful Pay = 0.00, Norm Regret = 0.0059
Node node-018 (Mech: greedy): Raw Regret = 25.26, Truthful Pay = 0.00, Norm Regret = 0.1036
Node node-019 (Mech: greedy): Raw Regret = 5.85, Truthful Pay = 0.00, Norm Regret = 0.0240
Node node-004 (Mech: trust_vcg): Raw Regret = 138.31, Truthful Pay = 367.42, Norm Regret = 0.5673
Node node-006 (Mech: trust_vcg): Raw Regret = 391.15, Truthful Pay = 0.00, Norm Regret = 1.6044

### Results Table (with 95% Bootstrap CIs over seeds)
Why are Welfare and SLA metrics identical across `trust_vcg`, `contingent`, `capped`, `proper_scoring`, and `audits`?
Because all these mechanisms use the exact same allocation rule (greedy ranking by expected trust score / VCG value). They differ ONLY in how payments and slashings are computed after the fact. The allocation sequence is identical, and thus the welfare and SLA success metrics, which depend solely on allocation and ground truth, are exactly the same under truthful bidding.

| Mechanism       | Unnorm Reg      | Norm J-Reg      | IR Viol%   | Pos-IR Reg      | Part. Loss      | Welfare         | Buyer Pay       | SLA%       | WTD Gain        | Sybil Gn        | Coll Gn        |
|-----------------|-----------------|-----------------|------------|-----------------|-----------------|-----------------|-----------------|------------|-----------------|-----------------|----------------|
| greedy          |   1.4±0.4       |  0.01±0.00      |  0.0%±0.0  |   1.4±0.4       |  0.00±0.00      |  7887±542       |   244±32        | 89.3%±3.2  |  -11.8±3.0      | -0.15±0.34      | -5.43±2.97     |
| trust_vcg       |  99.4±16.8      |  0.41±0.07      |  2.1%±0.8  |  87.4±16.1      | 11.56±6.44      |  8523±243       |   560±289       | 93.5%±2.5  | -2894.8±329.7   | -1.08±2.28      | 23.73±58.80    |
| contingent      |  21.5±4.9       |  0.09±0.02      |  0.3%±0.4  |  21.4±4.9       |  0.01±0.01      |  8523±243       |   324±47        | 93.5%±2.5  | -157.1±28.9     | -0.84±0.18      | -6.69±3.54     |
| capped          |  28.0±6.2       |  0.11±0.03      |  0.0%±0.0  |  28.0±6.2       |  0.00±0.00      |  8523±243       |   336±47        | 93.5%±2.5  |  -42.2±7.5      | -0.80±0.19      | -7.00±3.51     |
| proper_scoring  | 163.8±22.3      |  0.67±0.09      |  0.0%±0.0  | 163.8±22.3      |  0.00±0.00      |  8523±243       |  1211±56        | 93.5%±2.5  | -175.4±24.2     |  2.89±1.64      |  6.56±59.52    |
| audits          | 144.7±20.2      |  0.59±0.08      |  0.4%±0.5  | 144.1±20.2      |  0.34±0.40      |  8523±243       |  1093±112       | 93.5%±2.5  | -600.9±101.0    |  3.36±1.86      |  9.84±59.38    |

### Honest Node IR Violation in Trust-VCG
Sample of honest node with negative utility under `trust_vcg`:
Node node-026: Total Pay: -95.71, Slashed Amount: 500.00, Brier Penalty: 256.59, Total Cost: 35.00, Net Util: -130.71
The claim holds true: `trust_vcg` physically slashes funds from honest edge nodes that inherently crash occasionally (since they have a native reliability < 100%). This violates IR for perfectly honest nodes.

### Audits & Scoring Rule Parameter Sweep
Scoring Scale: Payment = price + (Claim_rel * p * F) [on success] - F [on audited failure]
| p   | F    | Regret     | Sybil Gn   | Coll Gn    | Buyer Pay |
|-----|------|------------|------------|------------|-----------|
| 0.1 | 10.0 |      20.54 |      -0.94 |      -4.25 |    305.74 |
| 0.1 | 50.0 |      19.61 |      -1.16 |      -4.26 |    310.69 |
| 0.2 | 50.0 |      20.87 |      -1.04 |      -5.04 |    333.93 |
| 0.5 | 50.0 |      36.80 |      -0.49 |      -8.37 |    473.62 |
| 0.5 | 100.0|      69.20 |      -0.10 |     -12.50 |    642.73 |

Conclusion: At settings where p*F is large enough (e.g. p=0.5, F=100), Sybil and Collusion gains become negative, but the Buyer Payment scales up proportionally since the mechanism pays out expected rebates.
