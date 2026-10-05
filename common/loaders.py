import os
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

class Azure2019Loader:
    def __init__(self, data_dir: str, seed: int = 42):
        self.data_dir = data_dir
        self.rng = np.random.default_rng(seed)
        
    def load_and_split(self, day: str = 'd01', num_funcs: int = 100, test_ratio: float = 0.2):
        print(f"Loading Azure 2019 dataset from {self.data_dir} for day {day}...")
        invocations_path = os.path.join(self.data_dir, f'invocations_per_function_md.anon.{day}.csv')
        durations_path = os.path.join(self.data_dir, f'function_durations_percentiles.anon.{day}.csv')
        memory_path = os.path.join(self.data_dir, f'app_memory_percentiles.anon.{day}.csv')
        
        # Load data
        print("Reading CSVs...")
        df_inv = pd.read_csv(invocations_path)
        df_dur = pd.read_csv(durations_path)
        df_mem = pd.read_csv(memory_path)
        
        print("Initial row counts:")
        print(f"  Invocations: {len(df_inv)}")
        print(f"  Durations: {len(df_dur)}")
        print(f"  Memory: {len(df_mem)}")
        
        # Sample functions to make processing tractable for demo
        valid_funcs = set(df_inv['HashFunction']).intersection(set(df_dur['HashFunction']))
        df_inv = df_inv[df_inv['HashFunction'].isin(valid_funcs)]
        
        valid_apps = set(df_inv['HashApp']).intersection(set(df_mem['HashApp']))
        df_inv = df_inv[df_inv['HashApp'].isin(valid_apps)]
        
        sampled_funcs = self.rng.choice(df_inv['HashFunction'].unique(), size=min(num_funcs, len(df_inv['HashFunction'].unique())), replace=False)
        df_inv = df_inv[df_inv['HashFunction'].isin(sampled_funcs)]
        
        # Split DEV vs TEST (80/20) based on HashFunction
        n_test = int(len(sampled_funcs) * test_ratio)
        test_funcs = self.rng.choice(sampled_funcs, size=n_test, replace=False)
        dev_funcs = [f for f in sampled_funcs if f not in test_funcs]
        
        df_inv_dev = df_inv[df_inv['HashFunction'].isin(dev_funcs)]
        df_inv_test = df_inv[df_inv['HashFunction'].isin(test_funcs)]
        
        # Process DEV arrivals
        print("Processing DEV arrivals (converting minute-buckets to random timestamps)...")
        dev_arrivals = self._process_arrivals(df_inv_dev)
        test_arrivals = self._process_arrivals(df_inv_test)
        
        df_dur_dev = df_dur[df_dur['HashFunction'].isin(dev_funcs)]
        df_dur_test = df_dur[df_dur['HashFunction'].isin(test_funcs)]
        
        dev_apps = df_inv_dev['HashApp'].unique()
        test_apps = df_inv_test['HashApp'].unique()
        df_mem_dev = df_mem[df_mem['HashApp'].isin(dev_apps)]
        df_mem_test = df_mem[df_mem['HashApp'].isin(test_apps)]
        
        return {
            'DEV': {'arrivals': dev_arrivals, 'durations': df_dur_dev, 'memory': df_mem_dev},
            'TEST': {'arrivals': test_arrivals, 'durations': df_dur_test, 'memory': df_mem_test}
        }

    def _process_arrivals(self, df_inv: pd.DataFrame) -> pd.DataFrame:
        arrivals_list = []
        minutes_cols = [str(i) for i in range(1, 1441)]
        for _, row in df_inv.iterrows():
            func_id = row['HashFunction']
            app_id = row['HashApp']
            for minute_idx, minute_col in enumerate(minutes_cols):
                count = row.get(minute_col, 0)
                if pd.isna(count) or count == 0:
                    continue
                count = int(count)
                start_sec = minute_idx * 60
                end_sec = start_sec + 60
                timestamps = self.rng.uniform(start_sec, end_sec, size=count)
                
                arrivals_list.append(pd.DataFrame({
                    'HashFunction': [func_id] * count,
                    'HashApp': [app_id] * count,
                    'arrival_time': timestamps
                }))
        if not arrivals_list:
            return pd.DataFrame(columns=['HashFunction', 'HashApp', 'arrival_time'])
        return pd.concat(arrivals_list, ignore_index=True)

