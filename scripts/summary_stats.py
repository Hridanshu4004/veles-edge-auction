import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from common.loaders import Azure2019Loader, WSDreamLoader

def main():
    print("=== SUMMARY STATS ===")
    
    # Azure
    azure_loader = Azure2019Loader('/home/hridanshu/veles-edge-auction/data/raw/azure/2019')
    azure_data = azure_loader.load_and_split(num_funcs=50)
    
    print("\n--- AZURE 2019 ---")
    for split in ['DEV', 'TEST']:
        print(f"\n[{split}] Arrivals:")
        arr = azure_data[split]['arrivals']
        print(f"Columns: {list(arr.columns)}")
        print(f"Row count: {len(arr)}")
        print("Sample 5 rows:")
        print(arr.head(5).to_string())
        
        print(f"\n[{split}] Durations:")
        dur = azure_data[split]['durations']
        print(f"Columns: {list(dur.columns)}")
        print(f"Row count: {len(dur)}")
        print("Sample 5 rows:")
        print(dur.head(5).to_string())
        
        print(f"\n[{split}] Memory:")
        mem = azure_data[split]['memory']
        print(f"Columns: {list(mem.columns)}")
        print(f"Row count: {len(mem)}")
        print("Sample 5 rows:")
        print(mem.head(5).to_string())
        
        # Save samples
        out_dir = f'/home/hridanshu/veles-edge-auction/data/samples/azure/{split}'
        os.makedirs(out_dir, exist_ok=True)
        arr.head(20).to_csv(f'{out_dir}/arrivals_sample.csv', index=False)
        dur.head(20).to_csv(f'{out_dir}/durations_sample.csv', index=False)
        mem.head(20).to_csv(f'{out_dir}/memory_sample.csv', index=False)

    # WSDREAM
    wsdream_loader = WSDreamLoader('/home/hridanshu/veles-edge-auction/data/raw/wsdream')
    wsdream_data = wsdream_loader.load_and_split(n_nodes=100)
    
    print("\n--- WS-DREAM ---")
    for split in ['DEV', 'TEST']:
        print(f"\n[{split}] Pairs:")
        pairs = wsdream_data[split]
        print(f"Columns: {list(pairs.columns)}")
        print(f"Row count: {len(pairs)}")
        print("Sample 5 rows:")
        print(pairs.head(5).to_string())
        
        out_dir = f'/home/hridanshu/veles-edge-auction/data/samples/wsdream/{split}'
        os.makedirs(out_dir, exist_ok=True)
        pairs.head(20).to_csv(f'{out_dir}/pairs_sample.csv', index=False)

    users = wsdream_data['users']
    services = wsdream_data['services']
    print(f"\nUsers - Row count: {len(users)}, Columns: {list(users.columns)}")
    print(users.head(5).to_string())
    print(f"\nServices - Row count: {len(services)}, Columns: {list(services.columns)}")
    print(services.head(5).to_string())
    
    out_dir = '/home/hridanshu/veles-edge-auction/data/samples/wsdream'
    users.head(20).to_csv(f'{out_dir}/users_sample.csv', index=False)
    services.head(20).to_csv(f'{out_dir}/services_sample.csv', index=False)

if __name__ == '__main__':
    main()
