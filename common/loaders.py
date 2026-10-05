import os

import numpy as np
import pandas as pd


class Azure2019Loader:
    def __init__(self, data_dir: str, seed: int = 42):
        self.data_dir = data_dir
        self.rng = np.random.default_rng(seed)
        
    def load_and_split(self, day: str = 'd01', num_funcs: int = 100, test_ratio: float = 0.2, allow_test: bool = False):
        print(f"Loading Azure 2019 dataset from {self.data_dir} for day {day}...")
        invocations_path = os.path.join(self.data_dir, f'invocations_per_function_md.anon.{day}.csv')
        durations_path = os.path.join(self.data_dir, f'function_durations_percentiles.anon.{day}.csv')
        memory_path = os.path.join(self.data_dir, f'app_memory_percentiles.anon.{day}.csv')
        
        print("Reading CSVs...")
        df_inv = pd.read_csv(invocations_path)
        df_dur = pd.read_csv(durations_path)
        df_mem = pd.read_csv(memory_path)
        
        valid_funcs = set(df_inv['HashFunction']).intersection(set(df_dur['HashFunction']))
        df_inv = df_inv[df_inv['HashFunction'].isin(valid_funcs)]
        
        valid_apps = set(df_inv['HashApp']).intersection(set(df_mem['HashApp']))
        df_inv = df_inv[df_inv['HashApp'].isin(valid_apps)]
        
        sampled_funcs = self.rng.choice(df_inv['HashFunction'].unique(), size=min(num_funcs, len(df_inv['HashFunction'].unique())), replace=False)
        df_inv = df_inv[df_inv['HashFunction'].isin(sampled_funcs)]
        
        n_test = int(len(sampled_funcs) * test_ratio)
        test_funcs = self.rng.choice(sampled_funcs, size=n_test, replace=False)
        dev_funcs = [f for f in sampled_funcs if f not in test_funcs]
        
        df_inv_dev = df_inv[df_inv['HashFunction'].isin(dev_funcs)]
        df_dur_dev = df_dur[df_dur['HashFunction'].isin(dev_funcs)]
        df_mem_dev = df_mem[df_mem['HashApp'].isin(df_inv_dev['HashApp'].unique())]
        
        print("Processing DEV tasks (interpolating durations and memory)...")
        dev_tasks = self._process_tasks(df_inv_dev, df_dur_dev, df_mem_dev)
        
        result = {'DEV': {'tasks': dev_tasks}}
        
        if allow_test:
            print("WARNING: TEST split access requested and enabled. Logging test split access.")
            df_inv_test = df_inv[df_inv['HashFunction'].isin(test_funcs)]
            df_dur_test = df_dur[df_dur['HashFunction'].isin(test_funcs)]
            df_mem_test = df_mem[df_mem['HashApp'].isin(df_inv_test['HashApp'].unique())]
            test_tasks = self._process_tasks(df_inv_test, df_dur_test, df_mem_test)
            result['TEST'] = {'tasks': test_tasks}
        else:
            print("ACCESS LOG: TEST split requested but blocked by allow_test=False. Returning DEV only.")
            
        return result

    def _process_tasks(self, df_inv: pd.DataFrame, df_dur: pd.DataFrame, df_mem: pd.DataFrame) -> pd.DataFrame:
        tasks_list = []
        minutes_cols = [str(i) for i in range(1, 1441)]
        
        dur_cols = ['percentile_Average_0', 'percentile_Average_1', 'percentile_Average_25', 'percentile_Average_50', 'percentile_Average_75', 'percentile_Average_99', 'percentile_Average_100']
        mem_cols = ['AverageAllocatedMb_pct1', 'AverageAllocatedMb_pct5', 'AverageAllocatedMb_pct25', 'AverageAllocatedMb_pct50', 'AverageAllocatedMb_pct75', 'AverageAllocatedMb_pct95', 'AverageAllocatedMb_pct99', 'AverageAllocatedMb_pct100']
        
        dur_map = df_dur.set_index('HashFunction')[dur_cols]
        mem_map = df_mem.set_index('HashApp')[mem_cols]
        
        for _, row in df_inv.iterrows():
            func_id = row['HashFunction']
            app_id = row['HashApp']
            
            if func_id not in dur_map.index or app_id not in mem_map.index:
                continue
                
            dur_pcts = dur_map.loc[func_id].values
            mem_pcts = mem_map.loc[app_id].values
            
            if len(dur_pcts.shape) > 1: dur_pcts = dur_pcts[0]
            if len(mem_pcts.shape) > 1: mem_pcts = mem_pcts[0]
            
            for minute_idx, minute_col in enumerate(minutes_cols):
                count = row.get(minute_col, 0)
                if pd.isna(count) or count == 0:
                    continue
                count = int(count)
                
                start_sec = minute_idx * 60
                end_sec = start_sec + 60
                timestamps = self.rng.uniform(start_sec, end_sec, size=count)
                
                # Interpolate duration
                p_dur = self.rng.uniform(0, 100, size=count)
                durations = np.interp(p_dur, [0, 1, 25, 50, 75, 99, 100], dur_pcts)
                
                # Interpolate memory
                p_mem = self.rng.uniform(1, 100, size=count)
                memories = np.interp(p_mem, [1, 5, 25, 50, 75, 95, 99, 100], mem_pcts)
                
                tasks_list.append(pd.DataFrame({
                    'HashFunction': [func_id] * count,
                    'HashApp': [app_id] * count,
                    'arrival_time': timestamps,
                    'duration_ms': durations,
                    'memory_mb': memories
                }))
                
        if not tasks_list:
            return pd.DataFrame(columns=['HashFunction', 'HashApp', 'arrival_time', 'duration_ms', 'memory_mb'])
        return pd.concat(tasks_list, ignore_index=True)

