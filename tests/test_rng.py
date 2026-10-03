import pytest
import numpy as np
import random
from common.rng import set_seed

def test_seeded_rng():
    set_seed(42)
    val1 = random.randint(1, 100)
    arr1 = np.random.rand(3)
    
    set_seed(42)
    val2 = random.randint(1, 100)
    arr2 = np.random.rand(3)
    
    assert val1 == val2
    assert np.array_equal(arr1, arr2)
