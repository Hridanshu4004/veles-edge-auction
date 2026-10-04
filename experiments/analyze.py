import json
import glob
import os

results_dir = "/home/hridanshu/veles-edge-auction/experiments/results"
if not os.path.exists(results_dir):
    results_dir = "C:/Users/hrida/.gemini/antigravity-ide/scratch/veles-hack-2026/results"

print("=== 50-SEED ABLATION RESULTS (Mean ± 95% CI) ===")
for f in glob.glob(f"{results_dir}/*.json"):
    data = json.load(open(f))
    print(f"\n--- {os.path.basename(f)} ---")
    for mech, res in data.items():
        succ = res.get("successful_tasks_mean", 0)
        succ_ci = res.get("successful_tasks_ci95", 0)
        sla = res.get("sla_violations_mean", 0)
        sla_ci = res.get("sla_violations_ci95", 0)
        welfare = res.get("social_welfare_mean", 0.0)
        
        att_prof = res.get("attacker_profit_mean", 0.0)
        hon_prof = res.get("honest_profit_mean", 0.0)
        num_att = res.get("num_attackers_mean", 1)
        num_hon = res.get("num_honest_mean", 1)
        
        if num_att > 0 and num_hon > 0:
            misreporting_gain = (att_prof / num_att) - (hon_prof / num_hon)
        else:
            misreporting_gain = 0.0
            
        print(f"{mech:23s} | Success: {succ:5.1f} ±{succ_ci:4.1f} | SLA Miss: {sla:4.1f} ±{sla_ci:4.1f} | Welfare: ${welfare:8.0f} | Misreporting Gain: ${misreporting_gain:7.0f}")
