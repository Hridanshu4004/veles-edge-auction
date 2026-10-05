import os

import yaml

out_dir = '/home/hridanshu/veles-edge-auction/scenarios'
os.makedirs(out_dir, exist_ok=True)

scenarios = [
    {
        'file': 'bursty_flood.yaml',
        'content': {
            'name': 'Bursty Flood',
            'description': 'Simulates an enormous spike in Azure function invocations based on the busiest real window.',
            'provenance': {
                'arrival_rate': 'REAL-PROXY (Azure 2019 busiest window)',
                'durations': 'DERIVED (Interpolated from percentiles)',
                'latency': 'DERIVED (Geographic distance + WS-DREAM variance)',
                'churn': 'SYNTHETIC'
            },
            'seed': 42,
            'parameters': {'arrival_multiplier': 5.0, 'node_capacity_multiplier': 1.0, 'latency_multiplier': 1.0, 'churn_rate': 0.01}
        }
    },
    {
        'file': 'high_latency_variance.yaml',
        'content': {
            'name': 'High Latency Variance',
            'description': 'Simulates high network latency variance.',
            'provenance': {
                'arrival_rate': 'REAL-PROXY',
                'durations': 'DERIVED',
                'latency': 'SYNTHETIC (3x multiplier)',
                'churn': 'SYNTHETIC'
            },
            'seed': 123,
            'parameters': {'arrival_multiplier': 1.0, 'node_capacity_multiplier': 1.0, 'latency_multiplier': 3.0, 'latency_variance': 2.0, 'churn_rate': 0.05}
        }
    },
    {
        'file': 'high_churn.yaml',
        'content': {
            'name': 'High Churn',
            'description': 'Simulates high edge node churn.',
            'provenance': {
                'arrival_rate': 'REAL-PROXY',
                'durations': 'DERIVED',
                'latency': 'DERIVED',
                'churn': 'SYNTHETIC (0.50 rate)'
            },
            'seed': 999,
            'parameters': {'arrival_multiplier': 1.0, 'node_capacity_multiplier': 1.0, 'latency_multiplier': 1.0, 'churn_rate': 0.50}
        }
    }
]

for s in scenarios:
    with open(os.path.join(out_dir, s['file']), 'w') as f:
        # Add comment blocks for provenance manually
        f.write("# PROVENANCE:\n")
        f.writelines(f"#   {k}: {v}\n" for k, v in s['content']['provenance'].items())
        f.write(f"# SEED: {s['content']['seed']}\n\n")
        yaml.dump({'name': s['content']['name'], 'description': s['content']['description'], 'parameters': s['content']['parameters']}, f, sort_keys=False)