class WSDreamLoader:
    def __init__(self, data_dir: str, seed: int = 42):
        self.data_dir = data_dir
        self.rng = np.random.default_rng(seed)
        
    def load_and_split(self, n_nodes: int = 100, test_ratio: float = 0.2):
        print(f"Loading WS-DREAM dataset from {self.data_dir}...")
        rt_path = os.path.join(self.data_dir, 'dataset1', 'rtMatrix.txt')
        tp_path = os.path.join(self.data_dir, 'dataset1', 'tpMatrix.txt')
        userlist_path = os.path.join(self.data_dir, 'dataset1', 'userlist.txt')
        wslist_path = os.path.join(self.data_dir, 'dataset1', 'wslist.txt')
        
        rt_matrix = np.loadtxt(rt_path)
        tp_matrix = np.loadtxt(tp_path)
        
        num_users, num_services = rt_matrix.shape
        print(f"Matrix shape: {num_users} users, {num_services} services")
        
        users = pd.read_csv(userlist_path, sep='\t', header=None, names=['UserID', 'IP', 'Country', 'Continent', 'AS', 'Lat', 'Lon', 'Region', 'City'], on_bad_lines='skip', encoding='latin1')
        services = pd.read_csv(wslist_path, sep='\t', header=None, names=['ServiceID', 'WSDL', 'Provider', 'IP', 'Country', 'Continent', 'AS', 'Lat', 'Lon', 'Region', 'City'], on_bad_lines='skip', encoding='latin1')
        
        sampled_users = self.rng.choice(num_users, size=min(n_nodes, num_users), replace=False)
        sampled_services = self.rng.choice(num_services, size=min(n_nodes, num_services), replace=False)
        
        records = []
        dropped_count = 0
        for u_idx in sampled_users:
            for s_idx in sampled_services:
                rt = rt_matrix[u_idx, s_idx]
                tp = tp_matrix[u_idx, s_idx]
                if rt == -1 or tp == -1:
                    dropped_count += 1
                    continue
                records.append({
                    'user_idx': u_idx,
                    'service_idx': s_idx,
                    'latency_rt': rt,
                    'throughput_tp': tp
                })
        
        df_pairs = pd.DataFrame(records)
        print(f"WS-DREAM dropped {dropped_count} invalid (-1) entries.")
        print(f"WS-DREAM retained {len(df_pairs)} valid pairs.")
        
        unique_users_retained = df_pairs['user_idx'].unique()
        n_test = int(len(unique_users_retained) * test_ratio)
        test_users = self.rng.choice(unique_users_retained, size=n_test, replace=False)
        dev_users = [u for u in unique_users_retained if u not in test_users]
        
        df_dev = df_pairs[df_pairs['user_idx'].isin(dev_users)]
        df_test = df_pairs[df_pairs['user_idx'].isin(test_users)]
        
        return {
            'DEV': df_dev,
            'TEST': df_test,
            'users': users.iloc[sampled_users],
            'services': services.iloc[sampled_services]
        }

if __name__ == '__main__':
    azure_loader = Azure2019Loader('/home/hridanshu/veles-edge-auction/data/raw/azure/2019')
    azure_data = azure_loader.load_and_split(num_funcs=10)
    print("\nAzure DEV arrivals preview:")
    print(azure_data['DEV']['arrivals'].head())
    print(f"Azure DEV arrivals count: {len(azure_data['DEV']['arrivals'])}")
    print("\nAzure DEV durations preview:")
    print(azure_data['DEV']['durations'].head())
    print("\nAzure DEV memory preview:")
    print(azure_data['DEV']['memory'].head())
    
    wsdream_loader = WSDreamLoader('/home/hridanshu/veles-edge-auction/data/raw/wsdream')
    wsdream_data = wsdream_loader.load_and_split(n_nodes=20)
    print("\nWS-DREAM DEV preview:")
    print(wsdream_data['DEV'].head())
    print(f"WS-DREAM DEV pairs count: {len(wsdream_data['DEV'])}")
