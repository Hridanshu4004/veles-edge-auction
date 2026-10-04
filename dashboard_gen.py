import json
import glob
import os

results_dir = "/home/hridanshu/veles-edge-auction/experiments/results"
html_out = "/home/hridanshu/veles-edge-auction/dashboard.html"

def generate_dashboard():
    html = """<!DOCTYPE html>
<html>
<head>
    <title>EdgeTruth Live Dashboard (50-Seed Ablation)</title>
    <style>
        body { font-family: -apple-system, system-ui, sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; }
        .card { background: #1e293b; padding: 1.5rem; border-radius: 8px; margin-bottom: 2rem; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
        h1, h2 { color: #38bdf8; }
        table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
        th, td { text-align: left; padding: 0.75rem; border-bottom: 1px solid #334155; }
        th { color: #94a3b8; font-weight: 500; }
        .success { color: #4ade80; }
        .warning { color: #facc15; }
        .danger { color: #f87171; }
        .neutral { color: #94a3b8; }
    </style>
</head>
<body>
    <h1>EdgeTruth Live Dashboard (50-Seed Ablation)</h1>
    <p>Empirical execution results across 50 independent seeds measuring Empirical Misreporting Gain.</p>
"""

    for f in glob.glob(f"{results_dir}/*.json"):
        scenario_name = os.path.basename(f).replace('results_', '').replace('.json', '').upper()
        with open(f, 'r') as file:
            data = json.load(file)
            
        html += f"""
    <div class="card">
        <h2>Scenario: {scenario_name}</h2>
        <table>
            <tr>
                <th>Mechanism</th>
                <th>Task Success (Mean ±95% CI)</th>
                <th>SLA Misses</th>
                <th>Social Welfare</th>
                <th>Misreporting Gain</th>
            </tr>
"""
        for mech, res in data.items():
            succ = res.get("successful_tasks_mean", 0)
            succ_ci = res.get("successful_tasks_ci95", 0)
            alloc = res.get("allocated_tasks_mean", 0)
            sla = res.get("sla_violations_mean", 0)
            welfare = res.get("social_welfare_mean", 0.0)
            
            att_prof = res.get("attacker_profit_mean", 0.0)
            hon_prof = res.get("honest_profit_mean", 0.0)
            num_att = res.get("num_attackers_mean", 1)
            num_hon = res.get("num_honest_mean", 1)
            
            gain = (att_prof / max(1, num_att)) - (hon_prof / max(1, num_hon)) if num_att > 0 and num_hon > 0 else 0.0
            
            html += f"""
            <tr>
                <td><strong>{mech.upper()}</strong></td>
                <td><span class="{'success' if alloc > 0 and succ/alloc > 0.9 else 'warning'}">{succ:.1f} ±{succ_ci:.1f} / {alloc:.1f}</span></td>
                <td><span class="{'danger' if sla > 70 else 'success'}">{sla:.1f}</span></td>
                <td><span class="{'success' if welfare > 200000 else 'neutral'}">${welfare:,.0f}</span></td>
                <td><span class="{'danger' if gain > 0 else 'success'}">${gain:,.0f}</span></td>
            </tr>
"""
        html += """
        </table>
    </div>
"""
    
    html += """
</body>
</html>
"""
    with open(html_out, "w") as f:
        f.write(html)
    print(f"Generated dashboard at {html_out}")

if __name__ == "__main__":
    generate_dashboard()
