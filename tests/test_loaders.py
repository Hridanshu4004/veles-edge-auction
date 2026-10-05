import json
import os

import pytest

from common.loaders import Azure2019Loader


def test_seed_determinism():
    loader1 = Azure2019Loader('/home/hridanshu/veles-edge-auction/data/raw/azure/2019', seed=123)
    data1 = loader1.load_and_split(num_funcs=5, allow_test=False)
    
    loader2 = Azure2019Loader('/home/hridanshu/veles-edge-auction/data/raw/azure/2019', seed=123)
    data2 = loader2.load_and_split(num_funcs=5, allow_test=False)
    
    # Check if the generated arrivals are identical
    tasks1 = data1['DEV']['tasks']
    tasks2 = data2['DEV']['tasks']
    assert len(tasks1) == len(tasks2)
    assert (tasks1['arrival_time'] == tasks2['arrival_time']).all()

def test_split_enforcement():
    loader = Azure2019Loader('/home/hridanshu/veles-edge-auction/data/raw/azure/2019')
    data_no_test = loader.load_and_split(num_funcs=5, allow_test=False)
    assert 'TEST' not in data_no_test
    
    data_with_test = loader.load_and_split(num_funcs=5, allow_test=True)
    assert 'TEST' in data_with_test

def test_loud_failure_on_missing_files():
    loader = Azure2019Loader('/home/hridanshu/veles-edge-auction/data/raw/fake_dir')
    with pytest.raises(FileNotFoundError):
        loader.load_and_split(num_funcs=5)

def test_test_split_logging(tmp_path):
    log_path = str(tmp_path / "access_log.jsonl")
    os.environ['ACCESS_LOG_PATH'] = log_path
    
    if os.path.exists(log_path):
        os.remove(log_path)
    loader = Azure2019Loader('/home/hridanshu/veles-edge-auction/data/raw/azure/2019')
    loader.load_and_split(num_funcs=5, allow_test=True)
    assert os.path.exists(log_path)
    with open(log_path, 'r') as f:
        log_lines = f.readlines()
    assert len(log_lines) >= 2
    log_entry = json.loads(log_lines[-1])
    assert log_entry['split'] == 'TEST'