class WSDreamLoader:
    def __init__(self, data_dir: str, seed: int = 42):
        self.data_dir = data_dir
        self.rng = np.random.default_rng(seed)
        
    def load_and_split(self, n_nodes: int = 100, test_ratio: float = 0.2, allow_test: bool = False):
        print(f"Loading WS-DREAM dataset from {self.data_dir}...")
        rt_path = os.path.join(self.data_dir, 'dataset1', 'rtMatrix.txt')
        tp_path = os.path.join(self.data_dir, 'dataset1', 'tpMatrix.txt')
        userlist_path = os.path.join(self.data_dir, 'dataset1', 'userlist.txt')
        wslist_path = os.path.join(self.data_dir, 'dataset1', 'wslist.txt')
        
        rt_matrix = np.loadtxt(rt_path)
        tp_matrix = np.loadtxt(tp_path)
        
        num_users, num_services = rt_matrix.shape
        print(f"Matrix shape: {num_users} users, {num_services} services")
        
        users = pd.read_csv(userlist_path, sep='\t', skiprows=2, header=None, names=['UserID', 'IP', 'Country', 'IP_No', 'AS', 'Lat', 'Lon'], on_bad_lines='skip', encoding='latin1')
        services = pd.read_csv(wslist_path, sep='\t', skiprows=2, header=None, names=['ServiceID', 'WSDL', 'Provider', 'IP', 'Country', 'IP_No', 'AS', 'Lat', 'Lon'], on_bad_lines='skip', encoding='latin1')
        
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
        
        result = {
            'DEV': df_dev,
            'users': users.iloc[sampled_users],
            'services': services.iloc[sampled_services]
        }
        
        if allow_test:
            print("WARNING: TEST split access requested and enabled. Logging test split access.")
            df_test = df_pairs[df_pairs['user_idx'].isin(test_users)]
            result['TEST'] = df_test
        else:
            print("ACCESS LOG: TEST split requested but blocked by allow_test=False. Returning DEV only.")
            
        return result
